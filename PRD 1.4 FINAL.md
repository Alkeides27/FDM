# PRD v1.4 — FINAL — Roles, Permisos, Onboarding y Seguridad

**Proyecto:** IngeniumCode-FDM
**Rama:** `Pagos-Login`
**Versión:** 1.4 (final, post-revisión)
**Fecha:** 2026-05-01
**Plazo estimado:** 5-6 horas

---

## 0. Instrucciones para la IA ejecutora

Este es el último PRD de programación antes de la entrega académica del 2 de mayo. Después de esto solo se documenta, no se codea.

**REGLAS DE ORO:**
1. Lee el documento completo antes de tocar nada.
2. Ejecuta las fases en orden estricto. NO saltes pasos.
3. Después de cada fase, ejecuta `python manage.py check` y `python manage.py runserver`. Si rompe, **detente y reporta**, no sigas adelante.
4. Haz commit después de cada fase con el mensaje sugerido.
5. Si encuentras un archivo que el PRD asume existente y NO existe → reporta antes de inventar.
6. Si encuentras código que el PRD pide modificar y la firma es distinta → reporta antes de adivinar.
7. Todo el código en español. Nombres, comentarios, mensajes UI.

Trabaja sobre la rama `Pagos-Login`.

---

## 1. Estado de partida esperado

Antes de empezar, verifica que estos archivos existen en la rama:

- `accounts/forms.py` con `RepresentanteSignUpForm` y `StaffOnlyAuthenticationForm`.
- `accounts/views.py` con `RepresentanteSignUpView`.
- `accounts/middleware.py` con `RatelimitLoggingMiddleware`.
- `accounts/signals.py` con eventos de auth.
- `finanzas/models.py` con `Pago`, `Mensualidad`, `PagoAuditLog`, `TasaBCV`, `TOLERANCIA_COBERTURA_USD`.
- `finanzas/views.py` con `reportar_pago`, `mis_pagos`, `bandeja_admin`, `detalle_admin`, `aprobar`, `rechazar`, `telegram_webhook`, función `es_admin`.
- `finanzas/urls.py` con `app_name = 'finanzas'`.
- `filiacion/models.py` con `Representante` que tiene `usuario` (OneToOne con auth.User).
- `project_gestion/settings.py` con `LOGIN_URL = 'login'`, cache locmem/redis toggle, INSTALLED_APPS incluye `accounts.apps.AccountsConfig`.
- `project_gestion/urls.py` con `RateLimitedLoginView` y rutas de finanzas.
- `core/views.py` con `dashboard` view (puede ser placeholder).
- `core/urls.py` con `path('', views.dashboard, name='dashboard')`.

Si **alguno falta**, detente y reporta.

---

## 2. Alcance

### 2.1 Dentro

- Migración de grupos: `Tesoreria`, `CoordinadorGeneral`, `CoordinadorDeportivo`, `Entrenador`.
- `RepresentanteSignUpForm` ampliado: cédula, nombres, apellidos, email, teléfono, dirección, password.
- Validación estricta de cédula (`V12345678`) y teléfono venezolano.
- Crear `Representante` automáticamente al hacer signup.
- Decoradores: `@tesoreria_required`, `@coord_general_required`, `@representante_required`, etc.
- Context processor para roles.
- Template tag `tiene_grupo`.
- Aplicar permisos a finanzas (reemplazar `is_staff` por grupo).
- Página 403 personalizada.
- `templates/base.html` con navbar condicional.
- Dashboard con tarjetas por rol.
- Vista `descargar_comprobante` con verificación de permisos y audit log.
- Reemplazar `pago.comprobante.url` en plantillas por la vista nueva.
- `select_related('actor')` en queries de audit log.

### 2.2 Fuera (no implementar)

- Storage S3.
- Recuperación de password.
- Email verification.
- 2FA.
- UI para crear/editar mensualidades (queda para v1.5).
- Auto-generación lazy (queda para v1.5).
- Estado de cuenta del atleta (queda para v1.5).

---

## 3. FASE 0 — Verificación de estado y preparación

**Tiempo: 10 min.**

### 3.1 Verificar archivos críticos

```bash
ls accounts/forms.py accounts/views.py accounts/middleware.py
ls finanzas/models.py finanzas/views.py finanzas/urls.py
ls filiacion/models.py
ls project_gestion/settings.py project_gestion/urls.py
ls core/views.py core/urls.py
```

Si todos existen, continúa. Si falta alguno, **detente y reporta**.

### 3.2 Verificar que el sistema arranca

```bash
python manage.py check
python manage.py runserver
```

Apaga el servidor con Ctrl+C cuando confirmes que arranca. Si no arranca, **detente y reporta el error**.

### 3.3 Verificar si existe `templates/base.html`

```bash
ls templates/base.html
```

- Si existe → tomar nota, en Fase 5 lo vamos a reemplazar (haz backup mental).
- Si no existe → tomar nota, en Fase 5 lo vamos a crear desde cero.

### 3.4 Verificar usuarios existentes (informativo)

```bash
python manage.py shell -c "from django.contrib.auth.models import User; print('Total:', User.objects.count()); print('Staff:', User.objects.filter(is_staff=True).count())"
```

Tomar nota mental. No modificar nada.

### 3.5 Sin commit en esta fase

No hay cambios. Solo verificación.

---

## 4. FASE 1 — Migración de grupos

**Tiempo: 20 min.**

### 4.1 Crear migración

```bash
python manage.py makemigrations accounts --empty --name crear_grupos
```

Esto crea `accounts/migrations/0002_crear_grupos.py`.

### 4.2 Editar el archivo

Reemplazar el contenido por:

```python
from django.db import migrations

GRUPOS = [
    'Tesoreria',
    'CoordinadorGeneral',
    'CoordinadorDeportivo',
    'Entrenador',
]


def crear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in GRUPOS:
        Group.objects.get_or_create(name=nombre)


def eliminar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=GRUPOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, eliminar_grupos),
    ]
```

### 4.3 Aplicar

```bash
python manage.py migrate
```

### 4.4 Verificar

```bash
python manage.py shell -c "from django.contrib.auth.models import Group; print(list(Group.objects.values_list('name', flat=True)))"
```

Debe mostrar: `['Tesoreria', 'CoordinadorGeneral', 'CoordinadorDeportivo', 'Entrenador']` (o un superconjunto).

### 4.5 Verificar arranque

```bash
python manage.py check
```

### 4.6 Commit

```bash
git add accounts/migrations/0002_crear_grupos.py
git commit -m "feat(accounts): migración de grupos de roles del sistema"
```

---

## 5. FASE 2 — SignUpForm completo con creación de Representante

**Tiempo: 1 hora.**

## 5.1 Reemplazar `accounts/forms.py` completo

