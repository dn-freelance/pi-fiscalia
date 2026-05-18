import json
import logging
from collections import Counter
from datetime import timedelta
from threading import Thread

import requests
from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import strip_tags

from feeds.models import DashboardWeeklySummary, NewsImportJob, NewsItem, NewsItemAnalysis
from feeds.services.news_analysis import (
    _build_openai_quota_message,
    _build_openai_rate_limit_message,
    _collect_openai_response_text,
    _describe_openai_http_error,
    _extract_openai_error_details,
    _parse_retry_after_seconds,
    _parse_structured_json_response,
)

logger = logging.getLogger(__name__)

SUMMARY_MAX_ITEMS = 25


class DashboardWeeklySummaryError(Exception):
    pass


class DashboardWeeklySummaryConfigurationError(DashboardWeeklySummaryError):
    pass


class DashboardWeeklySummaryProviderError(DashboardWeeklySummaryError):
    pass


class DashboardWeeklySummaryRateLimitError(DashboardWeeklySummaryProviderError):
    def __init__(self, message, retry_after_seconds=None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class DashboardWeeklySummaryQuotaError(DashboardWeeklySummaryRateLimitError):
    pass


def get_current_week_range(current_time=None):
    localized_now = timezone.localtime(current_time or timezone.now())
    week_start = localized_now.date() - timedelta(days=localized_now.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def invalidate_current_week_summary(current_time=None):
    week_start, week_end = get_current_week_range(current_time)

    with transaction.atomic():
        summary = DashboardWeeklySummary.objects.select_for_update().filter(week_start=week_start).first()
        if summary is None:
            return

        summary.week_end = week_end
        summary.revision += 1
        summary.status = DashboardWeeklySummary.STATUS_PENDING
        summary.overview = ''
        summary.main_changes = ''
        summary.attention = ''
        summary.news_count = 0
        summary.high_relevance_count = 0
        summary.effective_this_week_count = 0
        summary.error_message = ''
        summary.started_at = None
        summary.finished_at = None
        summary.save(
            update_fields=[
                'week_end',
                'revision',
                'status',
                'overview',
                'main_changes',
                'attention',
                'news_count',
                'high_relevance_count',
                'effective_this_week_count',
                'error_message',
                'started_at',
                'finished_at',
                'updated_at',
            ]
        )


def get_current_week_summary_state(start_async=False, current_time=None):
    if not NewsItem.objects.exists():
        return _build_no_news_summary_payload()

    week_start, week_end = get_current_week_range(current_time)
    import_in_progress = _has_active_import_job()

    summary = _get_or_create_weekly_summary(week_start, week_end)

    if start_async and not import_in_progress:
        summary = _ensure_summary_generation(summary)

    return _build_summary_payload(summary, import_in_progress)


def start_dashboard_weekly_summary_job(summary_id, expected_revision):
    worker = Thread(
        target=run_dashboard_weekly_summary_job,
        args=(summary_id, expected_revision),
        daemon=True,
        name=f'dashboard-weekly-summary-{summary_id}',
    )
    worker.start()
    return worker


def run_dashboard_weekly_summary_job(summary_id, expected_revision):
    close_old_connections()
    try:
        summary = DashboardWeeklySummary.objects.get(pk=summary_id)
        if summary.revision != expected_revision:
            return

        item_payload = _build_current_week_items_payload(summary.week_start, summary.week_end)
        if not item_payload['items']:
            _persist_summary_success(
                summary_id,
                expected_revision,
                {
                    'overview': 'Nenhum informativo com publicação ou vigência na semana atual foi identificado até o momento.',
                    'main_changes': 'Assim que surgirem novos movimentos fiscais nesta semana, o resumo será preenchido automaticamente.',
                    'attention': 'No momento, não há entradas da semana atual exigindo destaque imediato no dashboard.',
                },
                item_payload,
            )
            return

        llm_summary = _generate_weekly_summary_with_llm(item_payload)
        _persist_summary_success(summary_id, expected_revision, llm_summary, item_payload)
    except DashboardWeeklySummary.DoesNotExist:
        logger.warning('Resumo semanal %s não foi encontrado para geração.', summary_id)
    except DashboardWeeklySummaryError as error:
        logger.warning('Falha ao gerar resumo semanal %s: %s', summary_id, error)
        _persist_summary_failure(summary_id, expected_revision, str(error))
    except Exception as error:  # pragma: no cover - proteção adicional
        logger.exception('Falha inesperada ao gerar resumo semanal %s', summary_id)
        _persist_summary_failure(summary_id, expected_revision, str(error))
    finally:
        close_old_connections()


def _get_or_create_weekly_summary(week_start, week_end):
    summary, created = DashboardWeeklySummary.objects.get_or_create(
        week_start=week_start,
        defaults={'week_end': week_end},
    )

    if not created and summary.week_end != week_end:
        summary.week_end = week_end
        summary.save(update_fields=['week_end', 'updated_at'])

    return summary


def _ensure_summary_generation(summary):
    if summary.status == DashboardWeeklySummary.STATUS_COMPLETED:
        return summary

    if summary.status == DashboardWeeklySummary.STATUS_RUNNING:
        return summary

    with transaction.atomic():
        locked_summary = DashboardWeeklySummary.objects.select_for_update().get(pk=summary.pk)
        if locked_summary.status in {
            DashboardWeeklySummary.STATUS_COMPLETED,
            DashboardWeeklySummary.STATUS_RUNNING,
        }:
            return locked_summary

        locked_summary.status = DashboardWeeklySummary.STATUS_RUNNING
        locked_summary.overview = ''
        locked_summary.main_changes = ''
        locked_summary.attention = ''
        locked_summary.error_message = ''
        locked_summary.started_at = timezone.now()
        locked_summary.finished_at = None
        locked_summary.news_count = 0
        locked_summary.high_relevance_count = 0
        locked_summary.effective_this_week_count = 0
        locked_summary.save(
            update_fields=[
                'status',
                'overview',
                'main_changes',
                'attention',
                'error_message',
                'started_at',
                'finished_at',
                'news_count',
                'high_relevance_count',
                'effective_this_week_count',
                'updated_at',
            ]
        )

        expected_revision = locked_summary.revision

    start_dashboard_weekly_summary_job(summary.id, expected_revision)
    return locked_summary


def _build_summary_payload(summary, import_in_progress):
    status = summary.status
    if import_in_progress and status != DashboardWeeklySummary.STATUS_COMPLETED:
        message = 'As fontes estão sendo atualizadas. O resumo semanal será gerado assim que a importação terminar.'
    elif status == DashboardWeeklySummary.STATUS_RUNNING:
        message = 'Gerando o resumo semanal com IA em segundo plano.'
    elif status == DashboardWeeklySummary.STATUS_FAILED:
        message = summary.error_message or 'Não foi possível gerar o resumo semanal agora.'
    elif status == DashboardWeeklySummary.STATUS_COMPLETED:
        message = ''
    else:
        message = 'Preparando os informativos da semana para gerar o resumo com IA.'

    return {
        'status': status,
        'is_ready': status == DashboardWeeklySummary.STATUS_COMPLETED,
        'is_loading': status in {
            DashboardWeeklySummary.STATUS_PENDING,
            DashboardWeeklySummary.STATUS_RUNNING,
        },
        'overview': summary.overview,
        'main_changes': summary.main_changes,
        'attention': summary.attention,
        'error_message': summary.error_message,
        'message': message,
    }


def _build_no_news_summary_payload():
    return {
        'status': DashboardWeeklySummary.STATUS_COMPLETED,
        'is_ready': True,
        'is_loading': False,
        'overview': 'Nenhum informativo disponível no momento para compor o resumo semanal.',
        'main_changes': 'Assim que novas notícias forem importadas, o dashboard recalcula os destaques da semana.',
        'attention': 'No momento, não há movimentações registradas para exigir acompanhamento imediato.',
        'error_message': '',
        'message': '',
    }


def _has_active_import_job():
    return NewsImportJob.objects.filter(
        status__in=[NewsImportJob.STATUS_PENDING, NewsImportJob.STATUS_RUNNING]
    ).exists()


def _build_current_week_items_payload(week_start, week_end):
    news_items = list(
        NewsItem.objects.select_related('source', 'source__category', 'analysis')
        .annotate(reference_at=Coalesce('published_at', 'created_at'))
        .filter(
            Q(published_at__date__range=(week_start, week_end))
            | Q(published_at__isnull=True, created_at__date__range=(week_start, week_end))
            | Q(analysis__effective_date__range=(week_start, week_end))
        )
        .order_by(
            '-analysis__importance_score',
            'analysis__effective_date',
            '-reference_at',
            '-created_at',
        )
    )

    keyword_counter = Counter()
    high_relevance_count = 0
    effective_this_week_count = 0
    items = []

    for item in news_items:
        analysis = item.analysis_or_none
        effective_date = analysis.effective_date if analysis is not None else None
        is_effective_this_week = effective_date is not None and week_start <= effective_date <= week_end
        is_published_this_week = week_start <= item.reference_at.date() <= week_end

        if analysis is not None and analysis.impact_level == NewsItemAnalysis.IMPACT_HIGH:
            high_relevance_count += 1

        if is_effective_this_week:
            effective_this_week_count += 1

        keywords = analysis.keywords if analysis is not None and analysis.keywords else []
        keyword_counter.update(keywords)

        items.append(
            {
                'title': item.title,
                'source_name': item.source.name,
                'source_category': item.source.category.name if item.source.category_id else '',
                'published_at': _format_datetime(item.reference_at),
                'effective_date': analysis.effective_date_display if analysis is not None else '',
                'impact_level': analysis.impact_level if analysis is not None else '',
                'importance_score': analysis.importance_score if analysis is not None else None,
                'summary': (analysis.summary if analysis is not None and analysis.summary else item.summary)[:600],
                'keywords': keywords,
                'is_published_this_week': is_published_this_week,
                'is_effective_this_week': is_effective_this_week,
            }
        )

    return {
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat(),
        'total_items': len(news_items),
        'high_relevance_count': high_relevance_count,
        'effective_this_week_count': effective_this_week_count,
        'top_keywords': [keyword for keyword, _ in keyword_counter.most_common(5)],
        'items': items[:SUMMARY_MAX_ITEMS],
        'truncated_item_count': max(len(news_items) - SUMMARY_MAX_ITEMS, 0),
    }


def _generate_weekly_summary_with_llm(summary_payload):
    ai_settings = settings.NEWS_AI
    if not ai_settings['ENABLED']:
        raise DashboardWeeklySummaryConfigurationError('A IA está desabilitada nesta instalação.')

    provider_name = (ai_settings['PROVIDER'] or '').strip().lower()
    if provider_name != 'openai':
        raise DashboardWeeklySummaryConfigurationError(
            f'O provider "{provider_name}" não é suportado para o resumo semanal.'
        )

    api_key = ai_settings['OPENAI_API_KEY']
    if not api_key:
        raise DashboardWeeklySummaryConfigurationError('IA não configurada: defina OPENAI_API_KEY no .env.')

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    if ai_settings['OPENAI_ORG_ID']:
        headers['OpenAI-Organization'] = ai_settings['OPENAI_ORG_ID']
    if ai_settings['OPENAI_PROJECT']:
        headers['OpenAI-Project'] = ai_settings['OPENAI_PROJECT']

    endpoint = f"{(ai_settings['OPENAI_BASE_URL'] or 'https://api.openai.com/v1').rstrip('/')}/responses"

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=_build_openai_summary_payload(ai_settings['MODEL'], summary_payload),
            timeout=ai_settings['TIMEOUT_SECONDS'],
        )
    except requests.RequestException as error:
        raise DashboardWeeklySummaryProviderError(f'falha na consulta ao provider: {error}') from error

    if response.status_code == 429:
        error_type, error_code, error_message = _extract_openai_error_details(response)
        retry_after_seconds = _parse_retry_after_seconds(response.headers.get('Retry-After'))

        if error_code == 'insufficient_quota' or error_type == 'insufficient_quota':
            raise DashboardWeeklySummaryQuotaError(
                _build_openai_quota_message(error_message),
                retry_after_seconds=retry_after_seconds,
            )

        raise DashboardWeeklySummaryRateLimitError(
            _build_openai_rate_limit_message(error_message),
            retry_after_seconds=retry_after_seconds,
        )

    try:
        response.raise_for_status()
    except requests.RequestException as error:
        raise DashboardWeeklySummaryProviderError(_describe_openai_http_error(response, error)) from error

    payload = response.json()
    response_text = _collect_openai_response_text(payload)
    if not response_text:
        raise DashboardWeeklySummaryProviderError('o provider não retornou uma resposta estruturada utilizável.')

    try:
        content = _parse_structured_json_response(response_text)
    except json.JSONDecodeError as error:
        raise DashboardWeeklySummaryProviderError(f'resposta JSON inválida: {error}') from error

    return _normalize_weekly_summary_result(content)


def _build_openai_summary_payload(model_name, summary_payload):
    return {
        'model': model_name,
        'input': [
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            'Você é um analista fiscal brasileiro especializado em tributação, obrigações '
                            'acessórias, vigências e mudanças operacionais. Responda apenas com JSON válido '
                            'seguindo o schema informado. O tom deve ser objetivo, em PT-BR, com frases curtas '
                            'e úteis para um dashboard executivo. Considere como semana atual o intervalo '
                            'informado pelo usuário e dê mais peso a impact_level high, importance_score mais alto '
                            'e mudanças com vigência nesta mesma semana.'
                        ),
                    }
                ],
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            'Dados da semana atual em JSON para gerar o resumo do dashboard:\n'
                            f'{json.dumps(summary_payload, ensure_ascii=False)}'
                        ),
                    }
                ],
            },
        ],
        'max_output_tokens': 700,
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'dashboard_weekly_summary',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'overview': {'type': 'string'},
                        'main_changes': {'type': 'string'},
                        'attention': {'type': 'string'},
                    },
                    'required': ['overview', 'main_changes', 'attention'],
                },
            }
        },
    }


