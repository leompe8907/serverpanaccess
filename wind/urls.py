from django.urls import path
from wind.functions import (
    login,
    singleton,
    logged_in_view
)

urlpatterns = [
    path('login/', login, name='login'),
    path('logged-in/', logged_in_view, name='logged_in'),
    path('singleton/', singleton, name='singleton'),
]
