import pytest
from datetime import date
from decimal import Decimal
from django.urls import reverse
from finanzas.models import Pago


@pytest.mark.integration
def test_notificar_pago_aprobado_envia_mensaje_con_formato_correcto(
    representante_con_user, comprobante_pdf, mock_telegram
):
    """El mensaje de aprobación debe incluir número de pago y montos formateados."""
    from finanzas.telegram_bot import notificar_pago_aprobado
    
    pago = Pago.objects.create(
        representante=representante_con_user,
        concepto='Pago de Junio 2026',
        metodo='PAGO_MOVIL',
        banco_emisor='0134',
        referencia='12345689',
        monto_bs=Decimal('500.00'),
        tasa_bcv=Decimal('50.0000'),
        fecha_pago='2026-06-08',
        comprobante=comprobante_pdf,
        estado='APROBADO'
    )
    # save() calcula el monto_usd en base a monto_bs y tasa_bcv
    pago.refresh_from_db()
    
    notificar_pago_aprobado(pago)
    
    assert len(mock_telegram) == 1
    texto = mock_telegram[0]['texto']
    assert f'#{pago.id}' in texto
    assert 'APROBADO' in texto
    assert 'Bs' in texto  # Formato Bs presente
    assert '$' in texto   # Formato USD presente


@pytest.mark.integration
def test_notificar_pago_sin_chat_id_no_lanza_error(
    representante_con_user, comprobante_pdf, mock_telegram
):
    """Si representante.telegram_chat_id está vacío, no crashea."""
    from finanzas.telegram_bot import notificar_pago_aprobado
    
    representante_con_user.telegram_chat_id = ''
    representante_con_user.save()
    
    pago = Pago.objects.create(
        representante=representante_con_user,
        concepto='Pago de Junio 2026',
        metodo='PAGO_MOVIL',
        banco_emisor='0134',
        referencia='12345690',
        monto_bs=Decimal('500.00'),
        tasa_bcv=Decimal('50.0000'),
        fecha_pago='2026-06-08',
        comprobante=comprobante_pdf,
        estado='APROBADO'
    )
    pago.refresh_from_db()
    
    # No debe lanzar error/crashear
    success = notificar_pago_aprobado(pago)
    assert success is False
    assert len(mock_telegram) == 0


@pytest.mark.integration
def test_descargar_ficha_tecnica_pdf_retorna_content_type_pdf(
    client_representante, atleta_de
):
    """GET a DescargarFichaPDF retorna Content-Type: application/pdf."""
    url = reverse('atleta_ficha_pdf', args=[atleta_de.id])
    response = client_representante.get(url)
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'


@pytest.mark.integration
def test_representante_no_puede_descargar_ficha_de_atleta_ajeno(
    client_representante, categoria
):
    """Representante intenta descargar PDF de atleta de otro -> 403."""
    from django.contrib.auth.models import User
    from filiacion.models import Representante, Atleta
    
    otro_user = User.objects.create_user(username='otherrep5', password='ClaveSegura123!')
    otro_rep = Representante.objects.create(
        cedula_identidad='22222226', nombres='Otro', apellidos='Rep',
        telefono_principal='04141112233', direccion_habitacion='Caracas',
        correo_electronico='other5@test.com', usuario=otro_user
    )
    atleta_ajeno = Atleta.objects.create(
        representante=otro_rep, categoria=categoria,
        nombres='Juan', apellidos='Gomez',
        fecha_nacimiento=date(2017, 5, 20),
        lateralidad='DERECHO', posicion='DEL'
    )
    
    url = reverse('atleta_ficha_pdf', args=[atleta_ajeno.id])
    response = client_representante.get(url)
    assert response.status_code == 403
