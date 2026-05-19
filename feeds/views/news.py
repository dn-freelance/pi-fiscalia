import json
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from feeds.models import (
    NewsImportJob,
    NewsItem,
    NewsItemAnalysis,
    NewsItemFollow,
    NewsItemReminderNotification,
    Source,
)
from feeds.services.news_import_jobs import run_news_import_job, start_news_import_job

STATUS_ALL = 'all'
STATUS_READ = 'read'
STATUS_UNREAD = 'unread'
RELEVANCE_ALL = 'all'
RELEVANCE_HIGH = NewsItemAnalysis.IMPACT_HIGH
RELEVANCE_MEDIUM = NewsItemAnalysis.IMPACT_MEDIUM
RELEVANCE_LOW = NewsItemAnalysis.IMPACT_LOW
SORT_BY_PUBLICATION = 'publication'
SORT_BY_EFFECTIVE_DATE = 'effective_date'
SORT_BY_SCORE = 'score'
SORT_BY_IMPACT = 'impact'
BULK_ACTION_MARK_READ = 'mark_read'
BULK_ACTION_MARK_UNREAD = 'mark_unread'
REMINDER_DAY_OFFSETS = (30, 7, 1, 0)

SORT_OPTIONS = [
    (SORT_BY_PUBLICATION, 'Data de publicação'),
    (SORT_BY_EFFECTIVE_DATE, 'Vigência'),
    (SORT_BY_SCORE, 'Score'),
    (SORT_BY_IMPACT, 'Impacto'),
]
SORT_VALUES = {value for value, _label in SORT_OPTIONS}

STATUS_OPTIONS = [
    (STATUS_ALL, 'Todos'),
    (STATUS_UNREAD, 'Não lidos'),
    (STATUS_READ, 'Lidos'),
]

RELEVANCE_OPTIONS = [
    (RELEVANCE_ALL, 'Todas'),
    (RELEVANCE_HIGH, 'Alta'),
    (RELEVANCE_MEDIUM, 'Média'),
    (RELEVANCE_LOW, 'Baixa'),
]


def index(request):
    filters = _filters_from_query(request)
    news_items = NewsItem.objects.select_related('source', 'source__category', 'analysis')

    if filters['query']:
        news_items = news_items.filter(
            Q(title__icontains=filters['query'])
            | Q(summary__icontains=filters['query'])
            | Q(source__name__icontains=filters['query'])
        )

    if filters['source_id'] is not None:
        news_items = news_items.filter(source_id=filters['source_id'])

    if filters['status'] == STATUS_READ:
        news_items = news_items.filter(is_read=True)
    elif filters['status'] == STATUS_UNREAD:
        news_items = news_items.filter(is_read=False)

    if filters['relevance'] != RELEVANCE_ALL:
        news_items = news_items.filter(
            analysis__status=NewsItemAnalysis.STATUS_COMPLETED,
            analysis__impact_level=filters['relevance'],
        )

    if filters['effective_date_from']:
        news_items = news_items.filter(analysis__effective_date__gte=filters['effective_date_from'])

    if filters['effective_date_to']:
        news_items = news_items.filter(analysis__effective_date__lte=filters['effective_date_to'])

    news_items = list(_order_news_items(news_items, filters['sort']))
    tracked_news_ids = set(
        NewsItemFollow.objects.filter(news_item_id__in=[item.id for item in news_items]).values_list('news_item_id', flat=True)
    )

    for item in news_items:
        analysis = item.analysis_or_none
        item.has_trackable_effective_date = bool(analysis is not None and analysis.effective_date is not None)
        item.is_following_effective_date = item.id in tracked_news_ids

    context = {
        'news_items': news_items,
        'sources': Source.objects.order_by('name'),
        'status_options': STATUS_OPTIONS,
        'relevance_options': RELEVANCE_OPTIONS,
        'sort_options': SORT_OPTIONS,
        'selected_query': filters['query'],
        'selected_source': filters['source'],
        'selected_status': filters['status'],
        'selected_relevance': filters['relevance'],
        'selected_sort': filters['sort'],
        'selected_effective_date_from': filters['effective_date_from_raw'],
        'selected_effective_date_to': filters['effective_date_to_raw'],
        'unread_count': NewsItem.objects.filter(is_read=False).count(),
    }
    return render(request, 'pages/news/index.html', context)


