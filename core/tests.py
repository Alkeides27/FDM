# core/tests.py
# Pruebas unitarias — Módulo Core
# PRD v1.0 | IngeniumCode-FDM | 8 de junio de 2026

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse, NoReverseMatch


# ═══════════════════════════════════════════════════════════════
# Helpers de fábrica
# ═══════════════════════════════════════════════════════════════

def crear_usuario_test(username='testuser', password='ClaveSegura123!'):
    """Crea un User para tests de vista con login."""
    return User.objects.create_user(username=username, password=password)


# ═══════════════════════════════════════════════════════════════
# FASE 5 — Vista dashboard de core
# ═══════════════════════════════════════════════════════════════

class Fase5_DashboardCoreTestCase(TestCase):
    """Valida el control de acceso y renderizado del dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = crear_usuario_test()

    def test_dashboard_sin_login_redirige(self):
        """Un usuario anónimo debe ser redirigido al login al acceder al dashboard."""
        try:
            url = reverse('dashboard')
        except NoReverseMatch:
            url = '/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_dashboard_con_login_permite_acceso(self):
        """Un usuario autenticado debe poder acceder al dashboard."""
        self.client.login(username='testuser', password='ClaveSegura123!')
        try:
            url = reverse('dashboard')
        except NoReverseMatch:
            url = '/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_usa_template_correcto(self):
        """El dashboard debe renderizar el template 'core/dashboard.html'."""
        self.client.login(username='testuser', password='ClaveSegura123!')
        try:
            url = reverse('dashboard')
        except NoReverseMatch:
            url = '/'
        response = self.client.get(url)
        templates_usados = [t.name for t in response.templates if t.name]
        self.assertIn('core/dashboard.html', templates_usados)
