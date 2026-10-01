"""
APRS V8 PHASE 4B: SOURCE ADAPTER INTERFACE & NORMALIZATION CONTRACTS
====================================================================
Architectural Layer: Source Ingestion Adapter & Normalization Boundary
Purpose:
  Defines the contracts, intermediate representation (NormalizedOutcome),
  error categories, validation structures, and abstract adapter interface
  for ingesting real-world outcome observations from external commerce sources.

Non-Negotiable Invariants:
  1. Strict Separation: Adapters and normalizers produce normalized data;
     they NEVER directly write to SQLite tables (product_outcomes,
     prediction_calibrations, decision_ledger, master_products).
  2. Authoritative Persistence Boundary: Phase 3 OutcomeIngestionService
     remains the sole authoritative write boundary.
  3. No Live External Connections: No API keys, OAuth, or network requests.
  4. NULL Semantics (NULL != 0): Missing values remain None; never convert to zero.
  5. Deterministic Provenance: Every record carries data_source, source_record_id,
     source_schema_version, and timestamps.
  6. Strict Product Identity: Unresolved or ambiguous product identifiers are rejected;
     no guessing, fuzzy matching, or automatic master product creation.
  7. No Derived Value Competition: Adapters do not compute derived metrics (ASP, CM%,
     Return Rate, RTO Rate, CAC) unless explicitly provided by the source.
  8. Research Proxy Prohibition: Scraped market estimates and pre-launch proxies
     are strictly rejected.
  9. No Autonomous Learning: Normalization is pure data transformation; no self-mutation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import datetime
from typing import Dict, Any, List, Optional, Callable, Tuple

# -------------------------------------------------------------
# 1. ERROR CATEGORY CONSTANTS
# -------------------------------------------------------------
ERROR_INVALID_SOURCE_RECORD = "INVALID_SOURCE_RECORD"
ERROR_MISSING_PRODUCT_ID = "MISSING_PRODUCT_ID"
ERROR_UNRESOLVED_PRODUCT = "UNRESOLVED_PRODUCT"
ERROR_INVALID_PERIOD = "INVALID_PERIOD"
ERROR_UNSUPPORTED_PERIOD_TYPE = "UNSUPPORTED_PERIOD_TYPE"
ERROR_INVALID_NUMERIC_VALUE = "INVALID_NUMERIC_VALUE"
ERROR_INVALID_PERCENTAGE = "INVALID_PERCENTAGE"
ERROR_AMBIGUOUS_DECISION = "AMBIGUOUS_DECISION"
ERROR_UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"
ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME = "RESEARCH_ESTIMATE_NOT_OUTCOME"
ERROR_DUPLICATE_SOURCE_RECORD_ID = "DUPLICATE_SOURCE_RECORD_ID"
ERROR_DUPLICATE_HEADERS = "DUPLICATE_HEADERS"
ERROR_MISSING_REQUIRED_HEADERS = "MISSING_REQUIRED_HEADERS"
ERROR_OUTCOME_SOURCE_CONFLICT = "OUTCOME_SOURCE_CONFLICT"
ERROR_FILE_SAFETY_VIOLATION = "FILE_SAFETY_VIOLATION"

# -------------------------------------------------------------
# 2. SOURCE IDENTIFIER CONSTANTS
# -------------------------------------------------------------
SOURCE_MANUAL_CSV = "MANUAL_CSV"
SOURCE_SHOPIFY = "SHOPIFY"
SOURCE_AMAZON_SP_API = "AMAZON_SP_API"
SOURCE_MARKETPLACE_EXPORT = "MARKETPLACE_EXPORT"
SOURCE_WAREHOUSE = "WAREHOUSE"
SOURCE_AD_PLATFORM = "AD_PLATFORM"
SOURCE_FIXTURE = "FIXTURE"

VALID_DATA_SOURCES = {
    SOURCE_MANUAL_CSV,
    SOURCE_SHOPIFY,
    SOURCE_AMAZON_SP_API,
    SOURCE_MARKETPLACE_EXPORT,
    SOURCE_WAREHOUSE,
    SOURCE_AD_PLATFORM,
    SOURCE_FIXTURE,
}

# Forbidden pre-launch research proxies and estimate sources
FORBIDDEN_RESEARCH_PROXIES = {
    "GOOGLE_TRENDS",
    "COMPETITOR_BSR",
    "SCRAPED_ESTIMATE",
    "HELIUM_ESTIMATE",
    "MARKETPLACE_ESTIMATE",
    "MARKET_RESEARCH",
}

# Forbidden estimate field names that must never be mapped to actual metrics
FORBIDDEN_ESTIMATE_FIELDS = {
    "estimated_daily_units",
    "helium_monthly_revenue",
    "bsr_rank",
    "market_estimate",
    "projected_units",
    "scraped_revenue",
    "estimated_sales",
}

# Supported period types conforming to Phase 3 & Phase 4A
SUPPORTED_PERIOD_TYPES = {"DAY_30", "DAY_60", "DAY_90", "LIFETIME", "CUSTOM"}


# -------------------------------------------------------------
# 3. VALIDATION RESULT DATA STRUCTURE
# -------------------------------------------------------------
@dataclass
class ValidationResult:
    """Represents the outcome of an adapter or normalization validation pass."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    error_category: Optional[str] = None

    def add_error(self, message: str, category: Optional[str] = None) -> None:
        self.is_valid = False
        self.errors.append(message)
        if category and not self.error_category:
            self.error_category = category