@require_POST
def refresh_news(request):
    job = NewsImportJob.objects.create(
        redirect_query=request.POST.get('q', '').strip(),
        redirect_source=request.POST.get('source', '').strip(),
        redirect_status=request.POST.get('status', STATUS_ALL).strip() or STATUS_ALL,
        redirect_relevance=request.POST.get('relevance', RELEVANCE_ALL).strip() or RELEVANCE_ALL,
        redirect_sort=_normalize_sort(request.POST.get('sort', SORT_BY_PUBLICATION)),
        redirect_effective_date_from=request.POST.get('effective_date_from', '').strip(),
        redirect_effective_date_to=request.POST.get('effective_date_to', '').strip(),
    )

    if request.headers.get('X-Fiscalia-Sync-Import') == '1':
        run_news_import_job(job.id)
        return redirect('feeds:finalize_refresh_news_job', job_id=job.id)

    start_news_import_job(job.id)
    return redirect('feeds:refresh_news_progress', job_id=job.id)


def refresh_news_progress(request, job_id):
    job = get_object_or_404(NewsImportJob, pk=job_id)
    context = {
        'job': job,
        'job_status_url': reverse('feeds:refresh_news_progress_status', args=[job.id]),
        'job_finalize_url': reverse('feeds:finalize_refresh_news_job', args=[job.id]),
        'job_payload': _job_payload(job),
    }
    return render(request, 'pages/news/import_progress.html', context)


def refresh_news_progress_status(request, job_id):
    job = get_object_or_404(NewsImportJob, pk=job_id)
    return JsonResponse(_job_payload(job))


def finalize_refresh_news_job(request, job_id):
    job = get_object_or_404(NewsImportJob, pk=job_id)

    if not job.is_finished:
        return redirect('feeds:refresh_news_progress', job_id=job.id)

    for entry in job.result_messages:
        level = (entry.get('level') or 'info').strip().lower()
        text = (entry.get('text') or '').strip()
        if not text:
            continue

        if level == 'success':
            messages.success(request, text)
        elif level == 'warning':
            messages.warning(request, text)
        else:
            messages.error(request, text)

    return _redirect_with_job_filters(job)


@require_POST
def toggle_news_read(request, news_id):
    news_item = get_object_or_404(NewsItem, pk=news_id)
    news_item.is_read = not news_item.is_read
    news_item.save(update_fields=['is_read', 'updated_at'])

    status_label = 'lido' if news_item.is_read else 'não lido'
    messages.success(request, f'Informativo marcado como {status_label}.')

    return _redirect_with_filters(request)


