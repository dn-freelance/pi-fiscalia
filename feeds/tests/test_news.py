import json
from datetime import timedelta
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from feeds.models import NewsItem, NewsItemAnalysis, Source, SourceCategory


class DummyResponse:
    def __init__(self, content, status_code=200, url='https://example.com/rss', headers=None):
        self.text = content
        self.content = content.encode('utf-8')
        self.status_code = status_code
        self.url = url
        self.headers = headers or {'Content-Type': 'text/html; charset=utf-8'}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}')


class DummyJsonResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}')


def build_feed(items):
    xml_items = []
    for item in items:
        xml_items.append(
            f'''
            <item>
                <title>{item["title"]}</title>
                <link>{item["link"]}</link>
                <guid>{item["guid"]}</guid>
                <pubDate>{item["published_at"]}</pubDate>
                <description>{item["summary"]}</description>
            </item>
            '''
        )

    return f'''
    <rss version="2.0">
        <channel>
            <title>Feed de Teste</title>
            {"".join(xml_items)}
        </channel>
    </rss>
    '''


def build_atom_feed(entries):
    xml_entries = []
    for entry in entries:
        xml_entries.append(
            f'''
            <entry>
                <id>{entry["id"]}</id>
                <title type="text">{entry["title"]}</title>
                <updated>{entry["updated_at"]}</updated>
                <link rel="alternate" href="{entry["link"]}" />
                <content type="html">{entry["summary"]}</content>
            </entry>
            '''
        )

    return f'''
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title type="text">Feed Atom de Teste</title>
        {"".join(xml_entries)}
    </feed>
    '''


def build_article_page(title, paragraphs):
    paragraph_html = ''.join(f'<p>{paragraph}</p>' for paragraph in paragraphs)
    return f'''
    <html>
        <head><title>{title}</title></head>
        <body>
            <article>
                <h1>{title}</h1>
                {paragraph_html}
            </article>
        </body>
    </html>
    '''


def build_openai_analysis_payload(summary='Resumo IA', impact_level='high', impact_context='Impacto relevante.', keywords=None, importance_score=93, effective_date='2026-12-01', effective_date_label=''):
    if keywords is None:
        keywords = ['ICMS', 'SaaS', 'Jurisprudência']

    return {
        'output': [
            {
                'content': [
                    {
                        'type': 'output_text',
                        'text': (
                            '{'
                            f'"summary": {json.dumps(summary)}, '
                            f'"impact_level": {json.dumps(impact_level)}, '
                            f'"impact_context": {json.dumps(impact_context)}, '
                            f'"keywords": {json.dumps(keywords)}, '
                            f'"importance_score": {json.dumps(importance_score)}, '
                            f'"effective_date": {json.dumps(effective_date)}, '
                            f'"effective_date_label": {json.dumps(effective_date_label)}'
                            '}'
                        ),
                    }
                ]
            }
        ]
    }


def build_ai_settings(enabled=True):
    return {
        'ENABLED': enabled,
        'PROVIDER': 'openai',
        'MODEL': 'gpt-4o-mini',
        'TIMEOUT_SECONDS': 15,
        'PIPELINE_VERSION': 'v1',
        'BATCH_SIZE': 5,
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_BASE_URL': 'https://api.openai.com/v1',
        'OPENAI_ORG_ID': '',
        'OPENAI_PROJECT': '',
    }


def build_plone_structural_feed():
    return '''
    <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
        <channel>
            <title>Notícias</title>
            <link>https://www.gov.br/receitafederal/pt-br/assuntos/noticias</link>
            <item>
                <title>2026</title>
                <description></description>
                <pubDate>Fri, 02 Jan 2026 07:25:17 -0300</pubDate>
                <guid>https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026</guid>
                <dc:type>Folder</dc:type>
            </item>
            <item>
                <title>Sped</title>
                <description></description>
                <pubDate>Fri, 20 Mar 2026 10:05:18 -0300</pubDate>
                <guid>https://www.gov.br/receitafederal/pt-br/assuntos/noticias/sped</guid>
                <dc:type>Folder</dc:type>
            </item>
            <item>
                <title>Foz do Iguaçu</title>
                <description></description>
                <pubDate>Mon, 29 Dec 2025 10:21:23 -0300</pubDate>
                <guid>https://www.gov.br/receitafederal/pt-br/assuntos/noticias/parana-apreensao.png/view</guid>
                <dc:type>Image</dc:type>
            </item>
        </channel>
    </rss>
    '''


