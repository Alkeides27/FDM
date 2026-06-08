# accounts/tests.py
# Pruebas unitarias — Módulo Accounts
# PRD v1.0 | IngeniumCode-FDM | 8 de junio de 2026

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, Group, AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse

from accounts.forms import (
    StaffOnlyAuthenticationForm,
    RepresentanteSignUpForm,
    validar_cedula_venezolana,
    validar_telefono_venezolano,
)
from accounts.decorators import (
    tesoreria_required,
    coord_general_required,
    coord_deportivo_required,
    entrenador_required,
    representante_required,
    staff_required,
    lectura_atletas_required,
    edicion_atletas_required,
    gestion_deportiva_required,
)
from accounts.context_processors import roles
from accounts.templatetags.accounts_tags import tiene_grupo, es_representante

from filiacion.models import Representante


# ═══════════════════════════════════════════════════════════════
# Helpers de fábrica
# ═══════════════════════════════════════════════════════════════

def crear_usuario(username='12345678', password='ClaveSegura123!',
                  is_staff=False, is_superuser=False, email='user@test.com'):
    """Crea un User con datos mínimos válidos."""
    return User.objects.create_user(
        username=username,
        password=password,
        email=email,
        is_staff=is_staff,
        is_superuser=is_superuser,
    )


def crear_usuario_en_grupo(nombre_grupo, username='12345678'):
    """Crea un User y lo agrega al grupo nombrado."""
    user = crear_usuario(username=username)
    grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
    user.groups.add(grupo)
    return user


def crear_representante_con_user(cedula='12345678'):
    """Crea User + Representante asociado vía OneToOne. Retorna (user, representante)."""
    user = crear_usuario(username=cedula)
    representante = Representante.objects.create(
        cedula_identidad=cedula,
        nombres='Test',
        apellidos='Representante',
        telefono_principal='04141234567',
        direccion_habitacion='Calle de prueba',
        correo_electronico=f'{cedula}@test.com',
        usuario=user,
    )
    return user, representante


def vista_dummy(request):
    """Vista mínima usada para testear decoradores."""
    return HttpResponse('OK')


# ═══════════════════════════════════════════════════════════════
# FASE 1 — Validadores Venezolanos
# ═══════════════════════════════════════════════════════════════

class Fase1_ValidadoresVenezolanosTestCase(TestCase):
    """Valida los validadores de formato de cédula y teléfono de Venezuela."""

    def test_cedula_8_digitos_exactos_pasa_validacion(self):
        """Cédula de 8 dígitos exactos no debe lanzar ValidationError."""
        try:
            validar_cedula_venezolana('12345678')
        except ValidationError:
            self.fail('validar_cedula_venezolana() lanzó ValidationError inesperadamente.')

    def test_cedula_con_letras_lanza_validation_error(self):
        """Cédula que contiene letras debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            validar_cedula_venezolana('V1234567')

    def test_cedula_con_menos_de_8_digitos_lanza_validation_error(self):
        """Cédula con menos de 8 dígitos debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            validar_cedula_venezolana('1234567')

    def test_telefono_con_prefijo_valido_pasa_validacion(self):
        """Teléfono con prefijo venezolano válido (0414) no debe lanzar ValidationError."""
        try:
            validar_telefono_venezolano('04141234567')
        except ValidationError:
            self.fail('validar_telefono_venezolano() lanzó ValidationError inesperadamente.')

    def test_telefono_con_prefijo_invalido_lanza_validation_error(self):
        """Teléfono con prefijo no registrado (0400) debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            validar_telefono_venezolano('04001234567')

    def test_telefono_con_letras_lanza_validation_error(self):
        """Teléfono que contiene caracteres no numéricos debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            validar_telefono_venezolano('0414ABCDEFG')


# ═══════════════════════════════════════════════════════════════
# FASE 2 — StaffOnlyAuthenticationForm
# ═══════════════════════════════════════════════════════════════