@require_POST
def toggle_news_follow(request, news_id):
    news_item = get_object_or_404(NewsItem.objects.select_related('analysis'), pk=news_id)
    analysis = news_item.analysis_or_none
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if is_ajax:
        if analysis is None or analysis.effective_date is None:
            return JsonResponse(
                {
                    'ok': False,
                    'message': 'Esse informativo ainda não tem uma data de vigência para acompanhamento.',
                },
                status=400,
            )

        follow, created = NewsItemFollow.objects.get_or_create(news_item=news_item)
        if created:
            return JsonResponse(
                {
                    'ok': True,
                    'is_following': True,
                    'message': 'Acompanhamento da vigência ativado para este informativo.',
                }
            )

        NewsItemReminderNotification.objects.filter(news_item=news_item).delete()
        follow.delete()
        return JsonResponse(
            {
                'ok': True,
                'is_following': False,
                'message': 'Acompanhamento da vigência desativado para este informativo.',
            }
        )

    if analysis is None or analysis.effective_date is None:
        message = 'Esse informativo ainda não tem uma data de vigência para acompanhamento.'
        if is_ajax:
            return JsonResponse({'ok': False, 'message': message}, status=400)
        messages.error(request, 'Esse informativo ainda não tem uma data de vigência para acompanhamento.')
        return _redirect_with_filters(request)

    follow, created = NewsItemFollow.objects.get_or_create(news_item=news_item)
    if created:
        messages.success(request, 'Acompanhamento da vigência ativado para este informativo.')
    else:
        NewsItemReminderNotification.objects.filter(news_item=news_item).delete()
        follow.delete()
        messages.success(request, 'Acompanhamento da vigência desativado para este informativo.')

    return _redirect_with_filters(request)


def effective_date_reminders(request):
    today = timezone.localdate()
    _ensure_due_reminders(today)

    reminders = (
        NewsItemReminderNotification.objects.filter(
            reminder_date=today,
            dismissed_at__isnull=True,
            news_item__follow__isnull=False,
            news_item__analysis__effective_date=F('effective_date'),
        )
        .select_related('news_item', 'news_item__analysis', 'news_item__source')
        .order_by('days_before', '-created_at')
    )

    return JsonResponse(
        {
            'notifications': [_build_reminder_payload(reminder) for reminder in reminders],
        }
    )


@require_POST
def dismiss_effective_date_reminder(request):
    payload = _payload_from_request(request)
    reminder_id = payload.get('notification_id')
    reminder = get_object_or_404(NewsItemReminderNotification, pk=reminder_id)
    reminder.dismissed_at = timezone.now()
    reminder.save(update_fields=['dismissed_at', 'updated_at'])
    return JsonResponse({'ok': True})


@require_POST
def bulk_update_news_read(request):
    action = request.POST.get('bulk_action', '').strip()
    selected_ids = _selected_news_ids_from_request(request)

    if not selected_ids:
        messages.error(request, 'Selecione pelo menos um informativo para aplicar a ação em lote.')
        return _redirect_with_filters(request)

    if action not in {BULK_ACTION_MARK_READ, BULK_ACTION_MARK_UNREAD}:
        messages.error(request, 'A ação em lote solicitada é inválida.')
        return _redirect_with_filters(request)

    is_read = action == BULK_ACTION_MARK_READ
    updated_count = NewsItem.objects.filter(id__in=selected_ids).update(is_read=is_read)
    status_label = 'lidos' if is_read else 'não lidos'
    messages.success(request, f'{updated_count} informativo(s) marcado(s) como {status_label}.')

    return _redirect_with_filters(request)


def _filters_from_query(request):
    selected_status = request.GET.get('status', STATUS_ALL).strip() or STATUS_ALL
    if selected_status not in {STATUS_ALL, STATUS_READ, STATUS_UNREAD}:
        selected_status = STATUS_ALL

    selected_relevance = request.GET.get('relevance', RELEVANCE_ALL).strip() or RELEVANCE_ALL
    if selected_relevance not in {RELEVANCE_ALL, RELEVANCE_HIGH, RELEVANCE_MEDIUM, RELEVANCE_LOW}:
        selected_relevance = RELEVANCE_ALL

    selected_sort = _normalize_sort(request.GET.get('sort', SORT_BY_PUBLICATION))

    selected_source = request.GET.get('source', '').strip()
    source_id = None
    if selected_source:
        try:
            source_id = int(selected_source)
        except ValueError:
            selected_source = ''

    selected_effective_date_from = request.GET.get('effective_date_from', '').strip()
    selected_effective_date_to = request.GET.get('effective_date_to', '').strip()

    return {
        'query': request.GET.get('q', '').strip(),
        'source': selected_source,
        'source_id': source_id,
        'status': selected_status,
        'relevance': selected_relevance,
        'sort': selected_sort,
        'effective_date_from_raw': selected_effective_date_from,
        'effective_date_to_raw': selected_effective_date_to,
        'effective_date_from': parse_date(selected_effective_date_from) if selected_effective_date_from else None,
        'effective_date_to': parse_date(selected_effective_date_to) if selected_effective_date_to else None,
    }


