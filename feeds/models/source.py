from django.db import models

from feeds.models.source_category import SourceCategory


class Source(models.Model):
    name = models.CharField('nome', max_length=150)
    url = models.URLField('URL do feed RSS', max_length=500, unique=True)
    description = models.TextField('descrição', blank=True)
    category = models.ForeignKey(
        SourceCategory,
        verbose_name='categoria',
        on_delete=models.PROTECT,
        related_name='sources',
    )
    active = models.BooleanField('ativa', default=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Fonte RSS'
        verbose_name_plural = 'Fontes RSS'

    def __str__(self):
        return self.name