# -------------------------------------------------------------
# 4. NORMALIZED OUTCOME DATA STRUCTURE
# -------------------------------------------------------------
@dataclass
class NormalizedOutcome:
    """
    Canonical intermediate representation of an observed product outcome.
    
    Guarantees:
      - Clean separation from raw source schemas.
      - Preservation of NULL semantics (None != 0).
      - Transparent source provenance tracking.
      - 100% compatibility with Phase 3 OutcomeIngestionService.
    """
    product_id: str
    period_start: str
    period_end: str
    period_type: str
    data_source: str
    source_schema_version: str

    # Source identity & provenance
    source_record_id: Optional[str] = None
    source_product_id: Optional[str] = None
    decision_id: Optional[int] = None
    source_timestamp: Optional[str] = None
    raw_reference: Optional[str] = None

    # Observed actual business metrics (None = not reported; 0 = explicitly zero)
    actual_units_sold: Optional[int] = None
    actual_revenue: Optional[float] = None
    actual_avg_selling_price: Optional[float] = None
    actual_landed_cogs: Optional[float] = None
    actual_contribution_margin: Optional[float] = None
    actual_cm_pct: Optional[float] = None
    actual_returns_count: Optional[int] = None
    actual_return_rate_pct: Optional[float] = None
    actual_rto_count: Optional[int] = None
    actual_rto_rate_pct: Optional[float] = None
    actual_ad_spend: Optional[float] = None
    actual_cac: Optional[float] = None
    actual_inventory: Optional[int] = None
    actual_stockout_days: Optional[int] = None

    notes: Optional[str] = None

    def to_phase3_payload(self) -> Dict[str, Any]:
        """
        Converts NormalizedOutcome to the payload expected by
        OutcomeIngestionService.ingest_outcome(...) and validate_outcome_payload.
        Preserves provenance in notes without requiring DB schema modifications.
        """
        notes_parts = []
        if self.notes:
            notes_parts.append(self.notes)
        
        prov_tags = []
        if self.source_schema_version:
            prov_tags.append(f"schema_v:{self.source_schema_version}")
        if self.source_product_id:
            prov_tags.append(f"src_sku:{self.source_product_id}")
        if self.source_timestamp:
            prov_tags.append(f"src_time:{self.source_timestamp}")
        if self.raw_reference:
            prov_tags.append(f"raw_ref:{self.raw_reference}")
            
        if prov_tags:
            notes_parts.append(f"[{' | '.join(prov_tags)}]")

        full_notes = " ".join(notes_parts) if notes_parts else None

        return {
            "product_id": self.product_id,
            "decision_id": self.decision_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "period_type": self.period_type,
            "actual_units_sold": self.actual_units_sold,
            "actual_revenue": self.actual_revenue,
            "actual_avg_selling_price": self.actual_avg_selling_price,
            "actual_landed_cogs": self.actual_landed_cogs,
            "actual_contribution_margin": self.actual_contribution_margin,
            "actual_cm_pct": self.actual_cm_pct,
            "actual_returns_count": self.actual_returns_count,
            "actual_return_rate_pct": self.actual_return_rate_pct,
            "actual_rto_count": self.actual_rto_count,
            "actual_rto_rate_pct": self.actual_rto_rate_pct,
            "actual_ad_spend": self.actual_ad_spend,
            "actual_cac": self.actual_cac,
            "actual_inventory": self.actual_inventory,
            "actual_stockout_days": self.actual_stockout_days,
            "data_source": self.data_source,
            "source_record_id": self.source_record_id,
            "notes": full_notes,
        }