def _redirect_with_filters(request):
    params = {}

    for field_name in (
        'q',
        'source',
        'status',
        'relevance',
        'sort',
        'effective_date_from',
        'effective_date_to',
    ):
        value = request.POST.get(field_name, '').strip()
        if value and not (
            (field_name == 'status' and value == STATUS_ALL)
            or (field_name == 'relevance' and value == RELEVANCE_ALL)
            or (field_name == 'sort' and _normalize_sort(value) == SORT_BY_PUBLICATION)
        ):
            params[field_name] = value

    base_url = reverse('feeds:news')
    query_string = urlencode(params)

    if query_string:
        return redirect(f'{base_url}?{query_string}')

    return redirect(base_url)


def _redirect_with_job_filters(job):
    params = {}

    if job.redirect_query:
        params['q'] = job.redirect_query

    if job.redirect_source:
        params['source'] = job.redirect_source

    if job.redirect_status and job.redirect_status != STATUS_ALL:
        params['status'] = job.redirect_status

    if job.redirect_relevance and job.redirect_relevance != RELEVANCE_ALL:
        params['relevance'] = job.redirect_relevance

    if job.redirect_sort and job.redirect_sort != SORT_BY_PUBLICATION:
        params['sort'] = job.redirect_sort

    if job.redirect_effective_date_from:
        params['effective_date_from'] = job.redirect_effective_date_from

    if job.redirect_effective_date_to:
        params['effective_date_to'] = job.redirect_effective_date_to

    base_url = reverse('feeds:news')
    query_string = urlencode(params)

    if query_string:
        return redirect(f'{base_url}?{query_string}')

    return redirect(base_url)


def _selected_news_ids_from_request(request):
    selected_ids = []

    for raw_value in request.POST.getlist('selected_news_ids'):
        try:
            selected_ids.append(int(raw_value))
        except (TypeError, ValueError):
            continue

    return selected_ids


def _normalize_sort(value):
    selected_sort = (value or SORT_BY_PUBLICATION).strip() or SORT_BY_PUBLICATION
    if selected_sort not in SORT_VALUES:
        return SORT_BY_PUBLICATION

    return selected_sort


