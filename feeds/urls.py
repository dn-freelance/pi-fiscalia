from django.urls import path

from .views import api, dashboard, sources

app_name = 'feeds'

urlpatterns = [
    path('', dashboard.index, name='index'),
    
    path('api/exemplo/', api.exemplo_post, name='exemplo_post'),
    
    path('fontes/', sources.index, name='sources'),
    path('fontes/cadastrar/', sources.create_source, name='create_source'),
    path('fontes/<int:source_id>/editar/', sources.update_source, name='update_source'),
    path('fontes/<int:source_id>/excluir/', sources.delete_source, name='delete_source'),
    path('fontes/<int:source_id>/alternar-status/', sources.toggle_source_status, name='toggle_source_status'),
]
