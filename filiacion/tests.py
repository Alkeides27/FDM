# filiacion/tests.py
# Pruebas unitarias — Módulo Filiacion
# PRD v1.0 | IngeniumCode-FDM | 8 de junio de 2026

from datetime import date
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from filiacion.models import Representante, Atleta
from filiacion.views import _es_solo_representante
from administracion.models import Categoria


# ═══════════════════════════════════════════════════════════════
# Helpers de fábrica
# ═══════════════════════════════════════════════════════════════

def crear_representante(cedula='12345678', correo='rep@test.com', usuario=None):
    """Crea un Representante con datos mínimos válidos."""
    return Representante.objects.create(
        cedula_identidad=cedula,
        nombres='Juan',
        apellidos='Pérez',
        telefono_principal='04141234567',
        direccion_habitacion='Calle de prueba',
        correo_electronico=correo,
        usuario=usuario,
    )


def crear_categoria(nombre='Sub-9', genero='MASCULINO'):
    """Crea una Categoria con campos obligatorios reales del modelo."""
    return Categoria.objects.create(
        nombre=nombre,
        anio_nacimiento_min=2017,
        anio_nacimiento_max=2018,
        genero=genero,
    )


def crear_atleta(representante=None, categoria=None, fecha_nacimiento=None,
                 cedula_escolar=None, lateralidad='DERECHO', posicion='DEL'):
    """Crea un Atleta con datos mínimos válidos."""
    if representante is None:
        representante = crear_representante()
    if categoria is None:
        categoria = crear_categoria()
    return Atleta.objects.create(
        representante=representante,
        categoria=categoria,
        cedula_escolar=cedula_escolar,
        nombres='Pedro',
        apellidos='Pérez',
        fecha_nacimiento=fecha_nacimiento or date(2017, 3, 15),
        lateralidad=lateralidad,
        posicion=posicion,
    )


# ═══════════════════════════════════════════════════════════════
# FASE 1 — Modelo Representante
# ═══════════════════════════════════════════════════════════════

class Fase1_RepresentanteTestCase(TestCase):
    """Valida el correcto comportamiento del modelo Representante y sus restricciones."""

    def test_representante_se_crea_con_datos_minimos_validos(self):
        """Un Representante con todos los campos obligatorios se crea sin error."""
        rep = crear_representante()
        self.assertEqual(Representante.objects.count(), 1)
        self.assertEqual(rep.cedula_identidad, '12345678')

    def test_representante_str_retorna_formato_esperado(self):
        """El método __str__ de Representante debe retornar el formato 'Nombres Apellidos (C.I: cedula)'."""
        rep = crear_representante(cedula='12345678')
        self.assertEqual(str(rep), 'Juan Pérez (C.I: 12345678)')

    def test_representante_con_cedula_duplicada_lanza_integrity_error(self):
        """No se pueden crear dos representantes con la misma cédula. Debe lanzar IntegrityError."""
        crear_representante(cedula='12345678', correo='primero@test.com')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                crear_representante(cedula='12345678', correo='segundo@test.com')

    def test_representante_con_correo_duplicado_lanza_integrity_error(self):
        """No se pueden crear dos representantes con el mismo correo electrónico. Debe lanzar IntegrityError."""
        crear_representante(cedula='11111111', correo='duplicado@test.com')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                crear_representante(cedula='22222222', correo='duplicado@test.com')

    def test_representante_telegram_chat_id_es_opcional(self):
        """El campo telegram_chat_id debe ser opcional (blank=True) al crear un Representante."""
        rep = Representante.objects.create(
            cedula_identidad='12345678',
            nombres='Juan',
            apellidos='Pérez',
            telefono_principal='04141234567',
            direccion_habitacion='Calle de prueba',
            correo_electronico='rep@test.com',
            telegram_chat_id='',
        )
        self.assertEqual(rep.telegram_chat_id, '')


# ═══════════════════════════════════════════════════════════════
# FASE 2 — Relación Representante ↔ User
# ═══════════════════════════════════════════════════════════════

class Fase2_RepresentanteUsuarioTestCase(TestCase):
    """Valida la relación OneToOne entre Representante y el modelo User de Django."""

    def test_representante_puede_crearse_sin_usuario_asociado(self):
        """El campo usuario de Representante debe permitir None (null=True, blank=True)."""
        rep = crear_representante(usuario=None)
        self.assertIsNone(rep.usuario)

    def test_representante_vinculado_a_user_es_accesible_via_related_name(self):
        """El representante debe ser accesible desde el modelo User usando el related_name 'representante'."""
        user = User.objects.create_user(username='12345678', password='ClaveSegura123!')
        rep = crear_representante(cedula='12345678', usuario=user)
        user.refresh_from_db()
        self.assertEqual(user.representante, rep)

    def test_borrar_user_deja_representante_con_usuario_null(self):
        """on_delete=SET_NULL: borrar el User asociado deja el Representante con usuario=None."""
        user = User.objects.create_user(username='12345678', password='ClaveSegura123!')
        representante = crear_representante(cedula='12345678', usuario=user)
        user.delete()
        representante.refresh_from_db()
        self.assertIsNone(representante.usuario)