```python
import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from filiacion.models import Representante


# === Validadores ===
CEDULA_REGEX = re.compile(r'^\d{8}$')
TELEFONO_REGEX = re.compile(r'^0(412|414|416|424|426)\d{7}$')


def validar_cedula_venezolana(value):
    """8 dígitos numéricos exactos."""
    if not CEDULA_REGEX.match(value):
        raise ValidationError(
            'La cédula debe tener exactamente 8 dígitos. Ej: 12345678'
        )


def validar_telefono_venezolano(value):
    """11 dígitos exactos comenzando con operadora venezolana."""
    if not value.isdigit():
        raise ValidationError('El teléfono debe contener solo números.')
    if len(value) != 11:
        raise ValidationError('El teléfono debe tener exactamente 11 dígitos.')
    if not TELEFONO_REGEX.match(value):
        raise ValidationError(
            'Operadora inválida. Debe iniciar con 0412, 0414, 0416, 0424 o 0426.'
        )


# === Formularios ===
class StaffOnlyAuthenticationForm(AuthenticationForm):
    """Login restringido a usuarios con is_staff=True."""

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Credenciales incorrectas. Verifica tu usuario y contraseña.',
        'inactive': 'Esta cuenta está desactivada.',
        'no_staff': 'Esta cuenta no tiene acceso a la plataforma interna.',
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError(
                self.error_messages['no_staff'],
                code='no_staff',
            )


class RepresentanteSignUpForm(UserCreationForm):
    """Registro público de representantes. Crea User + Representante."""

    cedula_identidad = forms.CharField(
        max_length=8, min_length=8, required=True,
        label='Cédula de Identidad',
        help_text='8 dígitos numéricos. Ej: 12345678',
        validators=[validar_cedula_venezolana],
        widget=forms.TextInput(attrs={
            'placeholder': '12345678',
            'autocomplete': 'username',
            'maxlength': '8',
            'minlength': '8',
            'pattern': '\\d{8}',
            'inputmode': 'numeric',
            'title': 'Exactamente 8 dígitos numéricos',
            'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 8)",
        }),
    )
    nombres = forms.CharField(
        max_length=60, required=True, label='Nombres',
        widget=forms.TextInput(attrs={
            'autocomplete': 'given-name',
            'maxlength': '60',
            'oninput': "this.value = this.value.slice(0, 60)",
        }),
    )
    apellidos = forms.CharField(
        max_length=60, required=True, label='Apellidos',
        widget=forms.TextInput(attrs={
            'autocomplete': 'family-name',
            'maxlength': '60',
            'oninput': "this.value = this.value.slice(0, 60)",
        }),
    )
    correo_electronico = forms.EmailField(
        max_length=120, required=True, label='Correo Electrónico',
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email',
            'maxlength': '120',
            'oninput': "this.value = this.value.slice(0, 120)",
        }),
    )
    telefono_principal = forms.CharField(
        max_length=11, min_length=11, required=True,
        label='Teléfono Principal',
        help_text='11 dígitos. Ej: 04141234567',
        validators=[validar_telefono_venezolano],
        widget=forms.TextInput(attrs={
            'placeholder': '04141234567',
            'autocomplete': 'tel',
            'maxlength': '11',
            'minlength': '11',
            'pattern': '\\d{11}',
            'inputmode': 'numeric',
            'title': 'Exactamente 11 dígitos. Ej: 04141234567',
            'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 11)",
        }),
    )
    direccion_habitacion = forms.CharField(
        max_length=500, required=True, label='Dirección de Habitación',
        widget=forms.Textarea(attrs={
            'rows': 3,
            'maxlength': '500',
            'oninput': "this.value = this.value.slice(0, 500)",
        }),
    )

    class Meta:
        model = User
        fields = (
            'cedula_identidad', 'nombres', 'apellidos',
            'correo_electronico', 'telefono_principal', 'direccion_habitacion',
            'password1', 'password2',
        )

    def clean_cedula_identidad(self):
        cedula = self.cleaned_data['cedula_identidad']
        if User.objects.filter(username=cedula).exists():
            raise ValidationError('Ya existe una cuenta con esta cédula.')
        if Representante.objects.filter(cedula_identidad=cedula).exists():
            raise ValidationError('Ya existe un representante con esta cédula.')
        return cedula

    def clean_correo_electronico(self):
        email = self.cleaned_data['correo_electronico'].lower()
        if Representante.objects.filter(correo_electronico=email).exists():
            raise ValidationError('Ya existe un representante con este correo.')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Ya existe una cuenta con este correo.')
        return email

    @transaction.atomic
    def save(self, commit=True):
        cedula = self.cleaned_data['cedula_identidad']
        email = self.cleaned_data['correo_electronico']
        telefono = self.cleaned_data['telefono_principal']

        user = super().save(commit=False)
        user.username = cedula
        user.email = email
        user.first_name = self.cleaned_data['nombres']
        user.last_name = self.cleaned_data['apellidos']
        user.is_staff = False
        user.is_superuser = False

        if commit:
            user.save()
            Representante.objects.create(
                cedula_identidad=cedula,
                nombres=self.cleaned_data['nombres'],
                apellidos=self.cleaned_data['apellidos'],
                telefono_principal=telefono,
                direccion_habitacion=self.cleaned_data['direccion_habitacion'],
                correo_electronico=email,
                usuario=user,
            )

        return user
```

## 5.2 `accounts/views.py` queda igual

```python
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import RepresentanteSignUpForm


class RepresentanteSignUpView(CreateView):
    form_class = RepresentanteSignUpForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'
```

## 5.3 Verificar arranque

```bash
python manage.py check
```

## 5.4 Commit

```bash
git add accounts/forms.py
git commit -m "feat(accounts): SignUpForm crea Representante con validación VE (8 dígitos)"
```

## 6. FASE 3 — Decoradores helper

**Tiempo: 30 min.**

### 6.1 Crear `accounts/decorators.py`

```python
"""
Decoradores helper para control de acceso por rol.
Cada decorador valida que el usuario pertenezca al grupo requerido.
"""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def _en_grupo(user, nombre_grupo):
    return user.is_authenticated and user.groups.filter(name=nombre_grupo).exists()


def _es_representante(user):
    return (
        user.is_authenticated and
        hasattr(user, 'representante') and
        user.representante is not None
    )


def _forbidden(request):
    return render(request, '403.html', status=403)


def grupo_requerido(nombre_grupo):
    """Decorador genérico para exigir un grupo específico."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser or _en_grupo(request.user, nombre_grupo):
                return view_func(request, *args, **kwargs)
            return _forbidden(request)
        return _wrapped
    return decorator


def cualquier_grupo_requerido(*nombres_grupo):
    """Decorador para exigir al menos uno de varios grupos."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            for nombre in nombres_grupo:
                if _en_grupo(request.user, nombre):
                    return view_func(request, *args, **kwargs)
            return _forbidden(request)
        return _wrapped
    return decorator


# Decoradores específicos por rol
tesoreria_required = grupo_requerido('Tesoreria')
coord_general_required = grupo_requerido('CoordinadorGeneral')
coord_deportivo_required = grupo_requerido('CoordinadorDeportivo')
entrenador_required = grupo_requerido('Entrenador')


def representante_required(view_func):
    """Solo representantes (con perfil Representante asociado)."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if _es_representante(request.user):
            return view_func(request, *args, **kwargs)
        return _forbidden(request)
    return _wrapped


def cualquier_staff_required(view_func):
    """Cualquier rol interno (no representantes)."""
    return cualquier_grupo_requerido(
        'Tesoreria', 'CoordinadorGeneral', 'CoordinadorDeportivo', 'Entrenador'
    )(view_func)
```

### 6.2 Crear `templates/403.html`

