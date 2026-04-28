import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def exemplo_post(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mensagem = data.get('mensagem', 'Nenhuma mensagem recebida')
            return JsonResponse({
                'status': 'sucesso',
                'dados_recebidos': mensagem,
            })
        except json.JSONDecodeError:
            return JsonResponse({'status': 'erro', 'mensagem': 'JSON inválido'}, status=400)

    return JsonResponse({'status': 'erro', 'mensagem': 'Apenas requisições POST são permitidas'}, status=405)
