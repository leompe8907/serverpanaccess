"""
Vistas para la aplicación wind.
"""
from django.shortcuts import render


def login_test_view(request):
    """
    Página de prueba para iniciar sesión con Google.
    Muestra un botón que enlaza al flujo de allauth (Google).
    """
    return render(request, 'wind/login_test.html')
