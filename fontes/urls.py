from django.urls import path
from .views import cadastro_fonte

urlpatterns = [
    path('cadastro-fonte/', cadastro_fonte),
]