```html
{% extends 'base.html' %}
{% block title %}Acceso denegado{% endblock %}

{% block content %}
<div class="max-w-md mx-auto p-6 text-center mt-20">
  <h1 class="text-3xl font-bold text-red-700 mb-4">🚫 Acceso denegado</h1>
  <p class="text-gray-700 mb-4">
    No tienes permisos para acceder a esta sección.
  </p>
  <p class="text-sm text-gray-500 mb-6">
    Si crees que esto es un error, contacta a la administración.
  </p>
  <a href="{% url 'dashboard' %}" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
    Volver al inicio
  </a>
</div>
{% endblock %}
```

> **Nota:** este template extiende `base.html` que crearemos en la Fase 5. Hasta entonces dará error si se renderiza, pero ningún decorador se invocará todavía porque las vistas aún no usan los decoradores nuevos.

### 6.3 Verificar arranque

```bash
python manage.py check
```

### 6.4 Commit

```bash
git add accounts/decorators.py templates/403.html
git commit -m "feat(accounts): decoradores de roles + página 403"
```

---

## 7. FASE 4 — Context processor y template tags

**Tiempo: 30 min.**

### 7.1 Crear `accounts/context_processors.py`

```python
"""
Context processor que expone flags de rol a todas las plantillas.
"""


def roles(request):
    user = request.user

    if not user.is_authenticated:
        return {
            'is_tesoreria': False,
            'is_coord_general': False,
            'is_coord_deportivo': False,
            'is_entrenador': False,
            'is_representante': False,
            'is_admin_total': False,
        }

    grupos_usuario = set(user.groups.values_list('name', flat=True))
    es_representante = (
        hasattr(user, 'representante') and user.representante is not None
    )

    return {
        'is_tesoreria': 'Tesoreria' in grupos_usuario or user.is_superuser,
        'is_coord_general': 'CoordinadorGeneral' in grupos_usuario or user.is_superuser,
        'is_coord_deportivo': 'CoordinadorDeportivo' in grupos_usuario or user.is_superuser,
        'is_entrenador': 'Entrenador' in grupos_usuario or user.is_superuser,
        'is_representante': es_representante,
        'is_admin_total': user.is_superuser,
    }
```

### 7.2 Crear template tags

`accounts/templatetags/__init__.py` (vacío).

`accounts/templatetags/accounts_tags.py`:

```python
from django import template

register = template.Library()


@register.filter
def tiene_grupo(user, nombre_grupo):
    """Uso: {% if user|tiene_grupo:'Tesoreria' %}"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=nombre_grupo).exists()


@register.filter
def es_representante(user):
    """Uso: {% if user|es_representante %}"""
    return (
        user.is_authenticated and
        hasattr(user, 'representante') and
        user.representante is not None
    )
```

### 7.3 Registrar context processor en `settings.py`

Buscar el bloque `TEMPLATES` y agregar la línea nueva al final de `context_processors`:

```python
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.roles',  # ← AGREGAR
            ],
        },
    },
]
```

### 7.4 Verificar arranque

```bash
python manage.py check
```

### 7.5 Commit

```bash
git add accounts/context_processors.py accounts/templatetags/ project_gestion/settings.py
git commit -m "feat(accounts): context processor y template tags para roles"
```

---

## 8. FASE 5 — base.html y dashboard condicional

**Tiempo: 1.5 horas.**

> **Esta fase es crítica.** El resto del PRD asume que `base.html` existe y funciona. Si después de esta fase el sistema no levanta, NO continuar.

### 8.1 Crear/reemplazar `templates/base.html`

```html
{% load static %}
{% load accounts_tags %}
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}IngeniumCode FDM{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen flex flex-col">

  {% if user.is_authenticated %}
  <nav class="bg-blue-700 text-white shadow">
    <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between">
      <a href="{% url 'dashboard' %}" class="text-lg font-bold hover:text-blue-200">
        🜁 IngeniumCode FDM
      </a>

      <div class="flex flex-wrap gap-4 items-center text-sm">

        {% if is_representante %}
          <a href="{% url 'finanzas:mis_pagos' %}" class="hover:text-blue-200">Mis Pagos</a>
          <a href="{% url 'finanzas:reportar' %}" class="hover:text-blue-200">Reportar Pago</a>
        {% endif %}

        {% if is_tesoreria %}
          <a href="{% url 'finanzas:bandeja' %}" class="hover:text-blue-200">Bandeja Pagos</a>
        {% endif %}

        {% if is_coord_general and not is_tesoreria %}
          <a href="{% url 'finanzas:bandeja' %}" class="hover:text-blue-200">Pagos (lectura)</a>
        {% endif %}

        {% if is_admin_total %}
          <a href="{% url 'admin:index' %}" class="hover:text-blue-200">Admin</a>
        {% endif %}

        <span class="text-blue-200">|</span>
        <span class="text-blue-200">
          {{ user.first_name|default:user.username }}
        </span>
        <form method="post" action="{% url 'logout' %}" class="inline">
          {% csrf_token %}
          <button type="submit" class="hover:text-blue-200">Cerrar sesión</button>
        </form>

      </div>
    </div>
  </nav>
  {% endif %}

  <main class="flex-grow">
    {% if messages %}
      <div class="max-w-7xl mx-auto px-4 pt-4">
        {% for message in messages %}
          <div class="p-3 mb-2 rounded {% if message.tags == 'error' %}bg-red-100 text-red-800{% elif message.tags == 'warning' %}bg-yellow-100 text-yellow-800{% else %}bg-green-100 text-green-800{% endif %}">
            {{ message }}
          </div>
        {% endfor %}
      </div>
    {% endif %}

    {% block content %}{% endblock %}
  </main>

  <footer class="bg-gray-100 text-gray-600 text-xs py-3 text-center">
    Escuela de Fútbol Comunitaria Infantil "Francisco de Miranda"
  </footer>

</body>
</html>
```

### 8.2 Crear `core/templates/core/dashboard.html`

```html
{% extends 'base.html' %}
{% load accounts_tags %}

{% block title %}Inicio — IngeniumCode FDM{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto p-6">
  <h1 class="text-3xl font-bold mb-2">
    Bienvenido, {{ user.first_name|default:user.username }}
  </h1>
  <p class="text-gray-600 mb-8">
    {% if is_representante %}Panel de representante
    {% elif is_tesoreria %}Panel de tesorería
    {% elif is_coord_general %}Coordinador general
    {% elif is_coord_deportivo %}Coordinador deportivo
    {% elif is_entrenador %}Entrenador
    {% elif is_admin_total %}Administrador del sistema
    {% else %}Usuario{% endif %}
  </p>

  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

    {% if is_representante %}
      <a href="{% url 'finanzas:mis_pagos' %}" class="border rounded p-6 hover:shadow-lg bg-white">
        <h3 class="font-bold text-lg mb-2">💳 Mis Pagos</h3>
        <p class="text-sm text-gray-600">Historial de pagos reportados y su estado.</p>
      </a>
      <a href="{% url 'finanzas:reportar' %}" class="border rounded p-6 hover:shadow-lg bg-white">
        <h3 class="font-bold text-lg mb-2">📤 Reportar Pago</h3>
        <p class="text-sm text-gray-600">Registra un nuevo pago de mensualidad.</p>
      </a>
    {% endif %}

    {% if is_tesoreria %}
      <a href="{% url 'finanzas:bandeja' %}" class="border rounded p-6 hover:shadow-lg bg-white">
        <h3 class="font-bold text-lg mb-2">📋 Bandeja de Pagos</h3>
        <p class="text-sm text-gray-600">Aprobar o rechazar pagos pendientes.</p>
      </a>
    {% endif %}

    {% if is_coord_general and not is_tesoreria %}
      <a href="{% url 'finanzas:bandeja' %}" class="border rounded p-6 hover:shadow-lg bg-white">
        <h3 class="font-bold text-lg mb-2">👁️ Pagos (lectura)</h3>
        <p class="text-sm text-gray-600">Visualización de pagos para auditoría.</p>
      </a>
    {% endif %}

  </div>
</div>
{% endblock %}
```

