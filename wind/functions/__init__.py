"""
Módulo de funciones para la aplicación wind.

Este módulo exporta todas las funciones organizadas por archivo.
"""
from wind.functions.login import login
from wind.functions.singleton import singleton
from wind.functions.logged_in import logged_in_view
from wind.functions.sync_subscribers import sync_subscribers_view

# Importar funciones de smartcards para facilitar el acceso
from wind.functions.getSmartcard import (
    sync_smartcards,
    fetch_all_smartcards,
    download_smartcards_since_last,
    compare_and_update_all_smartcards,
    CallListSmartcards,
    DataBaseEmpty as SmartcardDataBaseEmpty,
    LastSmartcard
)

__all__ = [
    'login',
    'singleton',
    'logged_in_view',
    'sync_subscribers_view',
    'sync_smartcards',
    'fetch_all_smartcards',
    'download_smartcards_since_last',
    'compare_and_update_all_smartcards',
    'CallListSmartcards',
    'SmartcardDataBaseEmpty',
    'LastSmartcard',
]
