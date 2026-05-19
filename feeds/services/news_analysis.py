import hashlib
import html
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from feeds.models import NewsItemAnalysis

logger = logging.getLogger(__name__)

MAX_ARTICLE_TEXT_LENGTH = 7000
MIN_ARTICLE_TEXT_LENGTH = 120
MAX_PROVIDER_BATCH_SIZE = 10
HTML_BLOCK_PATTERNS = [
    re.compile(r'(?is)<article\b[^>]*>(.*?)</article>'),
    re.compile(r'(?is)<main\b[^>]*>(.*?)</main>'),
    re.compile(
        r'(?is)<(?:section|div)\b[^>]*(?:class|id)=["\'][^"\']*'
        r'(?:article|content|conteudo|noticia|noticia-texto|news|post|entry|texto|materia|body)'
        r'[^"\']*["\'][^>]*>(.*?)</(?:section|div)>'
    ),
]
NON_CONTENT_BLOCK_PATTERN = re.compile(
    r'(?is)<(script|style|noscript|template|svg|iframe|form|nav|footer|header|aside)\b.*?>.*?</\1>'
)
TITLE_PATTERN = re.compile(r'(?is)<title[^>]*>(.*?)</title>')


class NewsAnalysisError(Exception):
    pass


class NewsAnalysisConfigurationError(NewsAnalysisError):
    pass


class NewsAnalysisProviderError(NewsAnalysisError):
    pass


