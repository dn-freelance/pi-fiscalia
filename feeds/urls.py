from django.urls import path

from . import views

app_name = 'feeds'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/exemplo/', views.exemplo_post, name='exemplo_post'),
    path('configurar-fontes/', views.configure_sources, name='configure_sources'),
]
