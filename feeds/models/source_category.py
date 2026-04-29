from django.db import models


class SourceCategory(models.Model):
    name = models.CharField('nome', max_length=50, unique=True)
    order = models.PositiveSmallIntegerField('ordem', default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Categoria de fonte'
        verbose_name_plural = 'Categorias de fontes'

    def __str__(self):
        return self.name