class Fase2_StaffOnlyLoginTestCase(TestCase):
    """Valida el login restringido a staff y representantes del formulario StaffOnlyAuthenticationForm."""

    def test_login_permitido_para_usuario_staff(self):
        """Usuario con is_staff=True debe pasar confirm_login_allowed sin ValidationError."""
        user = crear_usuario(username='88888888', is_staff=True)
        form = StaffOnlyAuthenticationForm()
        try:
            form.confirm_login_allowed(user)
        except ValidationError:
            self.fail('confirm_login_allowed() lanzó ValidationError inesperadamente para usuario staff.')

    def test_login_permitido_para_representante_no_staff(self):
        """Usuario sin staff pero con perfil de representante debe poder iniciar sesión."""
        user, _ = crear_representante_con_user(cedula='12345678')
        # Aseguramos que no sea staff
        user.is_staff = False
        user.save()
        form = StaffOnlyAuthenticationForm()
        try:
            form.confirm_login_allowed(user)
        except ValidationError:
            self.fail('confirm_login_allowed() lanzó ValidationError inesperadamente para representante.')

    def test_login_rechazado_para_usuario_huerfano(self):
        """Usuario sin staff y sin perfil de representante debe ser rechazado con el código no_staff."""
        user = crear_usuario(username='99999999', is_staff=False)
        form = StaffOnlyAuthenticationForm()
        with self.assertRaises(ValidationError) as ctx:
            form.confirm_login_allowed(user)
        self.assertEqual(ctx.exception.code, 'no_staff')

    def test_login_rechazado_para_usuario_inactivo(self):
        """Usuario inactivo (is_active=False) debe lanzar ValidationError con código 'inactive'."""
        user = crear_usuario(username='77777777', is_staff=True)
        user.is_active = False
        user.save()
        form = StaffOnlyAuthenticationForm()
        with self.assertRaises(ValidationError) as ctx:
            form.confirm_login_allowed(user)
        # AuthenticationForm de Django lanza error 'inactive' cuando is_active=False
        self.assertEqual(ctx.exception.code, 'inactive')


# ═══════════════════════════════════════════════════════════════
# FASE 3 — RepresentanteSignUpForm
# ═══════════════════════════════════════════════════════════════

class Fase3_RepresentanteSignUpFormTestCase(TestCase):
    """Valida el comportamiento de creación de cuentas de RepresentanteSignUpForm."""

    def test_signup_form_valido_crea_user_y_representante_atomicamente(self):
        """Un form válido debe crear exactamente un User y un Representante asociado."""
        data = {
            'cedula_identidad': '12345678',
            'nombres': 'Juan',
            'apellidos': 'Pérez',
            'correo_electronico': 'juan@test.com',
            'telefono_principal': '04141234567',
            'direccion_habitacion': 'Calle de prueba',
            'password1': 'ClaveSegura2026!',
            'password2': 'ClaveSegura2026!',
        }
        form = RepresentanteSignUpForm(data=data)
        self.assertTrue(form.is_valid(), msg=form.errors)
        user = form.save()
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Representante.objects.count(), 1)
        self.assertEqual(user.username, '12345678')
        self.assertEqual(user.representante.nombres, 'Juan')

    def test_signup_form_user_creado_tiene_is_staff_false_y_username_es_cedula(self):
        """El User creado debe tener is_staff=False, is_superuser=False y username igual a la cédula."""
        data = {
            'cedula_identidad': '87654321',
            'nombres': 'María',
            'apellidos': 'Gómez',
            'correo_electronico': 'maria@test.com',
            'telefono_principal': '04121234567',
            'direccion_habitacion': 'Avenida principal',
            'password1': 'ClaveSegura2026!',
            'password2': 'ClaveSegura2026!',
        }
        form = RepresentanteSignUpForm(data=data)
        self.assertTrue(form.is_valid(), msg=form.errors)
        user = form.save()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.username, '87654321')

    def test_signup_form_con_cedula_duplicada_lanza_validation_error(self):
        """Si la cédula ya existe en User o en Representante, el formulario debe ser inválido."""
        # Creamos representante inicial
        crear_representante_con_user(cedula='12345678')

        data = {
            'cedula_identidad': '12345678',
            'nombres': 'Pedro',
            'apellidos': 'Pérez',
            'correo_electronico': 'pedro@test.com',
            'telefono_principal': '04161234567',
            'direccion_habitacion': 'Calle de prueba',
            'password1': 'ClaveSegura2026!',
            'password2': 'ClaveSegura2026!',
        }
        form = RepresentanteSignUpForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('cedula_identidad', form.errors)

    def test_signup_form_con_correo_duplicado_lanza_validation_error(self):
        """Si el correo ya existe en Representante o en User, el formulario debe ser inválido."""
        crear_representante_con_user(cedula='12345678')

        data = {
            'cedula_identidad': '87654321',
            'nombres': 'Luis',
            'apellidos': 'Rodríguez',
            'correo_electronico': '12345678@test.com',  # Correo ya tomado por el helper anterior
            'telefono_principal': '04241234567',
            'direccion_habitacion': 'Calle de prueba 2',
            'password1': 'ClaveSegura2026!',
            'password2': 'ClaveSegura2026!',
        }
        form = RepresentanteSignUpForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('correo_electronico', form.errors)

    def test_signup_form_correo_se_normaliza_a_minusculas(self):
        """El correo electrónico ingresado debe normalizarse a minúsculas en clean_correo_electronico."""
        data = {
            'cedula_identidad': '11223344',
            'nombres': 'Luis',
            'apellidos': 'Rodríguez',
            'correo_electronico': 'LUIS@TestMail.Com',
            'telefono_principal': '04241234567',
            'direccion_habitacion': 'Calle de prueba 2',
            'password1': 'ClaveSegura2026!',
            'password2': 'ClaveSegura2026!',
        }
        form = RepresentanteSignUpForm(data=data)
        self.assertTrue(form.is_valid(), msg=form.errors)
        self.assertEqual(form.cleaned_data['correo_electronico'], 'luis@testmail.com')

    def test_signup_form_con_cedula_invalida_no_crea_user(self):
        """Un formulario con formato de cédula inválido debe fallar en validación y no crear registros."""
        data = {
            'cedula_identidad': 'V1234567',  # Formato incorrecto
            'nombres': 'Luis',
            'apellidos': 'Rodríguez',
            'correo_electronico': 'luis@test.com',
            'telefono_principal': '04241234567',
            'direccion_habitacion': 'Calle de prueba 2',
            'password1': 'ClaveSegura2026!',
            'password2': 'ClaveSegura2026!',
        }
        form = RepresentanteSignUpForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Representante.objects.count(), 0)


