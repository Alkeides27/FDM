import pytest
from decimal import Decimal
from django.urls import reverse
from finanzas.models import Pago, PagoAuditLog, Mensualidad, TOLERANCIA_COBERTURA_USD


@pytest.mark.integration
def test_representante_reporta_pago_y_se_crea_en_estado_pendiente(
    client_representante, mensualidad_pendiente, comprobante_pdf
):
    """POST con form válido crea Pago con estado='PENDIENTE'."""
    url = reverse('finanzas:reportar')
    data = {
        'metodo': 'PAGO_MOVIL',
        'banco_emisor': '0134',
        'referencia': '12345678',
        'monto_bs': '500.00',
        'fecha_pago': '2026-06-08',
        'comprobante': comprobante_pdf,
        'mensualidades': [mensualidad_pendiente.id],
    }
    response = client_representante.post(url, data)
    assert response.status_code == 302
    pago = Pago.objects.latest('id')
    assert pago.estado == 'PENDIENTE'
    assert pago.monto_bs == Decimal('500.00')


@pytest.mark.integration
def test_pago_creado_genera_audit_log_con_accion_creado(
    client_representante, mensualidad_pendiente, comprobante_pdf
):
    """Después de reportar, existe PagoAuditLog con accion='CREADO'."""
    url = reverse('finanzas:reportar')
    data = {
        'metodo': 'PAGO_MOVIL',
        'banco_emisor': '0134',
        'referencia': '12345679',
        'monto_bs': '500.00',
        'fecha_pago': '2026-06-08',
        'comprobante': comprobante_pdf,
        'mensualidades': [mensualidad_pendiente.id],
    }
    client_representante.post(url, data)
    pago = Pago.objects.latest('id')
    audit = PagoAuditLog.objects.filter(pago=pago, accion='CREADO').first()
    assert audit is not None
    assert audit.estado_nuevo == 'PENDIENTE'


@pytest.mark.integration
def test_mensualidades_seleccionadas_quedan_vinculadas_al_pago_pero_no_pagadas(
    client_representante, mensualidad_pendiente, comprobante_pdf
):
    """Pago vincula mensualidades pero pagada=False hasta aprobación."""
    url = reverse('finanzas:reportar')
    data = {
        'metodo': 'PAGO_MOVIL',
        'banco_emisor': '0134',
        'referencia': '12345680',
        'monto_bs': '500.00',
        'fecha_pago': '2026-06-08',
        'comprobante': comprobante_pdf,
        'mensualidades': [mensualidad_pendiente.id],
    }
    client_representante.post(url, data)
    pago = Pago.objects.latest('id')
    mensualidad = m = Mensualidad.objects.get(id=mensualidad_pendiente.id)
    assert m.pago == pago
    assert m.pagada is False


@pytest.mark.integration
def test_tesorero_aprueba_pago_marca_mensualidades_pagadas(
    client_tesorero, representante_con_user, mensualidad_pendiente, comprobante_pdf
):
    """Aprobar marca Mensualidad.pagada=True para las vinculadas."""
    pago = Pago.objects.create(
        representante=representante_con_user,
        concepto='Test',
        metodo='PAGO_MOVIL',
        banco_emisor='0134',
        referencia='12345681',
        monto_bs=Decimal('500.00'),
        fecha_pago='2026-06-08',
        comprobante=comprobante_pdf,
        estado='PENDIENTE'
    )
    mensualidad_pendiente.pago = pago
    mensualidad_pendiente.save()

    url = reverse('finanzas:aprobar', args=[pago.id])
    response = client_tesorero.post(url, {'tasa_bcv': '50.0000'})
    assert response.status_code == 302
    
    pago.refresh_from_db()
    assert pago.estado == 'APROBADO'
    mensualidad_pendiente.refresh_from_db()
    assert mensualidad_pendiente.pagada is True


@pytest.mark.integration
def test_aprobar_pago_genera_audit_log_con_accion_aprobado(
    client_tesorero, representante_con_user, mensualidad_pendiente, comprobante_pdf
):
    """AuditLog tiene entrada accion='APROBADO' con tasa_bcv y monto_usd."""
    pago = Pago.objects.create(
        representante=representante_con_user,
        concepto='Test',
        metodo='PAGO_MOVIL',
        banco_emisor='0134',
        referencia='12345682',
        monto_bs=Decimal('500.00'),
        fecha_pago='2026-06-08',
        comprobante=comprobante_pdf,
        estado='PENDIENTE'
    )
    mensualidad_pendiente.pago = pago
    mensualidad_pendiente.save()

    url = reverse('finanzas:aprobar', args=[pago.id])
    client_tesorero.post(url, {'tasa_bcv': '50.0000'})
    
    audit = PagoAuditLog.objects.filter(pago=pago, accion='APROBADO').first()
    assert audit is not None
    assert audit.estado_nuevo == 'APROBADO'
    assert Decimal(audit.detalles['tasa_bcv']) == Decimal('50.0000')


@pytest.mark.integration
def test_aprobar_pago_dispara_notificacion_telegram_al_representante(
    client_tesorero, representante_con_user, mensualidad_pendiente, comprobante_pdf, mock_telegram
):
    """Al aprobar un pago, debe enviarse mensaje Telegram al representante."""
    pago = Pago.objects.create(
        representante=representante_con_user,
        concepto='Test',
        metodo='PAGO_MOVIL',
        banco_emisor='0134',
        referencia='12345683',
        monto_bs=Decimal('500.00'),
        fecha_pago='2026-06-08',
        comprobante=comprobante_pdf,
        estado='PENDIENTE'
    )
    mensualidad_pendiente.pago = pago
    mensualidad_pendiente.save()

    url = reverse('finanzas:aprobar', args=[pago.id])
    response = client_tesorero.post(url, {'tasa_bcv': '50.0000'})
    assert response.status_code == 302
    assert len(mock_telegram) == 1
    assert 'APROBADO' in mock_telegram[0]['texto']


@pytest.mark.integration
def test_aprobar_pago_con_cobertura_insuficiente_no_marca_mensualidades_pagadas(
    client_tesorero, representante_con_user, atleta_de, comprobante_pdf
):
    """Si la tasa aplicada no cubre el monto USD de las mensualidades, no se aprueba."""
    # Mensualidad cuesta 100 USD
    mensualidad_cara = Mensualidad.objects.create(
        atleta=atleta_de,
        periodo_mes=6,
        periodo_anio=2026,
        monto_usd=Decimal('100.00'),
        fecha_vencimiento='2026-06-30',
        pagada=False
    )
    # Pago es 100 Bs / tasa 50 = 2 USD -> insuficiente
    pago = Pago.objects.create(
        representante=representante_con_user,
        concepto='Test',
        metodo='PAGO_MOVIL',
        banco_emisor='0134',
        referencia='12345684',
        monto_bs=Decimal('100.00'),
        fecha_pago='2026-06-08',
        comprobante=comprobante_pdf,
        estado='PENDIENTE'
    )
    mensualidad_cara.pago = pago
    mensualidad_cara.save()

    url = reverse('finanzas:aprobar', args=[pago.id])
    response = client_tesorero.post(url, {'tasa_bcv': '50.0000'})
    # Debe redirigir de vuelta al detalle del pago con error
    assert response.status_code == 302
    pago.refresh_from_db()
    assert pago.estado == 'PENDIENTE'
    mensualidad_cara.refresh_from_db()
    assert mensualidad_cara.pagada is False
