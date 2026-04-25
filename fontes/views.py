from django.shortcuts import render

def cadastro_fonte(request):
    # Se o usuário clicar no botão Salvar
    if request.method == 'POST':
        nome = request.POST.get('nome')
        url = request.POST.get('url')
        # Aqui depois você adiciona a lógica para salvar no MySQL
        print(f"Salvando: {nome} - {url}")

    return render(request, 'cadastro_fonte.html') # Nome do seu arquivo na pasta templates