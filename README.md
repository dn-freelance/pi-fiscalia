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
