from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from feeds.models import NewsImportJob, NewsItem, Source, SourceCategory
from feeds.services.news_import_jobs import run_news_import_job
from feeds.tests.test_news import DummyResponse, build_ai_settings, build_feed


@override_settings(NEWS_AI=build_ai_settings(enabled=False))
class NewsImportProgressTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')

    def test_refresh_news_creates_job_and_redirects_to_progress_page(self):
        with patch('feeds.views.news.start_news_import_job') as mocked_start:
            response = self.client.post(
                reverse('feeds:refresh_news'),
                {
                    'q': 'icms',
                    'source': '12',
                    'status': 'unread',
                    'relevance': 'high',
                    'effective_date_from': '2026-05-01',
                    'effective_date_to': '2026-05-31',
                },
            )

        job = NewsImportJob.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('feeds:refresh_news_progress', args=[job.id]))
        self.assertEqual(job.redirect_query, 'icms')
        self.assertEqual(job.redirect_source, '12')
        self.assertEqual(job.redirect_status, 'unread')
        self.assertEqual(job.redirect_relevance, 'high')
        self.assertEqual(job.redirect_effective_date_from, '2026-05-01')
        self.assertEqual(job.redirect_effective_date_to, '2026-05-31')
        mocked_start.assert_called_once_with(job.id)

    def test_run_news_import_job_updates_job_counters_and_messages(self):
        Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )
        job = NewsImportJob.objects.create()
        feed_response = DummyResponse(
            build_feed(
                [
                    {
                        'title': 'Nova instrução normativa',
                        'link': 'https://example.com/noticia-1',
                        'guid': 'news-1',
                        'published_at': 'Tue, 12 May 2026 12:30:00 GMT',
                        'summary': 'Resumo de teste.',
                    },
                ]
            )
        )

        with patch('feeds.services.news_import.requests.get', return_value=feed_response):
            run_news_import_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, NewsImportJob.STATUS_COMPLETED)
        self.assertEqual(job.current_stage, NewsImportJob.STAGE_COMPLETED)
        self.assertEqual(job.rss_total_sources, 1)
        self.assertEqual(job.rss_processed_sources, 1)
        self.assertEqual(job.imported_created_count, 1)
        self.assertEqual(job.imported_existing_count, 0)
        self.assertEqual(job.analysis_total_items, 1)
        self.assertEqual(job.analysis_processed_items, 1)
        self.assertEqual(NewsItem.objects.count(), 1)
        self.assertTrue(job.result_messages)
        self.assertEqual(job.result_messages[0]['level'], 'success')

    def test_progress_status_view_returns_job_payload(self):
        job = NewsImportJob.objects.create(
            status=NewsImportJob.STATUS_RUNNING,
            current_stage=NewsImportJob.STAGE_RSS,
            stage_title='Importando',
            stage_message='Processando as fontes',
            rss_total_sources=4,
            rss_processed_sources=2,
            analysis_enabled=True,
            analysis_total_items=8,
            analysis_processed_items=3,
        )

        response = self.client.get(reverse('feeds:refresh_news_progress_status', args=[job.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], NewsImportJob.STATUS_RUNNING)
        self.assertEqual(payload['rss']['processed_sources'], 2)
        self.assertEqual(payload['analysis']['processed_items'], 3)
        self.assertFalse(payload['is_finished'])

    def test_finalize_job_adds_messages_and_preserves_filters(self):
        job = NewsImportJob.objects.create(
            status=NewsImportJob.STATUS_COMPLETED,
            current_stage=NewsImportJob.STAGE_COMPLETED,
            redirect_query='stf',
            redirect_source='7',
            redirect_status='unread',
            redirect_relevance='medium',
            redirect_effective_date_from='2026-05-01',
            redirect_effective_date_to='2026-05-31',
            result_messages=[
                {
                    'level': 'success',
                    'text': 'Atualização concluída: 1 nova(s) e 0 já existente(s).',
                }
            ],
        )

        response = self.client.get(reverse('feeds:finalize_refresh_news_job', args=[job.id]), follow=True)

        self.assertRedirects(
            response,
            (
                f"{reverse('feeds:news')}?q=stf&source=7&status=unread&relevance=medium"
                '&effective_date_from=2026-05-01&effective_date_to=2026-05-31'
            ),
        )
        self.assertContains(response, 'Atualização concluída: 1 nova(s) e 0 já existente(s).')
