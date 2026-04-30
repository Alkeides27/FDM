# finanzas/views.py
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit

from .models import Pago, Mensualidad, PagoAuditLog, TOLERANCIA_COBERTURA_USD
from .forms import ReportarPagoForm, AprobarPagoForm, RechazarPagoForm
from .telegram_bot import notificar_representante, enviar_mensaje


def es_admin(u):
    return u.is_authenticated and (
        u.is_staff or u.groups.filter(name='Tesoreria').exists()
    )


# === Vistas del representante ===

@login_required
@ratelimit(key='user', rate='5/h', method='POST', block=True)
def reportar_pago(request):
    if not hasattr(request.user, 'representante') or request.user.representante is None:
        messages.error(request, 'Tu usuario no está asociado a un representante.')
        return redirect('/')

    rep = request.user.representante

    if request.method == 'POST':
        form = ReportarPagoForm(request.POST, request.FILES, representante=rep)
        if form.is_valid():
            with transaction.atomic():
                pago = form.save(commit=False)
                pago.representante = rep

                # Hash anti-duplicado
                sha = hashlib.sha256()
                for chunk in pago.comprobante.chunks():
                    sha.update(chunk)
                pago.comprobante.seek(0)
                comp_hash = sha.hexdigest()

                if Pago.objects.filter(comprobante_hash=comp_hash).exists():
                    messages.error(request, 'Este comprobante ya fue reportado anteriormente.')
                    return render(request, 'finanzas/reportar.html', {'form': form})

                pago.comprobante_hash = comp_hash

                # Construir concepto desde mensualidades seleccionadas
                mensualidades = form.cleaned_data.get('mensualidades')
                if mensualidades:
                    etiquetas = [f"{m.atleta.nombres} {m.etiqueta_periodo}" for m in mensualidades]
                    pago.concepto = " + ".join(etiquetas)[:200]
                else:
                    pago.concepto = "Pago sin mensualidad asociada"

                try:
                    pago.save()
                except IntegrityError:
                    messages.error(
                        request,
                        'Esta referencia bancaria ya está registrada en otro pago activo.'
                    )
                    return render(request, 'finanzas/reportar.html', {'form': form})

                # AuditLog: creación
                pago.registrar_audit(
                    accion='CREADO',
                    actor=request.user,
                    estado_nuevo='PENDIENTE',
                    detalles={
                        'monto_bs': str(pago.monto_bs),
                        'metodo': pago.metodo,
                        'mensualidades_ids': [m.id for m in mensualidades] if mensualidades else [],
                    }
                )

                # Vincular mensualidades (sin marcarlas pagadas hasta aprobación)
                if mensualidades:
                    for m in mensualidades:
                        m.pago = pago
                        m.save()

            messages.success(
                request,
                f'Pago #{pago.id} recibido. Te notificaremos al verificarlo.'
            )
            return redirect('finanzas:mis_pagos')
    else:
        form = ReportarPagoForm(representante=rep)

    # Tasa de hoy para mostrar referencia (no rompe si falla)
    from finanzas.services.tasa_bcv import obtener_tasa
    tasa_hoy = obtener_tasa()

    return render(request, 'finanzas/reportar.html', {
        'form': form,
        'tasa_hoy': tasa_hoy,
    })


@login_required
def mis_pagos(request):
    if not hasattr(request.user, 'representante') or request.user.representante is None:
        messages.error(request, 'Tu usuario no está asociado a un representante.')
        return redirect('/')

    rep = request.user.representante
    pagos = Pago.objects.filter(representante=rep)
    mensualidades_pendientes = Mensualidad.objects.filter(
        atleta__representante=rep, pagada=False
    ).select_related('atleta')

    return render(request, 'finanzas/mis_pagos.html', {
        'pagos': pagos,
        'mensualidades_pendientes': mensualidades_pendientes,
    })


# === Vistas del administrador ===

@user_passes_test(es_admin)
def bandeja_admin(request):
    estado = request.GET.get('estado', 'PENDIENTE')
    if estado not in ['PENDIENTE', 'APROBADO', 'RECHAZADO', 'TODOS']:
        estado = 'PENDIENTE'

    if estado == 'TODOS':
        pagos = Pago.objects.all().select_related('representante')
    else:
        pagos = Pago.objects.filter(estado=estado).select_related('representante')

    return render(request, 'finanzas/bandeja.html', {
        'pagos': pagos,
        'estado_actual': estado,
    })


@user_passes_test(es_admin)
def detalle_admin(request, pk):
    pago = get_object_or_404(Pago, pk=pk)
    audit = pago.audit_log.all()[:20]

    # Pre-cargar tasa BCV de la fecha del pago (no rompe si falla)
    tasa_sugerida = None
    fuente_tasa = None
    if pago.estado == 'PENDIENTE':
        from finanzas.services.tasa_bcv import obtener_tasa
        tasa_sugerida = obtener_tasa(pago.fecha_pago)
        if tasa_sugerida is not None:
            from .models import TasaBCV
            cache_obj = TasaBCV.objects.filter(fecha=pago.fecha_pago).first()
            fuente_tasa = cache_obj.fuente if cache_obj else 'dolarapi'

    aprobar_form = AprobarPagoForm(
        initial={'tasa_bcv': tasa_sugerida} if tasa_sugerida else None
    )

    return render(request, 'finanzas/detalle.html', {
        'pago': pago,
        'audit_log': audit,
        'aprobar_form': aprobar_form,
        'rechazar_form': RechazarPagoForm(),
        'tasa_sugerida': tasa_sugerida,
        'fuente_tasa': fuente_tasa,
    })


