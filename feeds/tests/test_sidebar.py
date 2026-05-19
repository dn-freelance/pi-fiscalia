from django.test import TestCase
from django.urls import reverse

from feeds.models import DashboardWeeklySummary, NewsImportJob, NewsItem, NewsItemAnalysis, Source, SourceCategory
from feeds.services.dashboard_weekly_summary import get_current_week_range


class SidebarContextTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')

    def setUp(self):
        Source.objects.all().delete()

    def test_sidebar_shows_empty_state_and_pending_configuration(self):
        response = self.client.get(reverse('feeds:index'))

        slides = response.context['sidebar_assistant_slides']
        network_status = response.context['sidebar_network_status']

        self.assertEqual(len(slides), 3)
        self.assertIn('Ainda não há informativos carregados', slides[0]['description'])
        self.assertIn('Nenhuma fonte foi cadastrada ainda', slides[1]['description'])
        self.assertIn('Assim que novos informativos forem importados', slides[2]['description'])
        self.assertEqual(network_status['label'], 'Sem fontes')
        self.assertEqual(network_status['tone'], 'warning')

    def test_sidebar_shows_live_counts_and_running_sync_status(self):
        source = Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )
        news_item = NewsItem.objects.create(
            source=source,
            title='Nova atualização tributária',
            summary='Resumo do item.',
            link='https://example.com/noticia',
            external_id='news-1',
            dedupe_key='news-1',
            is_read=False,
        )
        NewsItemAnalysis.objects.create(
            news_item=news_item,
            status=NewsItemAnalysis.STATUS_COMPLETED,
            impact_level=NewsItemAnalysis.IMPACT_HIGH,
            importance_score=91,
        )

        week_start, week_end = get_current_week_range()
        DashboardWeeklySummary.objects.create(
            week_start=week_start,
            week_end=week_end,
            status=DashboardWeeklySummary.STATUS_COMPLETED,
            overview='A semana concentrou mudanças fiscais com impacto direto na operação.',
            main_changes='Resumo.',
            attention='Atenção.',
        )
        NewsImportJob.objects.create(status=NewsImportJob.STATUS_RUNNING)

        response = self.client.get(reverse('feeds:index'))

        slides = response.context['sidebar_assistant_slides']
        network_status = response.context['sidebar_network_status']

        self.assertIn('1 informativo(s)', slides[0]['description'])
        self.assertIn('1 de alta relevância', slides[0]['description'])
        self.assertIn('1 de 1 fonte(s)', slides[1]['description'])
        self.assertIn('A semana concentrou mudanças fiscais', slides[2]['description'])
        self.assertEqual(network_status['label'], 'Sincronizando')
        self.assertEqual(network_status['tone'], 'info')
