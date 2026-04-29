"""
URL configuration for project_gestion.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from accounts.forms import StaffOnlyAuthenticationForm


# ──────────────────────────────────────────────────────────────
# RATE LIMITED LOGIN VIEW
# Doble proteccion: por IP y por username
# ──────────────────────────────────────────────────────────────
@method_decorator(
    ratelimit(key='post:username', rate='10/h', method='POST', block=True),
    name='post',
)
@method_decorator(
    ratelimit(key='ip', rate='5/m', method='POST', block=True),
    name='post',
)
class RateLimitedLoginView(auth_views.LoginView):
    template_name = 'registration/login.html'
    authentication_form = StaffOnlyAuthenticationForm
    redirect_authenticated_user = True


urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticacion
    path('login/', RateLimitedLoginView.as_view(), name='login'),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),

    # Apps de negocio
    path('', include('core.urls')),
    path('', include('filiacion.urls')),
    path('', include('deportivo.urls')),
    path('', include('administracion.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )

# Handler personalizado para 429 (rate limit excedido)
handler429 = 'project_gestion.views.too_many_requests'