### 8.3 Crear/actualizar `templates/registration/signup.html`

```html
{% extends 'base.html' %}
{% block title %}Registro de Representante{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto p-6">
  <h1 class="text-2xl font-bold mb-6">Registro de Representante</h1>

  <div class="p-3 mb-4 rounded bg-blue-50 text-blue-900 text-sm">
    Solo representantes legales de atletas pueden registrarse aquí.
    El personal de la escuela debe iniciar sesión directamente.
  </div>

  <form method="post" class="space-y-4">
    {% csrf_token %}

    {% for field in form %}
      <div>
        <label class="block text-sm font-medium mb-1">
          {{ field.label }}
          {% if field.field.required %}<span class="text-red-600">*</span>{% endif %}
        </label>
        {{ field }}
        {% if field.help_text %}
          <p class="text-xs text-gray-500 mt-1">{{ field.help_text }}</p>
        {% endif %}
        {% if field.errors %}
          <p class="text-xs text-red-600 mt-1">{{ field.errors|join:", " }}</p>
        {% endif %}
      </div>
    {% endfor %}

    <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
      Crear cuenta
    </button>
    <a href="{% url 'login' %}" class="ml-2 text-blue-600 hover:underline">
      ¿Ya tienes cuenta? Inicia sesión
    </a>
  </form>
</div>
{% endblock %}
```

### 8.4 Verificar arranque

```bash
python manage.py check
python manage.py runserver
```

Visitar `http://127.0.0.1:8000/` → debe redirigir a `/login/`.
Visitar `http://127.0.0.1:8000/registro/` → debe mostrar formulario completo.

Apagar servidor.

### 8.5 Probar signup completo

Levantar servidor de nuevo. Crear un representante de prueba:

- Cédula: `V99999999`
- Nombres: `Test`
- Apellidos: `Usuario`
- Email: `test@example.com`
- Teléfono: `0412-1234567`
- Dirección: `Cualquier dirección`
- Password: `complejo123abc`

Submit. Debe redirigir a `/login/`.

Verificar en Django admin:
- Existe `User` con username `V99999999`, is_staff=False.
- Existe `Representante` con `usuario` apuntando a ese User.
- Teléfono normalizado a `+584121234567`.

### 8.6 Commit

```bash
git add templates/base.html core/templates/core/dashboard.html templates/registration/signup.html
git commit -m "feat(core): base.html con navbar condicional + dashboard + signup template"
```

---

## 9. FASE 6 — Aplicar permisos a vistas de finanzas

**Tiempo: 30 min.**

### 9.1 Modificar `finanzas/views.py`

Buscar en el archivo la función `es_admin`:

```python
def es_admin(u):
    return u.is_authenticated and (
        u.is_staff or u.groups.filter(name='Tesoreria').exists()
    )
```

**Eliminar esa función completa.**

Buscar los imports al tope y agregar después de los imports existentes:

```python
from accounts.decorators import (
    tesoreria_required, representante_required, cualquier_grupo_requerido
)
```

Quitar el import de `user_passes_test`:

```python
from django.contrib.auth.decorators import login_required, user_passes_test
```

Cambiarlo por:

```python
from django.contrib.auth.decorators import login_required
```

### 9.2 Reemplazar decoradores en cada vista

**Vista `reportar_pago`** — buscar:

```python
@login_required
@ratelimit(key='user', rate='5/h', method='POST', block=True)
def reportar_pago(request):
```

Reemplazar por:

```python
@representante_required
@ratelimit(key='user', rate='5/h', method='POST', block=True)
def reportar_pago(request):
```

**Vista `mis_pagos`** — buscar:

```python
@login_required
def mis_pagos(request):
```

Reemplazar por:

```python
@representante_required
def mis_pagos(request):
```

**Vista `bandeja_admin`** — buscar:

```python
@user_passes_test(es_admin)
def bandeja_admin(request):
```

Reemplazar por:

```python
@cualquier_grupo_requerido('Tesoreria', 'CoordinadorGeneral')
def bandeja_admin(request):
```

**Vista `detalle_admin`** — buscar:

```python
@user_passes_test(es_admin)
def detalle_admin(request, pk):
```

Reemplazar por:

```python
@cualquier_grupo_requerido('Tesoreria', 'CoordinadorGeneral')
def detalle_admin(request, pk):
```

Y en el cuerpo de `detalle_admin`, buscar:

```python
audit = pago.audit_log.all()[:20]
```

Reemplazar por:

```python
audit = pago.audit_log.select_related('actor').all()[:20]
```

**Vista `aprobar`** — buscar:

```python
@user_passes_test(es_admin)
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def aprobar(request, pk):
```

Reemplazar por:

```python
@tesoreria_required
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def aprobar(request, pk):
```

**Vista `rechazar`** — buscar:

```python
@user_passes_test(es_admin)
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def rechazar(request, pk):
```

Reemplazar por:

```python
@tesoreria_required
@ratelimit(key='user', rate='30/m', method='POST', block=True)
def rechazar(request, pk):
```

**`telegram_webhook`**: NO TOCAR.

### 9.3 Verificar arranque

```bash
python manage.py check
python manage.py runserver
```

### 9.4 Probar permisos

1. Crear desde Django admin un usuario en grupo `Tesoreria` (con `is_staff=True`).
2. Login como ese usuario → debe acceder a `/finanzas/admin/bandeja/`.
3. Logout. Login como el representante de prueba → intentar `/finanzas/admin/bandeja/` → debe dar **página 403**.
4. Como representante visitar `/finanzas/mis-pagos/` → debe funcionar.

### 9.5 Commit

```bash
git add finanzas/views.py
git commit -m "refactor(finanzas): decoradores de rol + select_related en audit log"
```

---

## 10. FASE 7 — Vista protegida de comprobantes

**Tiempo: 1 hora.**

### 10.1 Agregar choice nuevo en `finanzas/models.py`

Buscar `ACCION_AUDIT_CHOICES`:

```python
ACCION_AUDIT_CHOICES = [
    ('CREADO',          'Creado'),
    ('APROBADO',        'Aprobado'),
    ('RECHAZADO',       'Rechazado'),
    ('EDITADO',         'Editado'),
    ('ANULADO',         'Anulado'),
    ('MENSUALIDADES_VINCULADAS', 'Mensualidades vinculadas'),
]
```

Reemplazar por:

```python
ACCION_AUDIT_CHOICES = [
    ('CREADO',          'Creado'),
    ('APROBADO',        'Aprobado'),
    ('RECHAZADO',       'Rechazado'),
    ('EDITADO',         'Editado'),
    ('ANULADO',         'Anulado'),
    ('MENSUALIDADES_VINCULADAS', 'Mensualidades vinculadas'),
    ('COMPROBANTE_DESCARGADO', 'Comprobante descargado'),
]
```

### 10.2 Crear migración

```bash
python manage.py makemigrations finanzas
python manage.py migrate
```

### 10.3 Agregar vista en `finanzas/views.py`

