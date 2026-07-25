# Changelog

## 0.5.8 - 2026-07-25

**`SourceEntry.last_verified_at` becomes nullable (still required)**

- **FIX `SourceEntry`**: `last_verified_at: datetime` -> `datetime | None`. The key stays mandatory, exactly like the sibling `disabled_reason: str | None` right above it, so nobody can forget to state it; what changes is that an explicit `null` is now a legal value meaning "registered, never verified yet".

  That state is real rather than a placeholder. Push-stream sources have to be registered active *before* their first live session, because a session nobody records cannot be recovered afterwards, so there is genuinely no verified timestamp to declare until the session runs. `l1a/fqx/sources.yaml` hit this on 2026-07-25 with `m12-fqx-bidask-v1` and `m12-fqx-orderbook-changes-v1`: the whole file stopped validating, not just those two entries, because `load_sources_yaml` validates the document as a unit.

  This aligns the pydantic model with the rest of the codebase, which already treats null as legitimate: `l1a/research/contracts/reports_v1.py` declares the same column `nullable=True, required=True`, and several research collectors already emit `last_verified_at: None`.

- **TEST**: added coverage for both halves of the guarantee — explicit `null` is accepted, and an entry that omits the key entirely is still rejected, so "nullable" cannot quietly decay into "optional".

## 0.5.7 - 2026-07-21

**CONTRACTS-B09-D1: sync 4 pydantic models to already-shipped on-disk columns (G2-B09 contract-drift close)**

Ground-truthed against the real on-disk `~/HLPP-HOT/NORMALIZED` lake (latest partition per store) — every field below was already being written by the builder and physically present on disk; the pydantic model simply never declared it, so G2-B09 (`hlpp_pipelines.qa.bells_contract`, `pydantic_normalized` mechanism) RANG contract-drift for 4 stores.

- **FIX `FundamentalsQuarterly` / `FundamentalsAnnual`** (both, identically): add 29 fields ground-truthed against the live lake —
  - 10 per-share recompute audit columns (P11 Phương án A, `hlpp_pipelines.l1b.pershare_recompute`): `eps_basic_vendor`, `bvps_vendor`, `roe_vendor`, `roa_vendor`, `eps_diluted_recomputed`, `shares_outstanding_pit`, `eps_source`, `bvps_source`, `roe_source`, `roa_source`.
  - 1 general-surface field: `accounts_receivable`.
  - 4 bank-surface fields (fq-D4): `fee_commission_income`, `net_fee_income`, `credit_provision_expense`, `non_performing_loans`.
  - 6 securities-surface fields (fq-D4): `advisory_revenue`, `agency_underwriting_revenue`, `operating_revenue`, `client_deposits`, `available_for_sale_securities`, `held_to_maturity_securities`.
  - 8 insurance-surface fields (fq-D4): `premium_earned`, `claims_paid`, `claims_reserves`, `underwriting_expenses`, `underwriting_result`, `investment_income`, `technical_reserves`, `unexpired_risk_reserve`.
- **FIX `NewsHeadlineNormalized`**: add 3 news-revival-byproduct fields — `extraction_status`, `published_at_confidence`, `dedup_content_hash`.
- **FIX `ReportTextNormalized`**: add `body_text_hash` (SHA-256 of `body_text` alone, RPT-D4 — distinct from the shared ADR-022 `content_hash`).

All additive/backward-compatible (every new field is `Optional`/has a default). `l1b_bank_credit_quality`'s missing `business_date` (also flagged under this ticket) is declared on a `hlpp_pipelines`-local `SilverContract` dataclass, not a pydantic model in this package — fixed directly in `hlpp-pipelines/src/hlpp_pipelines/contracts/l1b_bank_credit_quality.py`, out of scope for this changelog.

## 0.5.3 - 2026-05-29

**Inline validation alignment: business_date + contract field fixes (Gate 6.1 / Decision-A)**

- **FIX `PriceDaily`**: `value_traded` → `float | None` (vnstock-fallback rows lack this field);
  `volume` type relaxed to `float` (FQX emits Float64, not int).
- **FIX `ForeignFlowDaily`**: `foreign_buy_volume` / `foreign_sell_volume` → `float` (vendor
  emits Float64); `foreign_net_volume` → `float | None` (not present in all m12 feeds).
- **FIX `CorpEventsParsed`**: `event_date` → `date | None` (DEGRADED rows with all-null vendor
  date fields emit null event_date, marked via `degraded_blocks="unparseable_date"`).
- **NOTE**: `business_date` (required on `HlppNormalizedBase`) is now populated by all 12
  ADR-022 L1b builders. Tier-B builders (intraday_snapshot, price_intraday_30s) remain exempt.

## 0.4.3 - 2026-05-28

**`ReportTextNormalized` L1b payload schema**

