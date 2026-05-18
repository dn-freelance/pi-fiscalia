from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import reverse

from feeds.models import NewsItem, NewsItemAnalysis
from feeds.tests.test_news import DummyJsonResponse, build_ai_settings
from feeds.tests.test_news_ai import NewsAnalysisTests


@override_settings(NEWS_AI=build_ai_settings())
class NewsAnalysisProviderHttpErrorTests(NewsAnalysisTests):
    def test_provider_http_error_does_not_become_feed_fetch_error(self):
        self._create_source()
        feed_response = self._feed_response(summary='Resumo da notícia.')
        article_response = self._article_response()

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse({}, status_code=404),
            ),
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        self.assertEqual(NewsItem.objects.count(), 1)
        analysis = NewsItemAnalysis.objects.get()
        self.assertEqual(analysis.status, NewsItemAnalysis.STATUS_FAILED)
        self.assertIn('falha na consulta ao provider: HTTP 404', analysis.error_message)
        self.assertContains(response, 'Atualização concluída: 1 nova(s) e 0 já existente(s).')
        self.assertNotContains(response, 'Fonte IA: falha ao buscar o feed RSS')