# ═══════════════════════════════════════════════════════════════
# FASE 3 — Modelo Atleta y sus relaciones
# ═══════════════════════════════════════════════════════════════

class Fase3_AtletaTestCase(TestCase):
    """Valida el comportamiento, relaciones FK y defaults del modelo Atleta."""

    def test_atleta_se_crea_con_datos_minimos_validos(self):
        """Un Atleta con todos los datos mínimos válidos debe crearse sin error."""
        atleta = crear_atleta()
        self.assertEqual(Atleta.objects.count(), 1)
        self.assertEqual(atleta.nombres, 'Pedro')

    def test_atleta_str_retorna_formato_esperado(self):
        """El método __str__ de Atleta debe retornar 'Nombres Apellidos' sin cédula ni paréntesis."""
        atleta = crear_atleta()
        self.assertEqual(str(atleta), 'Pedro Pérez')

    def test_atleta_nace_activo_y_no_becado_por_defecto(self):
        """Un atleta nuevo debe tener activo=True y becado=False por defecto."""
        atleta = crear_atleta()
        self.assertTrue(atleta.activo)
        self.assertFalse(atleta.becado)

    def test_borrar_representante_borra_sus_atletas_en_cascada(self):
        """on_delete=CASCADE en Atleta.representante: al borrar el representante se borran sus atletas."""
        rep = crear_representante()
        crear_atleta(representante=rep)
        crear_atleta(
            representante=rep,
            categoria=crear_categoria(nombre='Sub-10'),
        )
        self.assertEqual(Atleta.objects.count(), 2)
        rep.delete()
        self.assertEqual(Atleta.objects.count(), 0)

    def test_borrar_categoria_deja_atletas_con_categoria_null(self):
        """on_delete=SET_NULL en Atleta.categoria: borrar la Categoria debe dejar atleta.categoria=None."""
        cat = crear_categoria()
        atleta = crear_atleta(categoria=cat)
        self.assertEqual(atleta.categoria, cat)
        cat.delete()
        atleta.refresh_from_db()
        self.assertIsNone(atleta.categoria)

    def test_atleta_es_accesible_via_representante_related_name(self):
        """Los atletas deben ser accesibles desde el Representante usando el related_name 'atletas'."""
        rep = crear_representante()
        atleta = crear_atleta(representante=rep)
        self.assertIn(atleta, rep.atletas.all())


# ═══════════════════════════════════════════════════════════════
# FASE 4 — Helper _es_solo_representante
# ═══════════════════════════════════════════════════════════════

class Fase4_HelperRepresentantePuroTestCase(TestCase):
    """Valida la lógica del helper de filtrado por rol _es_solo_representante."""

    def test_es_solo_representante_con_superuser_retorna_false(self):
        """Un superusuario NO es considerado solo representante (debe ver todo)."""
        user = User.objects.create_superuser(username='admin', password='ClaveSegura123!', email='admin@test.com')
        self.assertFalse(_es_solo_representante(user))

    def test_es_solo_representante_con_user_staff_interno_retorna_false(self):
        """Un usuario perteneciente a un grupo de staff interno (Tesoreria) NO es solo representante."""
        user = User.objects.create_user(username='staffuser', password='ClaveSegura123!')
        grupo, _ = Group.objects.get_or_create(name='Tesoreria')
        user.groups.add(grupo)
        # Asociamos representante para validar que el rol staff interno gane y retorne False
        crear_representante(cedula='11223344', usuario=user)
        user.refresh_from_db()
        self.assertFalse(_es_solo_representante(user))

    def test_es_solo_representante_con_user_con_perfil_representante_retorna_true(self):
        """Un user sin grupos pero con perfil Representante asociado debe retornar True."""
        user = User.objects.create_user(username='12345678', password='ClaveSegura123!')
        crear_representante(cedula='12345678', usuario=user)
        user.refresh_from_db()
        self.assertTrue(_es_solo_representante(user))

    def test_es_solo_representante_con_user_sin_grupos_y_sin_perfil_retorna_false(self):
        """Un usuario huérfano sin grupos y sin perfil de representante debe retornar False."""
        user = User.objects.create_user(username='huerfano', password='ClaveSegura123!')
        self.assertFalse(_es_solo_representante(user))