class NewsAnalysisRateLimitError(NewsAnalysisProviderError):
    def __init__(self, message, retry_after_seconds=None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class NewsAnalysisQuotaError(NewsAnalysisRateLimitError):
    pass


class NewsArticleExtractionError(NewsAnalysisError):
    pass


@dataclass
class NewsArticleContent:
    text: str
    page_title: str = ''


@dataclass
class NewsAnalysisContext:
    local_id: str
    source_name: str
    source_category: str
    title: str
    source_summary: str
    published_at: str
    link: str
    article_text: str


@dataclass
class NewsAnalysisResult:
    summary: str
    impact_level: str
    impact_context: str
    keywords: list[str]
    importance_score: int | None
    effective_date: date | None
    effective_date_label: str


@dataclass
class PreparedNewsAnalysis:
    news_item: object
    input_hash: str
    context: NewsAnalysisContext


@dataclass
class NewsAnalysisExecutionResult:
    attempted: bool = False
    updated: bool = False
    failed: bool = False
    reason: str = ''


@dataclass
class NewsAnalysisBatchExecutionResult:
    updated_count: int = 0
    failed_count: int = 0
    skipped_current_count: int = 0
    halted: bool = False
    halt_reason: str = ''
    halted_pending_count: int = 0
    failure_details: list[tuple[object, str]] = field(default_factory=list)


class NewsAnalysisProvider:
    provider_name = ''
    model_name = ''

    def analyze(self, context):
        results_by_id = self.analyze_batch([context])
        return results_by_id[context.local_id]

    def analyze_batch(self, contexts):  # pragma: no cover - interface
        raise NotImplementedError


class OpenAINewsAnalysisProvider(NewsAnalysisProvider):
    provider_name = 'openai'

    def __init__(self, api_key, model_name, base_url, timeout_seconds, organization='', project=''):
        if not api_key:
            raise NewsAnalysisConfigurationError('IA não configurada: defina OPENAI_API_KEY no .env.')

        self.api_key = api_key
        self.model_name = model_name
        self.base_url = (base_url or 'https://api.openai.com/v1').rstrip('/')
        self.timeout_seconds = timeout_seconds
        self.organization = organization
        self.project = project

    def analyze_batch(self, contexts):
        if not contexts:
            return {}

        endpoint = f'{self.base_url}/responses'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        if self.organization:
            headers['OpenAI-Organization'] = self.organization
        if self.project:
            headers['OpenAI-Project'] = self.project

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=_build_openai_payload(self.model_name, contexts),
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as error:
            raise NewsAnalysisProviderError(f'falha na consulta ao provider: {error}') from error
        if response.status_code == 429:
            error_type, error_code, error_message = _extract_openai_error_details(response)
            retry_after_seconds = _parse_retry_after_seconds(response.headers.get('Retry-After'))

            if error_code == 'insufficient_quota' or error_type == 'insufficient_quota':
                detail_message = (
                    error_message
                    or 'a quota/crédito da API da OpenAI foi excedida. Verifique billing, limites e orçamento do projeto.'
                )
                raise NewsAnalysisQuotaError(detail_message, retry_after_seconds=retry_after_seconds)

            retry_suffix = ''
            if retry_after_seconds is not None:
                retry_suffix = f' Aguarde cerca de {retry_after_seconds} segundo(s) antes de tentar novamente.'

            detail_message = _build_openai_rate_limit_message(error_message)
            raise NewsAnalysisRateLimitError(detail_message + retry_suffix, retry_after_seconds=retry_after_seconds)

        try:
            response.raise_for_status()
        except requests.RequestException as error:
            raise NewsAnalysisProviderError(_describe_openai_http_error(response, error)) from error

        payload = response.json()
        response_text = _collect_openai_response_text(payload)
        if not response_text:
            raise NewsAnalysisProviderError('o provider não retornou uma resposta estruturada utilizável.')

        try:
            content = _parse_structured_json_response(response_text)
        except json.JSONDecodeError as error:
            raise NewsAnalysisProviderError(f'resposta JSON inválida: {error}') from error

        return _normalize_batch_analysis_results(content, contexts)


class NewsAnalysisService:
    def __init__(self, provider, timeout_seconds, pipeline_version, batch_size):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.pipeline_version = pipeline_version
        self.batch_size = max(1, min(MAX_PROVIDER_BATCH_SIZE, int(batch_size or 1)))

    def analyze_news_item(self, news_item):
        batch_result = self.analyze_news_items([news_item])
        if batch_result.halted:
            raise NewsAnalysisRateLimitError(batch_result.halt_reason)

        if batch_result.failure_details:
            raise NewsAnalysisError(batch_result.failure_details[0][1])

        return NewsAnalysisExecutionResult(
            attempted=bool(batch_result.updated_count or batch_result.failed_count),
            updated=bool(batch_result.updated_count),
            failed=bool(batch_result.failed_count),
            reason=batch_result.halt_reason,
        )

    def analyze_news_items(self, news_items, progress_callback=None):
        execution_result = NewsAnalysisBatchExecutionResult()
        prepared_items = []
        total_count = len(news_items)
        processed_count = 0

        def report_progress():
            if progress_callback is None:
                return

            progress_callback(
                processed_count=processed_count,
                total_count=total_count,
                updated_count=execution_result.updated_count,
                failed_count=execution_result.failed_count,
                skipped_count=execution_result.skipped_current_count,
                halted=execution_result.halted,
            )

        for news_item in news_items:
            try:
                prepared_item = self._prepare_news_item(news_item)
            except NewsAnalysisError as error:
                self.persist_failure(news_item, str(error))
                execution_result.failed_count += 1
                execution_result.failure_details.append((news_item, str(error)))
                processed_count += 1
                report_progress()
                continue

            if prepared_item is None:
                execution_result.skipped_current_count += 1
                processed_count += 1
                report_progress()
                continue

            prepared_items.append(prepared_item)

        batch_start = 0
        while batch_start < len(prepared_items):
            batch = prepared_items[batch_start:batch_start + self.batch_size]
            try:
                results_by_id = self.provider.analyze_batch([prepared_item.context for prepared_item in batch])
            except NewsAnalysisRateLimitError as error:
                execution_result.halted = True
                execution_result.halt_reason = str(error)
                execution_result.halted_pending_count = len(prepared_items) - batch_start
                report_progress()
                break
            except NewsAnalysisError:
                processed_count = self._analyze_prepared_items_individually(
                    batch,
                    execution_result,
                    processed_count,
                    total_count,
                    progress_callback,
                )
                if execution_result.halted:
                    execution_result.halted_pending_count += len(prepared_items) - (batch_start + len(batch))
                    break

                batch_start += len(batch)
                continue

            batch_ids = {prepared_item.context.local_id for prepared_item in batch}
            if any(local_id not in batch_ids for local_id in results_by_id):
                processed_count = self._analyze_prepared_items_individually(
                    batch,
                    execution_result,
                    processed_count,
                    total_count,
                    progress_callback,
                )
                if execution_result.halted:
                    execution_result.halted_pending_count += len(prepared_items) - (batch_start + len(batch))
                    break

                batch_start += len(batch)
                continue

            missing_items = []
            for prepared_item in batch:
                analysis_result = results_by_id.get(prepared_item.context.local_id)
                if analysis_result is None:
                    missing_items.append(prepared_item)
                    continue

                _persist_analysis_success(
                    prepared_item.news_item,
                    analysis_result,
                    self.provider.provider_name,
                    self.provider.model_name,
                    prepared_item.input_hash,
                    self.pipeline_version,
                )
                execution_result.updated_count += 1
                processed_count += 1
                report_progress()

            if missing_items:
                processed_count = self._analyze_prepared_items_individually(
                    missing_items,
                    execution_result,
                    processed_count,
                    total_count,
                    progress_callback,
                )
                if execution_result.halted:
                    execution_result.halted_pending_count += len(prepared_items) - (batch_start + len(batch))
                    break

            batch_start += len(batch)

        return execution_result

    def persist_failure(self, news_item, error_message):
        _persist_analysis_failure(
            news_item,
            self.provider.provider_name,
            self.provider.model_name,
            self.pipeline_version,
            error_message,
        )

    def _prepare_news_item(self, news_item):
        article_content = _fetch_article_content(news_item.link, self.timeout_seconds)
        input_hash = _build_input_hash(news_item, article_content.text)
        existing_analysis = news_item.analysis_or_none

        if _analysis_is_current(existing_analysis, input_hash, self.pipeline_version):
            return None

        source_category = ''
        if news_item.source.category_id and news_item.source.category is not None:
            source_category = news_item.source.category.name

        context = NewsAnalysisContext(
            local_id=str(news_item.pk),
            source_name=news_item.source.name,
            source_category=source_category,
            title=news_item.title,
            source_summary=news_item.summary,
            published_at=_published_label(news_item.published_at),
            link=news_item.link,
            article_text=article_content.text,
        )
        return PreparedNewsAnalysis(
            news_item=news_item,
            input_hash=input_hash,
            context=context,
        )

    def _analyze_prepared_items_individually(
        self,
        prepared_items,
        execution_result,
        processed_count,
        total_count,
        progress_callback,
    ):
        def report_progress():
            if progress_callback is None:
                return

            progress_callback(
                processed_count=processed_count,
                total_count=total_count,
                updated_count=execution_result.updated_count,
                failed_count=execution_result.failed_count,
                skipped_count=execution_result.skipped_current_count,
                halted=execution_result.halted,
            )

        for index, prepared_item in enumerate(prepared_items):
            try:
                analysis_result = self.provider.analyze(prepared_item.context)
            except NewsAnalysisRateLimitError as error:
                execution_result.halted = True
                execution_result.halt_reason = str(error)
                execution_result.halted_pending_count += len(prepared_items) - index
                report_progress()
                break
            except NewsAnalysisError as error:
                self.persist_failure(prepared_item.news_item, str(error))
                execution_result.failed_count += 1
                execution_result.failure_details.append((prepared_item.news_item, str(error)))
                processed_count += 1
                report_progress()
                continue
            except requests.RequestException as error:
                provider_error = f'falha na consulta ao provider: {error}'
                self.persist_failure(prepared_item.news_item, provider_error)
                execution_result.failed_count += 1
                execution_result.failure_details.append((prepared_item.news_item, provider_error))
                processed_count += 1
                report_progress()
                continue

            _persist_analysis_success(
                prepared_item.news_item,
                analysis_result,
                self.provider.provider_name,
                self.provider.model_name,
                prepared_item.input_hash,
                self.pipeline_version,
            )
            execution_result.updated_count += 1
            processed_count += 1
            report_progress()

        return processed_count


def build_news_analysis_service():
    ai_settings = settings.NEWS_AI
    if not ai_settings['ENABLED']:
        return None, ''

    provider_name = (ai_settings['PROVIDER'] or '').strip().lower()
    if provider_name != 'openai':
        return None, f'IA não executada: provider "{provider_name}" não é suportado na V1.'

    try:
        service = NewsAnalysisService(
            provider=OpenAINewsAnalysisProvider(
                api_key=ai_settings['OPENAI_API_KEY'],
                model_name=ai_settings['MODEL'],
                base_url=ai_settings['OPENAI_BASE_URL'],
                timeout_seconds=ai_settings['TIMEOUT_SECONDS'],
                organization=ai_settings['OPENAI_ORG_ID'],
                project=ai_settings['OPENAI_PROJECT'],
            ),
            timeout_seconds=ai_settings['TIMEOUT_SECONDS'],
            pipeline_version=ai_settings['PIPELINE_VERSION'],
            batch_size=ai_settings['BATCH_SIZE'],
        )
    except NewsAnalysisConfigurationError as error:
        return None, str(error)

    return service, ''


def _build_openai_payload(model_name, contexts):
    items_payload = [
        {
            'item_id': context.local_id,
            'source_name': context.source_name,
            'source_category': context.source_category,
            'title': context.title,
            'source_summary': context.source_summary,
            'published_at': context.published_at,
            'link': context.link,
            'article_text': context.article_text,
        }
        for context in contexts
    ]

    return {
        'model': model_name,
        'input': [
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            'Você é um analista especializado em notícias fiscais, tributárias, regulatórias e '
                            'jurisprudenciais brasileiras. Responda apenas com JSON válido seguindo o schema '
                            'informado. Analise todos os itens recebidos. Seja conservador: quando não conseguir '
                            'inferir algo com segurança, retorne null ou lista vazia naquele item. O resumo deve '
                            'ser curto. O impacto deve refletir efeito prático para empresas e escritórios '
                            'contábeis. O score vai de 0 a 100, em que notícias de mudança real de obrigação, '
                            'alíquota, vigência, jurisprudência vinculante ou regra operacional relevante recebem '
                            'notas maiores. Notícias institucionais, promocionais ou genéricas recebem notas menores.'
                        ),
                    }
                ],
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': (
                            'Notícias para análise em JSON:\n'
                            f'{json.dumps(items_payload, ensure_ascii=False)}'
                        ),
                    }
                ],
            },
        ],
        'max_output_tokens': min(4000, max(1200, 700 * len(contexts))),
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'news_item_analysis_batch',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'items': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'additionalProperties': False,
                                'properties': {
                                    'item_id': {'type': 'string'},
                                    'summary': {'type': ['string', 'null']},
                                    'impact_level': {
                                        'type': ['string', 'null'],
                                        'enum': ['high', 'medium', 'low', None],
                                    },
                                    'impact_context': {'type': ['string', 'null']},
                                    'keywords': {
                                        'type': ['array', 'null'],
                                        'items': {'type': 'string'},
                                    },
                                    'importance_score': {'type': ['integer', 'null']},
                                    'effective_date': {'type': ['string', 'null']},
                                    'effective_date_label': {'type': ['string', 'null']},
                                },
                                'required': [
                                    'item_id',
                                    'summary',
                                    'impact_level',
                                    'impact_context',
                                    'keywords',
                                    'importance_score',
                                    'effective_date',
                                    'effective_date_label',
                                ],
                            },
                        }
                    },
                    'required': ['items'],
                },
            }
        },
    }