@user_passes_test(es_admin)
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def aprobar(request, pk):
    pago = get_object_or_404(Pago, pk=pk)
    if pago.estado != 'PENDIENTE':
        messages.warning(request, 'Solo se pueden aprobar pagos pendientes.')
        return redirect('finanzas:detalle', pk=pk)

    if request.method == 'POST':
        form = AprobarPagoForm(request.POST)
        if form.is_valid():
            tasa = form.cleaned_data['tasa_bcv']

            # Calcular monto USD que se obtendría con esta tasa
            monto_usd_calculado = (pago.monto_bs / tasa).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            # Validar cobertura contra mensualidades vinculadas
            mensualidades = pago.mensualidades_cubiertas.all()
            total_esperado = sum(
                (m.monto_usd for m in mensualidades),
                Decimal('0.00')
            )

            if mensualidades.exists() and monto_usd_calculado < (total_esperado - TOLERANCIA_COBERTURA_USD):
                faltante = (total_esperado - monto_usd_calculado).quantize(Decimal('0.01'))
                messages.error(
                    request,
                    f'Cobertura insuficiente. Pago = {monto_usd_calculado} USD, '
                    f'mensualidades = {total_esperado} USD. '
                    f'Faltan {faltante} USD. Rechaza el pago o solicita complemento.'
                )
                return redirect('finanzas:detalle', pk=pk)

            with transaction.atomic():
                estado_anterior = pago.estado
                pago.tasa_bcv = tasa
                pago.estado = 'APROBADO'
                pago.revisado_por = request.user
                pago.revisado_en = timezone.now()
                pago.save()

                # Marcar mensualidades vinculadas como pagadas (cobertura validada)
                for m in mensualidades:
                    m.pagada = True
                    m.save()

                # AuditLog
                pago.registrar_audit(
                    accion='APROBADO',
                    actor=request.user,
                    estado_anterior=estado_anterior,
                    estado_nuevo='APROBADO',
                    detalles={
                        'tasa_bcv': str(pago.tasa_bcv),
                        'monto_usd': str(pago.monto_usd),
                        'total_esperado_usd': str(total_esperado),
                        'mensualidades_pagadas': [m.id for m in mensualidades],
                    }
                )

                if mensualidades.exists():
                    pago.registrar_audit(
                        accion='MENSUALIDADES_VINCULADAS',
                        actor=request.user,
                        detalles={'count': mensualidades.count()}
                    )

            from .telegram_bot import notificar_pago_aprobado
            notificar_pago_aprobado(pago)

            messages.success(request, f'Pago #{pago.id} aprobado.')
        else:
            messages.error(request, 'Tasa BCV inválida.')

    return redirect('finanzas:bandeja')


@user_passes_test(es_admin)
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def rechazar(request, pk):
    pago = get_object_or_404(Pago, pk=pk)
    if pago.estado != 'PENDIENTE':
        messages.warning(request, 'Solo se pueden rechazar pagos pendientes.')
        return redirect('finanzas:detalle', pk=pk)

    if request.method == 'POST':
        form = RechazarPagoForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                estado_anterior = pago.estado
                pago.estado = 'RECHAZADO'
                pago.motivo_rechazo = form.cleaned_data['motivo']
                pago.revisado_por = request.user
                pago.revisado_en = timezone.now()
                pago.save()

                # Desvincular mensualidades (siguen disponibles para otro pago)
                pago.mensualidades_cubiertas.update(pago=None)

                pago.registrar_audit(
                    accion='RECHAZADO',
                    actor=request.user,
                    estado_anterior=estado_anterior,
                    estado_nuevo='RECHAZADO',
                    detalles={'motivo': pago.motivo_rechazo}
                )

            from .telegram_bot import notificar_pago_rechazado
            notificar_pago_rechazado(pago)
            messages.success(request, f'Pago #{pago.id} rechazado.')
        else:
            messages.error(request, 'Motivo de rechazo requerido.')

    return redirect('finanzas:bandeja')


# === Webhook Telegram ===

@csrf_exempt
@ratelimit(key='ip', rate='60/m', block=True)
def telegram_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False})

    msg = data.get('message', {})
    text = msg.get('text', '')
    chat_id = msg.get('chat', {}).get('id')

    if not chat_id:
        return JsonResponse({'ok': True})

    if text.startswith('/start '):
        from filiacion.models import Representante
        token = text.split(' ', 1)[1].strip()
        try:
            rep = Representante.objects.get(cedula_identidad=token)
            rep.telegram_chat_id = str(chat_id)
            rep.save()
            enviar_mensaje(
                chat_id,
                f'✅ Listo, {rep.nombres}. Recibirás notificaciones aquí.'
            )
        except Representante.DoesNotExist:
            enviar_mensaje(
                chat_id,
                '❌ Cédula no encontrada. Envía: /start TU_CEDULA'
            )
    elif text == '/start':
        enviar_mensaje(
            chat_id,
            'Hola. Para asociar tu cuenta envía: /start TU_CEDULA'
        )

    return JsonResponse({'ok': True})
