from django.test import TestCase
from django.urls import reverse

from feeds.models import NewsItem, Source, SourceCategory


class BaseAccessibilityTemplateTests(TestCase):
    def test_base_layout_renders_skip_link_mobile_toggle_and_current_page(self):
        response = self.client.get(reverse('feeds:index'))

        self.assertContains(response, 'href="#main-content"')
        self.assertContains(response, 'data-sidebar-toggle')
        self.assertContains(response, 'id="app-sidebar"')
        self.assertContains(response, 'aria-current="page"', count=1)


class SourceAccessibilityTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')

    def test_sources_page_renders_accessible_dialogs_and_switches(self):
        Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )

        response = self.client.get(reverse('feeds:sources'))

        self.assertContains(response, 'role="dialog"', count=3)
        self.assertContains(response, 'aria-controls="div-source-create-modal"')
        self.assertContains(response, 'role="switch"')


class TagAccessibilityTemplateTests(TestCase):
    def test_tags_page_renders_color_picker_with_radio_semantics(self):
        response = self.client.get(reverse('feeds:tags'))

        self.assertContains(response, 'role="radiogroup"', count=2)
        self.assertContains(response, 'role="radio"')
        self.assertContains(response, 'aria-controls="div-tag-create-modal"')


class NewsAccessibilityTemplateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')

    def test_news_index_renders_live_region_and_list_controls(self):
        source = Source.objects.create(
            name='Fonte Fiscal',
            url='https://example.com/fiscal/rss',
            category=self.federal,
            active=True,
        )
        NewsItem.objects.create(
            source=source,
            title='Noticia acessivel',
            summary='Resumo curto.',
            link='https://example.com/noticia-acessivel',
            external_id='accessible-1',
            dedupe_key='accessible-1',
        )

        response = self.client.get(reverse('feeds:news'))

        self.assertContains(response, 'id="news-results-status"')
        self.assertContains(response, 'aria-controls="news-list"')
        self.assertContains(response, 'id="news-list"')