# -------------------------------------------------------------
# 5. BATCH RESULT DATA STRUCTURES
# -------------------------------------------------------------
@dataclass
class BatchItemError:
    """Records an error encountered during batch normalization for a single record."""
    index: int
    source_record_id: Optional[str]
    error_category: str
    error_message: str


@dataclass
class BatchNormalizationResult:
    """Represents the deterministic output of normalize_many."""
    successful: List[NormalizedOutcome] = field(default_factory=list)
    failed: List[BatchItemError] = field(default_factory=list)
    total_count: int = 0

    @property
    def success_count(self) -> int:
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        return len(self.failed)


# -------------------------------------------------------------
# 6. ABSTRACT SOURCE ADAPTER CONTRACT
# -------------------------------------------------------------
class OutcomeSourceAdapter(ABC):
    """
    Abstract base class for all outcome source adapters.
    
    Responsibilities:
      1. Understand source-specific fields.
      2. Validate source record structure.
      3. Map source fields into NormalizedOutcome.
      4. Preserve source provenance.
      5. Produce deterministic normalized data.
      6. Reject unsupported, research-proxy, or ambiguous records.
    
    Prohibitions:
      - NEVER write to SQLite directly.
      - NEVER invent missing business metrics.
      - NEVER compute competing derived formulas.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """The canonical name of the data source (e.g., FIXTURE, SHOPIFY)."""
        pass

    @property
    @abstractmethod
    def source_version(self) -> str:
        """The version of the source schema or adapter contract (e.g., 1.0.0)."""
        pass

    @abstractmethod
    def validate_source_record(self, record: Dict[str, Any]) -> ValidationResult:
        """Validates source record structure without mutating or persisting."""
        pass

    @abstractmethod
    def normalize(
        self,
        record: Dict[str, Any],
        product_resolver: Optional[Callable[[str], Optional[str]]] = None
    ) -> NormalizedOutcome:
        """
        Normalizes a single source record into a canonical NormalizedOutcome.
        Raises ValueError with an error category on invalid or unresolvable data.
        """
        pass

    def normalize_many(
        self,
        records: List[Dict[str, Any]],
        product_resolver: Optional[Callable[[str], Optional[str]]] = None
    ) -> BatchNormalizationResult:
        """
        Deterministically normalizes a batch of source records.
        Isolation guarantee: An error in one record never corrupts or aborts other records.
        """
        result = BatchNormalizationResult(total_count=len(records))
        for idx, rec in enumerate(records):
            src_rec_id = None
            if isinstance(rec, dict):
                src_rec_id = rec.get("source_record_id") or rec.get("id") or rec.get("order_id")
                if src_rec_id is not None:
                    src_rec_id = str(src_rec_id)
            try:
                norm = self.normalize(rec, product_resolver=product_resolver)
                result.successful.append(norm)
            except ValueError as ve:
                err_msg = str(ve)
                cat = ERROR_INVALID_SOURCE_RECORD
                for candidate_cat in (
                    ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME,
                    ERROR_MISSING_PRODUCT_ID,
                    ERROR_UNRESOLVED_PRODUCT,
                    ERROR_UNSUPPORTED_PERIOD_TYPE,
                    ERROR_INVALID_PERIOD,
                    ERROR_INVALID_NUMERIC_VALUE,
                    ERROR_INVALID_PERCENTAGE,
                    ERROR_UNSUPPORTED_SOURCE,
                    ERROR_AMBIGUOUS_DECISION,
                ):
                    if candidate_cat in err_msg:
                        cat = candidate_cat
                        break
                result.failed.append(BatchItemError(
                    index=idx,
                    source_record_id=src_rec_id,
                    error_category=cat,
                    error_message=err_msg
                ))
            except Exception as e:
                result.failed.append(BatchItemError(
                    index=idx,
                    source_record_id=src_rec_id,
                    error_category=ERROR_INVALID_SOURCE_RECORD,
                    error_message=str(e)
                ))
        return result
