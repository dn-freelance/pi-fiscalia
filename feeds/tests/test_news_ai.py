import json
from io import StringIO
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from feeds.models import NewsItem, NewsItemAnalysis, Source, SourceCategory
from feeds.tests.test_news import (
    DummyJsonResponse,
    DummyResponse,
    build_ai_settings,
    build_article_page,
    build_feed,
    build_openai_analysis_payload,
)


@override_settings(NEWS_AI=build_ai_settings())
class NewsAnalysisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')

    def setUp(self):
        self.client.defaults['HTTP_X_FISCALIA_SYNC_IMPORT'] = '1'

    def _create_source(self, name='Fonte IA', url='https://example.com/ia/rss'):
        return Source.objects.create(
            name=name,
            url=url,
            category=self.federal,
            active=True,
        )

    def _feed_response(
        self,
        title='STF julga inconstitucional cobrança de ICMS sobre software em nuvem',
        link='https://example.com/noticias/stf-icms-saas',
        guid='ai-news-1',
        summary='A decisão do STF impacta a tributação de software em nuvem e a adequação dos Estados.',
        published_at='Tue, 12 May 2026 12:30:00 GMT',
    ):
        return DummyResponse(build_feed([
            {
                'title': title,
                'link': link,
                'guid': guid,
                'published_at': published_at,
                'summary': summary,
            },
        ]))

    def _article_response(self, title='Matéria fiscal', paragraphs=None):
        if paragraphs is None:
            paragraphs = [
                'O Supremo Tribunal Federal decidiu, por maioria, que a cobrança de ICMS sobre licenciamento de software em nuvem é inconstitucional.',
                'A decisão tem efeito vinculante e os Estados devem se adequar no prazo fixado no julgamento.',
                'Empresas e escritórios contábeis precisarão revisar seus procedimentos tributários e acompanhar a data efetiva de aplicação.',
            ]

        return DummyResponse(build_article_page(title, paragraphs))

    def _request_get_side_effect(self, feed_response, article_response):
        def responder(url, *args, **kwargs):
            if url.endswith('/rss'):
                return feed_response

            return article_response

        return responder

    def _batched_post_response(self, summary_prefix='Resumo IA'):
        def responder(*args, **kwargs):
            payload_text = kwargs['json']['input'][1]['content'][0]['text']
            items = json.loads(payload_text.split('\n', 1)[1])
            response_items = []

            for index, item in enumerate(items, start=1):
                response_items.append({
                    'item_id': item['item_id'],
                    'summary': f'{summary_prefix} {index}',
                    'impact_level': 'medium',
                    'impact_context': f'Impacto do item {index}.',
                    'keywords': ['ICMS', f'Item {index}'],
                    'importance_score': 70 + index,
                    'effective_date': '2026-12-01',
                    'effective_date_label': f'Item {index} em Dez/2026',
                })

            return DummyJsonResponse(
                {
                    'output': [
                        {
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': json.dumps({'items': response_items}),
                                }
                            ]
                        }
                    ]
                }
            )

        return responder

    @override_settings(NEWS_AI=build_ai_settings(enabled=False))
    def test_refresh_news_with_ai_disabled_keeps_import_without_analysis(self):
        self._create_source()

        with patch('feeds.services.news_import.requests.get', return_value=self._feed_response()):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        imported_item = NewsItem.objects.get()
        self.assertContains(response, 'Atualização concluída: 1 nova(s) e 0 já existente(s).')
        self.assertIsNone(imported_item.analysis_or_none)

    def test_refresh_news_with_ai_persists_analysis_and_renders_sections(self):
        self._create_source()
        feed_response = self._feed_response()
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse(
                    build_openai_analysis_payload(
                        summary='STF declara inconstitucional ICMS sobre SaaS. Estados têm 180 dias para adequação.',
                        impact_level='high',
                        impact_context='Muito alto para empresas de software.',
                        keywords=['ICMS', 'SaaS', 'Jurisprudência'],
                        importance_score=93,
                        effective_date='2026-09-08',
                        effective_date_label='180 dias após publicação',
                    )
                ),
            ),
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        analysis = NewsItemAnalysis.objects.get()
        self.assertEqual(analysis.status, NewsItemAnalysis.STATUS_COMPLETED)
        self.assertEqual(
            analysis.summary,
            'STF declara inconstitucional ICMS sobre SaaS. Estados têm 180 dias para adequação.',
        )
        self.assertEqual(analysis.impact_level, NewsItemAnalysis.IMPACT_HIGH)
        self.assertEqual(analysis.impact_context, 'Muito alto para empresas de software.')
        self.assertEqual(analysis.keywords, ['ICMS', 'SaaS', 'Jurisprudência'])
        self.assertEqual(analysis.importance_score, 93)
        self.assertEqual(analysis.effective_date_label, '180 dias após publicação')
        self.assertEqual(analysis.effective_date_display, '08/09/2026 • 180 dias após publicação')

        self.assertContains(response, 'Muito alto para empresas de software.')
        self.assertContains(response, 'ICMS')
        self.assertContains(response, 'SaaS')
        self.assertContains(response, 'Score: 93')

        rendered_html = response.content.decode('utf-8')
        self.assertIn('news-ai-summary', rendered_html)
        self.assertIn('news-impact-box', rendered_html)
        self.assertIn('news-keywords-list', rendered_html)
        self.assertIn('Vigência:', rendered_html)
        self.assertIn('08/09/2026', rendered_html)
        self.assertIn('180 dias', rendered_html)

    def test_refresh_news_with_nullable_ai_fields_keeps_layout_without_optional_blocks(self):
        self._create_source()
        feed_response = self._feed_response()
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse(
                    build_openai_analysis_payload(
                        summary=None,
                        impact_level=None,
                        impact_context=None,
                        keywords=[],
                        importance_score=None,
                        effective_date=None,
                        effective_date_label=None,
                    )
                ),
            ),
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        analysis = NewsItemAnalysis.objects.get()
        self.assertEqual(analysis.status, NewsItemAnalysis.STATUS_COMPLETED)
        self.assertEqual(analysis.summary, '')
        self.assertEqual(analysis.impact_level, '')
        self.assertEqual(analysis.impact_context, '')
        self.assertEqual(analysis.keywords, [])
        self.assertIsNone(analysis.importance_score)
        self.assertIsNone(analysis.effective_date)
        self.assertEqual(analysis.effective_date_label, '')

        rendered_html = response.content.decode('utf-8')
        self.assertNotIn('news-ai-summary', rendered_html)
        self.assertNotIn('news-impact-box', rendered_html)
        self.assertNotIn('news-keywords-list', rendered_html)
        self.assertNotIn('Vigência:', rendered_html)
        self.assertNotIn('Score:', rendered_html)

    def test_refresh_news_uses_default_impact_context_when_only_level_is_inferred(self):
        self._create_source()
        feed_response = self._feed_response()
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse(
                    build_openai_analysis_payload(
                        summary='Resumo com baixo impacto.',
                        impact_level='low',
                        impact_context='',
                        keywords=['medicamento'],
                        importance_score=10,
                        effective_date=None,
                        effective_date_label=None,
                    )
                ),
            ),
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        analysis = NewsItemAnalysis.objects.get()
        self.assertEqual(analysis.impact_level, NewsItemAnalysis.IMPACT_LOW)
        self.assertEqual(analysis.impact_context, '')
        self.assertContains(
            response,
            'Baixo impacto fiscal imediato, sem indícios de mudança relevante até o momento.',
        )

    def test_refresh_news_preserves_base_item_when_ai_provider_fails(self):
        self._create_source()
        feed_response = self._feed_response()
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch('feeds.services.news_analysis.requests.post', side_effect=requests.Timeout('timeout')),
        ):
            self.client.post(reverse('feeds:refresh_news'), follow=True)

        imported_item = NewsItem.objects.get()
        analysis = NewsItemAnalysis.objects.get(news_item=imported_item)
        self.assertEqual(imported_item.title, 'STF julga inconstitucional cobrança de ICMS sobre software em nuvem')
        self.assertEqual(analysis.status, NewsItemAnalysis.STATUS_FAILED)
        self.assertIn('falha na consulta ao provider', analysis.error_message)

    def test_refresh_news_preserves_previous_analysis_when_new_attempt_fails(self):
        self._create_source()
        feed_response = self._feed_response()
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse(
                    build_openai_analysis_payload(
                        summary='Resumo anterior persistido.',
                        impact_level='medium',
                        impact_context='Impacto moderado para contribuintes.',
                        keywords=['ICMS', 'STF'],
                        importance_score=81,
                        effective_date='2026-08-01',
                        effective_date_label='01/08/2026',
                    )
                ),
            ),
        ):
            self.client.post(reverse('feeds:refresh_news'))

        analysis = NewsItemAnalysis.objects.get()
        analysis.pipeline_version = 'v0'
        analysis.save(update_fields=['pipeline_version', 'updated_at'])

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch('feeds.services.news_analysis.requests.post', side_effect=requests.Timeout('timeout')),
        ):
            self.client.post(reverse('feeds:refresh_news'))

        analysis.refresh_from_db()
        self.assertEqual(analysis.status, NewsItemAnalysis.STATUS_COMPLETED)
        self.assertEqual(analysis.summary, 'Resumo anterior persistido.')
        self.assertEqual(analysis.impact_level, NewsItemAnalysis.IMPACT_MEDIUM)
        self.assertEqual(analysis.keywords, ['ICMS', 'STF'])
        self.assertEqual(analysis.importance_score, 81)
        self.assertEqual(analysis.effective_date_label, '01/08/2026')
        self.assertIn('falha na consulta ao provider', analysis.error_message)

    def test_refresh_news_batches_multiple_news_in_single_provider_call(self):
        self._create_source()
        feed_response = DummyResponse(build_feed([
            {
                'title': 'Notícia em lote 1',
                'link': 'https://example.com/noticias/lote-1',
                'guid': 'ai-batch-1',
                'published_at': 'Tue, 12 May 2026 12:30:00 GMT',
                'summary': 'Resumo do lote 1.',
            },
            {
                'title': 'Notícia em lote 2',
                'link': 'https://example.com/noticias/lote-2',
                'guid': 'ai-batch-2',
                'published_at': 'Tue, 12 May 2026 13:30:00 GMT',
                'summary': 'Resumo do lote 2.',
            },
        ]))
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                side_effect=self._batched_post_response(),
            ) as mocked_post,
        ):
            self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertEqual(mocked_post.call_count, 1)
        self.assertEqual(NewsItemAnalysis.objects.count(), 2)
        self.assertTrue(NewsItemAnalysis.objects.filter(summary='Resumo IA 1').exists())
        self.assertTrue(NewsItemAnalysis.objects.filter(summary='Resumo IA 2').exists())

    def test_refresh_news_halts_ai_after_provider_rate_limit(self):
        self._create_source()
        feed_response = DummyResponse(build_feed([
            {
                'title': 'Notícia 1',
                'link': 'https://example.com/noticias/1',
                'guid': 'ai-rate-1',
                'published_at': 'Tue, 12 May 2026 12:30:00 GMT',
                'summary': 'Resumo 1.',
            },
            {
                'title': 'Notícia 2',
                'link': 'https://example.com/noticias/2',
                'guid': 'ai-rate-2',
                'published_at': 'Tue, 12 May 2026 13:30:00 GMT',
                'summary': 'Resumo 2.',
            },
        ]))
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse({}, status_code=429, headers={'Retry-After': '60'}),
            ) as mocked_post,
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertEqual(NewsItem.objects.count(), 2)
        self.assertEqual(NewsItemAnalysis.objects.count(), 0)
        self.assertEqual(mocked_post.call_count, 1)
        self.assertContains(
            response,
            'a API da OpenAI bloqueou temporariamente novas análises por limite de requisições ou tokens.',
        )
        self.assertContains(response, '2 notícia(s) foram importadas sem análise.')
        self.assertContains(response, '60 segundo(s)')
        self.assertIsNone(NewsItem.objects.get(link='https://example.com/noticias/2').analysis_or_none)

    def test_refresh_news_keeps_news_when_article_page_cannot_be_extracted(self):
        self._create_source()
        feed_response = self._feed_response()
        article_response = DummyResponse(
            'arquivo pdf',
            headers={'Content-Type': 'application/pdf'},
        )

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch('feeds.services.news_analysis.requests.post') as mocked_post,
        ):
            self.client.post(reverse('feeds:refresh_news'), follow=True)

        imported_item = NewsItem.objects.get()
        analysis = NewsItemAnalysis.objects.get(news_item=imported_item)
        mocked_post.assert_not_called()
        self.assertEqual(analysis.status, NewsItemAnalysis.STATUS_FAILED)
        self.assertIn('não é uma página HTML suportada', analysis.error_message)

    def test_refresh_news_skips_reprocessing_when_analysis_input_is_current(self):
        self._create_source()
        feed_response = self._feed_response()
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse(build_openai_analysis_payload()),
            ),
        ):
            self.client.post(reverse('feeds:refresh_news'))

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch('feeds.services.news_analysis.requests.post') as mocked_post,
        ):
            self.client.post(reverse('feeds:refresh_news'))

        mocked_post.assert_not_called()
        self.assertEqual(NewsItemAnalysis.objects.count(), 1)

    def test_backfill_news_analysis_processes_pending_news_items(self):
        source = self._create_source()
        news_item = NewsItem.objects.create(
            source=source,
            title='Atualização relevante de ICMS',
            summary='Resumo do RSS.',
            link='https://example.com/noticias/atualizacao-icms',
            external_id='backfill-1',
            dedupe_key='backfill-1',
            published_at=timezone.make_aware(timezone.datetime(2026, 5, 12, 9, 15)),
        )
        output = StringIO()

        with (
            patch('feeds.services.news_analysis.requests.get', return_value=self._article_response()),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse(
                    build_openai_analysis_payload(
                        summary='Resumo gerado no backfill.',
                        impact_level='low',
                        impact_context='Baixo impacto imediato.',
                        keywords=['ICMS'],
                        importance_score=42,
                        effective_date='2026-12-01',
                        effective_date_label='Dez/2026',
                    )
                ),
            ),
        ):
            call_command('backfill_news_analysis', stdout=output)

        analysis = NewsItemAnalysis.objects.get(news_item=news_item)
        self.assertEqual(analysis.status, NewsItemAnalysis.STATUS_COMPLETED)
        self.assertEqual(analysis.summary, 'Resumo gerado no backfill.')
        self.assertIn('1 análise(s) atualizada(s)', output.getvalue())
