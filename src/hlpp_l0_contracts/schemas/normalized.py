"""HLPP-NORMALIZED payload schemas per L1b dataset.

Each class extends HlppNormalizedBase + adds dataset-specific payload columns.
Builder must instantiate this class for each row before parquet write.

Per spec §9 classification (11 L1b datasets):
- price-intraday-30s, price-daily, foreign-flow-daily, index-daily
- block-deals, insider-trades, large-shareholders, corp-events-parsed
- liquidity-filters-daily, fundamentals-quarterly, ticker-360

Also includes:
- fundamentals-annual  (surface-aware; 44 payload cols + nullable surface-specifics)
- intraday-snapshot    (Tier-B; lite base — ADR-022 stamping intentionally omitted)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import HlppNormalizedBase


class PriceIntraday30s(HlppNormalizedBase):
    """30-second OHLC bars from m12-fqx-ohlcv-intraday raw snapshots."""

    adjustment_type: Literal["raw"] = "raw"
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: int = Field(..., ge=0)
    value: float = Field(..., ge=0)


class PriceDaily(HlppNormalizedBase):
    """Daily OHLC + adjustments from vnstock VCI EOD / FQX adjusted.

    Field names match the stable builder output columns (v3.1+):
    - ``close_adj``: split + dividend backward-adjusted close (was ``close_adjusted`` pre-v3.1)
    - ``value_traded``: total session traded value in VND (was ``value`` pre-v3.1)
    ``business_time`` from the base is irrelevant for daily bars and is left null.
    """

    adjustment_type: Literal["backward_adjusted"] = "backward_adjusted"
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    close_adj: float = Field(..., ge=0, description="Split + dividend backward-adjusted close")
    volume: int = Field(..., ge=0, description="Volume (canonical Int64; builder casts Float64 vendor output to int before validation)")
    value_traded: float | None = Field(
        None,
        ge=0,
        description=(
            "Total session traded value (VND). "
            "Null for vnstock-fallback rows (vendor does not provide value_traded); "
            "non-null for FQX rows."
        ),
    )


class ForeignFlowDaily(HlppNormalizedBase):
    """Daily foreign buy/sell flow aggregate.

    Field names use the ``foreign_`` prefix matching the stable builder output columns
    (silver_foreign_flow_daily _PAYLOAD_COLUMNS). The prefix distinguishes foreign-investor
    flow from total-market flow and matches the FQX vendor field naming convention.
    """

    adjustment_type: Literal["raw"] = "raw"
    foreign_buy_volume: float = Field(
        ..., ge=0, description="Foreign buy volume (Float64; vendor emits float not int)"
    )
    foreign_sell_volume: float = Field(
        ..., ge=0, description="Foreign sell volume (Float64; vendor emits float not int)"
    )
    foreign_buy_value: float = Field(..., ge=0)
    foreign_sell_value: float = Field(..., ge=0)
    foreign_net_volume: float | None = Field(
        None,
        description=(
            "Foreign net volume (buy − sell). "
            "Not present in all m12-fqx-foreign-flow-v1 feeds; null when absent."
        ),
    )
    foreign_net_value: float


class FundamentalsQuarterly(HlppNormalizedBase):
    """Quarterly BCTC fundamentals — surface-aware unified schema (5 surfaces).

    Mirrors FundamentalsAnnual's 44-column surface-aware schema (see that class
    for column-group documentation) but at quarterly granularity: ``period`` is a
    quarter string (e.g. '2025-Q4') and ``tet_q1_seasonal_flag`` marks Q1 rows of
    Tet-affected (FMCG/retail) issuers.

    Source: 5 BCTC m12 contracts routed via ICB → surface mapping, quarterly periods.
    PK: (ticker, period_end_date). Surface-specific columns are NULL for rows
    belonging to other surfaces; ``bctc_surface`` indicates which group is populated.

    REVISION (2026-05-29, Decision-A Task B / Wave 3): replaced the prior generic
    stub (fiscal_year/fiscal_quarter/revenue/net_income/eps/book_value_per_share)
    which was structurally incompatible with the surface-aware builder output.
    """

    adjustment_type: Literal["raw"] = "raw"

    # Identity
    period: str | None = Field(None, description="Fiscal quarter string e.g. '2025-Q4'")
    period_end_date: date | None = Field(None, description="Fiscal quarter end date")
    report_type: str | None = Field(None, description="'quarter' for quarterly rows")
    accounting_framework: str | None = Field(None, description="e.g. VAS / IFRS")
    bctc_surface: str = Field(
        ...,
        description="BCTC routing surface: general / bank / securities / insurance / fund",
    )

    # Universal (all 5 surfaces)
    net_profit_after_tax: float | None = None
    total_assets: float | None = None
    roe: float | None = None

    # Common-4 (general/bank/securities/insurance; null for fund)
    total_equity: float | None = None
    eps_basic: float | None = None
    bvps: float | None = None
    roa: float | None = None

    # Per-share recompute audit columns (P11 Phương án A, hlpp_pipelines.l1b.
    # pershare_recompute; general/bank/securities/insurance -- excluded for fund,
    # whose per-share economics are NAV/unit-based). eps_basic/bvps/roe/roa above
    # are COALESCED: field_recomputed when the recompute's own inputs (NPAT/
    # equity/assets/shares_outstanding_pit) resolved, else field_vendor unmodified
    # -- a resolve-miss on this arc's own inputs never blanks a real vendor value.
    eps_basic_vendor: float | None = Field(
        None, description="Vendor-reported eps_basic, preserved unmodified for audit (P11 coalesce)"
    )
    bvps_vendor: float | None = Field(
        None, description="Vendor-reported bvps, preserved unmodified for audit (P11 coalesce)"
    )
    roe_vendor: float | None = Field(
        None, description="Vendor-reported roe, preserved unmodified for audit (P11 coalesce)"
    )
    roa_vendor: float | None = Field(
        None, description="Vendor-reported roa, preserved unmodified for audit (P11 coalesce)"
    )
    eps_diluted_recomputed: float | None = Field(
        None,
        description=(
            "Always null -- eps_diluted is never recomputed (no dilutive-instrument "
            "data anywhere in the lake for any surface); vendor eps_diluted passes "
            "through completely untouched. Kept as an explicit audit column per the "
            "coalesce convention (P11 point 3)."
        ),
    )
    shares_outstanding_pit: float | None = Field(
        None,
        description=(
            "PIT-per-period shares outstanding used for the eps_basic/bvps recompute, "
            "resolved as-of period_end_date + 45d (quarterly publication lag, used for "
            "BOTH FQ and FA to keep the shares-lookup anchor identical) against "
            "m12-fqx-freefloat-v1 history via a backward as-of join. Null when "
            "unresolved -- e.g. pre-2019-01-02 freefloat coverage boundary, or ticker "
            "has no eligible snapshot -- never silently clamped to nearest available."
        ),
    )
    eps_source: str = Field(
        "vendor_coalesced",
        description="'recomputed' when eps_basic used the NPAT/shares_outstanding_pit recompute, else 'vendor_coalesced'",
    )
    bvps_source: str = Field(
        "vendor_coalesced",
        description="'recomputed' when bvps used the equity/shares_outstanding_pit recompute, else 'vendor_coalesced'",
    )
    roe_source: str = Field(
        "vendor_coalesced",
        description="'recomputed' when roe used the TTM-NPAT/avg-equity recompute, else 'vendor_coalesced'",
    )
    roa_source: str = Field(
        "vendor_coalesced",
        description="'recomputed' when roa used the TTM-NPAT/avg-assets recompute, else 'vendor_coalesced'",
    )

    # General-only
    net_sales: float | None = None
    gross_profit: float | None = None
    operating_profit: float | None = None
    total_debt: float | None = None
    cash: float | None = None
    operating_cash_flow: float | None = None
    eps_diluted: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None

    # General-only forensic/credit line-items (Altman EMS, Beneish M, DuPont-5)
    retained_earnings: float | None = None
    fixed_assets: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    profit_before_tax: float | None = None
    selling_expenses: float | None = None
    general_admin_expenses: float | None = None
    depreciation_amortization: float | None = None
    cost_of_sales: float | None = None
    inventory: float | None = None
    accounts_receivable: float | None = None
    accounts_payable: float | None = None
    short_term_investments: float | None = None

    # Bank-only
    net_interest_income: float | None = None
    loans_to_customers: float | None = None
    deposits_from_customers: float | None = None
    npl_ratio: float | None = None
    capital_adequacy_ratio: float | None = None
    tier1_capital_ratio: float | None = None
    nim: float | None = None
    # Bank Wave-4 income-statement line-items (RE-contagion / PPOP / pre-provision)
    loan_loss_reserves: float | None = None
    operating_expenses: float | None = None
    operating_income: float | None = None
    # Bank Wave-4 NIM-decomposition: gross interest income/expense (P2.6)
    interest_income: float | None = None
    interest_expense: float | None = None
    # Bank fq-D4: fee/credit-provision + regulatory NPL line-items
    fee_commission_income: float | None = None
    net_fee_income: float | None = None
    credit_provision_expense: float | None = None
    non_performing_loans: float | None = Field(
        None, description="Regulatory NPL balance (Circular-11 groups 3-5), distinct from npl_ratio"
    )

    # Securities-only
    brokerage_revenue: float | None = None
    proprietary_trading_pnl: float | None = None
    margin_lending_interest_income: float | None = None
    margin_loans_outstanding: float | None = None
    trading_securities: float | None = None
    # Securities fq-D4: revenue-mix + balance-sheet line-items
    advisory_revenue: float | None = None
    agency_underwriting_revenue: float | None = None
    operating_revenue: float | None = None
    client_deposits: float | None = None
    available_for_sale_securities: float | None = None
    held_to_maturity_securities: float | None = None

    # Insurance-only
    gross_written_premium: float | None = None
    net_written_premium: float | None = None
    claims_incurred: float | None = None
    combined_ratio: float | None = None
    solvency_capital_ratio: float | None = None
    # Insurance fq-D4: underwriting + technical-reserve line-items
    premium_earned: float | None = None
    claims_paid: float | None = None
    claims_reserves: float | None = None
    underwriting_expenses: float | None = None
    underwriting_result: float | None = None
    investment_income: float | None = None
    technical_reserves: float | None = None
    unexpired_risk_reserve: float | None = None

    # Fund-only
    total_aum: float | None = None
    total_nav: float | None = None
    nav_per_unit: float | None = None
    units_outstanding: float | None = None
    expense_ratio: float | None = None

    # Quarterly-specific
    tet_q1_seasonal_flag: bool | None = Field(
        None, description="True on Q1 rows of Tet-affected (FMCG/retail) issuers"
    )


class Ticker360(HlppNormalizedBase):
    """Ticker info aggregate — industry, mcap, free-float, foreign room, etc."""

    exchange: str = Field(..., description="HOSE/HNX/UPCOM")
    icb_code: str | None = None
    icb_name: str | None = None
    market_cap: float | None = Field(None, ge=0)
    free_float_pct: float | None = Field(None, ge=0, le=1)
    foreign_room_pct: float | None = Field(None, ge=0, le=1)
    state_owner_pct: float | None = Field(None, ge=0, le=1)
    listed_shares: int | None = Field(None, ge=0)


class ReportTextNormalized(HlppNormalizedBase):
    """Raw analyst report / market-commentary text from research collectors.

    Source: dsc_research / masvn_research / yuanta_research / vndirect_research
    pulled through ``ai-api-crawlers`` text-only wirings (PDF → pdfplumber →
    boilerplate strip → body_text). This is the SUBSTRATE the future
    sentiment / tone / numbers extraction tier (L2) reads — NO LLM extraction
    in this layer per operator directive ("chỉ pull chữ relevant thôi").

    Row granularity: ONE row per (report × primary_ticker). Reports that name
    no ticker (daily bulletins, macro commentary) use ticker="MARKET". Reports
    that name multiple tickers (cross-section notes) explode into one row per
    ticker, with the full mention list preserved in ``ticker_mentions``.
    """

    vendor: Literal["internal"] = "internal"
    adjustment_type: Literal["raw"] = "raw"

    # Source identification
    source_id: str = Field(
        ..., description="upstream collector source_id (e.g. 'masvn_research')"
    )
    ctck_source: str | None = Field(
        None, description="broker shorthand ('DSC' / 'MASVN' / 'YUANTA' / 'VNDIRECT')"
    )

    # Report metadata
    title: str = Field(..., min_length=1)
    report_date: date | None = Field(None, description="published_at date")
    landing_url: str | None = None
    pdf_url: str | None = None
    ticker_mentions: list[str] = Field(
        default_factory=list,
        description="Full ticker mention list from the report; row's `ticker` is the primary",
    )

    # Text extraction provenance
    body_text: str = Field(..., description="Cleaned relevant text; may be '' on failure")
    char_count: int = Field(..., ge=0)
    page_count: int = Field(..., ge=0, description="0 for HTML/summary inputs")
    content_hash: str = Field(
        ...,
        description=(
            "Row-level provenance struct-hash (Utf8) set by stamp_silver_per_row. "
            "NOT a sha256 of body_text — the column is overwritten by the stamping layer "
            "with a polars struct-hash, so it can change across rebuilds of the same "
            "document even when body_text is byte-identical. Use observation_id (the "
            "real dedup key) or body_text_hash for cross-rebuild same-content detection."
        ),
    )
    body_text_hash: str | None = Field(
        None,
        description=(
            "SHA-256 of body_text alone (RPT-D4), deliberately independent of the "
            "shared ADR-022 content_hash above. Null for empty body_text (a blank "
            "extraction never collides with another blank extraction under a shared "
            "hash value)."
        ),
    )
    extracted_via: Literal["pdfplumber", "html_summary", "html_body"] = "pdfplumber"
    # Renamed from "status" to avoid collision with the silver-stamping
    # row-level provenance status (ACTIVE/DEGRADED/DEAD) set by
    # ``hlpp_pipelines.utils.stamping.stamp_silver_per_row``.
    extraction_status: Literal[
        "OK", "PDF_FETCH_FAILED", "INVALID_PDF", "NO_TEXT_EXTRACTED"
    ] = "OK"
    fetch_error: str | None = None

    # Lineage
    origin_observation_id: str | None = Field(
        None, description="uuid of upstream collector's observation"
    )
    observation_id: str = Field(
        ..., description="uuid5 over (source_id, content_hash || status, ticker) — stable per row"
    )


# ---------------------------------------------------------------------------
# Phase 0.5 additions — 8 missing L1b contract classes (2026-05-29)
# ---------------------------------------------------------------------------


class BlockDeals(HlppNormalizedBase):
    """Per-ticker block trades and put-through events.

    Source: m12-vnstock-block-trades-v1 via silver_block_deals builder.
    PK: (ticker, trading_date, time, endpoint)
    """

    adjustment_type: Literal["raw"] = "raw"
    trading_date: date = Field(..., description="Trade date (parsed from DD/MM/YYYY vendor format)")
    time: str = Field(..., description="Trade time string as emitted by vnstock")
    endpoint: str | None = Field(None, description="vnstock endpoint: block_trades or put_through")
    exchange: str = Field(..., description="Exchange code e.g. HOSE/HNX")
    match_price: float = Field(..., ge=0, description="Matched block price (VND)")
    match_volume: int = Field(..., ge=0, description="Matched block volume (shares)")
    reference_price: float | None = Field(None, ge=0, description="Reference price at time of trade")
    floor_price: float | None = Field(None, ge=0, description="Floor price at time of trade")


class InsiderTrades(HlppNormalizedBase):
    """Insider trade events projected from silver_corp_events_parsed.

    Source: silver_corp_events_parsed (event_type='INSIDER_TRADE') via silver_insider_trades.
    PK: (ticker, event_date, event_type)

    Note: richer per-transaction share volume / price data is a Wave-F backlog item
    pending a dedicated m12-fqx-insider-deals collector.
    """

    adjustment_type: Literal["raw"] = "raw"
    event_date: date = Field(..., description="Insider trade date (public_date precedence)")
    event_type: Literal["INSIDER_TRADE"] = "INSIDER_TRADE"
    event_title: str | None = Field(None, description="Vendor event title (Vietnamese text)")
    vendor_event_label: str | None = Field(
        None, description="Vendor full event_name (Vietnamese, verbatim audit trail)"
    )
    organ_name: str | None = Field(None, description="Insider / organisation name")
    cash_amount_vnd: float | None = Field(
        None, description="Transaction value in VND (null when not reported)"
    )


class LargeShareholders(HlppNormalizedBase):
    """Latest snapshot of >=5% shareholders per ticker.

    Source: m12-vnstock-shareholders-v1 via silver_large_shareholders builder.
    PK: (symbol, name)

    IMPORTANT: This builder uses ``symbol`` as the primary entity identifier
    (not ``ticker``), matching the vnstock vendor convention for shareholder data.
    The ``ticker`` field on HlppNormalizedBase is populated with the same uppercase
    symbol value for contract consistency, but the dedicated ``symbol`` payload
    column is the canonical key downstream consumers use.
    """

    adjustment_type: Literal["raw"] = "raw"
    # Vendor uses 'symbol' (not 'ticker') as primary key — preserve verbatim.
    # See audit §5.4: large_shareholders diverges from all other builders here.
    symbol: str = Field(
        ..., description="Shareholder's associated ticker symbol (vnstock convention)"
    )
    name: str = Field(..., description="Shareholder name (individual or entity)")
    total_shares: int = Field(..., ge=0, description="Total shares held")
    rate: float = Field(..., ge=0, le=1, description="Ownership rate as decimal (0–1)")
    snapshot_date: date = Field(
        ..., description="Date of the shareholder snapshot (latest available)"
    )


class CorpEventsParsed(HlppNormalizedBase):
    """Wide per-event parsed silver for all corporate action types.

    Source: m12-vnstock-corp-actions-calendar-v1 via silver_corp_events_parsed builder.
    PK: (ticker, event_date, event_type)

    event_type is normalized from vendor short-codes via Appendix A mapping
    (DIV→DIVIDEND_CASH, AGME→AGM, etc.). See builder for full mapping.
    """

    adjustment_type: Literal["raw"] = "raw"
    event_date: date | None = Field(
        None,
        description=(
            "Resolved event date via per-event-type precedence rules. "
            "Null when all vendor date fields are missing/unparseable (DEGRADED row); "
            "business_date is set to as_of_date in that case."
        ),
    )
    event_type: str = Field(
        ...,
        description=(
            "Normalized silver enum: DIVIDEND_CASH / AGM / EGM / SHARE_ISSUE / "
            "LISTING / DELISTING / INSIDER_TRADE / OTHER"
        ),
    )
    vendor_event_label: str | None = Field(
        None, description="Vendor event_name (Vietnamese full-text, verbatim audit trail)"
    )
    vendor_event_type_code: str | None = Field(
        None, description="Vendor short-code e.g. DIV, AGME (preserved for cross-reference)"
    )
    vendor_symbol: str | None = Field(None, description="Vendor's raw symbol field")
    event_title: str | None = Field(None, description="Vendor event_title field")
    organ_name: str | None = Field(None, description="Organiser / counterparty name")
    cash_amount_vnd: float | None = Field(
        None, description="Cash dividend or transaction value in VND"
    )
    stock_ratio_decimal: float | None = Field(
        None, ge=0, description="Stock dividend / bonus-share ratio as decimal"
    )
    # Date passthroughs from vendor (all nullable; semantics vary by event_type)
    ex_right_date: date | None = None
    record_date: date | None = None
    payout_date: date | None = None
    public_date: date | None = None
    issue_date: date | None = None


class IndexDaily(HlppNormalizedBase):
    """Daily OHLCV bars for VN indices derived from intraday stream.

    Source: m12-fqx-index-intraday-v1 via silver_index_daily builder.
    PK: (ticker, business_date)
    ticker is the index identifier: VNINDEX / VN30 / HNX30 / HNXINDEX / UPCOMINDEX.
    """

    adjustment_type: Literal["raw"] = "raw"
    open: float = Field(..., ge=0, description="Session open price")
    high: float = Field(..., ge=0, description="Session high price")
    low: float = Field(..., ge=0, description="Session low price")
    close: float = Field(..., ge=0, description="Session close price")
    volume: float = Field(..., ge=0, description="Total session volume (float; summed from ticks)")
    value_traded: float = Field(..., ge=0, description="Total session traded value (VND)")


class LiquidityFiltersDaily(HlppNormalizedBase):
    """Rolling ADTV liquidity filter flags per ticker/date.

    Source: silver_price_daily via silver_liquidity_filters_daily builder.
    PK: (ticker, business_date)
    Includes M23 lineage columns (source_silver_set, derivation_recipe_id,
    pit_lineage, source_code_shas, recipe_version, expected_output_schema_id)
    in the parquet output beyond the contract payload fields below.
    """

    adjustment_type: Literal["raw"] = "raw"
    adtv_20d_vnd: float | None = Field(
        None, ge=0, description="20-day average daily traded value in VND; null if < 20 days data"
    )
    adtv_60d_vnd: float | None = Field(
        None, ge=0, description="60-day average daily traded value in VND; null if < 60 days data"
    )
    passes_min_adtv_20d_flag: bool | None = Field(
        None,
        description=(
            "True if adtv_20d_vnd >= min_adtv threshold; "
            "null when adtv_20d_vnd is null (insufficient history)"
        ),
    )
    passes_min_adtv_60d_flag: bool | None = Field(
        None,
        description=(
            "True if adtv_60d_vnd >= min_adtv threshold; "
            "null when adtv_60d_vnd is null (insufficient history)"
        ),
    )


class FundamentalsAnnual(HlppNormalizedBase):
    """Annual BCTC fundamentals — surface-aware unified schema (5 surfaces).

    Source: 5 BCTC m12 contracts routed via ICB → surface mapping.
    PK: (ticker, period_end_date)

    Surface routing: general / bank / securities / insurance / fund.
    All 5 surfaces share the same 44-column parquet schema; surface-specific
    columns are NULL for rows belonging to other surfaces. The ``bctc_surface``
    field indicates which surface's columns are populated.

    Column groups:
    - Identity (6):       ticker, period, period_end_date, report_type,
                          accounting_framework, bctc_surface
    - Universal (3):      net_profit_after_tax, total_assets, roe
    - Common-4 (4):       total_equity, eps_basic, bvps, roa
                          (null for fund surface)
    - General-only (9):   net_sales, gross_profit, operating_profit, total_debt,
                          cash, operating_cash_flow, eps_diluted, pe_ratio, pb_ratio
    - Bank-only (7):      net_interest_income, loans_to_customers,
                          deposits_from_customers, npl_ratio, capital_adequacy_ratio,
                          tier1_capital_ratio, nim
    - Securities-only (5): brokerage_revenue, proprietary_trading_pnl,
                           margin_lending_interest_income, margin_loans_outstanding,
                           trading_securities
    - Insurance-only (5): gross_written_premium, net_written_premium,
                          claims_incurred, combined_ratio, solvency_capital_ratio
    - Fund-only (5):      total_aum, total_nav, nav_per_unit, units_outstanding,
                          expense_ratio
    """

    adjustment_type: Literal["raw"] = "raw"

    # Identity
    period: str | None = Field(None, description="Fiscal year string e.g. '2025'")
    period_end_date: date | None = Field(None, description="Fiscal year end date")
    report_type: str | None = Field(
        None, description="'year' for annual rows (quarterly Q4 rows excluded)"
    )
    accounting_framework: str | None = Field(None, description="e.g. VAS / IFRS")
    bctc_surface: str = Field(
        ...,
        description="BCTC routing surface: general / bank / securities / insurance / fund",
    )

    # Universal (all 5 surfaces)
    net_profit_after_tax: float | None = None
    total_assets: float | None = None
    roe: float | None = None

    # Common-4 (general/bank/securities/insurance; null for fund)
    total_equity: float | None = None
    eps_basic: float | None = None
    bvps: float | None = None
    roa: float | None = None

    # Per-share recompute audit columns (P11 Phương án A, hlpp_pipelines.l1b.
    # pershare_recompute; general/bank/securities/insurance -- excluded for fund,
    # whose per-share economics are NAV/unit-based). eps_basic/bvps/roe/roa above
    # are COALESCED: field_recomputed when the recompute's own inputs (NPAT/
    # equity/assets/shares_outstanding_pit) resolved, else field_vendor unmodified
    # -- a resolve-miss on this arc's own inputs never blanks a real vendor value.
    eps_basic_vendor: float | None = Field(
        None, description="Vendor-reported eps_basic, preserved unmodified for audit (P11 coalesce)"
    )
    bvps_vendor: float | None = Field(
        None, description="Vendor-reported bvps, preserved unmodified for audit (P11 coalesce)"
    )
    roe_vendor: float | None = Field(
        None, description="Vendor-reported roe, preserved unmodified for audit (P11 coalesce)"
    )
    roa_vendor: float | None = Field(
        None, description="Vendor-reported roa, preserved unmodified for audit (P11 coalesce)"
    )
    eps_diluted_recomputed: float | None = Field(
        None,
        description=(
            "Always null -- eps_diluted is never recomputed (no dilutive-instrument "
            "data anywhere in the lake for any surface); vendor eps_diluted passes "
            "through completely untouched. Kept as an explicit audit column per the "
            "coalesce convention (P11 point 3)."
        ),
    )
    shares_outstanding_pit: float | None = Field(
        None,
        description=(
            "PIT-per-period shares outstanding used for the eps_basic/bvps recompute, "
            "resolved as-of period_end_date + 45d (quarterly publication lag, used for "
            "BOTH FQ and FA to keep the shares-lookup anchor identical -- 2026-07-21 "
            "fix, see FA docstring point 2b) against m12-fqx-freefloat-v1 history via "
            "a backward as-of join. Null when unresolved -- e.g. pre-2019-01-02 "
            "freefloat coverage boundary, or ticker has no eligible snapshot -- never "
            "silently clamped to nearest available."
        ),
    )
    eps_source: str = Field(
        "vendor_coalesced",
        description="'recomputed' when eps_basic used the NPAT/shares_outstanding_pit recompute, else 'vendor_coalesced'",
    )
    bvps_source: str = Field(
        "vendor_coalesced",
        description="'recomputed' when bvps used the equity/shares_outstanding_pit recompute, else 'vendor_coalesced'",
    )
    roe_source: str = Field(
        "vendor_coalesced",
        description="'recomputed' when roe used the TTM-NPAT/avg-equity recompute, else 'vendor_coalesced'",
    )
    roa_source: str = Field(
        "vendor_coalesced",
        description="'recomputed' when roa used the TTM-NPAT/avg-assets recompute, else 'vendor_coalesced'",
    )

    # General-only
    net_sales: float | None = None
    gross_profit: float | None = None
    operating_profit: float | None = None
    total_debt: float | None = None
    cash: float | None = None
    operating_cash_flow: float | None = None
    eps_diluted: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None

    # General-only forensic/credit line-items (Altman EMS, Beneish M, DuPont-5)
    retained_earnings: float | None = None
    fixed_assets: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    profit_before_tax: float | None = None
    selling_expenses: float | None = None
    general_admin_expenses: float | None = None
    depreciation_amortization: float | None = None
    cost_of_sales: float | None = None
    inventory: float | None = None
    accounts_receivable: float | None = None
    accounts_payable: float | None = None
    short_term_investments: float | None = None

    # Bank-only
    net_interest_income: float | None = None
    loans_to_customers: float | None = None
    deposits_from_customers: float | None = None
    npl_ratio: float | None = None
    capital_adequacy_ratio: float | None = None
    tier1_capital_ratio: float | None = None
    nim: float | None = None
    # Bank Wave-4 income-statement line-items (RE-contagion / PPOP / pre-provision)
    loan_loss_reserves: float | None = None
    operating_expenses: float | None = None
    operating_income: float | None = None
    # Bank Wave-4 NIM-decomposition: gross interest income/expense (P2.6)
    interest_income: float | None = None
    interest_expense: float | None = None
    # Bank fq-D4: fee/credit-provision + regulatory NPL line-items
    fee_commission_income: float | None = None
    net_fee_income: float | None = None
    credit_provision_expense: float | None = None
    non_performing_loans: float | None = Field(
        None, description="Regulatory NPL balance (Circular-11 groups 3-5), distinct from npl_ratio"
    )

    # Securities-only
    brokerage_revenue: float | None = None
    proprietary_trading_pnl: float | None = None
    margin_lending_interest_income: float | None = None
    margin_loans_outstanding: float | None = None
    trading_securities: float | None = None
    # Securities fq-D4: revenue-mix + balance-sheet line-items
    advisory_revenue: float | None = None
    agency_underwriting_revenue: float | None = None
    operating_revenue: float | None = None
    client_deposits: float | None = None
    available_for_sale_securities: float | None = None
    held_to_maturity_securities: float | None = None

    # Insurance-only
    gross_written_premium: float | None = None
    net_written_premium: float | None = None
    claims_incurred: float | None = None
    combined_ratio: float | None = None
    solvency_capital_ratio: float | None = None
    # Insurance fq-D4: underwriting + technical-reserve line-items
    premium_earned: float | None = None
    claims_paid: float | None = None
    claims_reserves: float | None = None
    underwriting_expenses: float | None = None
    underwriting_result: float | None = None
    investment_income: float | None = None
    technical_reserves: float | None = None
    unexpired_risk_reserve: float | None = None

    # Fund-only
    total_aum: float | None = None
    total_nav: float | None = None
    nav_per_unit: float | None = None
    units_outstanding: float | None = None
    expense_ratio: float | None = None


# ---------------------------------------------------------------------------
# Tier-B lite base — for real-time snapshots that intentionally skip ADR-022
# ---------------------------------------------------------------------------

class _HlppTierBBase(BaseModel):
    """Lite base for Tier-B real-time datasets that intentionally skip ADR-022 stamping.

    Tier-B builders (intraday_snapshot, price_intraday_30s) are best-effort,
    current-only, and not journaled into M23 lineage per operator directive.
    They omit the 4 mandatory HlppNormalizedBase provenance fields
    (vendor, schema_id, dataset_id, builder_version) because those require
    the full stamp_silver_shared_provenance pass that Tier-B explicitly skips.

    If a builder graduates from Tier-B to full ADR-022 compliance, migrate it
    to subclass HlppNormalizedBase instead.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str = Field(..., description="Uppercase, vendor-canonical")
    as_of_date: date = Field(..., description="Partition key (build date)")