def _extract_openai_response_text(payload):
    for item in payload.get('output', []):
        for content in item.get('content', []):
            if content.get('type') == 'refusal':
                refusal_text = _clean_text(content.get('refusal', ''))
                raise NewsAnalysisProviderError(refusal_text or 'o provider recusou a análise.')

            text_value = content.get('text', '')
            if text_value:
                return text_value

    return ''


def _collect_openai_response_text(payload):
    top_level_text = payload.get('output_text', '')
    if isinstance(top_level_text, str) and top_level_text.strip():
        return top_level_text.strip()

    text_parts = []
    for item in payload.get('output', []):
        for content in item.get('content', []):
            if content.get('type') == 'refusal':
                refusal_text = _clean_text(content.get('refusal', ''))
                raise NewsAnalysisProviderError(refusal_text or 'o provider recusou a análise.')

            text_value = content.get('text', '')
            if isinstance(text_value, str) and text_value:
                text_parts.append(text_value)

    if text_parts:
        return ''.join(text_parts).strip()

    return _extract_openai_response_text(payload)


def _parse_structured_json_response(response_text):
    normalized_text = str(response_text or '').strip()
    if not normalized_text:
        raise json.JSONDecodeError('empty response', normalized_text, 0)

    candidate_texts = [
        normalized_text,
        _strip_markdown_code_fence(normalized_text),
        _extract_json_substring(normalized_text),
    ]

    last_error = None
    for candidate_text in candidate_texts:
        if not candidate_text:
            continue

        try:
            return json.loads(candidate_text)
        except json.JSONDecodeError as error:
            last_error = error

    raise last_error or json.JSONDecodeError('invalid json', normalized_text, 0)


