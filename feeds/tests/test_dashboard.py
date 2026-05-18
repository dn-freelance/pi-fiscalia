from calendar import monthrange
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from feeds.models import DashboardWeeklySummary, NewsItem, NewsItemAnalysis, Source, SourceCategory
from feeds.tests.test_news import DummyResponse, build_ai_settings, build_feed


@override_settings(NEWS_AI=build_ai_settings(enabled=False))
class DashboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')

    def setUp(self):
        self.client.defaults['HTTP_X_FISCALIA_SYNC_IMPORT'] = '1'

    def test_dashboard_reads_metrics_topics_and_principal_change_from_ai_fields(self):
        source = Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )

        current_date = timezone.localdate()
        future_effective_date = current_date + timedelta(days=2)
        month_effective_date = current_date
        expected_effective_this_month_count = sum(
            1
            for date_value in [future_effective_date, month_effective_date]
            if date_value.month == current_date.month and date_value.year == current_date.year
        )

        principal_item = NewsItem.objects.create(
            source=source,
            title='Mudança relevante de ICMS para software',
            summary='Resumo do item principal.',
            link='https://example.com/noticia-principal',
            external_id='news-principal',
            dedupe_key='news-principal',
            published_at=timezone.now() - timedelta(hours=2),
            is_read=False,
        )
        month_item = NewsItem.objects.create(
            source=source,
            title='Nova regra de NCM com vigência no mês',
            summary='Resumo do item mensal.',
            link='https://example.com/noticia-mensal',
            external_id='news-month',
            dedupe_key='news-month',
            published_at=timezone.now() - timedelta(days=1),
            is_read=True,
        )
        low_item = NewsItem.objects.create(
            source=source,
            title='Comunicado institucional',
            summary='Resumo institucional.',
            link='https://example.com/noticia-low',
            external_id='news-low',
            dedupe_key='news-low',
            published_at=timezone.now() - timedelta(days=3),
            is_read=False,
        )

        NewsItemAnalysis.objects.create(
            news_item=principal_item,
            status=NewsItemAnalysis.STATUS_COMPLETED,
            summary='Resumo IA do principal.',
            impact_level=NewsItemAnalysis.IMPACT_HIGH,
            keywords=['ICMS', 'Software'],
            importance_score=97,
            effective_date=future_effective_date,
            effective_date_label=future_effective_date.strftime('%d/%m/%Y'),
        )
        NewsItemAnalysis.objects.create(
            news_item=month_item,
            status=NewsItemAnalysis.STATUS_COMPLETED,
            summary='Resumo IA do item mensal.',
            impact_level=NewsItemAnalysis.IMPACT_HIGH,
            keywords=['ICMS', 'NCM'],
            importance_score=82,
            effective_date=month_effective_date,
            effective_date_label=month_effective_date.strftime('%d/%m/%Y'),
        )
        NewsItemAnalysis.objects.create(
            news_item=low_item,
            status=NewsItemAnalysis.STATUS_COMPLETED,
            summary='Resumo IA institucional.',
            impact_level=NewsItemAnalysis.IMPACT_LOW,
            keywords=['Institucional'],
            importance_score=15,
        )

        response = self.client.get(reverse('feeds:index'))

        metrics = {metric['label']: metric for metric in response.context['dashboard_metrics']}

        self.assertEqual(metrics['Total de Informativos']['value'], 3)
        self.assertEqual(metrics['Não Lidos']['value'], 2)
        self.assertEqual(metrics['Alta Relevância']['value'], 2)
        self.assertEqual(metrics['Vigentes este Mês']['value'], expected_effective_this_month_count)

        self.assertEqual(metrics['Total de Informativos']['href'], reverse('feeds:news'))
        self.assertEqual(
            parse_qs(urlsplit(metrics['Não Lidos']['href']).query),
            {'status': ['unread']},
        )
        self.assertEqual(
            parse_qs(urlsplit(metrics['Alta Relevância']['href']).query),
            {'relevance': ['high']},
        )
        self.assertEqual(
            parse_qs(urlsplit(metrics['Vigentes este Mês']['href']).query),
            {
                'effective_date_from': [current_date.replace(day=1).isoformat()],
                'effective_date_to': [
                    current_date.replace(day=monthrange(current_date.year, current_date.month)[1]).isoformat()
                ],
            },
        )

        self.assertEqual(response.context['principal_change']['title'], principal_item.title)
        self.assertEqual(response.context['principal_change']['score'], 97)
        self.assertEqual(
            parse_qs(urlsplit(response.context['principal_change']['href']).query),
            {
                'q': [principal_item.title],
                'relevance': ['high'],
                'effective_date_from': [current_date.isoformat()],
            },
        )
        self.assertEqual(response.context['topic_rows'][0]['name'], 'ICMS')
        self.assertEqual(response.context['topic_rows'][0]['count'], 2)
        self.assertEqual(response.context['topic_rows'][0]['percentage'], 100)
        self.assertEqual(response.context['weekly_summary']['status'], DashboardWeeklySummary.STATUS_PENDING)

        self.assertContains(response, 'Dashboard de Insights Fiscais')
        self.assertContains(response, 'Temas Mais Recorrentes')
        self.assertContains(response, 'Resumo Semanal')

    def test_dashboard_loads_existing_weekly_summary_for_current_week(self):
        week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        week_end = week_start + timedelta(days=6)
        DashboardWeeklySummary.objects.create(
            week_start=week_start,
            week_end=week_end,
            status=DashboardWeeklySummary.STATUS_COMPLETED,
            overview='Foram identificados novos informativos relevantes nesta semana.',
            main_changes='ICMS e NCM lideram as mudanças mais recorrentes do período.',
            attention='Há vigências próximas que exigem atualização dos processos fiscais.',
        )

        source = Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )
        NewsItem.objects.create(
            source=source,
            title='Notícia da semana',
            summary='Resumo.',
            link='https://example.com/noticia-semana',
            external_id='news-week',
            dedupe_key='news-week',
            published_at=timezone.now(),
            is_read=False,
        )

        response = self.client.get(reverse('feeds:index'))

        self.assertTrue(response.context['weekly_summary']['is_ready'])
        self.assertContains(response, 'Foram identificados novos informativos relevantes nesta semana.')
        self.assertContains(response, 'ICMS e NCM lideram as mudanças mais recorrentes do período.')

    def test_dashboard_does_not_reuse_ready_weekly_summary_when_no_news_items_exist(self):
        week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        week_end = week_start + timedelta(days=6)
        DashboardWeeklySummary.objects.create(
            week_start=week_start,
            week_end=week_end,
            status=DashboardWeeklySummary.STATUS_COMPLETED,
            overview='Resumo que não deveria aparecer.',
            main_changes='Mudanças antigas.',
            attention='Atenção antiga.',
        )

        response = self.client.get(reverse('feeds:index'))

        self.assertTrue(response.context['weekly_summary']['is_ready'])
        self.assertEqual(
            response.context['weekly_summary']['overview'],
            'Nenhum informativo disponível no momento para compor o resumo semanal.',
        )
        self.assertNotContains(response, 'Resumo que não deveria aparecer.')

    @patch('feeds.services.dashboard_weekly_summary.start_dashboard_weekly_summary_job')
    def test_dashboard_weekly_summary_status_endpoint_starts_async_generation(self, mocked_start_job):
        source = Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )
        NewsItem.objects.create(
            source=source,
            title='Notícia para resumo',
            summary='Resumo.',
            link='https://example.com/noticia-resumo',
            external_id='news-summary',
            dedupe_key='news-summary',
            published_at=timezone.now(),
            is_read=False,
        )

        response = self.client.get(reverse('feeds:dashboard_weekly_summary_status'))

        summary = DashboardWeeklySummary.objects.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], DashboardWeeklySummary.STATUS_RUNNING)
        self.assertEqual(summary.status, DashboardWeeklySummary.STATUS_RUNNING)
        mocked_start_job.assert_called_once_with(summary.id, summary.revision)

    def test_refresh_news_invalidates_current_weekly_summary(self):
        week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        week_end = week_start + timedelta(days=6)
        summary = DashboardWeeklySummary.objects.create(
            week_start=week_start,
            week_end=week_end,
            status=DashboardWeeklySummary.STATUS_COMPLETED,
            revision=4,
            overview='Resumo antigo.',
            main_changes='Mudanças antigas.',
            attention='Atenção antiga.',
        )
        Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )

        response_content = DummyResponse(
            build_feed(
                [
                    {
                        'title': 'Nova atualização fiscal',
                        'link': 'https://example.com/noticia-1',
                        'guid': 'news-1',
                        'published_at': 'Tue, 12 May 2026 12:30:00 GMT',
                        'summary': 'Resumo do item.',
                    },
                ]
            )
        )

        with patch('feeds.services.news_import.requests.get', return_value=response_content):
            self.client.post(reverse('feeds:refresh_news'), follow=True)

        summary.refresh_from_db()
        self.assertEqual(summary.status, DashboardWeeklySummary.STATUS_PENDING)
        self.assertEqual(summary.revision, 5)
        self.assertEqual(summary.overview, '')
        self.assertEqual(summary.main_changes, '')
        self.assertEqual(summary.attention, '')
