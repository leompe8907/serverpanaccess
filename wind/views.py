"""
Vistas para la aplicación wind.
"""
from django.shortcuts import render
from django.conf import settings


def login_test_view(request):
    """
    Página de prueba para iniciar sesión con Google.
    Muestra un botón que enlaza al flujo de allauth (Google).
    """
    google_client_id = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']
    context = {
        'google_client_id': google_client_id,
    }
    return render(request, 'wind/login_test.html', context)