def _strip_markdown_code_fence(value):
    match = re.match(r'^\s*```(?:json)?\s*(.*?)\s*```\s*$', value, re.DOTALL | re.IGNORECASE)
    if not match:
        return value

    return match.group(1).strip()


def _extract_json_substring(value):
    start_index = value.find('{')
    end_index = value.rfind('}')
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return ''

    return value[start_index:end_index + 1].strip()


def _normalize_batch_analysis_results(content, contexts):
    context_by_id = {context.local_id: context for context in contexts}

    if 'items' not in content:
        if len(contexts) != 1:
            raise NewsAnalysisProviderError('o provider não retornou um lote válido de análises.')

        return {contexts[0].local_id: _normalize_analysis_result(content)}

    items = content.get('items')
    if not isinstance(items, list):
        raise NewsAnalysisProviderError('o provider retornou um lote inválido de análises.')

    results_by_id = {}
    for item_content in items:
        if not isinstance(item_content, dict):
            raise NewsAnalysisProviderError('o provider retornou um item inválido no lote de análises.')

        item_id = _clean_text(item_content.get('item_id', ''))
        if not item_id or item_id not in context_by_id:
            raise NewsAnalysisProviderError('o provider retornou um identificador de item inválido.')

        if item_id in results_by_id:
            raise NewsAnalysisProviderError('o provider retornou itens duplicados no lote de análises.')

        results_by_id[item_id] = _normalize_analysis_result(item_content)

    return results_by_id


