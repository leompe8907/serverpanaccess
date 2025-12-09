"""
Módulo de funciones para la aplicación wind.

Este módulo exporta todas las funciones organizadas por archivo.
"""
from wind.functions.login import login
from wind.functions.singleton import singleton
from wind.functions.logged_in import logged_in_view

__all__ = [
    'login',
    'singleton',
    'logged_in_view',
]