def _normalize_weekly_summary_result(content):
    if not isinstance(content, dict):
        raise DashboardWeeklySummaryProviderError('o provider retornou um resumo semanal inválido.')

    overview = _clean_text(content.get('overview', ''))
    main_changes = _clean_text(content.get('main_changes', ''))
    attention = _clean_text(content.get('attention', ''))

    if not overview or not main_changes or not attention:
        raise DashboardWeeklySummaryProviderError('o provider retornou um resumo semanal incompleto.')

    return {
        'overview': overview,
        'main_changes': main_changes,
        'attention': attention,
    }


def _persist_summary_success(summary_id, expected_revision, summary_content, item_payload):
    with transaction.atomic():
        summary = DashboardWeeklySummary.objects.select_for_update().filter(pk=summary_id).first()
        if summary is None or summary.revision != expected_revision:
            return

        summary.status = DashboardWeeklySummary.STATUS_COMPLETED
        summary.overview = summary_content['overview']
        summary.main_changes = summary_content['main_changes']
        summary.attention = summary_content['attention']
        summary.news_count = item_payload['total_items']
        summary.high_relevance_count = item_payload['high_relevance_count']
        summary.effective_this_week_count = item_payload['effective_this_week_count']
        summary.error_message = ''
        summary.finished_at = timezone.now()
        summary.save(
            update_fields=[
                'status',
                'overview',
                'main_changes',
                'attention',
                'news_count',
                'high_relevance_count',
                'effective_this_week_count',
                'error_message',
                'finished_at',
                'updated_at',
            ]
        )


def _persist_summary_failure(summary_id, expected_revision, error_message):
    with transaction.atomic():
        summary = DashboardWeeklySummary.objects.select_for_update().filter(pk=summary_id).first()
        if summary is None or summary.revision != expected_revision:
            return

        summary.status = DashboardWeeklySummary.STATUS_FAILED
        summary.error_message = _clean_text(error_message)[:255]
        summary.finished_at = timezone.now()
        summary.save(
            update_fields=[
                'status',
                'error_message',
                'finished_at',
                'updated_at',
            ]
        )


def _format_datetime(value):
    if value is None:
        return ''

    localized_value = timezone.localtime(value) if timezone.is_aware(value) else value
    return localized_value.strftime('%d/%m/%Y %H:%M')


def _clean_text(value):
    if not value:
        return ''

    text = strip_tags(str(value))
    text = text.replace('\xa0', ' ')
    return ' '.join(text.split()).strip()
