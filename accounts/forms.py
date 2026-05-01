import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from filiacion.models import Representante


INPUT_CSS = (
    'w-full px-4 py-2.5 rounded-lg '
    'bg-white dark:bg-slate-800 '
    'border border-slate-300 dark:border-slate-600 '
    'text-slate-900 dark:text-white '
    'placeholder-slate-400 '
    'focus:outline-none focus:ring-2 focus:ring-fdm-blue focus:border-transparent '
    'transition'
)


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
    """
    Login restringido a:
    - Usuarios staff (personal interno: tesorería, coordinadores, entrenadores)
    - Representantes registrados (con perfil Representante asociado)

    Rechaza usuarios huérfanos sin rol ni perfil.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': (
            'Credenciales incorrectas. Verifica tu usuario y contraseña.'
        ),
        'inactive': 'Esta cuenta está desactivada.',
        'no_staff': ('Esta cuenta no tiene un rol asignado. ' 
                     'Contacta al administrador.')
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)

        es_staff = user.is_staff
        es_representante = (
            hasattr(user, 'representante') and user.representante is not None
        )

        if not (es_staff or es_representante):
            raise ValidationError(
                self.error_messages['no_staff'],
                code='no_staff',
            )

class RepresentanteSignUpForm(UserCreationForm):
    """
    Registro público de representantes.
    Crea User + Representante asociado en la misma transacción atómica.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': INPUT_CSS})
        self.fields['password2'].widget.attrs.update({'class': INPUT_CSS})

    cedula_identidad = forms.CharField(
        max_length=8, min_length=8, required=True,
        label='Cédula de Identidad',
        help_text='8 dígitos numéricos. Ej: 12345678',
        validators=[validar_cedula_venezolana],
        widget=forms.TextInput(attrs={
            'class': INPUT_CSS,
            'placeholder': '12345678',
            'autocomplete': 'username',
            'maxlength': '8',
            'minlength': '8',
            'pattern': r'\d{8}',
            'inputmode': 'numeric',
            'title': 'Exactamente 8 dígitos numéricos',
            'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 8)",
        }),
    )
    nombres = forms.CharField(
        max_length=60, required=True, label='Nombres',
        widget=forms.TextInput(attrs={
            'class': INPUT_CSS,
            'autocomplete': 'given-name',
            'maxlength': '60',
            'oninput': "this.value = this.value.slice(0, 60)",
        }),
    )
    apellidos = forms.CharField(
        max_length=60, required=True, label='Apellidos',
        widget=forms.TextInput(attrs={
            'class': INPUT_CSS,
            'autocomplete': 'family-name',
            'maxlength': '60',
            'oninput': "this.value = this.value.slice(0, 60)",
        }),
    )
    correo_electronico = forms.EmailField(
        max_length=120, required=True, label='Correo Electrónico',
        widget=forms.EmailInput(attrs={
            'class': INPUT_CSS,
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
            'class': INPUT_CSS,
            'placeholder': '04141234567',
            'autocomplete': 'tel',
            'maxlength': '11',
            'minlength': '11',
            'pattern': r'\d{11}',
            'inputmode': 'numeric',
            'title': 'Exactamente 11 dígitos. Ej: 04141234567',
            'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 11)",
        }),
    )
    direccion_habitacion = forms.CharField(
        max_length=500, required=True, label='Dirección de Habitación',
        widget=forms.Textarea(attrs={
            'class': INPUT_CSS,
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
