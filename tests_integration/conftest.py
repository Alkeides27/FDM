import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import User, Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from filiacion.models import Representante, Atleta
from administracion.models import Categoria
from finanzas.models import Mensualidad, Pago


# ═══════════════════════════════════════════════════════════════
# Mocks automáticos para servicios externos
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def mock_telegram(monkeypatch):
    """Mockea Telegram. Retorna lista de mensajes 'enviados' para inspección."""
    enviadas = []
    
    def fake_enviar_mensaje(chat_id, texto):
        enviadas.append({'chat_id': chat_id, 'texto': texto})
        return True
    
    monkeypatch.setattr(
        'finanzas.telegram_bot.enviar_mensaje',
        fake_enviar_mensaje
    )
    return enviadas


@pytest.fixture(autouse=True)
def mock_tasa_bcv(monkeypatch):
    """Retorna tasa BCV fija de 50.0000 Bs por USD en todos los tests."""
    monkeypatch.setattr(
        'finanzas.services.tasa_bcv.obtener_tasa',
        lambda fecha=None: Decimal('50.0000')
    )


# ═══════════════════════════════════════════════════════════════
# Fixtures de usuarios y roles
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def representante_con_user(db):
    """Crea User + Representante asociado vía OneToOne."""
    user = User.objects.create_user(
        username='12345678',
        password='ClaveSegura123!',
        email='rep@test.com'
    )
    rep = Representante.objects.create(
        cedula_identidad='12345678',
        nombres='Juan', apellidos='Pérez',
        telefono_principal='04141234567',
        direccion_habitacion='Calle de prueba',
        correo_electronico='rep@test.com',
        telegram_chat_id='999999',
        usuario=user,
    )
    user.refresh_from_db()
    return rep


@pytest.fixture
def tesorero(db):
    """Crea User en grupo Tesoreria."""
    user = User.objects.create_user(
        username='tesorero01',
        password='ClaveSegura123!',
        is_staff=True,
    )
    grupo, _ = Group.objects.get_or_create(name='Tesoreria')
    user.groups.add(grupo)
    return user


@pytest.fixture
def coord_general(db):
    """Crea User en grupo CoordinadorGeneral."""
    user = User.objects.create_user(
        username='coord01',
        password='ClaveSegura123!',
        is_staff=True,
    )
    grupo, _ = Group.objects.get_or_create(name='CoordinadorGeneral')
    user.groups.add(grupo)
    return user


@pytest.fixture
def entrenador_user(db):
    """Crea User en grupo Entrenador."""
    user = User.objects.create_user(
        username='entr01',
        password='ClaveSegura123!',
        is_staff=True,
    )
    grupo, _ = Group.objects.get_or_create(name='Entrenador')
    user.groups.add(grupo)
    return user


# ═══════════════════════════════════════════════════════════════
# Fixtures de dominio
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def categoria(db):
    """Crea una Categoria mínima."""
    return Categoria.objects.create(
        nombre='Sub-9',
        anio_nacimiento_min=2017,
        anio_nacimiento_max=2018,
        genero='MASCULINO',
    )


@pytest.fixture
def atleta_de(representante_con_user, categoria):
    """Crea un Atleta asociado al representante y categoría."""
    return Atleta.objects.create(
        representante=representante_con_user,
        categoria=categoria,
        nombres='Pedro', apellidos='Pérez',
        fecha_nacimiento=date(2017, 3, 15),
        lateralidad='DERECHO', posicion='DEL',
    )


@pytest.fixture
def mensualidad_pendiente(atleta_de):
    """Crea una Mensualidad pendiente de 10 USD para el atleta."""
    return Mensualidad.objects.create(
        atleta=atleta_de,
        periodo_mes=6,
        periodo_anio=2026,
        monto_usd=Decimal('10.00'),
        fecha_vencimiento=timezone.now().date() + timedelta(days=15),
        pagada=False,
    )


@pytest.fixture
def comprobante_pdf():
    """SimpleUploadedFile PDF mock para subir como comprobante."""
    return SimpleUploadedFile(
        'comprobante.pdf',
        b'contenido_pdf_mock',
        content_type='application/pdf',
    )


# ═══════════════════════════════════════════════════════════════
# Fixtures de clientes Django logueados
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def client_representante(client, representante_con_user):
    """Cliente Django logueado como representante."""
    client.force_login(representante_con_user.usuario)
    return client


@pytest.fixture
def client_tesorero(client, tesorero):
    """Cliente Django logueado como tesorero."""
    client.force_login(tesorero)
    return client


@pytest.fixture
def client_coord_general(client, coord_general):
    """Cliente Django logueado como CoordinadorGeneral."""
    client.force_login(coord_general)
    return client


@pytest.fixture
def client_entrenador(client, entrenador_user):
    """Cliente Django logueado como Entrenador."""
    client.force_login(entrenador_user)
    return client
