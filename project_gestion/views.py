from django.shortcuts import render


def too_many_requests(request, exception=None):
    """Handler personalizado para HTTP 429 (rate limit excedido)."""
    return render(request, 'errors/429.html', status=429)
