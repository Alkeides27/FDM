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
