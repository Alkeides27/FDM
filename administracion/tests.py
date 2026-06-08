# administracion/tests.py
# Pruebas unitarias — Módulo Administracion
# PRD v1.0 | IngeniumCode-FDM | 8 de junio de 2026

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from administracion.models import Coordinador, Entrenador, Delegado, Categoria


# ═══════════════════════════════════════════════════════════════
# Helpers de fábrica
# ═══════════════════════════════════════════════════════════════

def crear_usuario(username='admin01', password='ClaveSegura123!'):
    """Crea un User básico para usar en OneToOne con Coordinador."""
    return User.objects.create_user(username=username, password=password)


def crear_coordinador(usuario=None, cargo='GENERAL',
                     nombres='María', apellidos='Coordina'):
    """Crea un Coordinador con User asociado."""
    if usuario is None:
        usuario = crear_usuario()
    return Coordinador.objects.create(
        usuario_sistema=usuario,
        nombres=nombres, apellidos=apellidos,
        cargo=cargo,
    )


def crear_entrenador(coordinador=None, licencia='FVF',
                    nombres='Carlos', apellidos='Entrena'):
    """Crea un Entrenador con o sin Coordinador asociado."""
    return Entrenador.objects.create(
        coordinador=coordinador,
        nombres=nombres, apellidos=apellidos,
        licencia=licencia,
        telefono='04141234567',
    )


def crear_delegado(nombres='Luis', apellidos='Delega'):
    """Crea un Delegado simple."""
    return Delegado.objects.create(
        nombres=nombres, apellidos=apellidos,
        telefono='04141234567',
    )


def crear_categoria(nombre='Sub-9', genero='MASCULINO',
                   anio_min=2017, anio_max=2018,
                   delegado=None, coordinador=None):
    """Crea una Categoria con campos obligatorios."""
    return Categoria.objects.create(
        nombre=nombre,
        anio_nacimiento_min=anio_min,
        anio_nacimiento_max=anio_max,
        genero=genero,
        delegado=delegado,
        coordinador_supervisor=coordinador,
    )


# ═══════════════════════════════════════════════════════════════
# FASE 1 — Modelo Coordinador
# ═══════════════════════════════════════════════════════════════

class Fase1_CoordinadorTestCase(TestCase):
    """Valida la creación, strings y unicidad del modelo Coordinador."""

    def test_coordinador_se_crea_con_user_asociado_via_onetoone(self):
        """OneToOne con User funciona, user.coordinador_profile es accesible."""
        user = crear_usuario()
        coord = crear_coordinador(usuario=user)
        self.assertEqual(Coordinador.objects.count(), 1)
        self.assertEqual(user.coordinador_profile, coord)

    def test_coordinador_str_incluye_cargo_display(self):
        """El método __str__ de Coordinador debe retornar 'Nombres Apellidos (Cargo)'."""
        coord = crear_coordinador(cargo='GENERAL')
        self.assertEqual(str(coord), "María Coordina (General)")

    def test_dos_coordinadores_mismo_user_lanza_integrity_error(self):
        """OneToOne con User: dos Coordinadores no pueden compartir el mismo User."""
        user = crear_usuario(username='admin01')
        crear_coordinador(usuario=user, cargo='GENERAL')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                crear_coordinador(usuario=user, cargo='DEPORTIVO')

    def test_borrar_user_borra_coordinador_en_cascada(self):
        """on_delete=CASCADE: borrar el User elimina el perfil Coordinador en cascada."""
        user = crear_usuario()
        coord = crear_coordinador(usuario=user)
        coord_id = coord.id
        user.delete()
        self.assertFalse(Coordinador.objects.filter(id=coord_id).exists())


# ═══════════════════════════════════════════════════════════════
# FASE 2 — Modelo Entrenador
# ═══════════════════════════════════════════════════════════════

