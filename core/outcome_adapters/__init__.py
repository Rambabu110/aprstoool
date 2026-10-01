"""
APRS V8 PHASE 4B: OUTCOME ADAPTERS PACKAGE
==========================================
Architectural Layer: Source Ingestion Adapter & Normalization Boundary
Exposes the contracts, intermediate representation, base adapter interface,
and reference fixture adapter.
"""

from core.outcome_adapters.base import (
    # Error categories
    ERROR_INVALID_SOURCE_RECORD,
    ERROR_MISSING_PRODUCT_ID,
    ERROR_UNRESOLVED_PRODUCT,
    ERROR_INVALID_PERIOD,
    ERROR_UNSUPPORTED_PERIOD_TYPE,
    ERROR_INVALID_NUMERIC_VALUE,
    ERROR_INVALID_PERCENTAGE,
    ERROR_AMBIGUOUS_DECISION,
    ERROR_UNSUPPORTED_SOURCE,
    ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME,
    ERROR_DUPLICATE_SOURCE_RECORD_ID,
    ERROR_DUPLICATE_HEADERS,
    ERROR_MISSING_REQUIRED_HEADERS,
    ERROR_OUTCOME_SOURCE_CONFLICT,
    ERROR_FILE_SAFETY_VIOLATION,
    # Data sources
    SOURCE_MANUAL_CSV,
    SOURCE_SHOPIFY,
    SOURCE_AMAZON_SP_API,
    SOURCE_MARKETPLACE_EXPORT,
    SOURCE_WAREHOUSE,
    SOURCE_AD_PLATFORM,
    SOURCE_FIXTURE,
    VALID_DATA_SOURCES,
    FORBIDDEN_RESEARCH_PROXIES,
    FORBIDDEN_ESTIMATE_FIELDS,
    SUPPORTED_PERIOD_TYPES,
    # Contracts & Dataclasses
    ValidationResult,
    NormalizedOutcome,
    BatchItemError,
    BatchNormalizationResult,
    OutcomeSourceAdapter,
)

from core.outcome_adapters.normalizer import (
    check_aprs_product_exists,
    check_research_proxy_rejection,
    resolve_product_identity,
    validate_and_normalize_period,
    clean_non_negative_int,
    clean_non_negative_float,
    clean_percentage,
)

from core.outcome_adapters.fixture_adapter import (
    FixtureOutcomeAdapter,
    ManualFixtureAdapter,
)

from core.outcome_adapters.manual_csv_adapter import (
    ManualCsvOutcomeAdapter,
    ManualCsvOutcomeService,
    CsvValidationReport,
    CsvIngestionReport,
    CsvRowError,
    CSV_REQUIRED_HEADER_CANDIDATES,
    CSV_SCHEMA_VERSION,
    CSV_SOURCE_VERSION,
)

__all__ = [
    # Errors
    "ERROR_INVALID_SOURCE_RECORD",
    "ERROR_MISSING_PRODUCT_ID",
    "ERROR_UNRESOLVED_PRODUCT",
    "ERROR_INVALID_PERIOD",
    "ERROR_UNSUPPORTED_PERIOD_TYPE",
    "ERROR_INVALID_NUMERIC_VALUE",
    "ERROR_INVALID_PERCENTAGE",
    "ERROR_AMBIGUOUS_DECISION",
    "ERROR_UNSUPPORTED_SOURCE",
    "ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME",
    "ERROR_DUPLICATE_SOURCE_RECORD_ID",
    "ERROR_DUPLICATE_HEADERS",
    "ERROR_MISSING_REQUIRED_HEADERS",
    "ERROR_OUTCOME_SOURCE_CONFLICT",
    "ERROR_FILE_SAFETY_VIOLATION",
    # Sources
    "SOURCE_MANUAL_CSV",
    "SOURCE_SHOPIFY",
    "SOURCE_AMAZON_SP_API",
    "SOURCE_MARKETPLACE_EXPORT",
    "SOURCE_WAREHOUSE",
    "SOURCE_AD_PLATFORM",
    "SOURCE_FIXTURE",
    "VALID_DATA_SOURCES",
    "FORBIDDEN_RESEARCH_PROXIES",
    "FORBIDDEN_ESTIMATE_FIELDS",
    "SUPPORTED_PERIOD_TYPES",
    # Data structures
    "ValidationResult",
    "NormalizedOutcome",
    "BatchItemError",
    "BatchNormalizationResult",
    "OutcomeSourceAdapter",
    # Normalizer utilities
    "check_aprs_product_exists",
    "check_research_proxy_rejection",
    "resolve_product_identity",
    "validate_and_normalize_period",
    "clean_non_negative_int",
    "clean_non_negative_float",
    "clean_percentage",
    # Adapters & Services
    "FixtureOutcomeAdapter",
    "ManualFixtureAdapter",
    "ManualCsvOutcomeAdapter",
    "ManualCsvOutcomeService",
    "CsvValidationReport",
    "CsvIngestionReport",
    "CsvRowError",
    "CSV_REQUIRED_HEADER_CANDIDATES",
    "CSV_SCHEMA_VERSION",
    "CSV_SOURCE_VERSION",
]