def _normalize_analysis_result(content):
    summary = _clean_text(content.get('summary', ''))
    impact_level = _normalize_impact_level(content.get('impact_level'))
    impact_context = _clean_text(content.get('impact_context', ''))
    keywords = _normalize_keywords(content.get('keywords'))
    importance_score = _normalize_importance_score(content.get('importance_score'))
    effective_date = _normalize_effective_date(content.get('effective_date'))
    effective_date_label = _clean_text(content.get('effective_date_label', ''))

    return NewsAnalysisResult(
        summary=summary,
        impact_level=impact_level,
        impact_context=impact_context,
        keywords=keywords,
        importance_score=importance_score,
        effective_date=effective_date,
        effective_date_label=effective_date_label,
    )


def _normalize_impact_level(value):
    normalized = _clean_text(value).lower()
    if normalized in {
        NewsItemAnalysis.IMPACT_HIGH,
        NewsItemAnalysis.IMPACT_MEDIUM,
        NewsItemAnalysis.IMPACT_LOW,
    }:
        return normalized

    return ''


def _normalize_keywords(value):
    if not isinstance(value, list):
        return []

    normalized_keywords = []
    seen_keywords = set()
    for item in value:
        keyword = _clean_text(item)
        if not keyword:
            continue

        lowered_keyword = keyword.casefold()
        if lowered_keyword in seen_keywords:
            continue

        seen_keywords.add(lowered_keyword)
        normalized_keywords.append(keyword)
        if len(normalized_keywords) == 5:
            break

    return normalized_keywords


