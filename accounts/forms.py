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
CEDULA_REGEX = re.compile(r'^\d{6,9}$')
TELEFONO_REGEX = re.compile(r'^0(412|414|416|424|426)\d{7}$')


def validar_cedula_venezolana(value):
    """6 a 9 dígitos numéricos."""
    if not CEDULA_REGEX.match(value):
        raise ValidationError(
            'La cédula debe tener entre 6 y 9 dígitos. Ej: 1234567'
        )


""" def validar_telefono_venezolano(value):
    if not value.isdigit():
        raise ValidationError('El teléfono debe contener solo números.')
    if len(value) != 11:
        raise ValidationError('El teléfono debe tener exactamente 11 dígitos.')
    if not TELEFONO_REGEX.match(value):
        raise ValidationError(
            'Operadora inválida. Debe iniciar con 0412, 0414, 0416, 0424 o 0426.'
        ) """


OPERADORAS_VENEZOLANAS = [
    ('0412', '0412'),
    ('0414', '0414'),
    ('0416', '0416'),
    ('0424', '0424'),
    ('0426', '0426'),
]

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
        self.fields['password1'].help_text = (
            'Mínimo 8 caracteres. Combina letras, números y al menos un símbolo. '
            'Evita usar tu cédula, nombre o palabras comunes.'
        )
        self.fields['password2'].help_text = 'Repite la misma contraseña para confirmar.'

    cedula_identidad = forms.CharField(
        max_length=9, min_length=6, required=True,
        label='Cédula de Identidad',
        help_text='Entre 6 y 9 dígitos numéricos.',
        validators=[validar_cedula_venezolana],
        widget=forms.TextInput(attrs={
            'class': INPUT_CSS,
            'placeholder': '12345678',
            'autocomplete': 'username',
            'maxlength': '9',
            'minlength': '6',
            'pattern': r'\d{6,9}',
            'inputmode': 'numeric',
            'title': 'Entre 6 y 9 dígitos numéricos',
            'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 9)",
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
    codigo_operadora = forms.ChoiceField(
        choices=OPERADORAS_VENEZOLANAS,
        required=True,
        label='Operadora',
        widget=forms.Select(attrs={
            'class': INPUT_CSS,
        }),
    )
    numero_telefono = forms.CharField(
        max_length=7, min_length=7, required=True,
        label='Número',
        help_text='7 dígitos numéricos. Ej: 1234567',
        widget=forms.TextInput(attrs={
            'class': INPUT_CSS,
            'placeholder': '1234567',
            'autocomplete': 'tel-national',
            'maxlength': '7',
            'minlength': '7',
            'pattern': r'\d{7}',
            'inputmode': 'numeric',
            'title': 'Exactamente 7 dígitos numéricos',
            'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 7)",
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
            'correo_electronico', 'codigo_operadora', 'numero_telefono',
            'direccion_habitacion', 'password1', 'password2',
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
    
    def clean(self):
        cleaned = super().clean()
        codigo = cleaned.get('codigo_operadora')
        numero = cleaned.get('numero_telefono')
        if codigo and numero:
            cleaned['telefono_principal'] = codigo + numero
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        cedula = self.cleaned_data['cedula_identidad']
        email = self.cleaned_data['correo_electronico']
        telefono = self.cleaned_data.get('telefono_principal') or (
            self.cleaned_data['codigo_operadora'] + self.cleaned_data['numero_telefono']
        )

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
