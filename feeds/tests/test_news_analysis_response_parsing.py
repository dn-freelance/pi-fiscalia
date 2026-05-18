import json
from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import reverse

from feeds.models import NewsItemAnalysis
from feeds.services.news_analysis import _parse_structured_json_response
from feeds.tests.test_news import DummyJsonResponse, build_ai_settings
from feeds.tests.test_news_ai import NewsAnalysisTests


@override_settings(NEWS_AI=build_ai_settings())
class NewsAnalysisResponseParsingTests(NewsAnalysisTests):
    def test_refresh_news_accepts_split_output_text_blocks(self):
        self._create_source()
        feed_response = self._feed_response()
        article_response = self._article_response()

        response_text = json.dumps(
            {
                'items': [
                    {
                        'item_id': '1',
                        'summary': 'Resumo consolidado em partes.',
                        'impact_level': 'medium',
                        'impact_context': 'Impacto moderado.',
                        'keywords': ['ICMS', 'STF'],
                        'importance_score': 82,
                        'effective_date': '2026-12-01',
                        'effective_date_label': 'Dez/2026',
                    }
                ]
            },
            ensure_ascii=False,
        )

        split_index = len(response_text) // 2
        split_payload = {
            'output': [
                {
                    'content': [
                        {'type': 'output_text', 'text': response_text[:split_index]},
                        {'type': 'output_text', 'text': response_text[split_index:]},
                    ]
                }
            ]
        }

        with (
            patch(
                'feeds.services.news_import.requests.get',
                side_effect=self._request_get_side_effect(feed_response, article_response),
            ),
            patch(
                'feeds.services.news_analysis.requests.post',
                return_value=DummyJsonResponse(split_payload),
            ),
        ):
            response = self.client.post(reverse('feeds:refresh_news'), follow=True)

        analysis = NewsItemAnalysis.objects.get()
        self.assertEqual(analysis.status, NewsItemAnalysis.STATUS_COMPLETED)
        self.assertEqual(analysis.summary, 'Resumo consolidado em partes.')
        self.assertContains(response, 'Resumo consolidado em partes.')

    def test_parse_structured_json_response_accepts_markdown_fence(self):
        parsed = _parse_structured_json_response(
            '```json\n{"items":[{"item_id":"1","summary":"ok"}]}\n```'
        )

        self.assertEqual(parsed['items'][0]['item_id'], '1')
        self.assertEqual(parsed['items'][0]['summary'], 'ok')
