from django.urls import path

from . import views

app_name = 'feeds'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/exemplo/', views.exemplo_post, name='exemplo_post'),
    path('configurar-fontes/', views.configure_sources, name='configure_sources'),
    path('configurar-fontes/cadastrar/', views.create_source, name='create_source'),
    path('configurar-fontes/<int:source_id>/editar/', views.update_source, name='update_source'),
    path('configurar-fontes/<int:source_id>/excluir/', views.delete_source, name='delete_source'),
    path('configurar-fontes/<int:source_id>/alternar-status/', views.toggle_source_status, name='toggle_source_status'),
]
