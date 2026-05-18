from calendar import monthrange
from collections import Counter
from urllib.parse import urlencode

from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from feeds.models import NewsItem, NewsItemAnalysis
from feeds.services.dashboard_weekly_summary import get_current_week_summary_state


def get_dashboard_context():
    current_time = timezone.localtime()
    current_date = timezone.localdate()
    current_month_start = current_date.replace(day=1)
    current_month_end = current_date.replace(day=monthrange(current_date.year, current_date.month)[1])

    news_items = list(
        NewsItem.objects.select_related('source', 'source__category', 'analysis')
        .annotate(reference_at=Coalesce('published_at', 'created_at'))
        .order_by('-reference_at', '-created_at')
    )

    unread_count = 0
    high_relevance_count = 0
    effective_this_month_count = 0
    keyword_counter = Counter()
    principal_candidates = []

    for item in news_items:
        analysis = item.analysis_or_none
        item.dashboard_summary = _item_summary(item, analysis)
        item.dashboard_score = analysis.importance_score if analysis is not None else None
        item.dashboard_effective_date = analysis.effective_date if analysis is not None else None
        item.dashboard_effective_date_display = analysis.effective_date_display if analysis is not None else ''
        item.dashboard_keywords = analysis.keywords if analysis is not None and analysis.keywords else []

        if not item.is_read:
            unread_count += 1

        if analysis is None:
            continue

        if analysis.impact_level == NewsItemAnalysis.IMPACT_HIGH:
            high_relevance_count += 1
            if analysis.effective_date is not None and analysis.effective_date > current_date:
                principal_candidates.append(item)

        if (
            analysis.effective_date is not None
            and analysis.effective_date.month == current_date.month
            and analysis.effective_date.year == current_date.year
        ):
            effective_this_month_count += 1

        keyword_counter.update(item.dashboard_keywords)

    topic_rows = _build_topic_rows(keyword_counter)
    principal_change = _select_principal_change(principal_candidates, current_date)
    weekly_summary = get_current_week_summary_state(start_async=False, current_time=current_time)

    return {
        'dashboard_metrics': [
            {
                'label': 'Total de Informativos',
                'value': len(news_items),
                'icon': 'chart-column',
                'variant': 'blue',
                'href': _build_news_url(),
            },
            {
                'label': 'Não Lidos',
                'value': unread_count,
                'icon': 'eye',
                'variant': 'orange',
                'href': _build_news_url({'status': 'unread'}),
            },
            {
                'label': 'Alta Relevância',
                'value': high_relevance_count,
                'icon': 'triangle-alert',
                'variant': 'red',
                'href': _build_news_url({'relevance': NewsItemAnalysis.IMPACT_HIGH}),
            },
            {
                'label': 'Vigentes este Mês',
                'value': effective_this_month_count,
                'icon': 'calendar',
                'variant': 'green',
                'href': _build_news_url(
                    {
                        'effective_date_from': current_month_start.isoformat(),
                        'effective_date_to': current_month_end.isoformat(),
                    }
                ),
            },
        ],
        'principal_change': principal_change,
        'topic_rows': topic_rows,
        'weekly_summary': weekly_summary,
        'unread_count': unread_count,
    }


def _item_summary(item, analysis):
    if analysis is not None and analysis.summary:
        return analysis.summary

    return item.summary


def _build_topic_rows(keyword_counter):
    if not keyword_counter:
        return []

    highest_count = max(keyword_counter.values())
    rows = []
    for keyword, count in keyword_counter.most_common(5):
        rows.append(
            {
                'name': keyword,
                'count': count,
                'percentage': round((count / highest_count) * 100) if highest_count else 0,
            }
        )

    return rows


def _select_principal_change(principal_candidates, current_date):
    if not principal_candidates:
        return None

    selected_item = max(
        principal_candidates,
        key=lambda item: (
            item.dashboard_score if item.dashboard_score is not None else -1,
            -item.dashboard_effective_date.toordinal() if item.dashboard_effective_date is not None else 0,
            item.reference_at,
        ),
    )

    return {
        'title': selected_item.title,
        'description': selected_item.dashboard_summary,
        'effective_date_display': selected_item.dashboard_effective_date_display,
        'score': selected_item.dashboard_score if selected_item.dashboard_score is not None else '-',
        'href': _build_news_url(
            {
                'q': selected_item.title,
                'relevance': NewsItemAnalysis.IMPACT_HIGH,
                'effective_date_from': current_date.isoformat(),
            }
        ),
    }


def _build_news_url(params=None):
    base_url = reverse('feeds:news')
    if not params:
        return base_url

    query_string = urlencode(params)
    if not query_string:
        return base_url

    return f'{base_url}?{query_string}'
