import json
from django.shortcuts import render
from django.http import JsonResponse
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
