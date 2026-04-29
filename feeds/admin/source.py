from django.contrib import admin

from feeds.models import Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'active', 'url', 'updated_at')
    list_filter = ('category', 'active')
    search_fields = ('name', 'url', 'description')
    readonly_fields = ('created_at', 'updated_at')