def build_gov_br_news_listing():
    return '''
    <ul>
        <li>
            <div class="conteudo">
                <div class="subtitulo-noticia">Serviços</div>
                <h2 class="titulo">
                    <a href="https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/maio/microempreendedor-individual-mei-tem-ate-31-de-maio-para-entregar-declaracao-anual">
                        Microempreendedor Individual (MEI) tem até 31 de maio para entregar declaração anual
                    </a>
                </h2>
                <span class="descricao">
                    <span class="data">11/05/2026</span>
                    <span> - </span>
                    A DASN-Simei referente ao ano-calendário de 2025 deve ser enviada por todos os Microempreendedores.
                </span>
            </div>
        </li>
        <li>
            <div class="conteudo">
                <div class="subtitulo-noticia">Institucional</div>
                <h2 class="titulo">
                    <a href="https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/maio/nota-de-esclarecimento-e-orientacao-sobre-o-painel-receita-e-a-protecao-das-informacoes">
                        Nota de esclarecimento e orientação sobre o Painel Receita e a proteção das informações
                    </a>
                </h2>
                <span class="descricao">
                    <span class="data">05/05/2026</span>
                    <span> - </span>
                    A Receita Federal esclarece os critérios de segurança adotados no Painel Receita.
                </span>
            </div>
        </li>
    </ul>
    '''


def build_gov_br_article_page(published_at):
    return f'''
    <div class="documentByLine" id="plone-document-byline">
        <span class="documentPublished">
            <span>Publicado em</span>
            <span class="value">{published_at}</span>
        </span>
    </div>
    '''


def build_gov_br_response_map():
    return {
        'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS': DummyResponse(
            build_plone_structural_feed(),
            url='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS',
        ),
        'https://www.gov.br/receitafederal/pt-br/assuntos/noticias': DummyResponse(
            build_gov_br_news_listing(),
            url='https://www.gov.br/receitafederal/pt-br/assuntos/noticias',
        ),
        'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/maio/microempreendedor-individual-mei-tem-ate-31-de-maio-para-entregar-declaracao-anual': DummyResponse(
            build_gov_br_article_page('11/05/2026 10h46'),
        ),
        'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/maio/nota-de-esclarecimento-e-orientacao-sobre-o-painel-receita-e-a-protecao-das-informacoes': DummyResponse(
            build_gov_br_article_page('05/05/2026 08h15'),
        ),
    }