def _normalize_importance_score(value):
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return None

    return max(0, min(100, numeric_value))


def _normalize_effective_date(value):
    cleaned_value = _clean_text(value)
    if not cleaned_value:
        return None

    try:
        return date.fromisoformat(cleaned_value)
    except ValueError:
        return None


def _analysis_is_current(existing_analysis, input_hash, pipeline_version):
    if existing_analysis is None:
        return False

    if existing_analysis.status != NewsItemAnalysis.STATUS_COMPLETED:
        return False

    if existing_analysis.pipeline_version != pipeline_version:
        return False

    return existing_analysis.input_hash == input_hash


def _build_input_hash(news_item, article_text):
    raw_value = '\n'.join([
        news_item.source.name,
        news_item.source.category.name if news_item.source.category_id else '',
        news_item.title,
        news_item.summary,
        news_item.link,
        _published_label(news_item.published_at),
        article_text,
    ])
    normalized_value = re.sub(r'\s+', ' ', raw_value).strip().casefold()
    return hashlib.sha256(normalized_value.encode('utf-8')).hexdigest()


def _published_label(value):
    if value is None:
        return ''

    localized_value = timezone.localtime(value) if timezone.is_aware(value) else value
    return localized_value.isoformat()


def _persist_analysis_success(news_item, analysis_result, provider_name, model_name, input_hash, pipeline_version):
    now = timezone.now()

    with transaction.atomic():
        analysis, _ = NewsItemAnalysis.objects.get_or_create(news_item=news_item)
        analysis.summary = analysis_result.summary
        analysis.impact_level = analysis_result.impact_level
        analysis.impact_context = analysis_result.impact_context
        analysis.keywords = analysis_result.keywords
        analysis.importance_score = analysis_result.importance_score
        analysis.effective_date = analysis_result.effective_date
        analysis.effective_date_label = analysis_result.effective_date_label
        analysis.status = NewsItemAnalysis.STATUS_COMPLETED
        analysis.provider = provider_name
        analysis.model = model_name
        analysis.input_hash = input_hash
        analysis.pipeline_version = pipeline_version
        analysis.error_message = ''
        analysis.analyzed_at = now
        analysis.last_attempt_at = now
        analysis.save()


def _persist_analysis_failure(news_item, provider_name, model_name, pipeline_version, error_message):
    now = timezone.now()

    with transaction.atomic():
        analysis, created = NewsItemAnalysis.objects.get_or_create(news_item=news_item)
        if created or analysis.status != NewsItemAnalysis.STATUS_COMPLETED:
            analysis.summary = ''
            analysis.impact_level = ''
            analysis.impact_context = ''
            analysis.keywords = []
            analysis.importance_score = None
            analysis.effective_date = None
            analysis.effective_date_label = ''
            analysis.status = NewsItemAnalysis.STATUS_FAILED

        analysis.provider = provider_name
        analysis.model = model_name
        analysis.pipeline_version = pipeline_version
        analysis.error_message = _clean_text(error_message)[:255]
        analysis.last_attempt_at = now
        analysis.save()


def _fetch_article_content(url, timeout_seconds):
    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                'User-Agent': 'PI-Fiscalia/1.0 (+https://127.0.0.1:8000)',
                'Accept': 'text/html,application/xhtml+xml',
            },
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise NewsArticleExtractionError(f'falha ao buscar a matéria original: {error}') from error

    content_type = response.headers.get('Content-Type', '')
    if content_type and 'html' not in content_type.lower():
        raise NewsArticleExtractionError('a matéria original não é uma página HTML suportada.')

    article_text = _extract_article_text(response.text)
    if len(article_text) < MIN_ARTICLE_TEXT_LENGTH:
        raise NewsArticleExtractionError('não foi possível extrair texto suficiente da matéria original.')

    page_title = _extract_page_title(response.text)
    return NewsArticleContent(text=article_text, page_title=page_title)


