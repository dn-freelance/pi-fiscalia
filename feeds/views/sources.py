from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from feeds.models import Source, SourceCategory
from feeds.services.dashboard_weekly_summary import invalidate_current_week_summary


def index(request):
    context = {
        'sources': Source.objects.select_related('category'),
        'source_categories': SourceCategory.objects.all(),
    }

    return render(request, 'pages/sources/index.html', context)


@require_POST
def create_source(request):
    source_data = _source_payload_from_request(request)

    if not _source_payload_is_valid(source_data):
        messages.error(request, 'Informe nome, URL e categoria para cadastrar a fonte.')
        return redirect('feeds:sources')

    source = Source()
    category, error_message = _get_source_category(source_data['category'])

    if category is None:
        messages.error(request, error_message)
        return redirect('feeds:sources')

    saved, error_message = _save_source(source, source_data, category)
    if not saved:
        messages.error(request, error_message)
        return redirect('feeds:sources')

    invalidate_current_week_summary()
    messages.success(request, f'Fonte "{source.name}" cadastrada com sucesso.')
    return redirect('feeds:sources')


@require_POST
def update_source(request, source_id):
    source_data = _source_payload_from_request(request)

    if not _source_payload_is_valid(source_data):
        messages.error(request, 'Informe nome, URL e categoria para salvar a fonte.')
        return redirect('feeds:sources')

    source = get_object_or_404(Source, pk=source_id)
    category, error_message = _get_source_category(source_data['category'])

    if category is None:
        messages.error(request, error_message)
        return redirect('feeds:sources')

    saved, error_message = _save_source(source, source_data, category)
    if not saved:
        messages.error(request, error_message)
        return redirect('feeds:sources')

    invalidate_current_week_summary()
    messages.success(request, f'Fonte "{source.name}" atualizada com sucesso.')
    return redirect('feeds:sources')


@require_POST
def delete_source(request, source_id):
    source = get_object_or_404(Source, pk=source_id)
    name = source.name

    source.delete()
    invalidate_current_week_summary()
    messages.success(request, f'Fonte "{name}" excluída com sucesso.')
    return redirect('feeds:sources')


@require_POST
def toggle_source_status(request, source_id):
    source = get_object_or_404(Source, pk=source_id)
    active = request.POST.get('active') == 'on'
    status = 'ativada' if active else 'desativada'

    source.active = active
    source.save(update_fields=['active', 'updated_at'])

    invalidate_current_week_summary()
    messages.success(request, f'Fonte "{source.name}" {status} com sucesso.')
    return redirect('feeds:sources')


def _source_payload_from_request(request):
    return {
        'name': request.POST.get('name', '').strip(),
        'url': request.POST.get('url', '').strip(),
        'description': request.POST.get('description', '').strip(),
        'category': request.POST.get('category', '').strip(),
    }


def _source_payload_is_valid(source_data):
    return bool(source_data['name'] and source_data['url'] and source_data['category'])


def _get_source_category(category_id):
    try:
        return SourceCategory.objects.get(pk=category_id), ''
    except (SourceCategory.DoesNotExist, ValueError):
        return None, 'Selecione uma categoria válida.'


def _save_source(source, source_data, category):
    source.name = source_data['name']
    source.url = source_data['url']
    source.description = source_data['description']
    source.category = category

    try:
        source.full_clean()
        source.save()
    except ValidationError as error:
        return False, _validation_error_message(error)
    except IntegrityError:
        return False, 'Já existe uma fonte cadastrada com esta URL.'

    return True, ''


def _validation_error_message(error):
    if hasattr(error, 'message_dict'):
        if 'url' in error.message_dict:
            return 'Informe uma URL válida e que ainda não esteja cadastrada.'
        if 'category' in error.message_dict:
            return 'Selecione uma categoria válida.'

    return 'Não foi possível salvar a fonte. Revise os dados informados.'
