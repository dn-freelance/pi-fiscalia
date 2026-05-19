from django.urls import path

from .views import api, dashboard, news, sources, tags

app_name = 'feeds'

urlpatterns = [
    path('', dashboard.index, name='index'),
    path('dashboard/resumo-semanal/status/', dashboard.weekly_summary_status, name='dashboard_weekly_summary_status'),

    path('api/exemplo/', api.exemplo_post, name='exemplo_post'),

    path('informativos/', news.index, name='news'),
    path('informativos/atualizar/', news.refresh_news, name='refresh_news'),
    path('informativos/atualizacoes/<uuid:job_id>/', news.refresh_news_progress, name='refresh_news_progress'),
    path(
        'informativos/atualizacoes/<uuid:job_id>/status/',
        news.refresh_news_progress_status,
        name='refresh_news_progress_status',
    ),
    path(
        'informativos/atualizacoes/<uuid:job_id>/finalizar/',
        news.finalize_refresh_news_job,
        name='finalize_refresh_news_job',
    ),
    path('informativos/acoes-em-lote/', news.bulk_update_news_read, name='bulk_update_news_read'),
    path('informativos/<int:news_id>/alternar-leitura/', news.toggle_news_read, name='toggle_news_read'),
    path('informativos/<int:news_id>/alternar-acompanhamento/', news.toggle_news_follow, name='toggle_news_follow'),
    path('notificacoes/vigencia/', news.effective_date_reminders, name='effective_date_reminders'),
    path('notificacoes/vigencia/dispensar/', news.dismiss_effective_date_reminder, name='dismiss_effective_date_reminder'),

    path('fontes/', sources.index, name='sources'),
    path('fontes/cadastrar/', sources.create_source, name='create_source'),
    path('fontes/<int:source_id>/editar/', sources.update_source, name='update_source'),
    path('fontes/<int:source_id>/excluir/', sources.delete_source, name='delete_source'),
    path('fontes/<int:source_id>/alternar-status/', sources.toggle_source_status, name='toggle_source_status'),

    path('tags/', tags.index, name='tags'),
    path('tags/cadastrar/', tags.create_tag, name='create_tag'),
    path('tags/<int:tag_id>/editar/', tags.update_tag, name='update_tag'),
    path('tags/<int:tag_id>/excluir/', tags.delete_tag, name='delete_tag'),
]
