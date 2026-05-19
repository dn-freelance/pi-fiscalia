from django.db import models

from feeds.models.news_item import NewsItem


class NewsItemFollow(models.Model):
    news_item = models.OneToOneField(
        NewsItem,
        verbose_name='informativo',
        on_delete=models.CASCADE,
        related_name='follow',
    )
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Acompanhamento de Informativo'
        verbose_name_plural = 'Acompanhamentos de Informativos'

    def __str__(self):
        return f'Acompanhamento - {self.news_item.title}'
