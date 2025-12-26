from django.urls import path
from wind.functions import (
    login,
    singleton,
    logged_in_view,
    sync_subscribers_view,
    sync_products_view,
    test_call_list_products,
    products_stats_view,
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
]
