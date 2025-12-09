from django.urls import path
from wind import views

urlpatterns = [
    path('login/', views.test_login, name='test_login'),
    path('logged-in/', views.test_logged_in, name='test_logged_in'),
    path('test/singleton/', views.test_singleton, name='test_singleton'),
]