@override_settings(NEWS_AI=build_ai_settings(enabled=False))
class NewsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')
        cls.estadual = SourceCategory.objects.get(name='Estadual')

    def setUp(self):
        self.client.defaults['HTTP_X_FISCALIA_SYNC_IMPORT'] = '1'

    def test_refresh_news_imports_items_without_duplicates(self):
        Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )

        response_content = DummyResponse(build_feed([
            {
                'title': 'STJ afasta limite de 20 salários mínimos',
                'link': 'https://example.com/noticia-1',
                'guid': 'news-1',
                'published_at': 'Tue, 12 May 2026 12:30:00 GMT',
                'summary': 'Resumo do item.',
            },
        ]))

        with patch('feeds.services.news_import.requests.get', return_value=response_content):
            first_response = self.client.post(reverse('feeds:refresh_news'), follow=True)
            second_response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertEqual(NewsItem.objects.count(), 1)
        self.assertContains(first_response, 'Atualização concluída: 1 nova(s) e 0 já existente(s).')
        self.assertContains(second_response, 'Atualização concluída: 0 nova(s) e 1 já existente(s).')

    def test_refresh_news_imports_atom_feeds_with_html_content(self):
        Source.objects.create(
            name='Banco Central',
            url='https://example.com/bcb/atom',
            category=self.federal,
            active=True,
        )

        response_content = DummyResponse(build_atom_feed([
            {
                'id': 'sitefeeds_21118',
                'title': 'LiveBC: Mercado imobiliário',
                'updated_at': '2026-05-08T17:14:34-03:00',
                'link': 'https://www.bcb.gov.br/detalhenoticia/21118/noticia',
                'summary': '&lt;p&gt;Na LiveBC de segunda-feira, o BC apresenta as recentes mudanças no crédito imobiliário.&lt;/p&gt;',
            },
        ]))

        with patch('feeds.services.news_import.requests.get', return_value=response_content):
            self.client.post(reverse('feeds:refresh_news'))

        imported_item = NewsItem.objects.get()
        self.assertEqual(imported_item.title, 'LiveBC: Mercado imobiliário')
        self.assertEqual(imported_item.link, 'https://www.bcb.gov.br/detalhenoticia/21118/noticia')
        self.assertIn('crédito imobiliário', imported_item.summary)
        localized_published_at = timezone.localtime(imported_item.published_at)
        self.assertEqual(localized_published_at.hour, 17)
        self.assertEqual(localized_published_at.minute, 14)

    def test_refresh_news_uses_only_active_sources(self):
        active_source = Source.objects.create(
            name='Fonte Ativa',
            url='https://example.com/ativa/rss',
            category=self.federal,
            active=True,
        )
        Source.objects.create(
            name='Fonte Inativa',
            url='https://example.com/inativa/rss',
            category=self.estadual,
            active=False,
        )

        response_content = DummyResponse(build_feed([
            {
                'title': 'Atualização da fonte ativa',
                'link': 'https://example.com/noticia-ativa',
                'guid': 'active-news-1',
                'published_at': 'Tue, 12 May 2026 10:30:00 GMT',
                'summary': 'Notícia de teste.',
            },
        ]))

        with patch('feeds.services.news_import.requests.get', return_value=response_content) as mocked_get:
            self.client.post(reverse('feeds:refresh_news'))

        self.assertEqual(mocked_get.call_count, 1)
        self.assertEqual(mocked_get.call_args[0][0], active_source.url)
        self.assertEqual(NewsItem.objects.get().source, active_source)

    def test_refresh_news_cleans_generic_forum_boilerplate_from_summary(self):
        Source.objects.create(
            name='Contábeis',
            url='https://example.com/forum/rss',
            category=self.federal,
            active=True,
        )

        response_content = DummyResponse(build_feed([
            {
                'title': 'PIS e COFINS',
                'link': 'https://example.com/forum/pis-cofins',
                'guid': 'forum-1',
                'published_at': 'Tue, 12 May 2026 11:57:15 -0300',
                'summary': (
                    'Boa tarde! Tenho uma dúvida tributária importante.'
                    '<p>0 Respostas</p>'
                    '<p>Leia mais em <a href="https://example.com/forum/pis-cofins">https://example.com/forum/pis-cofins</a></p>'
                ),
            },
        ]))

        with patch('feeds.services.news_import.requests.get', return_value=response_content):
            self.client.post(reverse('feeds:refresh_news'))

        imported_item = NewsItem.objects.get()
        self.assertEqual(imported_item.summary, 'Boa tarde! Tenho uma dúvida tributária importante.')

    def test_refresh_news_skips_failed_item_without_interrupting_other_news(self):
        Source.objects.create(
            name='Fonte Parcial',
            url='https://example.com/parcial/rss',
            category=self.federal,
            active=True,
        )

        response_content = DummyResponse(build_feed([
            {
                'title': 'Notícia íntegra',
                'link': 'https://example.com/noticia-ok',
                'guid': 'partial-1',
                'published_at': 'Tue, 12 May 2026 12:00:00 GMT',
                'summary': 'Resumo da notícia íntegra.',
            },
            {
                'title': 'Notícia com falha',
                'link': 'https://example.com/noticia-falha',
                'guid': 'partial-2',
                'published_at': 'Tue, 12 May 2026 12:05:00 GMT',
                'summary': 'Resumo da notícia com falha.',
            },
        ]))
        original_get_or_create = NewsItem.objects.get_or_create
        call_counter = {'count': 0}

        def flaky_get_or_create(*args, **kwargs):
            call_counter['count'] += 1
            if call_counter['count'] == 2:
                raise RuntimeError('falha simulada ao persistir item')

            return original_get_or_create(*args, **kwargs)

        with patch('feeds.services.news_import.requests.get', return_value=response_content):
            with patch('feeds.services.news_import.NewsItem.objects.get_or_create', side_effect=flaky_get_or_create):
                response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertEqual(NewsItem.objects.count(), 1)
        self.assertTrue(NewsItem.objects.filter(title='Notícia íntegra').exists())
        self.assertFalse(NewsItem.objects.filter(title='Notícia com falha').exists())
        self.assertContains(response, 'item(ns) ignorado(s) por dados incompletos ou erro no processamento')

    def test_refresh_news_reports_error_when_no_item_can_be_imported_safely(self):
        Source.objects.create(
            name='Fonte Inválida',
            url='https://example.com/invalida/rss',
            category=self.federal,
            active=True,
        )

        response_content = DummyResponse(build_feed([
            {
                'title': '',
                'link': '',
                'guid': 'invalid-1',
                'published_at': 'Tue, 12 May 2026 12:00:00 GMT',
                'summary': 'Sem dados essenciais.',
            },
        ]))

        with patch('feeds.services.news_import.requests.get', return_value=response_content):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertEqual(NewsItem.objects.count(), 0)
        self.assertContains(response, 'Nenhum informativo')
        self.assertContains(response, 'nenhum item')

    def test_news_index_filters_by_relevance_using_ai_impact_level(self):
        source = Source.objects.create(
            name='Fonte Fiscal',
            url='https://example.com/fiscal/rss',
            category=self.federal,
            active=True,
        )
        high_item = NewsItem.objects.create(
            source=source,
            title='Mudança relevante de ICMS',
            summary='Resumo A',
            link='https://example.com/a',
            external_id='a',
            dedupe_key='a',
        )
        low_item = NewsItem.objects.create(
            source=source,
            title='Nota institucional',
            summary='Resumo B',
            link='https://example.com/b',
            external_id='b',
            dedupe_key='b',
        )
        NewsItemAnalysis.objects.create(
            news_item=high_item,
            status=NewsItemAnalysis.STATUS_COMPLETED,
            impact_level=NewsItemAnalysis.IMPACT_HIGH,
        )
        NewsItemAnalysis.objects.create(
            news_item=low_item,
            status=NewsItemAnalysis.STATUS_COMPLETED,
            impact_level=NewsItemAnalysis.IMPACT_LOW,
        )

        response = self.client.get(reverse('feeds:news'), {'relevance': 'high'})

        self.assertContains(response, 'Mudança relevante de ICMS')
        self.assertNotContains(response, 'Nota institucional')

    def test_delete_source_removes_news_items(self):
        source = Source.objects.create(
            name='Fonte com notícias',
            url='https://example.com/fonte/rss',
            category=self.federal,
        )
        NewsItem.objects.create(
            source=source,
            title='Notícia vinculada',
            summary='Resumo',
            link='https://example.com/noticia-vinculada',
            external_id='news-linked-1',
            dedupe_key='dedupe-linked-1',
        )

        source.delete()

        self.assertEqual(NewsItem.objects.count(), 0)

    def test_refresh_news_continues_when_one_source_fails(self):
        Source.objects.create(
            name='A Fonte com erro',
            url='https://example.com/error/rss',
            category=self.federal,
            active=True,
        )
        successful_source = Source.objects.create(
            name='B Fonte com sucesso',
            url='https://example.com/success/rss',
            category=self.estadual,
            active=True,
        )

        response_content = DummyResponse(build_feed([
            {
                'title': 'Notícia importada após erro em outra fonte',
                'link': 'https://example.com/noticia-ok',
                'guid': 'success-1',
                'published_at': 'Tue, 12 May 2026 09:15:00 GMT',
                'summary': 'Importação deve continuar.',
            },
        ]))

        with patch(
            'feeds.services.news_import.requests.get',
            side_effect=[requests.RequestException('boom'), response_content],
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertEqual(NewsItem.objects.count(), 1)
        self.assertEqual(NewsItem.objects.get().source, successful_source)
        self.assertContains(response, 'Atualização concluída: 1 nova(s) e 0 já existente(s).')
        self.assertContains(response, '1 fonte(s) com erro:')

    def test_news_filters_by_query_source_and_status(self):
        source_a = Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita-federal/rss',
            category=self.federal,
        )
        source_b = Source.objects.create(
            name='SEFAZ-SP',
            url='https://example.com/sefaz-sp/rss',
            category=self.estadual,
        )

        unread_item = NewsItem.objects.create(
            source=source_a,
            title='ICMS para software em nuvem',
            summary='Discussão sobre tributação estadual.',
            link='https://example.com/icms-nuvem',
            external_id='icms-1',
            dedupe_key='dedupe-icms-1',
            is_read=False,
        )
        read_item = NewsItem.objects.create(
            source=source_b,
            title='PIS/COFINS na importação',
            summary='Créditos tributários em operações internacionais.',
            link='https://example.com/piscofins-importacao',
            external_id='pis-1',
            dedupe_key='dedupe-pis-1',
            is_read=True,
        )

        response = self.client.get(reverse('feeds:news'), {'q': 'ICMS'})
        self.assertEqual(list(response.context['news_items']), [unread_item])

        response = self.client.get(reverse('feeds:news'), {'source': source_b.id})
        self.assertEqual(list(response.context['news_items']), [read_item])

        response = self.client.get(reverse('feeds:news'), {'status': 'unread'})
        self.assertEqual(list(response.context['news_items']), [unread_item])

        response = self.client.get(reverse('feeds:news'), {'status': 'read'})
        self.assertEqual(list(response.context['news_items']), [read_item])

    def test_toggle_news_read_updates_status_and_shows_message(self):
        source = Source.objects.create(
            name='Fonte Toggle',
            url='https://example.com/toggle/rss',
            category=self.federal,
        )
        item = NewsItem.objects.create(
            source=source,
            title='Notícia para alternar leitura',
            summary='Resumo curto.',
            link='https://example.com/toggle-news',
            external_id='toggle-1',
            dedupe_key='dedupe-toggle-1',
            is_read=False,
        )

        response = self.client.post(
            reverse('feeds:toggle_news_read', args=[item.id]),
            {'q': 'toggle', 'source': str(source.id), 'status': 'unread'},
            follow=True,
        )

        item.refresh_from_db()
        self.assertTrue(item.is_read)
        self.assertEqual(
            response.redirect_chain[0][0],
            f"{reverse('feeds:news')}?q=toggle&source={source.id}&status=unread",
        )
        self.assertContains(response, 'Informativo marcado como lido.')

    def test_bulk_update_news_read_marks_selected_items_and_preserves_filters(self):
        source = Source.objects.create(
            name='Fonte Lote',
            url='https://example.com/lote/rss',
            category=self.federal,
        )
        selected_item = NewsItem.objects.create(
            source=source,
            title='Selecionado para leitura',
            summary='Resumo selecionado.',
            link='https://example.com/bulk-read-1',
            external_id='bulk-read-1',
            dedupe_key='dedupe-bulk-read-1',
            is_read=False,
        )
        untouched_item = NewsItem.objects.create(
            source=source,
            title='Não selecionado',
            summary='Resumo não selecionado.',
            link='https://example.com/bulk-read-2',
            external_id='bulk-read-2',
            dedupe_key='dedupe-bulk-read-2',
            is_read=False,
        )

        response = self.client.post(
            reverse('feeds:bulk_update_news_read'),
            {
                'bulk_action': 'mark_read',
                'selected_news_ids': [str(selected_item.id)],
                'q': 'lote',
                'source': str(source.id),
                'status': 'unread',
            },
            follow=True,
        )

        selected_item.refresh_from_db()
        untouched_item.refresh_from_db()
        self.assertTrue(selected_item.is_read)
        self.assertFalse(untouched_item.is_read)
        self.assertEqual(
            response.redirect_chain[0][0],
            f"{reverse('feeds:news')}?q=lote&source={source.id}&status=unread",
        )
        self.assertContains(response, '1 informativo(s) marcado(s) como lidos.')

    def test_bulk_update_news_read_marks_selected_items_as_unread(self):
        source = Source.objects.create(
            name='Fonte Lote Não Lido',
            url='https://example.com/lote-unread/rss',
            category=self.federal,
        )
        selected_item = NewsItem.objects.create(
            source=source,
            title='Selecionado para não lido',
            summary='Resumo selecionado.',
            link='https://example.com/bulk-unread-1',
            external_id='bulk-unread-1',
            dedupe_key='dedupe-bulk-unread-1',
            is_read=True,
        )

        response = self.client.post(
            reverse('feeds:bulk_update_news_read'),
            {
                'bulk_action': 'mark_unread',
                'selected_news_ids': [str(selected_item.id)],
            },
            follow=True,
        )

        selected_item.refresh_from_db()
        self.assertFalse(selected_item.is_read)
        self.assertContains(response, '1 informativo(s) marcado(s) como não lidos.')

    def test_bulk_update_news_read_requires_selection(self):
        response = self.client.post(
            reverse('feeds:bulk_update_news_read'),
            {'bulk_action': 'mark_read'},
            follow=True,
        )

        self.assertContains(response, 'Selecione pelo menos um informativo para aplicar a ação em lote.')

    def test_news_index_orders_by_published_at_with_created_at_fallback(self):
        source = Source.objects.create(
            name='Fonte Ordenação',
            url='https://example.com/ordenacao/rss',
            category=self.federal,
        )
        older_published = NewsItem.objects.create(
            source=source,
            title='Publicação antiga',
            summary='Resumo antigo.',
            link='https://example.com/old-news',
            external_id='old-1',
            dedupe_key='dedupe-old-1',
            published_at=timezone.now() - timedelta(days=3),
        )
        fallback_created = NewsItem.objects.create(
            source=source,
            title='Sem data publicada',
            summary='Usa created_at como fallback.',
            link='https://example.com/fallback-news',
            external_id='fallback-1',
            dedupe_key='dedupe-fallback-1',
            published_at=None,
        )
        newer_published = NewsItem.objects.create(
            source=source,
            title='Publicação mais recente',
            summary='Resumo recente.',
            link='https://example.com/new-news',
            external_id='new-1',
            dedupe_key='dedupe-new-1',
            published_at=timezone.now() - timedelta(hours=2),
        )

        response = self.client.get(reverse('feeds:news'))

        self.assertEqual(
            list(response.context['news_items']),
            [fallback_created, newer_published, older_published],
        )

    def test_news_index_renders_date_in_prototype_format(self):
        source = Source.objects.create(
            name='Fonte Data',
            url='https://example.com/data/rss',
            category=self.federal,
        )
        NewsItem.objects.create(
            source=source,
            title='Notícia com data formatada',
            summary='Resumo.',
            link='https://example.com/date-news',
            external_id='date-1',
            dedupe_key='dedupe-date-1',
            published_at=timezone.make_aware(timezone.datetime(2026, 3, 18, 13, 25)),
        )

        response = self.client.get(reverse('feeds:news'))

        self.assertContains(response, '18 DE MAR, 2026 ÀS 13:25')

    def test_refresh_news_falls_back_to_gov_br_listing_when_feed_is_structural(self):
        source = Source.objects.create(
            name='Receita Federal',
            url='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS',
            category=self.federal,
            active=True,
        )
        responses_by_url = build_gov_br_response_map()

        with patch(
            'feeds.services.news_import.requests.get',
            side_effect=lambda url, **kwargs: responses_by_url[url],
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertContains(response, 'Atualização concluída: 2 nova(s) e 0 já existente(s).')
        self.assertEqual(NewsItem.objects.count(), 2)
        self.assertFalse(NewsItem.objects.filter(title__in=['2026', 'Sped', 'Foz do Iguaçu']).exists())

        imported_item = NewsItem.objects.get(
            link='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/maio/microempreendedor-individual-mei-tem-ate-31-de-maio-para-entregar-declaracao-anual'
        )
        self.assertEqual(
            imported_item.title,
            'Microempreendedor Individual (MEI) tem até 31 de maio para entregar declaração anual',
        )
        self.assertIn('Microempreendedores', imported_item.summary)
        self.assertEqual(imported_item.source, source)
        localized_published_at = timezone.localtime(imported_item.published_at)
        self.assertEqual(localized_published_at.hour, 10)
        self.assertEqual(localized_published_at.minute, 46)

    def test_refresh_news_falls_back_to_gov_br_listing_when_feed_request_fails(self):
        source = Source.objects.create(
            name='Receita Federal',
            url='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS',
            category=self.federal,
            active=True,
        )
        responses_by_url = build_gov_br_response_map()
        responses_by_url['https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS'] = DummyResponse(
            'forbidden',
            status_code=403,
            url='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS',
        )

        with patch(
            'feeds.services.news_import.requests.get',
            side_effect=lambda url, **kwargs: responses_by_url[url],
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertContains(response, 'Atualização concluída: 2 nova(s) e 0 já existente(s).')
        self.assertNotContains(response, 'Receita Federal: falha ao buscar o feed RSS')
        self.assertEqual(NewsItem.objects.filter(source=source).count(), 2)

    def test_refresh_news_removes_bad_structural_items_when_gov_br_fallback_runs(self):
        source = Source.objects.create(
            name='Receita Federal',
            url='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS',
            category=self.federal,
            active=True,
        )
        responses_by_url = build_gov_br_response_map()
        NewsItem.objects.create(
            source=source,
            title='Sped',
            summary='',
            link='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/sped',
            external_id='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/sped',
            dedupe_key='legacy-sped-item',
        )

        with patch(
            'feeds.services.news_import.requests.get',
            side_effect=lambda url, **kwargs: responses_by_url[url],
        ):
            self.client.post(reverse('feeds:refresh_news'))

        self.assertFalse(NewsItem.objects.filter(link='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/sped').exists())
        self.assertTrue(
            NewsItem.objects.filter(
                link='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/maio/microempreendedor-individual-mei-tem-ate-31-de-maio-para-entregar-declaracao-anual'
            ).exists()
        )

    def test_refresh_news_keeps_existing_items_when_gov_br_listing_cannot_be_interpreted(self):
        source = Source.objects.create(
            name='Receita Federal',
            url='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS',
            category=self.federal,
            active=True,
        )
        NewsItem.objects.create(
            source=source,
            title='Sped',
            summary='',
            link='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/sped',
            external_id='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/sped',
            dedupe_key='legacy-sped-item',
        )
        responses_by_url = build_gov_br_response_map()
        responses_by_url['https://www.gov.br/receitafederal/pt-br/assuntos/noticias'] = DummyResponse(
            '<html><body>sem cards de notícias</body></html>',
            url='https://www.gov.br/receitafederal/pt-br/assuntos/noticias',
        )

        with patch(
            'feeds.services.news_import.requests.get',
            side_effect=lambda url, **kwargs: responses_by_url[url],
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertTrue(NewsItem.objects.filter(link='https://www.gov.br/receitafederal/pt-br/assuntos/noticias/sped').exists())
        self.assertContains(response, 'Receita Federal: o feed é estrutural e a página de notícias não pôde ser interpretada')
