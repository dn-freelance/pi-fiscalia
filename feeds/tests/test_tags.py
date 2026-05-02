from django.test import TestCase
from django.urls import reverse

from feeds.models import Tag


class TagViewTests(TestCase):
    def test_create_tag_persists_tag(self):
        response = self.client.post(reverse('feeds:create_tag'), {
            'name': 'Nova Tag de Teste',
            'color': 'blue',
        })

        self.assertRedirects(response, reverse('feeds:tags'))
        self.assertTrue(Tag.objects.filter(name='Nova Tag de Teste', color='blue').exists())

    def test_default_tags_are_seeded(self):
        default_tags = [
            ('NCM', 'blue'),
            ('ICMS', 'green'),
            ('PIS/COFINS', 'purple'),
            ('Simples Nacional', 'yellow'),
            ('CEST', 'orange'),
            ('Substituição Tributária', 'red'),
        ]

        for name, color in default_tags:
            self.assertTrue(
                Tag.objects.filter(name=name, color=color).exists(),
                f'Tag padrão {name} não foi semeada corretamente.',
            )

    def test_create_tag_rejects_invalid_payload(self):
        response = self.client.post(reverse('feeds:create_tag'), {
            'name': '',
            'color': 'green',
        })

        self.assertRedirects(response, reverse('feeds:tags'))
        self.assertEqual(Tag.objects.count(), 6)

    def test_update_tag_changes_name_and_color(self):
        tag = Tag.objects.create(name='ICMS Teste', color='yellow')

        response = self.client.post(reverse('feeds:update_tag', args=[tag.id]), {
            'name': 'ICMS Atualizado',
            'color': 'red',
        })

        self.assertRedirects(response, reverse('feeds:tags'))
        tag.refresh_from_db()
        self.assertEqual(tag.name, 'ICMS Atualizado')
        self.assertEqual(tag.color, 'red')

    def test_delete_tag_removes_tag(self):
        tag = Tag.objects.create(name='Substituição Tributária Teste', color='orange')

        response = self.client.post(reverse('feeds:delete_tag', args=[tag.id]))

        self.assertRedirects(response, reverse('feeds:tags'))
        self.assertFalse(Tag.objects.filter(id=tag.id).exists())
