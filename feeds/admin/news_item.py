from django.contrib import admin

from feeds.models import NewsItem


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'is_read', 'published_at', 'updated_at')
    list_filter = ('is_read', 'source')
    search_fields = ('title', 'link', 'source__name')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('source',)