Al final del archivo, agregar:

```python
import os
import mimetypes
from django.http import FileResponse, Http404


@login_required
def descargar_comprobante(request, pago_id):
    """
    Sirve el comprobante de un pago con verificación de permisos.
    """
    pago = get_object_or_404(Pago, pk=pago_id)
    user = request.user

    es_admin_total = user.is_superuser
    es_tesoreria = user.groups.filter(name='Tesoreria').exists()
    es_coord_general = user.groups.filter(name='CoordinadorGeneral').exists()
    es_dueno = (
        hasattr(user, 'representante') and
        user.representante is not None and
        pago.representante_id == user.representante.id
    )

    permitido = es_admin_total or es_tesoreria or es_coord_general or es_dueno

    if not permitido:
        return render(request, '403.html', status=403)

    if not pago.comprobante or not os.path.exists(pago.comprobante.path):
        raise Http404('Comprobante no encontrado.')

    pago.registrar_audit(
        accion='COMPROBANTE_DESCARGADO',
        actor=user,
        detalles={
            'rol': (
                'admin' if es_admin_total else
                'tesoreria' if es_tesoreria else
                'coord_general' if es_coord_general else
                'representante_dueno'
            ),
            'ip': request.META.get('REMOTE_ADDR', 'unknown'),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        }
    )

    filename = os.path.basename(pago.comprobante.name)
    content_type, _ = mimetypes.guess_type(filename)
    response = FileResponse(
        pago.comprobante.open('rb'),
        content_type=content_type or 'application/octet-stream',
    )
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
```

### 10.4 Agregar URL en `finanzas/urls.py`

Agregar al final de `urlpatterns`:

```python
path('comprobante/<int:pago_id>/', views.descargar_comprobante, name='comprobante'),
```

### 10.5 Modificar `templates/finanzas/detalle.html`

Buscar el bloque del comprobante:

```html
{% with ext=pago.comprobante.url|lower %}
  {% if '.pdf' in ext %}
    <embed src="{{ pago.comprobante.url }}" type="application/pdf" class="w-full h-96" />
    <a href="{{ pago.comprobante.url }}" target="_blank" class="text-blue-600 hover:underline mt-2 inline-block">Abrir PDF</a>
  {% else %}
    <img src="{{ pago.comprobante.url }}" class="w-full border" alt="Comprobante" />
  {% endif %}
{% endwith %}
```

Reemplazar por:

```html
{% with comprobante_nombre=pago.comprobante.name|lower %}
  {% if '.pdf' in comprobante_nombre %}
    <embed src="{% url 'finanzas:comprobante' pago.id %}" type="application/pdf" class="w-full h-96" />
    <a href="{% url 'finanzas:comprobante' pago.id %}" target="_blank" class="text-blue-600 hover:underline mt-2 inline-block">
      Abrir PDF
    </a>
  {% else %}
    <img src="{% url 'finanzas:comprobante' pago.id %}" class="w-full border" alt="Comprobante" />
  {% endif %}
{% endwith %}
```

### 10.6 Verificar arranque

```bash
python manage.py check
python manage.py runserver
```

### 10.7 Probar

1. Como representante reportar pago con comprobante (imagen).
2. Logout. Crear otro representante distinto (signup).
3. Login con el segundo representante.
4. Intentar acceder a `/finanzas/comprobante/1/` → debe dar 403.
5. Login como superuser → ver `/finanzas/admin/bandeja/` → click en pago → ver comprobante.
6. Verificar en Django admin → Pago audit logs → debe haber entradas `COMPROBANTE_DESCARGADO`.

### 10.8 Commit

```bash
git add finanzas/models.py finanzas/views.py finanzas/urls.py finanzas/migrations/ templates/finanzas/detalle.html
git commit -m "feat(finanzas): vista protegida de comprobantes con audit log"
```

---

## 11. FASE 8 — QA final

**Tiempo: 30 min.**

### 11.1 Tests integrados

Levantar servidor con datos limpios (no es necesario reiniciar BD).

**Setup:**
1. Crear superuser si no existe.
2. Crear 1 representante vía signup (ej: `V11111111`).
3. Desde Django admin crear:
   - Usuario `tesoreria_user` con `is_staff=True`, agregar al grupo `Tesoreria`.
   - Usuario `coord_general_user` con `is_staff=True`, agregar al grupo `CoordinadorGeneral`.
   - Usuario `coord_deportivo_user` con `is_staff=True`, agregar al grupo `CoordinadorDeportivo`.

**Tests:**

- [ ] **Login restringido:** intentar login con el representante (cédula `V11111111`) → debe rechazar con "no tiene acceso a la plataforma interna" (porque is_staff=False).
- [ ] **Acceso por rol:** login como `tesoreria_user` → ver "Bandeja Pagos" en navbar.
- [ ] **Acceso bloqueado:** login como `coord_deportivo_user` → no ve nada de finanzas en navbar. Si va a `/finanzas/admin/bandeja/` → 403.
- [ ] **Lectura para coord general:** login como `coord_general_user` → ve "Pagos (lectura)". Acceso a bandeja OK.
- [ ] **Comprobante propio (representante):** representante reporta pago → puede ver su comprobante.
- [ ] **Comprobante ajeno (representante):** crear segundo representante, intentar acceder al comprobante del primero → 403.
- [ ] **Audit log:** verificar en Django admin que cada acceso a comprobante quedó registrado.
- [ ] **Página 403:** acceder a URL prohibida → ver template 403 estilizado.
- [ ] **Logout:** click en "Cerrar sesión" → redirige a login.
- [ ] **Signup completo:** crear un representante nuevo → verificar que se creó User + Representante en BD.

### 11.2 Verificar que NO se rompió nada del módulo de pagos previo

- [ ] Reportar pago con mensualidad seleccionada → funciona.
- [ ] Aprobar pago con tasa BCV pre-cargada de DolarAPI → funciona.
- [ ] Notificación Telegram sigue llegando con formato venezolano.
- [ ] Mensualidad se marca como pagada al aprobar.
- [ ] Validación de cobertura sigue bloqueando pagos insuficientes.

### 11.3 Commit final

```bash
git add -A
git commit -m "chore: QA de PRD v1.4 (roles + onboarding + comprobantes protegidos)"
```

### 11.4 Push a remoto

```bash
git push origin Pagos-Login
```

---

## 12. Trampas conocidas

1. **Si `STATICFILES_DIRS` apunta a una carpeta que no existe**, `runserver` no falla pero `python manage.py check --deploy` advierte. No crítico ahora.

2. **`Tailwind CDN` carga en cada request.** Es ok para desarrollo. En producción debe compilarse local.

3. **El usuario superuser pasa todos los decoradores** porque hay `if request.user.is_superuser: return view_func(...)` en cada uno. Si quieres que el superuser ESCAPE de un decorador específico, hay que quitarle esa línea, pero para esta entrega no aplica.

4. **Los grupos se cargan al login.** Si modificas grupos de un usuario logueado, debe hacer logout/login para que `request.user.groups` refleje el cambio.

5. **`representante_required` falla si el usuario es admin pero NO tiene `Representante` asociado.** Por diseño: la vista de "Mis Pagos" no tiene sentido para un admin sin perfil de representante. El admin va a `Bandeja Pagos`.

6. **Si la migración 0002 ya existe en la rama** (porque se intentó antes), `makemigrations --empty` creará 0003. Renombrar manualmente.

