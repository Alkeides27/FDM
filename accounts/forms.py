from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class StaffOnlyAuthenticationForm(AuthenticationForm):
    """
    Login restringido a usuarios con is_staff=True.
    Los representantes y usuarios externos no pueden iniciar sesión.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': (
            'Credenciales incorrectas. Verifica tu usuario y contraseña.'
        ),
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