- **SCHEMA**: add `ReportTextNormalized` to `schemas/normalized.py` for the new
  L1b silver `silver_report_text_daily` (hlpp-pipelines). Carries raw analyst
  report / market-commentary text pulled by `ai-api-crawlers` text-only
  wirings (PDF → pdfplumber → boilerplate strip → body_text). Payload columns:
  `source_id`, `ctck_source`, `title`, `report_date`, `landing_url`,
  `pdf_url`, `ticker_mentions`, `body_text`, `char_count`, `page_count`,
  `content_hash`, `extracted_via` (Literal pdfplumber/html_summary/html_body),
  `status` (Literal OK/PDF_FETCH_FAILED/INVALID_PDF/NO_TEXT_EXTRACTED),
  `fetch_error`, `origin_observation_id`, `observation_id`. `vendor` pinned
  to `"internal"`. Additive, backward-compatible.

## 0.4.2 - 2026-05-28

**`report_text` source family**

- **SCHEMA**: extend `SourceFamily` `Literal` with `"report_text"` for the
  text-only enricher tier (PDF/HTML → relevant text, no LLM). Additive,
  backward-compatible. Consumed by `ai-api-crawlers/text/ReportTextExtractor`
  to emit raw analyst-report text observations that the downstream
  sentiment/tone/numbers tier reads.

## 0.4.0 - 2026-05-26

**Wave 8 research-papers contract**

- **NEW `hlpp_l0_contracts.schemas.research_papers`** — Pydantic `ResearchPaperV1`
  contract for Wave 8 academic-paper collectors (SSRN, RePEc, AMRO, IMF working-papers,
  OECD, Heliyon, VEPR, Fulbright FSPPM). Monthly PDF + metadata polling.
  - Required fields: `paper_id` (DOI or hash), `source` (8-source enum), `title`,
    `authors` (non-empty list), `published_at`, `language` (ISO 639-1), `as_of_date`
    (PIT partition key).
  - Optional: `abstract`, `pdf_url`, `doi` (canonical 10.NNNN/... form),
    `keywords`, `ticker_mentions` (populated by L2 TickerResolver NLP; L0 leaves
    `[]`), `paper_type` (`working_paper` / `journal` / `policy_brief` /
    `conference`), `institution`, `source_metadata` (vendor-specific raw fields).
  - Validators: PIT discipline (`as_of_date >= published_at`), DOI regex,
    language ISO 639-1, paper_id charset, non-empty authors+title.
  - `extra="forbid"` + `frozen=True` per existing L0 schema discipline.
- Re-exported from `hlpp_l0_contracts.schemas` package surface as `ResearchPaperV1`,
  `ResearchSource`, `PaperType` for downstream collector + L2 NLP consumers.
- **Tests:** +35 new tests in `test_research_papers_schema.py` covering enum,
  PIT discipline, DOI canonical form, frozen model, optional defaults,
  round-trip dict, and ISO 639-1 language enforcement.
- **Version:** `0.3.0` → `0.4.0` (minor bump; backward-compatible additive).

## 0.2.0 - 2026-05-21

**HLPP rebrand + foundation contracts**

- **BREAKING (soft):** Package renamed `ht-l1-core` → `hlpp-l0-contracts`. Old import path
  `ht_l1_core` was supported via a backward-compat shim (removed in Phase 8b / v0.5.5+).
  Use `hlpp_l0_contracts` directly.
- **GitHub:** repo renamed `hgthinhng/ht-l1-core` → `hgthinhng/hlpp-l0-contracts` (PUBLIC,
  old URL auto-redirects 90 days). Git remote updated; module imports mass find/replaced
  across src/, tests/, docs/, pyproject.toml, README, CHANGELOG, Makefile.
- **NEW `hlpp_l0_contracts.schemas`** — Pydantic contracts for the HLPP v1.0 storage
  taxonomy (spec §7-§8 in `~/.omc/plans/2026-05-20-hlpp-v1-architecture.md`):
  - `schemas.base.HlppNormalizedBase` — mandatory L1b cols (ticker, as_of_date,
    business_date, business_time, vendor, ingested_at, schema_id, dataset_id,
    builder_version). Frozen, `extra="forbid"`.
  - `schemas.base.HlppComputedBase` — extends NORMALIZED + adds analysis lineage
    (analysis_version, input_partitions, chain_depth ∈ l2a..l2f, domain ∈ factor/ta/fa
    /signal/regime/alert, lookback_days).
  - `schemas.normalized` — 5 sample L1b payloads (PriceIntraday30s, PriceDaily,
    ForeignFlowDaily, FundamentalsQuarterly, Ticker360). 6 remaining classified in spec
    §9 deferred to Phase 4 builder migration.
  - `schemas.computed` — 10 sample L2 payloads spanning L2a (FactorSize, FactorMomentum
    _12_1m, FactorQuality, CapmBeta, TaIndicator, FaDupont3Way), L2b (FactorResidualMomentum,
    Peg, RegimeMarkovVnindex), and L2c (SignalBlend).
