from collections import Counter
from datetime import timedelta
import re
import unicodedata

from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from feeds.models import NewsItem, Source, SourceCategory, Tag
from feeds.templatetags.news_extras import MONTH_ABBREVIATIONS


def get_dashboard_context():
    current_time = timezone.localtime()
    month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recent_cutoff = current_time - timedelta(days=7)

    tags = list(Tag.objects.order_by('name'))
    tag_matchers = _build_tag_matchers(tags)
    news_items = list(
        NewsItem.objects.select_related('source', 'source__category')
        .annotate(reference_at=Coalesce('published_at', 'created_at'))
        .order_by('-reference_at', '-created_at')
    )

    unread_count = 0
    published_this_month_count = 0
    attention_count = 0
    topic_counter = Counter()
    tag_counter = Counter()

    for item in news_items:
        item.matched_topics = _match_topics_for_item(item, tag_matchers)
        item.dashboard_topics = item.matched_topics[:3] or [item.source.category.name]
        item.focus_score = _focus_score(item, current_time, month_start, recent_cutoff)
        item.focus_reason = _focus_reason(item, current_time, month_start, recent_cutoff)

        if not item.is_read:
            unread_count += 1

        if item.reference_at >= month_start:
            published_this_month_count += 1

        if not item.is_read and item.reference_at >= month_start:
            attention_count += 1

        if item.matched_topics:
            for topic_name in item.matched_topics:
                topic_counter[topic_name] += 1
                tag_counter[topic_name] += 1
        else:
            topic_counter[item.source.category.name] += 1

    total_news = len(news_items)
    topic_rows = _build_topic_rows(topic_counter)
    principal_change = _select_principal_change(news_items)
    active_topic_count = sum(1 for row in topic_rows if row['count'] > 0)

    top_sources = list(
        Source.objects.select_related('category')
        .annotate(
            news_total=Count('news_items'),
            unread_total=Count('news_items', filter=Q(news_items__is_read=False)),
        )
        .order_by('-news_total', '-unread_total', '-active', 'name')[:5]
    )

    category_rows = list(
        SourceCategory.objects.annotate(
            source_total=Count('sources', distinct=True),
            active_source_total=Count('sources', filter=Q(sources__active=True), distinct=True),
            news_total=Count('sources__news_items', distinct=True),
        )
    )

    total_source_count = Source.objects.count()
    active_source_count = Source.objects.filter(active=True).count()
    source_health = {
        'active_count': active_source_count,
        'inactive_count': max(total_source_count - active_source_count, 0),
        'active_percentage': round((active_source_count / total_source_count) * 100) if total_source_count else 0,
    }

    top_source = next((source for source in top_sources if source.news_total), None)
    summary_points = _build_summary_points(
        unread_count=unread_count,
        published_this_month_count=published_this_month_count,
        attention_count=attention_count,
        top_topics=topic_rows[:3],
        top_source=top_source,
        current_month_label=MONTH_ABBREVIATIONS.get(current_time.month, ''),
    )

    monitored_tags = [
        {
            'name': tag.name,
            'color': tag.color,
            'count': tag_counter.get(tag.name, 0),
        }
        for tag in tags
    ]

    return {
        'dashboard_metrics': [
            {
                'label': 'Total de Informativos',
                'value': total_news,
                'icon': 'chart-column',
                'variant': 'blue',
                'hint': 'Base consolidada',
            },
            {
                'label': 'Não Lidos',
                'value': unread_count,
                'icon': 'eye',
                'variant': 'orange',
                'hint': 'Pendentes de leitura',
            },
            {
                'label': 'Em Foco Agora',
                'value': attention_count,
                'icon': 'triangle-alert',
                'variant': 'red',
                'hint': 'Não lidos deste mês',
            },
            {
                'label': 'Assuntos em Destaque',
                'value': active_topic_count,
                'icon': 'trending-up',
                'variant': 'green',
                'hint': 'Temas recorrentes no monitoramento',
            },
        ],
        'ai_metrics': [
            {'label': 'Alertas com IA', 'value': 0},
            {'label': 'Priorização com IA', 'value': 0},
        ],
        'principal_change': principal_change,
        'topic_rows': topic_rows[:5],
        'recent_news_items': news_items[:5],
        'summary_points': summary_points,
        'top_sources': top_sources,
        'category_rows': category_rows,
        'monitored_tags': monitored_tags,
        'source_health': source_health,
        'unread_count': unread_count,
        'published_this_month_count': published_this_month_count,
        'current_month_label': MONTH_ABBREVIATIONS.get(current_time.month, ''),
    }