def _extract_article_text(html_content):
    cleaned_html = NON_CONTENT_BLOCK_PATTERN.sub(' ', html_content)
    candidates = []

    for pattern in HTML_BLOCK_PATTERNS:
        for match in pattern.finditer(cleaned_html):
            candidate_text = _clean_text(match.group(1))
            if candidate_text:
                candidates.append(candidate_text)

    if candidates:
        candidates.sort(key=len, reverse=True)
        return candidates[0][:MAX_ARTICLE_TEXT_LENGTH]

    body_match = re.search(r'(?is)<body\b[^>]*>(.*?)</body>', cleaned_html)
    body_content = body_match.group(1) if body_match else cleaned_html
    return _clean_text(body_content)[:MAX_ARTICLE_TEXT_LENGTH]


def _extract_page_title(html_content):
    match = TITLE_PATTERN.search(html_content)
    if not match:
        return ''

    return _clean_text(match.group(1))


def _clean_text(value):
    if not value:
        return ''

    text = strip_tags(str(value))
    text = html.unescape(text)
    text = text.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _extract_openai_error_details(response):
    payload = {}
    try:
        payload = response.json()
    except (AttributeError, TypeError, ValueError):
        payload = {}

    error_payload = payload.get('error') if isinstance(payload, dict) else {}
    if not isinstance(error_payload, dict):
        error_payload = {}

    error_type = _clean_text(error_payload.get('type', '')).lower()
    error_code = _clean_text(error_payload.get('code', '')).lower()
    error_message = _clean_text(error_payload.get('message', ''))

    if _is_openai_quota_error(error_type, error_code, error_message):
        return 'insufficient_quota', 'insufficient_quota', _build_openai_quota_message(error_message)

    fallback_message = error_message or _clean_text(getattr(response, 'text', ''))
    return error_type, error_code, fallback_message


def _describe_openai_http_error(response, error):
    status_code = getattr(response, 'status_code', None)
    error_type, error_code, error_message = _extract_openai_error_details(response)

    details = []
    if status_code:
        details.append(f'HTTP {status_code}')
    if error_type:
        details.append(f'type={error_type}')
    if error_code:
        details.append(f'code={error_code}')

    detail_prefix = ' '.join(details).strip()
    provider_detail = error_message or _clean_text(str(error))

    if detail_prefix and provider_detail:
        return f'falha na consulta ao provider: {detail_prefix}. {provider_detail}'
    if detail_prefix:
        return f'falha na consulta ao provider: {detail_prefix}'

    return f'falha na consulta ao provider: {provider_detail or error}'


def _is_openai_quota_error(error_type, error_code, error_message):
    normalized_message = _clean_text(error_message).casefold()
    markers = ' '.join([error_type or '', error_code or '', normalized_message])
    return any(marker in markers for marker in (
        'insufficient_quota',
        'current quota',
        'monthly spend',
        'usage limit',
        'billing',
        'credit',
        'credits',
        'budget',
        'quota',
    ))


def _build_openai_quota_message(error_message):
    provider_detail = _clean_text(error_message)
    base_message = (
        'a API da OpenAI recusou a análise por quota, crédito ou orçamento insuficiente. '
        'Verifique Usage, Limits e Billing da organização/projeto na plataforma.'
    )
    if not provider_detail:
        return base_message

    return f'{base_message} Detalhe do provider: {provider_detail}'


def _build_openai_rate_limit_message(error_message):
    provider_detail = _clean_text(error_message)
    base_message = 'a API da OpenAI bloqueou temporariamente novas análises por limite de requisições ou tokens.'
    if not provider_detail:
        return base_message

    return f'{base_message} Detalhe do provider: {provider_detail}'


def _parse_retry_after_seconds(value):
    try:
        retry_after_seconds = int(str(value).strip())
    except (TypeError, ValueError):
        return None

    return max(0, retry_after_seconds)
