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
- `feeds/urls.py`: URLs públicas e nomes internos de rotas do app principal.
- `feeds/views/`: Views separadas por página.
- `feeds/models/`: Models separados por domínio.
- `feeds/admin/`: Configurações do Django Admin separadas por domínio.
- `feeds/tests/`: Testes separados por domínio ou página.
- `feeds/data/`: Dados temporários e catálogos usados até a criação dos models.
- `static/`: Arquivos estáticos (CSS, JS, Imagens).
- `static/css/components/`: Estilos reutilizáveis, como botões, formulários, mensagens e modais.
- `static/css/layouts/`: Estilos da estrutura principal da aplicação.
- `static/css/pages/`: Estilos específicos de cada página.
- `static/js/app.js`: Comportamentos globais.
- `static/js/pages/`: Scripts específicos de cada página.
- `templates/`: Templates HTML globais.
- `templates/layouts/`: Partes estruturais do layout, como sidebar.
- `templates/pages/`: Templates organizados por página.

## Padrões do Projeto

### URLs, rotas e views
- URL pública é o caminho que aparece no navegador. Exemplo: `/fontes/`.
- Nome da rota é o identificador interno usado em `{% url %}`, `reverse()` e `redirect()`. Exemplo: `feeds:sources`.
- View, ou handler, é a função que responde à requisição. Exemplo: `sources.index`.
- Em `path('fontes/', sources.index, name='sources')`, `fontes/` é a URL pública, `sources.index` é a view e `sources` é o nome interno da rota.

### Convenções
- Use inglês para nomes internos: arquivos, pastas, módulos, funções, variáveis, classes e IDs no HTML/CSS e nomes internos de rotas.
- Use português para textos exibidos ao usuário: títulos, botões, labels, mensagens e itens do menu.
- URLs públicas podem ser em português quando fizer sentido para o usuário final.
- Cada página deve ter seu módulo em `feeds/views/`. Exemplo: `feeds/views/sources.py`.
- Use `index` como view principal da página. Exemplo: `sources.index`.
- Ações da mesma página ficam no mesmo módulo. Exemplo: `create_source`, `update_source`, `delete_source`.
- Cada domínio persistido deve ter seu módulo em `feeds/models/`. Exemplo: `feeds/models/source.py`.
- Reexporte os models em `feeds/models/__init__.py` para manter imports como `from feeds.models import Source`.
- Configurações do admin também devem ficar por domínio em `feeds/admin/`. Exemplo: `feeds/admin/source.py`.
- Testes devem ficar em `feeds/tests/`, agrupados por domínio ou página. Exemplo: `feeds/tests/test_sources.py`.
- Dados temporários ou mockados devem ficar em `feeds/data/`. Exemplo: `feeds/data/sources.py`.
- O template principal da página fica em `templates/pages/<page>/index.html`.
- Use `templates/pages/<page>/partials/` para partes da página, como modais, formulários e blocos reaproveitados.
- Layouts globais ficam em `templates/layouts/`, como `sidebar.html`.
- CSS global entra em `static/css/base.css`; CSS de página entra em `static/css/pages/`.
- JS global entra em `static/js/app.js`; JS de página entra em `static/js/pages/`.
- Evite criar abstrações globais antes da necessidade. Se é usado por uma página só, deixe perto dela.

## Checklist para novas páginas
1. Crie `feeds/views/<page>.py`.
2. Crie a view principal `index`.
3. Cadastre a URL pública e o nome interno da rota em `feeds/urls.py`.
4. Coloque dados temporários em `feeds/data/<page>.py`, se houver.
5. Crie `templates/pages/<page>/index.html`.
6. Crie `templates/pages/<page>/partials/` se precisar de modais ou blocos reaproveitados.
7. Crie CSS/JS em `static/css/pages/` e `static/js/pages/`, se necessário.
8. Inclua CSS e JS usando os blocos `styles` e `scripts`.
9. Se aparecer na sidebar, adicione o link em `templates/layouts/sidebar.html`.
10. Rode `python manage.py check`.

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
