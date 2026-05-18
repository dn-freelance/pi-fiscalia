from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import reverse

from feeds.models import NewsItem, NewsItemAnalysis
from feeds.tests.test_news import DummyJsonResponse, DummyResponse, build_ai_settings, build_feed
from feeds.tests.test_news_ai import NewsAnalysisTests


@override_settings(NEWS_AI=build_ai_settings())
class NewsAnalysis429Tests(NewsAnalysisTests):
    def test_refresh_news_shows_quota_message_when_openai_reports_insufficient_quota(self):
        self._create_source()
        feed_response = DummyResponse(build_feed([
            {
                'title': 'Noticia 1',
                'link': 'https://example.com/noticias/quota-1',
                'guid': 'ai-quota-1',
                'published_at': 'Tue, 12 May 2026 12:30:00 GMT',
                'summary': 'Resumo 1.',
            },
            {
                'title': 'Noticia 2',
                'link': 'https://example.com/noticias/quota-2',
                'guid': 'ai-quota-2',
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
                return_value=DummyJsonResponse(
                    {
                        'error': {
                            'type': 'insufficient_quota',
                            'code': 'insufficient_quota',
                            'message': 'You exceeded your current quota, please check your plan and billing details.',
                        }
                    },
                    status_code=429,
                ),
            ) as mocked_post,
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertEqual(NewsItem.objects.count(), 2)
        self.assertEqual(NewsItemAnalysis.objects.count(), 0)
        self.assertEqual(mocked_post.call_count, 1)
        self.assertContains(response, 'a API da OpenAI recusou a analise por quota, credito ou orcamento insuficiente.')
        self.assertContains(response, 'Usage, Limits e Billing da organizacao/projeto na plataforma.')
        self.assertIsNone(NewsItem.objects.get(link='https://example.com/noticias/quota-2').analysis_or_none)
