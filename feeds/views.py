import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt


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
