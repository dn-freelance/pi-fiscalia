from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from feeds.models import NewsItem, Source
from feeds.services import import_news_items

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
    news_items = NewsItem.objects.select_related('source', 'source__category')

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
    result = import_news_items()

    if result.source_count == 0:
        messages.error(request, 'Nenhuma fonte ativa disponível para atualização.')
        return _redirect_with_filters(request)

    if result.created_count or result.existing_count:
        messages.success(request, result.summary_message())
    elif result.error_count:
        messages.error(request, 'Nenhum informativo pÃ´de ser importado com seguranÃ§a nesta atualizaÃ§Ã£o.')

    if result.skipped_count:
        messages.warning(request, result.warning_message())

    if result.error_count:
        messages.error(request, result.error_message())

    return _redirect_with_filters(request)


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


def _selected_news_ids_from_request(request):
    selected_ids = []

    for raw_value in request.POST.getlist('selected_news_ids'):
        try:
            selected_ids.append(int(raw_value))
        except (TypeError, ValueError):
            continue

    return selected_ids