# ═══════════════════════════════════════════════════════════════
# FASE 4 — Decoradores básicos por rol
# ═══════════════════════════════════════════════════════════════

class Fase4_DecoradoresBasicosTestCase(TestCase):
    """Prueba el control de acceso en los decoradores de rol básicos."""

    def setUp(self):
        self.factory = RequestFactory()

    # --- tesoreria_required ---

    def test_tesoreria_required_con_user_en_grupo_tesoreria_permite_acceso(self):
        """Un user en el grupo Tesoreria debe pasar el decorador tesoreria_required."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('Tesoreria', username='11111111')
        vista_protegida = tesoreria_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    def test_tesoreria_required_con_user_en_grupo_distinto_retorna_403(self):
        """Un user en un grupo diferente debe recibir status 403."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('Entrenador', username='22222222')
        vista_protegida = tesoreria_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 403)

    def test_tesoreria_required_con_superuser_permite_acceso(self):
        """Un superusuario debe poder acceder sin pertenecer explícitamente al grupo Tesoreria."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario(username='99999999', is_superuser=True)
        vista_protegida = tesoreria_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    # --- coord_general_required ---

    def test_coord_general_required_con_user_en_grupo_coord_general_permite_acceso(self):
        """Un user en el grupo CoordinadorGeneral debe pasar el decorador coord_general_required."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('CoordinadorGeneral', username='11111112')
        vista_protegida = coord_general_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    def test_coord_general_required_con_user_en_grupo_distinto_retorna_403(self):
        """Un user en un grupo diferente debe recibir status 403."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('Tesoreria', username='22222223')
        vista_protegida = coord_general_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 403)

    def test_coord_general_required_con_superuser_permite_acceso(self):
        """Un superusuario debe poder acceder sin pertenecer al grupo CoordinadorGeneral."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario(username='99999998', is_superuser=True)
        vista_protegida = coord_general_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    # --- coord_deportivo_required ---

    def test_coord_deportivo_required_con_user_en_grupo_coord_deportivo_permite_acceso(self):
        """Un user en el grupo CoordinadorDeportivo debe pasar el decorador coord_deportivo_required."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('CoordinadorDeportivo', username='11111113')
        vista_protegida = coord_deportivo_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    def test_coord_deportivo_required_con_user_en_grupo_distinto_retorna_403(self):
        """Un user en un grupo diferente debe recibir status 403."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('Tesoreria', username='22222224')
        vista_protegida = coord_deportivo_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 403)

    def test_coord_deportivo_required_con_superuser_permite_acceso(self):
        """Un superusuario debe poder acceder sin pertenecer al grupo CoordinadorDeportivo."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario(username='99999997', is_superuser=True)
        vista_protegida = coord_deportivo_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    # --- entrenador_required ---

    def test_entrenador_required_con_user_en_grupo_entrenador_permite_acceso(self):
        """Un user en el grupo Entrenador debe pasar el decorador entrenador_required."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('Entrenador', username='11111114')
        vista_protegida = entrenador_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    def test_entrenador_required_con_user_en_grupo_distinto_retorna_403(self):
        """Un user en un grupo diferente debe recibir status 403."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('Tesoreria', username='22222225')
        vista_protegida = entrenador_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 403)

    def test_entrenador_required_con_superuser_permite_acceso(self):
        """Un superusuario debe poder acceder sin pertenecer al grupo Entrenador."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario(username='99999996', is_superuser=True)
        vista_protegida = entrenador_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)


# ═══════════════════════════════════════════════════════════════
# FASE 5 — Decoradores compuestos
# ═══════════════════════════════════════════════════════════════

