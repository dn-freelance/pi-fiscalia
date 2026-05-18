import calendar
import hashlib
import html
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree import ElementTree

import feedparser
import requests
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from feeds.models import NewsItem, Source
from feeds.services.news_analysis import build_news_analysis_service

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_HEADERS = {
    'User-Agent': 'PI-Fiscalia/1.0 (+https://127.0.0.1:8000)',
    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
}

STRUCTURAL_PLONE_TYPES = {'Collection', 'File', 'Folder', 'Image', 'Link'}
FORUM_SUMMARY_SUFFIX_PATTERN = re.compile(
    r'\s*\d+\s*Respostas?\s*Leia mais em\s*https?://\S+\s*$',
    re.IGNORECASE,
)
READ_MORE_SUFFIX_PATTERN = re.compile(
    r'\s*Leia mais em\s*https?://\S+\s*$',
    re.IGNORECASE,
)
GOV_BR_NEWS_CARD_PATTERN = re.compile(
    r'<div class="conteudo">\s*'
    r'(?:<div class="subtitulo-noticia">\s*(?P<category>.*?)\s*</div>\s*)?'
    r'<h2 class="titulo">\s*<a href="(?P<link>[^"]+)">(?P<title>.*?)</a>\s*</h2>.*?'
    r'<span class="descricao">\s*<span class="data">\s*(?P<date>\d{2}/\d{2}/\d{4})\s*</span>\s*'
    r'(?:<span>\s*-\s*</span>\s*)?(?P<summary>.*?)\s*</span>',
    re.IGNORECASE | re.DOTALL,
)
GOV_BR_PUBLISHED_AT_PATTERN = re.compile(
    r'<span class="documentPublished">.*?<span class="value">\s*(?P<value>\d{2}/\d{2}/\d{4}\s+\d{2}h\d{2})\s*</span>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class NewsImportResult:
    created_count: int = 0
    existing_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    analysis_failure_count: int = 0
    analysis_skipped_count: int = 0
    analysis_halted: bool = False
    analysis_halt_reason: str = ''
    source_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    analysis_warnings: list[str] = field(default_factory=list)

    def summary_message(self):
        return (
            'Atualização concluída: '
            f'{self.created_count} nova(s) e {self.existing_count} já existente(s).'
        )

    def error_message(self):
        if not self.errors:
            return ''

        return f'{self.error_count} fonte(s) com erro: ' + '; '.join(self.errors)

    def warning_message(self):
        if not self.warnings:
            return ''

        return f'{self.skipped_count} notÃ­cia(s) ignorada(s): ' + '; '.join(self.warnings)


    def analysis_warning_messages(self):
        messages = []

        if self.analysis_halted:
            affected_count = self.analysis_failure_count + self.analysis_skipped_count
            halted_message = (
                'IA foi interrompida nesta atualização por limite do provider. '
                f'{affected_count} notícia(s) foram importadas sem análise.'
            )
            if self.analysis_halt_reason:
                halted_message = f'{halted_message} {self.analysis_halt_reason}'

            messages.append(halted_message)

        if self.analysis_warnings and self.analysis_failure_count:
            details = '; '.join(self.analysis_warnings[:3])
            if len(self.analysis_warnings) > 3:
                details = f'{details}; ...'

            messages.append(
                f'IA não conseguiu concluir a análise de {self.analysis_failure_count} notícia(s): {details}'
            )
        elif self.analysis_warnings:
            messages.extend(self.analysis_warnings)

        return messages


def build_news_import_feedback(result):
    feedback = []

    if result.source_count == 0:
        return [
            {
                'level': 'error',
                'text': 'Nenhuma fonte ativa disponível para atualização.',
            }
        ]

    if result.created_count or result.existing_count:
        feedback.append(
            {
                'level': 'success',
                'text': result.summary_message(),
            }
        )
    elif result.error_count:
        feedback.append(
            {
                'level': 'error',
                'text': 'Nenhum informativo pôde ser importado com segurança nesta atualização.',
            }
        )

    if result.skipped_count:
        feedback.append(
            {
                'level': 'warning',
                'text': result.warning_message(),
            }
        )

    for warning_message in result.analysis_warning_messages():
        feedback.append(
            {
                'level': 'warning',
                'text': warning_message,
            }
        )

    if result.error_count:
        feedback.append(
            {
                'level': 'error',
                'text': result.error_message(),
            }
        )

    return feedback


def import_news_items(timeout=15, progress_callback=None):
    result = NewsImportResult()
    analysis_service, analysis_warning = build_news_analysis_service()
    sources = Source.objects.filter(active=True).order_by('name')
    result.source_count = sources.count()
    analysis_candidates = []

    if analysis_warning:
        result.analysis_warnings.append(analysis_warning)

    if progress_callback is not None:
        progress_callback(
            'rss_start',
            total_sources=result.source_count,
            analysis_enabled=analysis_service is not None,
        )

    for source_index, source in enumerate(sources, start=1):
        try:
            response = _request_url(source.url, timeout)
            _import_source_entries(source, response, result, timeout, analysis_candidates)
        except requests.RequestException as error:
            if _try_import_source_with_listing_fallback(source, result, timeout, analysis_candidates, error):
                if progress_callback is not None:
                    progress_callback(
                        'rss_progress',
                        processed_sources=source_index,
                        total_sources=result.source_count,
                        source_name=source.name,
                        created_count=result.created_count,
                        existing_count=result.existing_count,
                        error_count=result.error_count,
                        skipped_count=result.skipped_count,
                        queued_analysis_count=len(analysis_candidates),
                    )
                continue

            logger.warning('Erro ao atualizar feed %s: %s', source.url, error)
            _register_error(result, source, _describe_feed_fetch_error(error))
        except Exception as error:  # pragma: no cover - proteção extra para feeds inválidos
            logger.exception('Erro inesperado ao importar feed %s', source.url)
            _register_error(result, source, f'erro inesperado: {error}')

        if progress_callback is not None:
            progress_callback(
                'rss_progress',
                processed_sources=source_index,
                total_sources=result.source_count,
                source_name=source.name,
                created_count=result.created_count,
                existing_count=result.existing_count,
                error_count=result.error_count,
                skipped_count=result.skipped_count,
                queued_analysis_count=len(analysis_candidates),
            )

    if progress_callback is not None:
        progress_callback(
            'analysis_start',
            total_items=len(analysis_candidates),
            analysis_enabled=analysis_service is not None,
        )

    _run_news_analysis_batch(
        analysis_candidates,
        analysis_service,
        result,
        progress_callback=progress_callback,
    )

    if progress_callback is not None:
        progress_callback('completed', result=result)

    return result


def _import_source_entries(source, response, result, timeout, analysis_candidates):
    feed = feedparser.parse(response.content)
    plone_item_types = _extract_plone_item_types(response.content)

    if _should_use_gov_br_listing_fallback(source.url, plone_item_types):
        _import_gov_br_listing(source, feed, response.url, result, timeout, analysis_candidates)
        return

    if not feed.entries:
        _register_error(result, source, _describe_unimportable_feed(feed))
        return

    imported_count = 0
    skipped_count = 0

    for entry in feed.entries:
        try:
            payload = _build_news_payload(entry)
        except Exception:
            logger.warning('Item do feed %s foi ignorado por falha ao montar o payload', source.url, exc_info=True)
            skipped_count += 1
            continue

        if not payload['title'] or not payload['link']:
            skipped_count += 1
            continue

        try:
            with transaction.atomic():
                news_item, created, _ = _upsert_news_item(source, _build_dedupe_key(entry, payload), payload)
        except Exception:
            logger.warning('Item %s da fonte %s foi ignorado por erro ao persistir', payload['link'], source.url, exc_info=True)
            skipped_count += 1
            continue

        imported_count += 1
        analysis_candidates.append(news_item)

        if created:
            result.created_count += 1
            continue

        result.existing_count += 1

    _finalize_source_processing(result, source, imported_count, skipped_count, feed)


def _request_url(url, timeout, accept_html=False):
    headers = dict(DEFAULT_REQUEST_HEADERS)
    if accept_html:
        headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'

    response = requests.get(url, timeout=timeout, headers=headers)
    response.raise_for_status()
    return response


def _try_import_source_with_listing_fallback(source, result, timeout, analysis_candidates, original_error):
    if not _is_gov_br_source(source.url):
        return False

    logger.warning(
        'Falha ao buscar feed RSS %s. Tentando fallback direto pela listagem gov.br: %s',
        source.url,
        original_error,
    )
    try:
        _import_gov_br_listing(
            source,
            feed=None,
            source_url=source.url,
            result=result,
            timeout=timeout,
            analysis_candidates=analysis_candidates,
        )
    except requests.RequestException as listing_error:
        logger.warning('Fallback direto da listagem gov.br também falhou em %s: %s', source.url, listing_error)
        return False

    return True


def _describe_feed_fetch_error(error):
    status_code = getattr(getattr(error, 'response', None), 'status_code', None)
    if status_code:
        return f'falha ao buscar o feed RSS (HTTP {status_code})'

    return 'falha ao buscar o feed RSS'


def _build_news_payload(entry):
    published_at = _parse_entry_datetime(entry)
    content_value = _entry_content_value(entry)

    return {
        'title': _clean_text(entry.get('title', '')),
        'summary': _clean_summary(entry.get('summary') or entry.get('description') or content_value),
        'link': _extract_entry_link(entry),
        'external_id': _extract_entry_external_id(entry),
        'published_at': published_at,
    }


def _build_dedupe_key(entry, payload):
    published_reference = ''
    if payload['published_at'] is not None:
        published_reference = payload['published_at'].astimezone(dt_timezone.utc).isoformat()

    raw_value = (
        entry.get('id')
        or entry.get('guid')
        or payload['link']
        or f"{payload['title']}|{published_reference}"
    )

    normalized_value = _normalize_for_hash(raw_value)
    return hashlib.sha256(normalized_value.encode('utf-8')).hexdigest()


def _parse_entry_datetime(entry):
    parsed_value = entry.get('published_parsed') or entry.get('updated_parsed')
    if parsed_value:
        timestamp = calendar.timegm(parsed_value)
        return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)

    raw_value = entry.get('published') or entry.get('updated')
    if not raw_value:
        return None

    try:
        parsed_datetime = parsedate_to_datetime(raw_value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    if parsed_datetime.tzinfo is None:
        return parsed_datetime.replace(tzinfo=dt_timezone.utc)

    return parsed_datetime.astimezone(dt_timezone.utc)


def _clean_text(value):
    if not value:
        return ''

    text = strip_tags(str(value))
    text = html.unescape(text)
    text = text.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _clean_summary(value):
    summary = _clean_text(value)
    if not summary:
        return ''

    summary = FORUM_SUMMARY_SUFFIX_PATTERN.sub('', summary)
    summary = READ_MORE_SUFFIX_PATTERN.sub('', summary)
    return summary.strip()


def _clean_url(value):
    return str(value or '').strip()


def _normalize_for_hash(value):
    normalized_value = unicodedata.normalize('NFKC', str(value or ''))
    normalized_value = html.unescape(normalized_value)
    normalized_value = re.sub(r'\s+', ' ', normalized_value).strip().casefold()
    return normalized_value


def _register_error(result, source, message):
    result.error_count += 1
    result.errors.append(f'{source.name}: {message}')


def _register_warning(result, source, skipped_count):
    result.skipped_count += skipped_count
    result.warnings.append(
        f'{source.name}: {skipped_count} item(ns) ignorado(s) por dados incompletos ou erro no processamento'
    )


def _register_analysis_warning(result, source, news_item, message):
    result.analysis_failure_count += 1
    result.analysis_warnings.append(f'{source.name} / {news_item.title}: {message}')


def _run_news_analysis_batch(news_items, analysis_service, result, progress_callback=None):
    if analysis_service is None:
        result.analysis_skipped_count += len(news_items)
        if progress_callback is not None:
            progress_callback(
                'analysis_progress',
                processed_count=len(news_items),
                total_count=len(news_items),
                updated_count=0,
                failed_count=0,
                skipped_count=len(news_items),
                halted=False,
            )
        return

    if not news_items:
        if progress_callback is not None:
            progress_callback(
                'analysis_progress',
                processed_count=0,
                total_count=0,
                updated_count=0,
                failed_count=0,
                skipped_count=0,
                halted=False,
            )
        return

    if result.analysis_halted:
        result.analysis_skipped_count += len(news_items)
        return

    execution_result = analysis_service.analyze_news_items(
        news_items,
        progress_callback=_wrap_analysis_progress(progress_callback),
    )

    for news_item, error_message in execution_result.failure_details:
        logger.warning('IA nÃ£o conseguiu analisar o informativo %s: %s', news_item.link, error_message)
        _register_analysis_warning(result, news_item.source, news_item, error_message)

    if execution_result.halted:
        logger.warning('IA foi interrompida durante a atualizaÃ§Ã£o dos informativos: %s', execution_result.halt_reason)
        result.analysis_halted = True
        result.analysis_halt_reason = execution_result.halt_reason
        result.analysis_skipped_count += execution_result.halted_pending_count

def _wrap_analysis_progress(progress_callback):
    if progress_callback is None:
        return None

    def reporter(**payload):
        progress_callback('analysis_progress', **payload)

    return reporter


def _finalize_source_processing(result, source, imported_count, skipped_count, feed=None):
    if imported_count == 0:
        if skipped_count:
            _register_error(result, source, 'nenhum item pÃ´de ser importado com seguranÃ§a')
            return

        _register_error(result, source, _describe_unimportable_feed(feed))
        return

    if skipped_count:
        _register_warning(result, source, skipped_count)


def _describe_unimportable_feed(feed):
    if getattr(feed, 'bozo', False):
        return 'o feed retornou um formato invÃ¡lido ou incompatÃ­vel'

    return 'nenhum item importÃ¡vel foi encontrado na fonte'


def _entry_content_value(entry):
    content_blocks = entry.get('content') or []
    if not content_blocks:
        return ''

    return content_blocks[0].get('value', '')


def _extract_entry_link(entry):
    entry_link = _clean_url(entry.get('link', ''))
    if entry_link:
        return entry_link

    for link_data in entry.get('links') or []:
        href = _clean_url(link_data.get('href', ''))
        rel = _clean_text(link_data.get('rel', ''))
        if href and (not rel or rel == 'alternate'):
            return href

    return ''


def _extract_entry_external_id(entry):
    external_id = _clean_text(entry.get('id') or entry.get('guid') or '')
    if external_id:
        return external_id

    return _extract_entry_link(entry)


def _extract_plone_item_types(content):
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return {}

    namespaces = {
        'default': 'http://purl.org/rss/1.0/',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'dc': 'http://purl.org/dc/elements/1.1/',
    }

    item_types = {}
    for item in root.findall('.//default:item', namespaces) + root.findall('.//item'):
        guid = _xml_text(item.find('default:guid', namespaces) or item.find('guid'))
        if not guid:
            guid = item.attrib.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about', '')

        item_type = _xml_text(item.find('dc:type', namespaces))
        if guid and item_type:
            item_types[guid.strip()] = item_type.strip()

    return item_types


def _xml_text(node):
    if node is None or node.text is None:
        return ''

    return node.text


def _should_use_gov_br_listing_fallback(source_url, plone_item_types):
    if not _is_gov_br_source(source_url):
        return False

    if not plone_item_types:
        return False

    return all(item_type in STRUCTURAL_PLONE_TYPES for item_type in plone_item_types.values())


def _is_gov_br_source(source_url):
    hostname = urlparse(source_url).hostname or ''
    return hostname == 'gov.br' or hostname.endswith('.gov.br')


def _cleanup_structural_items(source, feed):
    if feed is None:
        return

    bad_links = [
        _clean_url(entry.get('link', ''))
        for entry in feed.entries
        if _clean_url(entry.get('link', ''))
    ]

    if bad_links:
        NewsItem.objects.filter(source=source, link__in=bad_links).delete()


def _upsert_news_item(source, dedupe_key, payload):
    news_item, created = NewsItem.objects.get_or_create(
        source=source,
        dedupe_key=dedupe_key,
        defaults=payload,
    )

    if created:
        return news_item, True, True

    changed_fields = []
    for field_name, field_value in payload.items():
        if getattr(news_item, field_name) != field_value:
            setattr(news_item, field_name, field_value)
            changed_fields.append(field_name)

    if changed_fields:
        changed_fields.append('updated_at')
        news_item.save(update_fields=changed_fields)

    return news_item, False, bool(changed_fields)


def _import_gov_br_listing(source, feed, source_url, result, timeout, analysis_candidates):
    listing_url = _resolve_gov_br_listing_url(source_url)
    response = _request_url(listing_url, timeout, accept_html=True)

    entries = _extract_gov_br_news_entries(response.text)
    if not entries:
        _register_error(result, source, 'o feed é estrutural e a página de notícias não pôde ser interpretada')
        return

    existing_items_by_link = {
        news_item.link: news_item
        for news_item in NewsItem.objects.filter(
            source=source,
            link__in=[entry['link'] for entry in entries],
        )
    }
    published_at_by_link = _load_gov_br_article_published_at_batch(entries, existing_items_by_link, timeout)
    _cleanup_structural_items(source, feed)

    imported_count = 0
    skipped_count = 0

    for entry in entries:
        existing_item = existing_items_by_link.get(entry['link'])
        published_at = published_at_by_link.get(entry['link'])

        if published_at is None and existing_item and _has_precise_local_time(existing_item.published_at):
            published_at = existing_item.published_at

        if published_at is None:
            published_at = entry['published_at']

        payload = {
            'title': entry['title'],
            'summary': entry['summary'],
            'link': entry['link'],
            'external_id': entry['link'],
            'published_at': published_at,
        }

        if not payload['title'] or not payload['link']:
            skipped_count += 1
            continue

        try:
            with transaction.atomic():
                news_item, created, _ = _upsert_news_item(
                    source,
                    _build_dedupe_key({'link': entry['link']}, payload),
                    payload,
                )
        except Exception:
            logger.warning(
                'Notícia %s da fonte %s foi ignorada por erro ao persistir',
                payload['link'],
                source.url,
                exc_info=True,
            )
            skipped_count += 1
            continue

        imported_count += 1
        analysis_candidates.append(news_item)

        if created:
            result.created_count += 1
            continue

        result.existing_count += 1

    _finalize_source_processing(result, source, imported_count, skipped_count)


def _resolve_gov_br_listing_url(source_url):
    normalized_url = source_url.rstrip('/')

    for suffix in ('/RSS', '/rss.xml', '/atom.xml'):
        if normalized_url.endswith(suffix):
            return normalized_url[:-len(suffix)]

    return normalized_url


def _extract_gov_br_news_entries(html_content):
    entries = []
    for match in GOV_BR_NEWS_CARD_PATTERN.finditer(html_content):
        title = _clean_text(match.group('title'))
        link = _clean_url(match.group('link'))
        summary = _clean_text(match.group('summary'))
        published_at = _parse_gov_br_listing_date(match.group('date'))

        if not title or not link:
            continue

        entries.append({
            'title': title,
            'link': link,
            'summary': summary,
            'published_at': published_at,
        })

    return entries


def _parse_gov_br_listing_date(date_value):
    cleaned_value = _clean_text(date_value)
    if not cleaned_value:
        return None

    try:
        parsed_date = datetime.strptime(cleaned_value, '%d/%m/%Y')
    except ValueError:
        return None

    return timezone.make_aware(parsed_date, timezone.get_current_timezone())


def _load_gov_br_article_published_at(article_url, timeout):
    try:
        response = _request_url(article_url, timeout, accept_html=True)
    except requests.RequestException:
        return None

    match = GOV_BR_PUBLISHED_AT_PATTERN.search(response.text)
    if not match:
        return None

    raw_value = _clean_text(match.group('value')).replace('h', ':')
    try:
        parsed_datetime = datetime.strptime(raw_value, '%d/%m/%Y %H:%M')
    except ValueError:
        return None

    return timezone.make_aware(parsed_datetime, timezone.get_current_timezone())


def _load_gov_br_article_published_at_batch(entries, existing_items_by_link, timeout):
    article_links = []
    for entry in entries:
        existing_item = existing_items_by_link.get(entry['link'])
        if existing_item and _has_precise_local_time(existing_item.published_at):
            continue

        article_links.append(entry['link'])

    if not article_links:
        return {}

    published_at_by_link = {}
    max_workers = min(4, len(article_links))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_by_link = {
            executor.submit(_load_gov_br_article_published_at, article_link, timeout): article_link
            for article_link in article_links
        }

        for future in as_completed(future_by_link):
            article_link = future_by_link[future]
            try:
                published_at_by_link[article_link] = future.result()
            except Exception:  # pragma: no cover - proteção adicional
                published_at_by_link[article_link] = None

    return published_at_by_link


def _has_precise_local_time(value):
    if value is None:
        return False

    localized_value = timezone.localtime(value) if timezone.is_aware(value) else value
    return not (localized_value.hour == 0 and localized_value.minute == 0)