class IntradaySnapshot(_HlppTierBBase):
    """Best-effort per-ticker daily intraday snapshot (Tier-B, no ADR-022 stamping).

    Source: daemon-written tick parquet under ~/data/m12/fqx/{ticker}/dt={date}/*.parquet
    via silver_intraday_snapshot builder.
    PK: (ticker, as_of_date) — one row per ticker per day.

    TIER-B EXEMPTION: vendor, schema_id, dataset_id, builder_version are intentionally
    absent. This builder is current_only and best-effort; partial-universe output is
    acceptable. See builder docstring for rationale.
    """

    last_event_ts: datetime = Field(
        ..., description="UTC timestamp of the latest tick observed today"
    )
    last_price: float = Field(..., ge=0, description="Close of the latest tick (~current price)")
    day_open: float = Field(..., ge=0, description="Open of the first tick in the session")
    day_high: float = Field(..., ge=0, description="Running session high")
    day_low: float = Field(..., ge=0, description="Running session low")
    day_close: float = Field(..., ge=0, description="Alias for last_price (for downstream readers)")
    day_volume: float = Field(..., ge=0, description="Cumulative tick volume")
    day_value_vnd: float = Field(..., ge=0, description="Cumulative tick traded value (VND)")


class NewsHeadlineNormalized(HlppNormalizedBase):
    """One normalized headline row from VN news/disclosure sources.

    Sources: hose_news (HSX API), cafef_per_ticker (CafeF per-ticker page),
    rss (Vietnamese-language RSS feeds). NO sentiment/scoring — raw text
    normalization only. That is an L2 concern.

    Row granularity: ONE row per headline URL (or per source_id+headline+date
    when URL is absent). Headlines without a ticker association use
    ticker="MARKET".

    Dedup key: url (preferred) or (source_id, headline, published_date).
    """

    vendor: Literal["internal"] = "internal"
    adjustment_type: Literal["raw"] = "raw"

    # Source identification
    source_id: str = Field(
        ...,
        description=(
            "Upstream collector source_id: 'hose_news' / 'cafef_per_ticker' / "
            "RSS feed id (e.g. 'vnexpress_kinhdoanh')"
        ),
    )
    source_name: str | None = Field(
        default=None,
        description="Publisher display name (e.g. 'CafeF', 'HOSE', RSS <source> title). None when unknown.",
    )

    # Headline content
    headline: str = Field(..., min_length=1, description="Article title / headline text")
    url: str | None = Field(None, description="Canonical article URL; null for API-only sources")
    published_at: datetime | None = Field(
        None, description="Publisher-reported publish timestamp (UTC-aware when available)"
    )
    published_date: date | None = Field(
        None, description="Date part of published_at; null when published_at is null"
    )
    summary: str | None = Field(
        None, description="Short snippet / lead paragraph if provided by source; null otherwise"
    )

    # Ticker association (optional — many headlines are market-wide)
    tickers: list[str] = Field(
        default_factory=list,
        description=(
            "Uppercase ticker codes mentioned / associated with this headline. "
            "Empty list for market-wide headlines (ticker='MARKET' on base). "
            "Set to [ticker] for per-ticker source pulls (cafef_per_ticker)."
        ),
    )

    # Dedup + lineage
    headline_id: str = Field(
        ...,
        description=(
            "uuid5 over dedup key: url when present, else "
            "(source_id, headline[:120], published_date_iso). Stable across re-runs."
        ),
    )
    language: str = Field("vi", description="ISO 639-1 language code of the headline")

    # News revival byproduct (2026-07 wire-first revival; 3 cols)
    extraction_status: str = Field(
        "OK",
        description=(
            "Extraction outcome for this row, currently always 'OK' (no error path "
            "populates a different value yet — kept as a plain str, not a Literal, "
            "so a future error-path addition is additive rather than a contract break)."
        ),
    )
    published_at_confidence: str = Field(
        "none",
        description=(
            "Confidence marker for published_at's accuracy, sourced from the "
            "collector's raw article extra['published_at_confidence'] when present, "
            "else 'none' (published_at absent/unreliable)."
        ),
    )
    dedup_content_hash: str | None = Field(
        None,
        description=(
            "SHA-256 over the whitespace-normalized (headline, summary) pair — url "
            "EXCLUDED — so the same story re-published under a different url "
            "collapses to one hash (basis for cross-source clustering / "
            "cluster_source_count). Computed AFTER provenance stamping, so it is "
            "NOT part of the ADR-022 content_hash payload struct. Distinct from "
            "content_hash (which fingerprints the whole row, url included)."
        ),
    )


__all__ = [
    "BlockDeals",
    "CorpEventsParsed",
    "ForeignFlowDaily",
    "FundamentalsAnnual",
    "FundamentalsQuarterly",
    "IndexDaily",
    "InsiderTrades",
    "IntradaySnapshot",
    "LargeShareholders",
    "LiquidityFiltersDaily",
    "NewsHeadlineNormalized",
    "PriceDaily",
    "PriceIntraday30s",
    "ReportTextNormalized",
    "Ticker360",
]