class Fase5_DecoradoresCompuestosTestCase(TestCase):
    """Prueba el control de acceso en los decoradores compuestos de rol y permisos."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_staff_required_con_user_en_cualquier_grupo_interno_permite_acceso(self):
        """Un usuario en el grupo Tesoreria debe poder acceder a la vista protegida con staff_required."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('Tesoreria', username='11111115')
        vista_protegida = staff_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    def test_representante_required_con_user_con_perfil_representante_permite_acceso(self):
        """Un usuario con un perfil de representante debe poder acceder a la vista con representante_required."""
        request = self.factory.get('/dummy-url/')
        user, _ = crear_representante_con_user(cedula='12345678')
        request.user = user
        vista_protegida = representante_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    def test_representante_required_con_user_sin_perfil_retorna_403(self):
        """Un usuario sin perfil de representante asociado debe recibir status 403 al acceder a representante_required."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario(username='99999999')
        vista_protegida = representante_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 403)

    def test_lectura_atletas_required_con_representante_permite_acceso(self):
        """Un usuario representante (no staff) debe poder leer atletas."""
        request = self.factory.get('/dummy-url/')
        user, _ = crear_representante_con_user(cedula='12345678')
        request.user = user
        vista_protegida = lectura_atletas_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 200)

    def test_edicion_atletas_required_con_user_en_tesoreria_retorna_403(self):
        """Un usuario en el grupo Tesoreria no debe poder editar atletas y debe recibir 403."""
        request = self.factory.get('/dummy-url/')
        request.user = crear_usuario_en_grupo('Tesoreria', username='22222226')
        vista_protegida = edicion_atletas_required(vista_dummy)
        response = vista_protegida(request)
        self.assertEqual(response.status_code, 403)


# ═══════════════════════════════════════════════════════════════
# FASE 6 — Context Processor y Template Tags
# ═══════════════════════════════════════════════════════════════

class Fase6_ContextProcessorYTemplateTagsTestCase(TestCase):
    """Prueba los flags retornados por el context processor y la lógica de los tags."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_context_processor_anonimo_retorna_todos_flags_false(self):
        """Un usuario anónimo debe recibir todos los flags de rol en False."""
        request = self.factory.get('/')
        request.user = AnonymousUser()
        flags = roles(request)
        self.assertFalse(flags['is_tesoreria'])
        self.assertFalse(flags['is_coord_general'])
        self.assertFalse(flags['is_coord_deportivo'])
        self.assertFalse(flags['is_entrenador'])
        self.assertFalse(flags['is_representante'])
        self.assertFalse(flags['is_admin_total'])

    def test_context_processor_superuser_retorna_admin_total_true(self):
        """Un superusuario debe recibir is_admin_total en True y flags de staff interno en True."""
        request = self.factory.get('/')
        request.user = crear_usuario(username='99999999', is_superuser=True)
        flags = roles(request)
        self.assertTrue(flags['is_admin_total'])
        self.assertTrue(flags['is_tesoreria'])
        self.assertTrue(flags['is_coord_general'])
        self.assertTrue(flags['is_coord_deportivo'])
        self.assertTrue(flags['is_entrenador'])

    def test_template_tag_tiene_grupo_con_superuser_retorna_true_siempre(self):
        """El template tag tiene_grupo debe retornar True para un superusuario en cualquier grupo."""
        user = crear_usuario(username='99999999', is_superuser=True)
        self.assertTrue(tiene_grupo(user, 'CualquierGrupo'))

    def test_template_tag_es_representante_con_user_con_perfil_retorna_true(self):
        """El template tag es_representante debe retornar True para usuarios con perfil asociado."""
        user, _ = crear_representante_con_user(cedula='12345678')
        self.assertTrue(es_representante(user))


# ═══════════════════════════════════════════════════════════════
# FASE 7 — Migración de grupos
# ═══════════════════════════════════════════════════════════════

class Fase7_MigracionGruposTestCase(TestCase):
    """Valida la existencia de los grupos de usuario del sistema."""

    def test_los_4_grupos_existen_despues_de_migrate(self):
        """Los 4 grupos internos requeridos por el sistema deben existir en la base de datos de pruebas."""
        grupos_esperados = ['Tesoreria', 'CoordinadorGeneral', 'CoordinadorDeportivo', 'Entrenador']
        cantidad_existente = Group.objects.filter(name__in=grupos_esperados).count()
        self.assertEqual(cantidad_existente, 4)

    def test_grupos_no_se_duplican_al_correr_funcion_dos_veces(self):
        """La creación de grupos no debe duplicar registros si se intenta registrar el mismo nombre de nuevo."""
        Group.objects.get_or_create(name='GrupoDePrueba')
        Group.objects.get_or_create(name='GrupoDePrueba')
        self.assertEqual(Group.objects.filter(name='GrupoDePrueba').count(), 1)
