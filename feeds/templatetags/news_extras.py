from django import template
from django.utils import timezone

register = template.Library()

MONTH_ABBREVIATIONS = {
    1: 'JAN',
    2: 'FEV',
    3: 'MAR',
    4: 'ABR',
    5: 'MAI',
    6: 'JUN',
    7: 'JUL',
    8: 'AGO',
    9: 'SET',
    10: 'OUT',
    11: 'NOV',
    12: 'DEZ',
}


@register.filter
def news_card_datetime(value):
    if value is None:
        return ''

    localized_value = timezone.localtime(value) if timezone.is_aware(value) else value
    month_label = MONTH_ABBREVIATIONS.get(localized_value.month, '')
    date_label = f'{localized_value.day:02d} DE {month_label}, {localized_value.year}'

    if localized_value.hour == 0 and localized_value.minute == 0:
        return date_label

    return f'{date_label} ÀS {localized_value:%H:%M}'
