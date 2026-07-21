"""Public API for HLPP L0 Contracts (renamed from hlpp-l0-contracts 2026-05-20 v0.2.0).

NEW v0.2.0+ HLPP modules:
- schemas/   — Pydantic models for HLPP-NORMALIZED + HLPP-COMPUTED (spec §7-§8)
- universe/  — Versioned ticker universe (v2_120 = 120 tickers, v1_130 legacy)
- validators — validate_normalized() / validate_computed() gate before parquet write
- git_meta   — git_commit_hash() auto-inject for builder_version/analysis_version

LEGACY (kept from hlpp_l0_contracts 0.1.x):
collector, llm, schema (CrawlerBase), protocols, browser_fetch, http,
idempotency, stamping, sources_config, backfillable, source_status.
"""

from . import schemas, universe, validators, git_meta  # noqa: F401
__version__ = "0.5.7"

from .browser_fetch import (
    BrowserFetchAuthError,
    BrowserFetchBadRequest,
    BrowserFetchClient,
    BrowserFetchError,
    BrowserFetchPoolTimeout,
    BrowserFetchServerError,
    BrowserFetchTimeoutError,
    BrowserFetchUnavailable,
    BrowserFetchUpstreamFailed,
    Cookie,
    HealthResult,
    RenderResult,
)
from .collector.base import BaseCollector, RawArticle
from .llm.provider import AIProvider, AIResponse, ProviderChain
from .llm.usage import AIUsage, UsageRecord
from .llm.budget import BudgetExceeded, CostBudgetGuard
from .http import HttpClient
from .schema.crawler_base import (
    CRAWLER_BASE_COLUMNS,
    CrawlerBaseSchema,
    _CrawlerBaseMixin,
)
from .schema.lineage import LineageSchema, _LineageMixin
from .schema.provenance import BronzeProvenanceSchema, _BronzeProvenanceMixin
from .schema.vintage import VintageSchema, _VintageMixin
from .protocols import (
    Backfillable,
    BackfillResult,
    BackfillTargetYearUnavailable,
    BarData,
    TierAStreamConsumer,
    TierAStreamSession,
)
from .sources_config import SourceEntry, load_sources_yaml
from .idempotency import idempotent_insert, sha256_url
from .stamping import stamp_for_bronze

__all__ = [
    # browser_fetch
    "BrowserFetchClient",
    "Cookie",
    "RenderResult",
    "HealthResult",
    "BrowserFetchError",
    "BrowserFetchUnavailable",
    "BrowserFetchAuthError",
    "BrowserFetchTimeoutError",
    "BrowserFetchBadRequest",
    "BrowserFetchUpstreamFailed",
    "BrowserFetchPoolTimeout",
    "BrowserFetchServerError",
    # collector
    "BaseCollector",
    "RawArticle",
    "ProviderChain",
    "AIProvider",
    "AIResponse",
    "AIUsage",
    "UsageRecord",
    "CostBudgetGuard",
    "BudgetExceeded",
    "HttpClient",
    "Backfillable",
    "BackfillResult",
    "BackfillTargetYearUnavailable",
    "BarData",
    "TierAStreamConsumer",
    "TierAStreamSession",
    "_BronzeProvenanceMixin",
    "BronzeProvenanceSchema",
    "_LineageMixin",
    "LineageSchema",
    "_VintageMixin",
    "VintageSchema",
    "_CrawlerBaseMixin",
    "CrawlerBaseSchema",
    "CRAWLER_BASE_COLUMNS",
    "load_sources_yaml",
    "SourceEntry",
    "sha256_url",
    "idempotent_insert",
    "stamp_for_bronze",
]
