from django.contrib import admin

from feeds.models import SourceCategory


@admin.register(SourceCategory)
class SourceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    ordering = ('order', 'name')
