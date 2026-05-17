from django.urls import path
from wind.functions import (
    login,
    singleton,
    logged_in_view,
    sync_subscribers_view,
    compare_and_update_subscribers_view,
    sync_products_view,
    test_call_list_products,
    products_stats_view,
    sync_smartcards_view,
    test_call_list_smartcards,
    smartcards_stats_view,
    create_subscriber_view,
    change_password_view,
    full_sync_view,
)
from wind.views import login_test_view, login_page_view, dashboard_view, subscriber_test_view
from wind.auth_views import GoogleLoginView
from wind.views import login_facebook_test_view
from wind.auth_views import FacebookLoginView
from wind.views import register_view
from wind.views import credentials_view

urlpatterns = [
    # Portal de usuario
    path('', login_page_view, name='home'),
    path('login/', login_page_view, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('subscriber-test/', subscriber_test_view, name='subscriber_test'),

    # Autenticación Social vía REST API (Token de Google a JWT Django)
    path('auth/google/', GoogleLoginView.as_view(), name='google_login_api'),
    
    # Autenticación Social vía REST API (Token de Facebook a JWT Django)
    path('auth/facebook/', FacebookLoginView.as_view(), name='facebook_login_api'),

    # Página de prueba: Iniciar sesión con Google (nativo HTML)
    path('login-test/', login_test_view, name='login_test'),
    
    # Página de prueba: Iniciar sesión con Facebook (SDK JS)
    path('login-test-facebook/', login_facebook_test_view, name='login_test_facebook'),
    
    # Registro web (formulario usable)
    path('register/', register_view, name='register_web'),
    # Página para mostrar credenciales recién creadas (token firmado)
    path('credentials/', credentials_view, name='credentials_web'),
    # Autenticación PanAccess legada
    path('login/', login, name='login'),
    path('logged-in/', logged_in_view, name='logged_in'),
    path('singleton/', singleton, name='singleton'),
    
    # Sincronización de suscriptores
    # Valida automáticamente la BD: si está vacía hace descarga completa,
    # si tiene datos hace descarga incremental
    # Parámetros: limit (opcional, default: 100, máximo: 1000)
    path('sync-subscribers/', sync_subscribers_view, name='sync_subscribers'),
    
    # Comparar y actualizar suscriptores
    # Compara todos los suscriptores de PanAccess con los locales:
    # - Si cantidades iguales: actualiza los diferentes
    # - Si PanAccess tiene menos: elimina los de más (con credenciales)
    # Parámetros: limit (opcional, default: 100, máximo: 1000)
    path('compare-and-update-subscribers/', compare_and_update_subscribers_view, name='compare_and_update_subscribers'),
    
    # Endpoints de productos
    # Sincronización: valida automáticamente la BD y descarga según corresponda
    # Parámetros: limit (opcional, default: 100, máximo: 1000)
    path('sync-products/', sync_products_view, name='sync_products'),
    
    # Endpoints de smartcards
    # Sincronización: valida automáticamente la BD y descarga según corresponda
    # Parámetros: limit (opcional, default: 100, máximo: 1000)
    path('sync-smartcards/', sync_smartcards_view, name='sync_smartcards'),
    
    # Endpoint para crear suscriptores
    path('create-subscriber/', create_subscriber_view, name='create_subscriber'),

    # Cambio de contraseña (PanAccess)
    path('change-password/', change_password_view, name='change_password'),

    # Sincronización global (todas las tablas)
    path('full-sync/', full_sync_view, name='full_sync'),
]