7. **El signup form rechaza si `Representante.cedula_identidad` ya existe en BD.** Si tu colega creó manualmente representantes en Django admin antes, esos representantes no tienen `usuario` asociado. El signup con esa cédula fallará. Solución: borrar esos representantes manualmente o asignarles usuarios.

---

## 13. Resumen del plan

| Fase | Tarea | Tiempo | Commit |
|---|---|---|---|
| **0** | Verificación de estado | 10 min | (sin commit) |
| **1** | Migración de grupos | 20 min | `feat(accounts): migración de grupos de roles del sistema` |
| **2** | SignUpForm + crear Representante | 1h | `feat(accounts): SignUpForm crea Representante con validación VE` |
| **3** | Decoradores + página 403 | 30 min | `feat(accounts): decoradores de roles + página 403` |
| **4** | Context processor + template tags | 30 min | `feat(accounts): context processor y template tags para roles` |
| **5** | base.html + dashboard + signup template | 1.5h | `feat(core): base.html con navbar condicional + dashboard + signup template` |
| **6** | Permisos a finanzas + N+1 | 30 min | `refactor(finanzas): decoradores de rol + select_related en audit log` |
| **7** | Vista protegida de comprobantes | 1h | `feat(finanzas): vista protegida de comprobantes con audit log` |
| **8** | QA final | 30 min | `chore: QA de PRD v1.4` |
| **TOTAL** | | **~5.5h** | |

---

## 14. Mensaje de PR sugerido

```
feat: sistema de roles, onboarding completo y comprobantes protegidos

## Cambios principales
- 4 grupos de roles (Tesoreria, CoordinadorGeneral, CoordinadorDeportivo, Entrenador)
- RepresentanteSignUpForm crea User + Representante atómicamente
- Validación venezolana de cédula y teléfono
- Decoradores helper por rol con página 403
- Context processor + template tags para roles
- Navbar condicional en base.html
- Dashboard con tarjetas por rol
- Vista protegida de comprobantes con audit log de accesos
- Optimización N+1 en audit log con select_related('actor')

## Listo para documentar
- Sistema completo de control de acceso
- Onboarding de representantes funcional end-to-end
- Comprobantes financieros blindados
```

---

# FASE 9 — Límites estrictos en TODO el proyecto

**Tiempo: 45 min.**

> **Esta fase se ejecuta DESPUÉS de la Fase 8 (QA final).**

## 9.1 Premisa

**Todos los inputs limitados deben tener tres mecanismos:**

```html
<input
  type="text"
  maxlength="8"
  pattern="\d{8}"
  oninput="this.value = this.value.slice(0, 8)"
>
```

- `maxlength`: bloquea desde el navegador en tipos compatibles.
- `pattern`: marca el input como inválido si no cumple.
- `oninput`: **truncado físico garantizado**, funciona incluso en `number`.

Para inputs tipo `number` que necesiten limitación de dígitos, el `oninput` es la única solución real.

## 9.2 Decisión: usar `text` + `inputmode='numeric'` en vez de `number` para campos limitados

**Razón:** los campos como cédula, teléfono, referencia bancaria son secuencias de dígitos de longitud fija, no "números" matemáticos. No se suman, no se promedian, no tienen decimales. Tratarlos como `text` con `inputmode='numeric'` da:

- `maxlength` funcional.
- Teclado numérico en móviles.
- No aparecen las flechitas de incremento que confunden.
- No se pierden ceros a la izquierda (problema clásico con `type=number`).

Para campos verdaderamente numéricos (monto Bs, tasa BCV, peso, altura, goles), seguimos usando `number` pero con `oninput` de truncado.

## 9.3 Ajustar Fase 2 — SignUpForm sin V/E

**Antes de aplicar la Fase 9, hay que corregir la Fase 2 del PRD v1.4 que pidió cédula con V/E.**

En `accounts/forms.py`, buscar:

```python
CEDULA_REGEX = re.compile(r'^[VE]\d{6,9}$')


def validar_cedula_venezolana(value):
    """V12345678 o E1234567. Mayúscula obligatoria."""
    if not CEDULA_REGEX.match(value):
        raise ValidationError(
            'Formato inválido. Usa V o E seguido de 6-9 dígitos. Ej: V12345678'
        )
```

Reemplazar por:

```python
CEDULA_REGEX = re.compile(r'^\d{8}$')


def validar_cedula_venezolana(value):
    """8 dígitos exactos, solo números."""
    if not CEDULA_REGEX.match(value):
        raise ValidationError(
            'La cédula debe tener exactamente 8 dígitos. Ej: 12345678'
        )
```

En el método `clean_cedula_identidad`, buscar:

```python
def clean_cedula_identidad(self):
    cedula = self.cleaned_data['cedula_identidad'].upper()
```

Reemplazar por:

```python
def clean_cedula_identidad(self):
    cedula = self.cleaned_data['cedula_identidad']
```

(Eliminar el `.upper()` porque ya no hay letras.)

## 9.4 Aplicar límites en `accounts/forms.py`

**Campo `cedula_identidad`** — modificar el widget:

```python
widget=forms.TextInput(attrs={
    'placeholder': '12345678',
    'autocomplete': 'username',
    'maxlength': '8',
    'minlength': '8',
    'pattern': '\\d{8}',
    'inputmode': 'numeric',
    'title': 'Exactamente 8 dígitos numéricos',
    'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 8)",
}),
```

**Campo `nombres`:**

```python
widget=forms.TextInput(attrs={
    'autocomplete': 'given-name',
    'maxlength': '60',
    'oninput': "this.value = this.value.slice(0, 60)",
}),
```

**Campo `apellidos`:**

```python
widget=forms.TextInput(attrs={
    'autocomplete': 'family-name',
    'maxlength': '60',
    'oninput': "this.value = this.value.slice(0, 60)",
}),
```

**Campo `correo_electronico`:**

```python
widget=forms.EmailInput(attrs={
    'autocomplete': 'email',
    'maxlength': '120',
    'oninput': "this.value = this.value.slice(0, 120)",
}),
```

**Campo `telefono_principal`** — este es el caso crítico. Reemplazar widget completo:

```python
widget=forms.TextInput(attrs={
    'placeholder': '04141234567',
    'autocomplete': 'tel',
    'maxlength': '11',
    'minlength': '11',
    'pattern': '\\d{11}',
    'inputmode': 'numeric',
    'title': 'Exactamente 11 dígitos. Ej: 04141234567',
    'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 11)",
}),
```

Y modificar el validador de teléfono. Buscar:

```python
TELEFONO_REGEX = re.compile(
    r'^(?:\+58|0)?\s?-?(412|414|416|424|426)\s?-?\d{7}$'
)


def validar_telefono_venezolano(value):
    limpio = re.sub(r'[\s\-]', '', value)
    if not TELEFONO_REGEX.match(limpio):
        raise ValidationError(
            'Formato inválido. Ej: 0412-1234567, 04141234567, +58 416 1234567'
        )


def normalizar_telefono(value):
    limpio = re.sub(r'[\s\-]', '', value)
    if limpio.startswith('+58'):
        return limpio
    if limpio.startswith('0'):
        return '+58' + limpio[1:]
    return '+58' + limpio
```

Reemplazar por:

