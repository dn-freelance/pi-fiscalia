# PI Fiscalia

Portal informativo que centraliza feeds RSS de diferentes fontes sobre informações fiscais.

## Tecnologias
- Python 3.11+
- Django 5.x
- django-environ (Gerenciamento de variáveis de ambiente)

## Como rodar o projeto

### 1. Clonar o repositório
```bash
git clone https://github.com/dn-freelance/pi-fiscalia.git
cd pi-fiscalia
```

### 2. Criar e ativar o ambiente virtual (opcional, mas recomendado)
```bash
python -m venv venv
# No Windows:
.\venv\Scripts\activate
# No Linux/macOS:
source venv/bin/activate
```

### 3. Instalar as dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar as variáveis de ambiente
Crie um arquivo `.env` na raiz do projeto (use o `.env.example` como base se disponível, ou crie um novo):
```env
DEBUG=True
SECRET_KEY=django-insecure-sua-chave-aqui
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=sqlite:///db.sqlite3
```

### 5. Executar as migrações iniciais
```bash
python manage.py migrate
```

### 6. Iniciar o servidor de desenvolvimento
```bash
python manage.py runserver
```
O projeto estará disponível em `http://127.0.0.1:8000/`.

## Estrutura do Projeto
- `config/`: Configurações principais do Django.
- `feeds/`: App principal para gestão de fontes e itens RSS.
- `static/`: Arquivos estáticos (CSS, JS, Imagens).
- `templates/`: Templates HTML globais.

## Como Contribuir

Se você deseja contribuir com o projeto, siga os passos abaixo para criar uma nova branch e abrir um Pull Request:

1. Atualize sua branch principal para garantir que está com o código mais recente:
   ```bash
   git checkout main
   git pull origin main
   ```

2. Crie uma nova branch para a sua feature ou correção:
   ```bash
   git checkout -b minha-nova-feature
   ```

3. Faça as suas alterações e salve os commits:
   ```bash
   git add .
   git commit -m "feat: adiciona nova funcionalidade X"
   ```

4. Envie a sua branch para o repositório remoto:
   ```bash
   git push origin minha-nova-feature
   ```

5. Acesse o repositório no GitHub e abra um **Pull Request** da sua branch para a branch principal, descrevendo detalhadamente as mudanças e o contexto da sua contribuição.