class Fase2_EntrenadorTestCase(TestCase):
    """Valida la creación, defaults y relaciones del modelo Entrenador."""

    def test_entrenador_se_crea_con_defaults_correctos(self):
        """Un Entrenador nuevo debe nacer con activo=True."""
        ent = crear_entrenador()
        self.assertTrue(ent.activo)

    def test_entrenador_str_retorna_nombres_y_apellidos(self):
        """El método __str__ de Entrenador debe retornar 'Nombres Apellidos'."""
        ent = crear_entrenador()
        self.assertEqual(str(ent), "Carlos Entrena")

    def test_borrar_coordinador_deja_entrenador_con_coordinador_null(self):
        """on_delete=SET_NULL: borrar el Coordinador deja el campo coordinador en None."""
        coord = crear_coordinador()
        ent = crear_entrenador(coordinador=coord)
        coord.delete()
        ent.refresh_from_db()
        self.assertIsNone(ent.coordinador)

    def test_entrenador_es_accesible_via_coordinador_related_name(self):
        """El Coordinador debe acceder a sus entrenadores mediante entrenadores_a_cargo."""
        coord = crear_coordinador()
        ent = crear_entrenador(coordinador=coord)
        self.assertIn(ent, coord.entrenadores_a_cargo.all())


# ═══════════════════════════════════════════════════════════════
# FASE 3 — Modelo Delegado
# ═══════════════════════════════════════════════════════════════

class Fase3_DelegadoTestCase(TestCase):
    """Valida la creación y string del modelo Delegado."""

    def test_delegado_se_crea_con_datos_minimos_validos(self):
        """Un Delegado con datos obligatorios debe crearse sin error."""
        d = crear_delegado()
        self.assertEqual(Delegado.objects.count(), 1)
        self.assertEqual(d.nombres, "Luis")

    def test_delegado_str_retorna_nombres_y_apellidos(self):
        """El método __str__ de Delegado debe retornar 'Nombres Apellidos'."""
        d = crear_delegado()
        self.assertEqual(str(d), "Luis Delega")


# ═══════════════════════════════════════════════════════════════
# FASE 4 — Modelo Categoria (relaciones complejas)
# ═══════════════════════════════════════════════════════════════

class Fase4_CategoriaTestCase(TestCase):
    """Valida restricciones de unicidad, relaciones OneToOne y M2M del modelo Categoria."""

    def test_categoria_str_retorna_solo_nombre(self):
        """El método __str__ de Categoria debe retornar únicamente su nombre."""
        cat = crear_categoria(nombre='Sub-12')
        self.assertEqual(str(cat), "Sub-12")

    def test_dos_categorias_mismo_nombre_lanza_integrity_error(self):
        """El nombre de la categoría es único (unique=True). Nombres duplicados lanzan IntegrityError."""
        crear_categoria(nombre='Sub-12')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                crear_categoria(nombre='Sub-12')

    def test_delegado_no_puede_ser_de_dos_categorias(self):
        """OneToOne delegado: un mismo Delegado no puede asignarse a más de una Categoria."""
        d = crear_delegado()
        crear_categoria(nombre='Sub-12', delegado=d)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                crear_categoria(nombre='Sub-13', delegado=d)

    def test_borrar_delegado_deja_categoria_con_delegado_null(self):
        """on_delete=SET_NULL: borrar un Delegado deja el campo delegado de la Categoria en None."""
        d = crear_delegado()
        cat = crear_categoria(nombre='Sub-12', delegado=d)
        d.delete()
        cat.refresh_from_db()
        self.assertIsNone(cat.delegado)

    def test_categoria_acepta_multiples_entrenadores_asignados_via_m2m(self):
        """La relación M2M permite que una Categoria tenga varios entrenadores asignados."""
        cat = crear_categoria(nombre='Sub-12')
        ent1 = crear_entrenador(nombres='Carlos', apellidos='Uno')
        ent2 = crear_entrenador(nombres='Luis', apellidos='Dos')
        cat.entrenadores_asignados.add(ent1, ent2)
        self.assertEqual(cat.entrenadores_asignados.count(), 2)

    def test_entrenador_puede_estar_en_multiples_categorias_via_m2m(self):
        """La relación M2M permite que un Entrenador esté asignado a varias categorías."""
        cat1 = crear_categoria(nombre='Sub-12')
        cat2 = crear_categoria(nombre='Sub-13')
        ent = crear_entrenador()
        cat1.entrenadores_asignados.add(ent)
        cat2.entrenadores_asignados.add(ent)
        self.assertEqual(ent.categorias_asignadas.count(), 2)