def _order_news_items(news_items, selected_sort):
    news_items = news_items.annotate(
        sort_publication_date=Coalesce('published_at', 'created_at'),
        sort_has_effective_date=Case(
            When(analysis__effective_date__isnull=False, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        sort_has_score=Case(
            When(analysis__importance_score__isnull=False, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        sort_impact_rank=Case(
            When(analysis__impact_level=NewsItemAnalysis.IMPACT_HIGH, then=Value(3)),
            When(analysis__impact_level=NewsItemAnalysis.IMPACT_MEDIUM, then=Value(2)),
            When(analysis__impact_level=NewsItemAnalysis.IMPACT_LOW, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    )

    if selected_sort == SORT_BY_EFFECTIVE_DATE:
        return news_items.order_by(
            '-sort_has_effective_date',
            'analysis__effective_date',
            '-sort_publication_date',
            '-created_at',
        )

    if selected_sort == SORT_BY_SCORE:
        return news_items.order_by(
            '-sort_has_score',
            '-analysis__importance_score',
            '-sort_impact_rank',
            '-sort_publication_date',
            '-created_at',
        )

    if selected_sort == SORT_BY_IMPACT:
        return news_items.order_by(
            '-sort_impact_rank',
            '-sort_has_score',
            '-analysis__importance_score',
            '-sort_publication_date',
            '-created_at',
        )

    return news_items.order_by(
        '-sort_publication_date',
        '-created_at',
    )


def _job_payload(job):
    return {
        'id': str(job.id),
        'status': job.status,
        'current_stage': job.current_stage,
        'stage_title': job.stage_title,
        'stage_message': job.stage_message,
        'is_finished': job.is_finished,
        'finalize_url': reverse('feeds:finalize_refresh_news_job', args=[job.id]),
        'rss': {
            'total_sources': job.rss_total_sources,
            'processed_sources': job.rss_processed_sources,
            'progress_percent': job.rss_progress_percent,
            'created_count': job.imported_created_count,
            'existing_count': job.imported_existing_count,
            'error_count': job.import_error_count,
            'skipped_count': job.import_skipped_count,
        },
        'analysis': {
            'enabled': job.analysis_enabled,
            'total_items': job.analysis_total_items,
            'processed_items': job.analysis_processed_items,
            'progress_percent': job.analysis_progress_percent,
            'failure_count': job.analysis_failure_count,
            'skipped_count': job.analysis_skipped_count,
        },
    }


def _ensure_due_reminders(reference_date):
    follows = NewsItemFollow.objects.select_related('news_item', 'news_item__analysis')

    for follow in follows:
        analysis = follow.news_item.analysis_or_none
        if analysis is None or analysis.effective_date is None:
            continue

        days_before = (analysis.effective_date - reference_date).days
        if days_before not in REMINDER_DAY_OFFSETS:
            continue

        NewsItemReminderNotification.objects.get_or_create(
            news_item=follow.news_item,
            effective_date=analysis.effective_date,
            days_before=days_before,
            defaults={'reminder_date': analysis.effective_date - timedelta(days=days_before)},
        )


def _build_reminder_payload(reminder):
    item = reminder.news_item
    analysis = item.analysis_or_none
    description = ''

    if analysis is not None and analysis.summary:
        description = analysis.summary
    elif item.summary:
        description = item.summary

    return {
        'id': reminder.id,
        'title': item.title,
        'description': _truncate_text(description.strip(), 220),
        'priority': _priority_from_analysis(analysis),
        'priority_label': _priority_label_from_analysis(analysis),
        'effective_date_display': analysis.effective_date_display if analysis is not None else reminder.effective_date.strftime('%d/%m/%Y'),
        'reminder_label': _reminder_label(reminder.days_before),
        'source_name': item.source.name,
        'href': f"{reverse('feeds:news')}#article-news-card-{item.id}",
    }


def _priority_from_analysis(analysis):
    if analysis is None:
        return 'medium'

    if analysis.impact_level == NewsItemAnalysis.IMPACT_HIGH:
        return 'high'
    if analysis.impact_level == NewsItemAnalysis.IMPACT_LOW:
        return 'low'
    return 'medium'


def _priority_label_from_analysis(analysis):
    if analysis is None:
        return 'ACOMPANHAR'

    return {
        NewsItemAnalysis.IMPACT_HIGH: 'ALTA PRIORIDADE',
        NewsItemAnalysis.IMPACT_MEDIUM: 'ACOMPANHAR',
        NewsItemAnalysis.IMPACT_LOW: 'BAIXA PRIORIDADE',
    }.get(analysis.impact_level, 'ACOMPANHAR')


def _reminder_label(days_before):
    if days_before == 0:
        return 'Vigência hoje'
    if days_before == 1:
        return 'Vigência amanhã'
    return f'Vigência em {days_before} dias'


def _payload_from_request(request):
    if (request.content_type or '').startswith('application/json'):
        try:
            raw_body = request.body.decode('utf-8') if request.body else '{}'
            return json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    return {
        'notification_id': request.POST.get('notification_id'),
    }


def _truncate_text(value, max_length):
    if len(value) <= max_length:
        return value

    return value[: max_length - 1].rstrip() + '…'
