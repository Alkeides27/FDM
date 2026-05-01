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
