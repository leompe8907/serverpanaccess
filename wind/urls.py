from django.urls import path
from wind.functions import (
    login,
    singleton,
    logged_in_view,
    sync_subscribers_view,
    sync_products_view,
    test_call_list_products,
    products_stats_view,
    sync_smartcards_view,
    test_call_list_smartcards,
    smartcards_stats_view,
    create_subscriber_view,
)

urlpatterns = [
    path('login/', login, name='login'),
    path('logged-in/', logged_in_view, name='logged_in'),
    path('singleton/', singleton, name='singleton'),
    path('sync-subscribers/', sync_subscribers_view, name='sync_subscribers'),
    # Endpoints de productos
    path('sync-products/', sync_products_view, name='sync_products'),
    path('test-products/', test_call_list_products, name='test_call_list_products'),
    path('products-stats/', products_stats_view, name='products_stats'),
    # Endpoints de smartcards
    path('sync-smartcards/', sync_smartcards_view, name='sync_smartcards'),
    path('test-smartcards/', test_call_list_smartcards, name='test_call_list_smartcards'),
    path('smartcards-stats/', smartcards_stats_view, name='smartcards_stats'),
    # Endpoint para crear suscriptores
    path('create-subscriber/', create_subscriber_view, name='create_subscriber'),
]