- **NEW `hlpp_l0_contracts.universe`** — versioned YAML loader. Ships skeleton
  `v2_120.yaml` (120 tickers = VN30 + HOSE50_ex_VN30 + HNX30 + UPCOM10) + the
  `ticker_master_v1_seed.csv` (1534-row full universe reference, migrated from
  `silver-builders-seed/`). Sub-pool tickers populated from vendor query at Phase 8a.
- **NEW `hlpp_l0_contracts.validators`** — `validate_normalized()` and
  `validate_computed()` gate parquet writes; check mandatory columns, dataset_id /
  chain_depth / domain uniformity, plus Pydantic row sampling. Raise
  `SchemaValidationError`. CI lint (deferred) will enforce a call upstream of every
  `to_parquet()` in pipelines source.
- **NEW `hlpp_l0_contracts.git_meta`** — `git_commit_hash()` (LRU-cached, short or full)
  and `git_dirty()` to auto-inject `builder_version` / `analysis_version`. Rejects
  manual semver bumps (per Gemini round-2 critic — solo-dev bumps get forgotten).
- **Tests:** +30 new tests across `test_hlpp_schemas_base.py`, `test_hlpp_universe.py`,
  `test_hlpp_validators.py`, `test_hlpp_git_meta.py`. Total suite: **167 pass**.

## 0.1.9 - 2026-05-10

- feat(L1-W6.JB6.a + JB4): Backfillable Protocol + SourceStatus enum + emit_skipped_row helper
- Added `hlpp_l0_contracts.backfillable` module with `@backfillable_check` decorator that wraps
  collector methods and raises `RuntimeError` when all returned rows have today's date instead
  of the requested `target_year` (anti-reestamp guard).  Re-exports `Backfillable`,
  `BackfillResult`, `BackfillTargetYearUnavailable` from `hlpp_l0_contracts.protocols`.
- Added `hlpp_l0_contracts.source_status` module with `SourceStatus` (`StrEnum`: ACTIVE,
  EXTERNAL_DEAD, EXPERIMENTAL), `SourceManifestEntry` dataclass, and `emit_skipped_row`
  helper that returns a 20-col `CrawlerBaseSchema`-shaped row with `status="SKIPPED"`.
  Loud WARNING log fires whenever `status=EXTERNAL_DEAD` per loud-fail discipline.

## 0.1.8 - 2026-05-10

- Removed the silent `metadata.version()` fallback from `_code_sha`. When git checkout
  detection fails and `HT_CODE_SHA` is unset, provenance stamping now raises a loud
  `RuntimeError` instead of writing parquet with a stale package version.

## 0.1.7 - 2026-05-10

- **MAJOR fix (Codex):** `BrowserFetchClient` default timeout raised from 30 s → 45 s.
  Aligns with service legal maximum: `QUEUE_TIMEOUT_MS` (10 s) + `MAX_RENDER_MS` (30 s) + 5 s
  network overhead. Prevents false `BrowserFetchTimeoutError` on valid queued renders.
  Module-level constant `DEFAULT_TIMEOUT_S = 45.0` exported for callers that need to
  reference the rationale in their own code.
- **MINOR fix (Gemini):** `BrowserFetchError` base class and all subclasses now accept and
  expose a `fetch_ms: int | None` attribute. `_parse_render_response` plumbs `fetch_ms` from
  the service error envelope (SERVICE_SPEC §3) to the raised exception. Consumers can now
  observe how long the upstream attempted before failing (e.g. 30 001 ms on a 504
  RENDER_TIMEOUT). `None` when the error is transport-level (TCP timeout, connection refused).
  Backwards-compatible additive change.

## 0.1.6 - 2026-05-10

- Added `BrowserFetchClient` — sync typed client for the hlpp-l0-browser L0 headless-Chromium
  rendering service (ADR-019). Includes `RenderResult`, `HealthResult`, `Cookie` dataclasses
  and a full loud-fail error hierarchy (`BrowserFetchUnavailable`, `BrowserFetchAuthError`,
  `BrowserFetchTimeoutError`, `BrowserFetchBadRequest`, `BrowserFetchUpstreamFailed`,
  `BrowserFetchPoolTimeout`, `BrowserFetchServerError`). Built-in 429 retry (3 attempts,
  base 1 s, cap 8 s). Sync-only; async client deferred to v0.1.7+.

## 0.1.5 - 2026-05-07

- Clarified ADR-016 notation, rationale, trigger-transport consequences, and Tier-A protocol
  inventory.
- Expanded `TierAStreamConsumer` and `TierAStreamSession` lifecycle docstrings and documented
  `BarData.observed_at` timezone-awareness.
- Documented collector-specific keyword passthrough for `Backfillable.backfill`.

## 0.1.4 - 2026-05-07

- Added `Backfillable`, `BackfillResult`, and `BackfillTargetYearUnavailable` protocol
  contracts for target-year backfill collectors.
- Added `TierAStreamConsumer`, `TierAStreamSession`, and `BarData` protocol contracts for
  Tier-A stream consumers.
- Added ADR-016 documenting the tiered L1→L2 trigger transport matrix.