def _build_tag_matchers(tags):
    matchers = []

    for tag in tags:
        aliases = {_normalize_text(tag.name)}

        for fragment in re.split(r'[/()-]+', tag.name):
            normalized_fragment = _normalize_text(fragment)
            if len(normalized_fragment) >= 3:
                aliases.add(normalized_fragment)

        matchers.append({
            'name': tag.name,
            'aliases': [alias for alias in aliases if alias],
        })

    return matchers


def _match_topics_for_item(item, tag_matchers):
    normalized_text = _normalize_text(' '.join(filter(None, [item.title, item.summary])))
    matched_topics = []

    for matcher in tag_matchers:
        if any(alias in normalized_text for alias in matcher['aliases']):
            matched_topics.append(matcher['name'])

    return matched_topics


def _normalize_text(value):
    normalized_value = unicodedata.normalize('NFKD', str(value or ''))
    normalized_value = ''.join(character for character in normalized_value if not unicodedata.combining(character))
    normalized_value = normalized_value.casefold()
    return re.sub(r'\s+', ' ', normalized_value).strip()


def _focus_score(item, current_time, month_start, recent_cutoff):
    score = 0

    if not item.is_read:
        score += 40

    if item.reference_at >= recent_cutoff:
        score += 25

    if item.reference_at >= month_start:
        score += 15

    score += min(len(item.matched_topics), 3) * 5

    if item.summary:
        score += 3

    if item.reference_at >= current_time - timedelta(days=2):
        score += 10

    return score


def _focus_reason(item, current_time, month_start, recent_cutoff):
    reasons = []

    if not item.is_read:
        reasons.append('Não lido')

    if item.reference_at >= recent_cutoff:
        reasons.append('Recente')

    if item.reference_at >= month_start:
        reasons.append('Publicado neste mês')

    if item.matched_topics:
        reasons.append('Tema monitorado')

    if item.reference_at >= current_time - timedelta(days=2):
        reasons.append('Entrada muito nova')

    return ' • '.join(reasons[:3])


def _select_principal_change(news_items):
    if not news_items:
        return None

    return max(
        news_items,
        key=lambda item: (
            item.focus_score,
            1 if not item.is_read else 0,
            item.reference_at,
        ),
    )


def _build_topic_rows(topic_counter):
    if not topic_counter:
        return []

    highest_count = max(topic_counter.values())
    rows = []

    for topic_name, count in topic_counter.most_common(5):
        rows.append({
            'name': topic_name,
            'count': count,
            'percentage': round((count / highest_count) * 100) if highest_count else 0,
        })

    return rows


def _build_summary_points(unread_count, published_this_month_count, attention_count, top_topics, top_source, current_month_label):
    top_topic_names = ', '.join(topic['name'] for topic in top_topics)
    top_source_name = top_source.name if top_source is not None else 'nenhuma fonte com atividade'

    points = [
        (
            f'{unread_count} informativo(s) aguardam leitura no momento, '
            f'e {attention_count} deles foram publicados em {current_month_label or "este mês"}.'
        ),
        (
            f'Os assuntos que mais se repetem agora são: {top_topic_names}.'
            if top_topic_names
            else 'Ainda não há recorrência suficiente para apontar assuntos dominantes.'
        ),
        (
            f'{published_this_month_count} registro(s) entraram na base neste mês, '
            f'com maior concentração em {top_source_name}.'
        ),
    ]

    return points