```python
TELEFONO_REGEX = re.compile(r'^0(412|414|416|424|426)\d{7}$')


def validar_telefono_venezolano(value):
    """11 dígitos exactos comenzando con operadora venezolana."""
    if not value.isdigit():
        raise ValidationError('El teléfono debe contener solo números.')
    if len(value) != 11:
        raise ValidationError('El teléfono debe tener exactamente 11 dígitos.')
    if not TELEFONO_REGEX.match(value):
        raise ValidationError(
            'Operadora inválida. Debe iniciar con 0412, 0414, 0416, 0424 o 0426.'
        )


def normalizar_telefono(value):
    """Ya viene como 11 dígitos puros, no necesita normalización."""
    return value
```

> **Importante:** ahora el teléfono se guarda como `04141234567` (11 dígitos puros), consistente con `RepresentanteForm` y `EntrenadorForm` de tu colega.

**Campo `direccion_habitacion`:**

```python
widget=forms.Textarea(attrs={
    'rows': 3,
    'maxlength': '500',
    'oninput': "this.value = this.value.slice(0, 500)",
}),
```

## 9.5 Aplicar límites en `finanzas/forms.py`

**Campo `referencia` en `ReportarPagoForm`** — buscar en el bloque `widgets`:

```python
'referencia': forms.TextInput(attrs={'class': INPUT_CSS, 'placeholder': 'Nro. de referencia'}),
```

Reemplazar por:

```python
'referencia': forms.TextInput(attrs={
    'class': INPUT_CSS,
    'placeholder': 'Nro. de referencia',
    'maxlength': '12',
    'pattern': '\\d{1,12}',
    'inputmode': 'numeric',
    'title': 'Hasta 12 dígitos numéricos',
    'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 12)",
}),
```

**Campo `monto_bs`** — buscar:

```python
'monto_bs': forms.NumberInput(attrs={'class': INPUT_CSS, 'placeholder': '0.00', 'step': '0.01'}),
```

Reemplazar por:

```python
'monto_bs': forms.NumberInput(attrs={
    'class': INPUT_CSS,
    'placeholder': '0.00',
    'step': '0.01',
    'min': '0',
    'max': '99999999999.99',
    'inputmode': 'decimal',
    'oninput': "if (this.value.length > 14) this.value = this.value.slice(0, 14)",
}),
```

> **Nota:** `monto_bs` permite hasta 14 caracteres (incluyendo punto decimal). El campo BD es `max_digits=14, decimal_places=2`, así que puede llegar hasta `999999999999.99`. El límite físico de 14 caracteres en el input previene texto basura.

**Campo `tasa_bcv` en `AprobarPagoForm`** — buscar:

```python
widget=forms.NumberInput(attrs={
    'class': INPUT_CSS,
    'placeholder': 'Ej: 36.5000',
    'step': '0.0001',
})
```

Reemplazar por:

```python
widget=forms.NumberInput(attrs={
    'class': INPUT_CSS,
    'placeholder': 'Ej: 486.0000',
    'step': '0.0001',
    'min': '0',
    'max': '999999.9999',
    'inputmode': 'decimal',
    'oninput': "if (this.value.length > 12) this.value = this.value.slice(0, 12)",
})
```

**Campo `motivo` en `RechazarPagoForm`** — buscar:

```python
widget=forms.Textarea(attrs={'rows': 3, 'class': TEXTAREA_CSS, 'placeholder': 'Motivo del rechazo...'}),
```

Reemplazar por:

```python
widget=forms.Textarea(attrs={
    'rows': 3,
    'class': TEXTAREA_CSS,
    'placeholder': 'Motivo del rechazo...',
    'maxlength': '500',
    'oninput': "this.value = this.value.slice(0, 500)",
}),
```

## 9.6 Aplicar límites en `filiacion/forms.py`

**`RepresentanteForm` — campo `cedula_identidad`** — ya tiene `maxlength=8` y `minlength=8`. Solo agregar `oninput`:

Buscar:

```python
'cedula_identidad': forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'maxlength': '8', 'minlength': '8'}),
```

Reemplazar por:

```python
'cedula_identidad': forms.TextInput(attrs={
    'inputmode': 'numeric',
    'pattern': '\\d{8}',
    'maxlength': '8',
    'minlength': '8',
    'title': 'Exactamente 8 dígitos',
    'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 8)",
}),
```

**Campo `telefono_principal`** — buscar:

```python
'telefono_principal': forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'maxlength': '11', 'placeholder': '04141234567'}),
```

Reemplazar por:

```python
'telefono_principal': forms.TextInput(attrs={
    'inputmode': 'numeric',
    'pattern': '\\d{11}',
    'maxlength': '11',
    'minlength': '11',
    'placeholder': '04141234567',
    'title': 'Exactamente 11 dígitos',
    'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 11)",
}),
```

**Campo `direccion_habitacion`** — buscar:

```python
'direccion_habitacion': forms.Textarea(attrs={'rows': 3}),
```

Reemplazar por:

```python
'direccion_habitacion': forms.Textarea(attrs={
    'rows': 3,
    'maxlength': '500',
    'oninput': "this.value = this.value.slice(0, 500)",
}),
```

**`AtletaForm` — campo `cedula_escolar`** — buscar:

```python
'cedula_escolar': forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'maxlength': '8', 'minlength': '8'}),
```

Reemplazar por:

```python
'cedula_escolar': forms.TextInput(attrs={
    'inputmode': 'numeric',
    'pattern': '\\d{8}',
    'maxlength': '8',
    'minlength': '8',
    'title': 'Exactamente 8 dígitos',
    'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 8)",
}),
```

**Campo `peso_kg`** — ya tiene `oninput` pero está mal hecho (limita a 3 caracteres incluyendo punto decimal). Buscar:

```python
'peso_kg': forms.NumberInput(attrs={
    'step': '0.01',
    'min': '10',
    'max': '200',
    'oninput': 'if(this.value.length > 3) this.value = this.value.slice(0, 3);'
}),
```

Reemplazar por:

```python
'peso_kg': forms.NumberInput(attrs={
    'step': '0.01',
    'min': '10',
    'max': '200',
    'inputmode': 'decimal',
    'oninput': "if (this.value.length > 6) this.value = this.value.slice(0, 6)",
}),
```

> **Nota:** 6 caracteres permite valores como `99.99` o `200.00`. El anterior `slice(0, 3)` no dejaba escribir `100` correctamente porque truncaba a `100` y luego al intentar agregar el decimal `.00` se cortaba.

**Campo `altura_mts`** — buscar:

```python
'altura_mts': forms.NumberInput(attrs={'step': '0.01', 'min': '0.50', 'max': '2.50'}),
```

Reemplazar por:

```python
'altura_mts': forms.NumberInput(attrs={
    'step': '0.01',
    'min': '0.50',
    'max': '2.50',
    'inputmode': 'decimal',
    'oninput': "if (this.value.length > 4) this.value = this.value.slice(0, 4)",
}),
```

> **Nota:** 4 caracteres para valores como `2.50` o `1.85`.

## 9.7 Agregar límites a campos sin widget definido

Los campos `nombres` y `apellidos` de `RepresentanteForm` y `AtletaForm` **no tienen widget custom**, así que solo se les aplica la clase CSS común. Hay que agregarles widgets explícitos.

En `filiacion/forms.py` `RepresentanteForm.Meta.widgets` agregar:

