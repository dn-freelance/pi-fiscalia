import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


def index(request):
    return render(request, 'index.html')


@csrf_exempt
def exemplo_post(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mensagem = data.get('mensagem', 'Nenhuma mensagem recebida')
            return JsonResponse({
                'status': 'sucesso',
                'dados_recebidos': mensagem
            })
        except json.JSONDecodeError:
            return JsonResponse({'status': 'erro', 'mensagem': 'JSON inválido'}, status=400)

    return JsonResponse({'status': 'erro', 'mensagem': 'Apenas requisições POST são permitidas'}, status=405)


def configure_sources(request):
    sources = [
        {
            'id': 1,
            'name': 'Receita Federal do Brasil',
            'category': 'Federal',
            'description': 'Instruções normativas, atos declaratórios e comunicados oficiais.',
            'url': 'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/rss',
            'active': True,
        },
        {
            'id': 2,
            'name': 'CONFAZ',
            'category': 'Estadual',
            'description': 'Convênios ICMS, ajustes SINIEF e despachos publicados pelo conselho.',
            'url': 'https://www.confaz.fazenda.gov.br/legislacao/rss',
            'active': True,
        },
        {
            'id': 3,
            'name': 'Portal SPED',
            'category': 'Federal',
            'description': 'Notícias sobre EFD, ECD, NF-e e demais obrigações acessórias.',
            'url': 'http://sped.rfb.gov.br/rss/noticias',
            'active': True,
        },
        {
            'id': 4,
            'name': 'SEFAZ São Paulo',
            'category': 'Federal',
            'description': 'Portarias, comunicados CAT e atualizações da administração tributária paulista.',
            'url': 'https://portal.fazenda.sp.gov.br/rss/noticias',
            'active': False,
        },
    ]

    return render(request, 'configure_sources.html', {'sources': sources})


@require_POST
def create_source(request):
    source_data = {
        'name': request.POST.get('name', '').strip(),
        'url': request.POST.get('url', '').strip(),
        'description': request.POST.get('description', '').strip(),
        'category': request.POST.get('category', '').strip(),
        'active': True,
    }

    if not source_data['name'] or not source_data['url'] or not source_data['category']:
        messages.error(request, 'Informe nome, URL e categoria para cadastrar a fonte.')
        return redirect('feeds:configure_sources')

    # TODO: persistir a fonte no banco quando o model de fontes RSS estiver definido.
    messages.success(request, f'Fonte "{source_data["name"]}" enviada para cadastro.')

    return redirect('feeds:configure_sources')


@require_POST
def update_source(request, source_id):
    source_data = {
        'id': source_id,
        'name': request.POST.get('name', '').strip(),
        'url': request.POST.get('url', '').strip(),
        'description': request.POST.get('description', '').strip(),
        'category': request.POST.get('category', '').strip(),
    }

    if not source_data['name'] or not source_data['url'] or not source_data['category']:
        messages.error(request, 'Informe nome, URL e categoria para salvar a fonte.')
        return redirect('feeds:configure_sources')

    # TODO: atualizar a fonte no banco quando o model de fontes RSS estiver definido.
    messages.success(request, f'Fonte "{source_data["name"]}" enviada para atualização.')

    return redirect('feeds:configure_sources')


@require_POST
def delete_source(request, source_id):
    name = request.POST.get('name', '').strip() or f'#{source_id}'

    # TODO: remover a fonte no banco quando o model de fontes RSS estiver definido.
    messages.success(request, f'Fonte "{name}" enviada para exclusão.')

    return redirect('feeds:configure_sources')


@require_POST
def toggle_source_status(request, source_id):
    active = request.POST.get('active') == 'on'
    name = request.POST.get('name', '').strip() or f'#{source_id}'
    status = 'ativação' if active else 'desativação'

    # TODO: atualizar o status da fonte no banco quando o model de fontes RSS estiver definido.
    messages.success(request, f'Fonte "{name}" enviada para {status}.')

    return redirect('feeds:configure_sources')
