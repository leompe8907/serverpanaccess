from django.urls import path
from wind.functions import (
    login,
    singleton,
    logged_in_view,
    sync_subscribers_view,
)

urlpatterns = [
    path('login/', login, name='login'),
    path('logged-in/', logged_in_view, name='logged_in'),
    path('singleton/', singleton, name='singleton'),
    path('sync-subscribers/', sync_subscribers_view, name='sync_subscribers'),
]