```python
'nombres': forms.TextInput(attrs={
    'maxlength': '60',
    'oninput': "this.value = this.value.slice(0, 60)",
}),
'apellidos': forms.TextInput(attrs={
    'maxlength': '60',
    'oninput': "this.value = this.value.slice(0, 60)",
}),
'correo_electronico': forms.EmailInput(attrs={
    'maxlength': '120',
    'oninput': "this.value = this.value.slice(0, 120)",
}),
```

En `AtletaForm.Meta.widgets` agregar:

```python
'nombres': forms.TextInput(attrs={
    'maxlength': '60',
    'oninput': "this.value = this.value.slice(0, 60)",
}),
'apellidos': forms.TextInput(attrs={
    'maxlength': '60',
    'oninput': "this.value = this.value.slice(0, 60)",
}),
```

## 9.8 Aplicar límites en `administracion/forms.py`

**`EntrenadorForm` — campo `nombres` y `apellidos`** — buscar:

```python
'nombres': forms.TextInput(attrs={'placeholder': 'Nombre del entrenador'}),
'apellidos': forms.TextInput(attrs={'placeholder': 'Apellido del entrenador'}),
```

Reemplazar por:

```python
'nombres': forms.TextInput(attrs={
    'placeholder': 'Nombre del entrenador',
    'maxlength': '60',
    'oninput': "this.value = this.value.slice(0, 60)",
}),
'apellidos': forms.TextInput(attrs={
    'placeholder': 'Apellido del entrenador',
    'maxlength': '60',
    'oninput': "this.value = this.value.slice(0, 60)",
}),
```

**Campo `telefono`** — buscar:

```python
'telefono': forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'maxlength': '11', 'placeholder': '04141234567'}),
```

Reemplazar por:

```python
'telefono': forms.TextInput(attrs={
    'inputmode': 'numeric',
    'pattern': '\\d{11}',
    'maxlength': '11',
    'minlength': '11',
    'placeholder': '04141234567',
    'title': 'Exactamente 11 dígitos',
    'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 11)",
}),
```

## 9.9 Aplicar límites en `deportivo/forms.py`

**`PartidoProgramarForm` — campo `equipo_rival`** — buscar:

```python
'equipo_rival': forms.TextInput(attrs={'placeholder': 'Nombre del equipo rival'}),
```

Reemplazar por:

```python
'equipo_rival': forms.TextInput(attrs={
    'placeholder': 'Nombre del equipo rival',
    'maxlength': '100',
    'oninput': "this.value = this.value.slice(0, 100)",
}),
```

**`PartidoResultadoForm` — campos de goles** — buscar:

```python
'goles_favor_escuela': forms.NumberInput(attrs={'min': '0', 'max': '50'}),
'goles_contra_rival': forms.NumberInput(attrs={'min': '0', 'max': '50'}),
```

Reemplazar por:

```python
'goles_favor_escuela': forms.NumberInput(attrs={
    'min': '0', 'max': '50',
    'inputmode': 'numeric',
    'oninput': "if (this.value.length > 2) this.value = this.value.slice(0, 2)",
}),
'goles_contra_rival': forms.NumberInput(attrs={
    'min': '0', 'max': '50',
    'inputmode': 'numeric',
    'oninput': "if (this.value.length > 2) this.value = this.value.slice(0, 2)",
}),
```

**`EstadisticaForm` — campos numéricos compactos** — buscar el bloque `widgets` y aplicar `oninput` a cada uno:

```python
widgets = {
    'es_titular': forms.CheckboxInput(attrs={
        'class': TAILWIND_COMPACT_CHECKBOX
    }),
    'goles': forms.NumberInput(attrs={
        'class': TAILWIND_COMPACT_NUMBER,
        'min': '0', 'max': '20',
        'oninput': "if (this.value.length > 2) this.value = this.value.slice(0, 2)",
    }),
    'asistencias': forms.NumberInput(attrs={
        'class': TAILWIND_COMPACT_NUMBER,
        'min': '0', 'max': '20',
        'oninput': "if (this.value.length > 2) this.value = this.value.slice(0, 2)",
    }),
    'tarjetas_amarillas': forms.NumberInput(attrs={
        'class': TAILWIND_COMPACT_NUMBER,
        'min': '0', 'max': '2',
        'oninput': "if (this.value.length > 1) this.value = this.value.slice(0, 1)",
    }),
    'tarjetas_rojas': forms.NumberInput(attrs={
        'class': TAILWIND_COMPACT_NUMBER,
        'min': '0', 'max': '1',
        'oninput': "if (this.value.length > 1) this.value = this.value.slice(0, 1)",
    }),
    'calificacion_dt': forms.NumberInput(attrs={
        'class': TAILWIND_COMPACT_NUMBER,
        'min': '1', 'max': '10',
        'oninput': "if (this.value.length > 2) this.value = this.value.slice(0, 2)",
    }),
}
```

## 9.10 Verificar arranque

```bash
python manage.py check
python manage.py runserver
```

## 9.11 Probar exhaustivamente

**Test del bug original:**

- [ ] Ir a `/registro/` → en cédula intentar escribir 30 caracteres con letras → debe permitir solo 8 dígitos numéricos.
- [ ] En teléfono intentar pegar `04141234567000` → debe truncar a `04141234567`.
- [ ] En email intentar pegar 500 caracteres → debe cortar en 120.
- [ ] En dirección intentar pegar texto largo → debe cortar en 500.

**Test en otros forms:**

- [ ] Ir al admin → registrar atleta → en cédula escolar intentar 12 dígitos → corta en 8.
- [ ] En peso kg intentar `12345.67` → debe cortar en 6 caracteres.
- [ ] En altura intentar `2.5099` → debe cortar en 4 caracteres.

**Test en pagos:**

- [ ] Ir a Reportar Pago → en referencia intentar `123456789012345` → corta en 12.
- [ ] En referencia intentar `abc12345` → no permite letras, queda solo `12345`.
- [ ] En monto Bs intentar `999999999999999` → corta en 14 caracteres.

**Test en deportivo:**

- [ ] En Partido programar → equipo rival intentar texto de 200 caracteres → corta en 100.
- [ ] En estadísticas → goles intentar `999` → corta en 2 dígitos.
- [ ] Tarjetas amarillas intentar `9` → corta en 1 dígito.

**Test en entrenadores:**

- [ ] Crear entrenador → teléfono intentar 20 dígitos → corta en 11.

## 9.12 Commit

```bash
git add accounts/forms.py finanzas/forms.py filiacion/forms.py administracion/forms.py deportivo/forms.py
git commit -m "feat(forms): límites estrictos con oninput en TODO el proyecto"
```

---

## Resumen de la Fase 9

| Archivo                   | Campos limitados                                                                                                                     |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `accounts/forms.py`       | cédula(8), nombres(60), apellidos(60), email(120), teléfono(11), dirección(500)                                                      |
| `finanzas/forms.py`       | referencia(12), monto_bs(14), tasa_bcv(12), motivo(500)                                                                              |
| `filiacion/forms.py`      | cédula representante(8), nombres(60), apellidos(60), email(120), teléfono(11), dirección(500), cédula escolar(8), peso(6), altura(4) |
| `administracion/forms.py` | nombres(60), apellidos(60), teléfono entrenador(11)                                                                                  |
| `deportivo/forms.py`      | equipo_rival(100), goles(2), tarjetas amarillas(1), rojas(1), calificación(2)                                                        |

**Total: ~25 inputs con límite físico garantizado.**

---

**Fin del PRD.**

---

