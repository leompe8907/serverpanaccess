"""
Módulo de vistas para la aplicación wind.

Este módulo exporta todas las vistas organizadas por categoría.
"""
from wind.views.test_views import (
    test_login,
    test_singleton,
    test_logged_in
)

__all__ = [
    'test_login',
    'test_singleton',
    'test_logged_in',
]

