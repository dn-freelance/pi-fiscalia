from django.conf import settings
from django.urls import reverse

from feeds.models import DashboardWeeklySummary, NewsImportJob, NewsItem, NewsItemAnalysis, Source
from feeds.services.dashboard_weekly_summary import get_current_week_range


def sidebar_context(request):
    total_news = NewsItem.objects.count()
    unread_count = NewsItem.objects.filter(is_read=False).count()
    high_relevance_count = NewsItemAnalysis.objects.filter(
        status=NewsItemAnalysis.STATUS_COMPLETED,
        impact_level=NewsItemAnalysis.IMPACT_HIGH,
    ).count()
    total_sources = Source.objects.count()
    active_sources = Source.objects.filter(active=True).count()
    current_summary = _get_current_week_summary()

    slides = [
        {
            'title': 'Assistência Fiscal',
            'description': _build_assistance_description(total_news, unread_count, high_relevance_count),
            'href': reverse('feeds:news'),
        },
        {
            'title': 'Cobertura das Fontes',
            'description': _build_sources_description(total_sources, active_sources),
            'href': reverse('feeds:sources'),
        },
        {
            'title': 'Resumo Semanal',
            'description': _build_weekly_summary_description(current_summary, total_news),
            'href': reverse('feeds:index'),
        },
    ]

    network_status = _build_network_status(active_sources, total_sources, current_summary)

    return {
        'sidebar_app_version': getattr(settings, 'APP_VERSION', '2.4.0'),
        'sidebar_assistant_slides': slides,
        'sidebar_network_status': network_status,
    }


def _get_current_week_summary():
    week_start, _ = get_current_week_range()
    return DashboardWeeklySummary.objects.filter(week_start=week_start).first()


def _build_assistance_description(total_news, unread_count, high_relevance_count):
    if total_news <= 0:
        return 'Ainda não há informativos carregados. Assim que as fontes forem atualizadas, os destaques aparecem aqui.'

    return (
        f'Você acompanha {total_news} informativo(s), com {high_relevance_count} de alta relevância '
        f'e {unread_count} ainda pendente(s) de leitura.'
    )


def _build_sources_description(total_sources, active_sources):
    if total_sources <= 0:
        return 'Nenhuma fonte foi cadastrada ainda. Configure as fontes RSS para iniciar o monitoramento tributário.'

    if active_sources <= 0:
        return (
            f'Existem {total_sources} fonte(s) cadastrada(s), mas todas estão pausadas. '
            'Ative pelo menos uma para voltar a importar informativos.'
        )

    return (
        f'O monitoramento está cobrindo {active_sources} de {total_sources} fonte(s) cadastrada(s), '
        'mantendo o fluxo de notícias fiscais atualizado.'
    )


def _build_weekly_summary_description(summary, total_news):
    if total_news <= 0:
        return 'Assim que novos informativos forem importados, o dashboard passa a montar o resumo da semana automaticamente.'

    if summary is None or summary.status == DashboardWeeklySummary.STATUS_PENDING:
        return 'Os informativos da semana já estão sendo preparados para gerar o resumo executivo com apoio da IA.'

    if summary.status == DashboardWeeklySummary.STATUS_RUNNING:
        return 'O resumo semanal está sendo gerado em segundo plano e será preenchido automaticamente assim que concluir.'

    if summary.status == DashboardWeeklySummary.STATUS_FAILED:
        return summary.error_message or 'O resumo semanal precisa de uma nova tentativa para ficar disponível no dashboard.'

    return _truncate_text(summary.overview, 120)


def _build_network_status(active_sources, total_sources, current_summary):
    has_running_import = NewsImportJob.objects.filter(
        status__in=[NewsImportJob.STATUS_PENDING, NewsImportJob.STATUS_RUNNING]
    ).exists()
    latest_job = NewsImportJob.objects.order_by('-created_at').first()

    if total_sources <= 0:
        return {
            'label': 'Sem fontes',
            'tone': 'warning',
            'progress': 18,
            'href': reverse('feeds:sources'),
        }

    if active_sources <= 0:
        return {
            'label': 'Pausado',
            'tone': 'warning',
            'progress': 26,
            'href': reverse('feeds:sources'),
        }

    if has_running_import:
        return {
            'label': 'Sincronizando',
            'tone': 'info',
            'progress': 68,
            'href': reverse('feeds:news'),
        }

    if latest_job is not None and latest_job.status == NewsImportJob.STATUS_FAILED:
        return {
            'label': 'Atenção',
            'tone': 'danger',
            'progress': 38,
            'href': reverse('feeds:news'),
        }

    if current_summary is not None and current_summary.status == DashboardWeeklySummary.STATUS_FAILED:
        return {
            'label': 'Atenção',
            'tone': 'danger',
            'progress': 52,
            'href': reverse('feeds:index'),
        }

    if active_sources < total_sources:
        return {
            'label': 'Parcial',
            'tone': 'warning',
            'progress': max(35, round((active_sources / total_sources) * 100)),
            'href': reverse('feeds:sources'),
        }

    return {
        'label': 'Estável',
        'tone': 'success',
        'progress': 92,
        'href': reverse('feeds:index'),
    }


def _truncate_text(value, limit):
    text = (value or '').strip()
    if len(text) <= limit:
        return text

    return f"{text[: limit - 3].rstrip()}..."
