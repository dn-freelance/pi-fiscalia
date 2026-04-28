from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from feeds.data.sources import SOURCE_CATEGORIES, get_demo_sources


def index(request):
    context = {
        'sources': get_demo_sources(),
        'source_categories': SOURCE_CATEGORIES,
    }

    return render(request, 'pages/sources/index.html', context)


@require_POST
def create_source(request):
    source_data = _source_payload_from_request(request)

    if not _source_payload_is_valid(source_data):
        messages.error(request, 'Informe nome, URL e categoria para cadastrar a fonte.')
        return redirect('feeds:sources')

    # TODO: persistir a fonte no banco quando o model de fontes RSS estiver definido.
    messages.success(request, f'Fonte "{source_data["name"]}" enviada para cadastro.')

    return redirect('feeds:sources')


@require_POST
def update_source(request, source_id):
    source_data = _source_payload_from_request(request)
    source_data['id'] = source_id

    if not _source_payload_is_valid(source_data):
        messages.error(request, 'Informe nome, URL e categoria para salvar a fonte.')
        return redirect('feeds:sources')

    # TODO: atualizar a fonte no banco quando o model de fontes RSS estiver definido.
    messages.success(request, f'Fonte "{source_data["name"]}" enviada para atualização.')

    return redirect('feeds:sources')


@require_POST
def delete_source(request, source_id):
    name = request.POST.get('name', '').strip() or f'#{source_id}'

    # TODO: remover a fonte no banco quando o model de fontes RSS estiver definido.
    messages.success(request, f'Fonte "{name}" enviada para exclusão.')

    return redirect('feeds:sources')


@require_POST
def toggle_source_status(request, source_id):
    active = request.POST.get('active') == 'on'
    name = request.POST.get('name', '').strip() or f'#{source_id}'
    status = 'ativação' if active else 'desativação'

    # TODO: atualizar o status da fonte no banco quando o model de fontes RSS estiver definido.
    messages.success(request, f'Fonte "{name}" enviada para {status}.')

    return redirect('feeds:sources')


def _source_payload_from_request(request):
    return {
        'name': request.POST.get('name', '').strip(),
        'url': request.POST.get('url', '').strip(),
        'description': request.POST.get('description', '').strip(),
        'category': request.POST.get('category', '').strip(),
        'active': True,
    }


def _source_payload_is_valid(source_data):
    return bool(source_data['name'] and source_data['url'] and source_data['category'])
