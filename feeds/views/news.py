from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from feeds.models import NewsImportJob, NewsItem, Source
from feeds.services.news_import_jobs import run_news_import_job, start_news_import_job

STATUS_ALL = 'all'
STATUS_READ = 'read'
STATUS_UNREAD = 'unread'
BULK_ACTION_MARK_READ = 'mark_read'
BULK_ACTION_MARK_UNREAD = 'mark_unread'

STATUS_OPTIONS = [
    (STATUS_ALL, 'Todos'),
    (STATUS_UNREAD, 'Não lidos'),
    (STATUS_READ, 'Lidos'),
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

    news_items = news_items.order_by(
        Coalesce('published_at', 'created_at').desc(),
        '-created_at',
    )

    context = {
        'news_items': news_items,
        'sources': Source.objects.order_by('name'),
        'status_options': STATUS_OPTIONS,
        'selected_query': filters['query'],
        'selected_source': filters['source'],
        'selected_status': filters['status'],
        'unread_count': NewsItem.objects.filter(is_read=False).count(),
    }
    return render(request, 'pages/news/index.html', context)


@require_POST
def refresh_news(request):
    job = NewsImportJob.objects.create(
        redirect_query=request.POST.get('q', '').strip(),
        redirect_source=request.POST.get('source', '').strip(),
        redirect_status=request.POST.get('status', STATUS_ALL).strip() or STATUS_ALL,
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

    selected_source = request.GET.get('source', '').strip()
    source_id = None
    if selected_source:
        try:
            source_id = int(selected_source)
        except ValueError:
            selected_source = ''

    return {
        'query': request.GET.get('q', '').strip(),
        'source': selected_source,
        'source_id': source_id,
        'status': selected_status,
    }


def _redirect_with_filters(request):
    params = {}

    for field_name in ('q', 'source', 'status'):
        value = request.POST.get(field_name, '').strip()
        if value and not (field_name == 'status' and value == STATUS_ALL):
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
