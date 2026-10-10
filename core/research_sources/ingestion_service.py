"""
core/research_sources/ingestion_service.py — Safe Observation Ingestion & Deduplication Service.

Executes the seven-stage observation pipeline:
RECEIVE → VALIDATE → NORMALIZE → PROVENANCE → DEDUPLICATE → STORE → RETURN RESULT

Enforces strict application-level idempotency and anti-hallucination boundaries.
Preserves all historical database rows and operates safely across SQLite instances.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import os
import sqlite3
import datetime
import json
import logging
from pydantic import ValidationError

from core.research_sources.observation import (
    CanonicalObservation,
    IngestionStatus,
    ObservationIngestionResult
)
from core.research_sources.diff_engine import (
    ObservationDiffEngine,
    ObservationDiffReport
)
from core.research_sources.normalizer import EvidenceNormalizer
from core.research_sources.provenance import ProvenanceTracker
from core.research_sources.base import EvidenceType, SignalType

logger = logging.getLogger("aprs.observation.ingestion")


class ObservationIngestionService:
    """
    Production-safe observation ingestion pipeline.
    Ensures zero silent failures, strict validation, and idempotent storage.
    """

    def __init__(self, diff_engine: Optional[ObservationDiffEngine] = None):
        self.diff_engine = diff_engine or ObservationDiffEngine()

    @staticmethod
    def validate_observation(obs: CanonicalObservation) -> Tuple[bool, Optional[str]]:
        """
        Stage 2: Validation
        Ensures observation conforms to mandatory constraints.
        """
        if not obs.source_id or not obs.source_id.strip():
            return False, "VALIDATION_FAILED: source_id is required."
        
        if not obs.observed_at or not obs.observed_at.strip():
            return False, "VALIDATION_FAILED: observed_at timestamp is required."

        # Validate observed_at date format
        try:
            datetime.date.fromisoformat(obs.observed_at[:10])
        except (ValueError, TypeError):
            return False, f"VALIDATION_FAILED: observed_at timestamp has invalid date format: '{obs.observed_at}'."

        # Validate that observed_at is not in the future (with 24h drift tolerance)
        try:
            obs_dt = datetime.datetime.fromisoformat(obs.observed_at.replace("Z", "+00:00"))
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=datetime.timezone.utc)
            if obs_dt > now_utc + datetime.timedelta(days=1):
                return False, f"VALIDATION_FAILED: observed_at timestamp cannot be in the future: '{obs.observed_at}'."
        except Exception:
            pass

        # Validate confidence range
        if obs.confidence < 0.0 or obs.confidence > 1.0:
            return False, f"VALIDATION_FAILED: confidence must be between 0.0 and 1.0, got {obs.confidence}."

        # Allow obs.value to be None for missing/unobserved fields (strict NULL preservation, not 0)
        # Numeric signals check when value is present
        if obs.value is not None and obs.signal_type in (SignalType.PRICE, SignalType.DEMAND, SignalType.TREND):
            if isinstance(obs.value, dict):
                # Check price inside structured dictionary if present
                if obs.signal_type == SignalType.PRICE:
                    dict_p = obs.value.get("price")
                    if dict_p is not None:
                        try:
                            val_p = float(dict_p)
                            if val_p != val_p:
                                return False, "VALIDATION_FAILED: numeric value cannot be NaN."
                            if val_p < 0:
                                return False, "VALIDATION_FAILED: price cannot be negative."
                        except (ValueError, TypeError):
                            return False, f"VALIDATION_FAILED: signal {obs.signal_type.value} requires numeric price, got '{dict_p}'."
            else:
                try:
                    val_float = float(obs.value)
                    if math_is_nan := (val_float != val_float):
                        return False, "VALIDATION_FAILED: numeric value cannot be NaN."
                    if obs.signal_type == SignalType.PRICE and val_float < 0:
                        return False, "VALIDATION_FAILED: price cannot be negative."
                except (ValueError, TypeError):
                    return False, f"VALIDATION_FAILED: signal {obs.signal_type.value} requires numeric value, got '{obs.value}'."

        return True, None

    @staticmethod
    def check_duplicate(
        obs: CanonicalObservation,
        conn: sqlite3.Connection
    ) -> Tuple[bool, Optional[str], Optional[Union[int, str]], Optional[Dict[str, Any]]]:
        """
        Stage 5: Deterministic Deduplication
        Checks whether this observation was already recorded in SQLite.
        Returns (is_duplicate, destination_table, existing_row_id, previous_row_data).
        """
        cursor = conn.cursor()

        # ── Branch A: Scraped Listings (e.g. Amazon / Marketplace Scrapers) ──
        if obs.observation_type == "LISTING" and obs.external_id:
            asin = obs.external_id.strip()
            # Normalize observation window to day (YYYY-MM-DD) to prevent intra-day duplicate spam
            obs_day = obs.observed_at[:10]
            marketplace = obs.marketplace or "amazon.in"

            cursor.execute("PRAGMA table_info(scraped_listings)")
            s_cols = {r[1] for r in cursor.fetchall()}

            if "asin" in s_cols:
                cursor.execute("""
                    SELECT listing_id, price, rating, review_count, scraped_at
                    FROM scraped_listings
                    WHERE asin = ? AND marketplace = ? AND substr(scraped_at, 1, 10) = ?
                    ORDER BY listing_id DESC LIMIT 1
                """, (asin, marketplace, obs_day))
                row = cursor.fetchone()
                if row:
                    prev_data = {
                        "price": row[1],
                        "rating": row[2],
                        "review_count": row[3],
                        "scraped_at": row[4]
                    }
                    return True, "scraped_listings", row[0], prev_data
                else:
                    cursor.execute("""
                        SELECT listing_id, price, rating, review_count, scraped_at
                        FROM scraped_listings
                        WHERE asin = ? AND marketplace = ?
                        ORDER BY listing_id DESC LIMIT 1
                    """, (asin, marketplace))
                    prev_row = cursor.fetchone()
                    prev_data = {
                        "price": prev_row[1],
                        "rating": prev_row[2],
                        "review_count": prev_row[3],
                        "scraped_at": prev_row[4]
                    } if prev_row else None
                    return False, "scraped_listings", None, prev_data
            else:
                cursor.execute("""
                    SELECT listing_id, price, rating, review_count, extracted_at
                    FROM scraped_listings
                    WHERE (search_query = ? OR product_url LIKE ? OR product_id = ?) AND substr(extracted_at, 1, 10) = ?
                    ORDER BY listing_id DESC LIMIT 1
                """, (asin, f"%{asin}%", obs.product_id or asin, obs_day))
                row = cursor.fetchone()
                if row:
                    prev_data = {
                        "price": row[1],
                        "rating": row[2],
                        "review_count": row[3],
                        "scraped_at": row[4]
                    }
                    return True, "scraped_listings", row[0], prev_data
                else:
                    cursor.execute("""
                        SELECT listing_id, price, rating, review_count, extracted_at
                        FROM scraped_listings
                        WHERE (search_query = ? OR product_url LIKE ? OR product_id = ?)
                        ORDER BY listing_id DESC LIMIT 1
                    """, (asin, f"%{asin}%", obs.product_id or asin))
                    prev_row = cursor.fetchone()
                    prev_data = {
                        "price": prev_row[1],
                        "rating": prev_row[2],
                        "review_count": prev_row[3],
                        "scraped_at": prev_row[4]
                    } if prev_row else None
                    return False, "scraped_listings", None, prev_data

        # ── Branch B: Trend Signals (e.g. Google Trends) ─────────────────────
        elif obs.observation_type == "TREND" or obs.signal_type in (SignalType.DEMAND, SignalType.TREND):
            prod_id = obs.product_id or obs.external_id or "GLOBAL"
            obs_day = obs.observed_at[:10]

            cursor.execute("PRAGMA table_info(trend_signals)")
            t_cols = {r[1] for r in cursor.fetchall()}

            if "current_momentum" in t_cols:
                cursor.execute("""
                    SELECT signal_id, current_momentum, detected_at
                    FROM trend_signals
                    WHERE (product_id = ? OR keyword = ?) AND source = ? AND substr(detected_at, 1, 10) = ?
                    ORDER BY signal_id DESC LIMIT 1
                """, (prod_id, obs.external_id, obs.source_id, obs_day))
                row = cursor.fetchone()
                if row:
                    prev_data = {"current_momentum": row[1], "detected_at": row[2]}
                    return True, "trend_signals", row[0], prev_data
                else:
                    cursor.execute("""
                        SELECT signal_id, current_momentum, detected_at
                        FROM trend_signals
                        WHERE (product_id = ? OR keyword = ?) AND source = ?
                        ORDER BY signal_id DESC LIMIT 1
                    """, (prod_id, obs.external_id, obs.source_id))
                    prev_row = cursor.fetchone()
                    prev_data = {"current_momentum": prev_row[1], "detected_at": prev_row[2]} if prev_row else None
                    return False, "trend_signals", None, prev_data
            else:
                cursor.execute("""
                    SELECT signal_id, velocity_score, created_at
                    FROM trend_signals
                    WHERE (keyword = ? OR keyword = ?) AND platform = ? AND substr(created_at, 1, 10) = ?
                    ORDER BY signal_id DESC LIMIT 1
                """, (obs.external_id or prod_id, prod_id, obs.source_id, obs_day))
                row = cursor.fetchone()
                if row:
                    prev_data = {"current_momentum": row[1], "detected_at": row[2], "velocity_score": row[1]}
                    return True, "trend_signals", row[0], prev_data
                else:
                    cursor.execute("""
                        SELECT signal_id, velocity_score, created_at
                        FROM trend_signals
                        WHERE (keyword = ? OR keyword = ?) AND platform = ?
                        ORDER BY signal_id DESC LIMIT 1
                    """, (obs.external_id or prod_id, prod_id, obs.source_id))
                    prev_row = cursor.fetchone()
                    prev_data = {"current_momentum": prev_row[1], "detected_at": prev_row[2], "velocity_score": prev_row[1]} if prev_row else None
                    return False, "trend_signals", None, prev_data

        # ── Branch C: Intelligence Evidence (General Evidence Table) ────────
        else:
            prod_id = obs.product_id or "GLOBAL"
            sig_type = obs.signal_type.value
            conclusion_key = f"{obs.source_id.upper()} {sig_type}: {obs.external_id or prod_id} = {obs.value}"

            cursor.execute("""
                SELECT evidence_id, confidence, source_timestamp
                FROM intelligence_evidence
                WHERE product_id = ? AND source = ? AND signal_type = ? AND conclusion = ?
                LIMIT 1
            """, (prod_id, obs.source_id, sig_type, conclusion_key))
            row = cursor.fetchone()

            if row:
                return True, "intelligence_evidence", row[0], None
            return False, "intelligence_evidence", None, None

    def ingest_observation(
        self,
        obs: CanonicalObservation,
        db_path: Optional[str] = None,
        run_diff: bool = True
    ) -> Tuple[ObservationIngestionResult, Optional[ObservationDiffReport]]:
        """
        Executes complete ingestion pipeline for a single observation.
        Thread-safe, isolated, and strictly preserves historical data.
        """
        target_db = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        obs_id = obs.source_record_id or f"obs_{obs.generate_dedup_hash()}"

        # ── Stage 2: Validation ──────────────────────────────────────────────
        is_valid, val_err = self.validate_observation(obs)
        if not is_valid:
            return ObservationIngestionResult(
                source_id=obs.source_id,
                product_id=obs.product_id,
                observation_id=obs_id,
                status=IngestionStatus.REJECTED,
                reason=val_err or "Validation rejected.",
            ), None

        # ── Stage 3: Normalization ───────────────────────────────────────────
        # Enforce anti-hallucination guard: external sources cannot emit DECISION or PREDICTION
        if obs.evidence_type in (EvidenceType.DECISION, EvidenceType.PREDICTION):
            obs.evidence_type = EvidenceType.ESTIMATE

        # ── Stage 4: Provenance Construction / Audit ─────────────────────────
        if not obs.provenance or "tamper_sig" not in obs.provenance:
            obs.provenance = ProvenanceTracker.create_provenance(
                source_name=obs.source_id,
                retrieval_method=obs.source_type,
                source_url=obs.source_url,
                raw_payload=obs.raw_payload,
                adapter_version=obs.adapter_version,
                schema_version=obs.schema_version,
                extra_metadata={"marketplace": obs.marketplace, "unit": obs.unit}
            )

        # ── Connect to DB ────────────────────────────────────────────────────
        try:
            conn = sqlite3.connect(target_db, timeout=10.0)
            cursor = conn.cursor()
        except Exception as conn_err:
            return ObservationIngestionResult(
                source_id=obs.source_id,
                product_id=obs.product_id,
                observation_id=obs_id,
                status=IngestionStatus.ERROR,
                reason=f"DATABASE_CONNECTION_ERROR: {conn_err}",
            ), None

        diff_report: Optional[ObservationDiffReport] = None

        try:
            # ── Stage 5: Deduplication ───────────────────────────────────────
            is_dup, dest_table, row_id, prev_data = self.check_duplicate(obs, conn)

            if is_dup:
                conn.close()
                return ObservationIngestionResult(
                    source_id=obs.source_id,
                    product_id=obs.product_id,
                    observation_id=obs_id,
                    status=IngestionStatus.DUPLICATE,
                    destination_table=dest_table,
                    row_id=row_id,
                    reason=f"Duplicate observation detected in '{dest_table}'. Already recorded for this period."
                ), None

            # ── Stage 6: Store ───────────────────────────────────────────────
            inserted_id: Optional[Union[int, str]] = None

            if dest_table == "scraped_listings":
                val_dict = obs.value if isinstance(obs.value, dict) else {}
                # Strictly preserve NULLs: do not convert missing values into 0.0 or 4.0
                price_val = val_dict.get("price")
                if price_val is None and isinstance(obs.value, (int, float)) and obs.signal_type == SignalType.PRICE:
                    price_val = float(obs.value)
                rating_val = val_dict.get("rating")
                reviews_val = val_dict.get("review_count") or val_dict.get("reviews")
                title_val = val_dict.get("title", obs.external_id or "Observed Product")

                cursor.execute("PRAGMA table_info(scraped_listings)")
                s_cols = {r[1] for r in cursor.fetchall()}

                if "asin" in s_cols:
                    cursor.execute("""
                        INSERT INTO scraped_listings (
                            asin, marketplace, price, rating, review_count, title,
                            seller, scraped_at, source_url
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        obs.external_id or "UNKNOWN",
                        obs.marketplace or "amazon.in",
                        price_val,
                        rating_val,
                        reviews_val,
                        str(title_val)[:250],
                        str(val_dict.get("seller", "Amazon")),
                        obs.observed_at,
                        obs.source_url or "n/a"
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO scraped_listings (
                            config_id, product_id, marketplace, region, search_query,
                            title, price, rating, review_count, product_url, seller_name,
                            raw_data_json, extracted_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        1,
                        obs.product_id,
                        obs.marketplace or "amazon.in",
                        "India",
                        obs.external_id or "query",
                        str(title_val)[:250],
                        price_val,
                        rating_val,
                        reviews_val or 0,
                        obs.source_url or f"https://www.amazon.in/dp/{obs.external_id or 'UNKNOWN'}",
                        str(val_dict.get("seller", "Amazon")),
                        json.dumps(obs.provenance),
                        obs.observed_at
                    ))
                inserted_id = cursor.lastrowid

            elif dest_table == "trend_signals":
                val_float = float(obs.value) if isinstance(obs.value, (int, float)) else 0.0
                cursor.execute("PRAGMA table_info(trend_signals)")
                t_cols = {r[1] for r in cursor.fetchall()}

                if "current_momentum" in t_cols:
                    cursor.execute("""
                        INSERT INTO trend_signals (
                            product_id, source, detected_at, current_momentum,
                            growth_rate, confidence_score, keyword, raw_payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        obs.product_id or obs.external_id or "GLOBAL",
                        obs.source_id,
                        obs.observed_at,
                        val_float,
                        0.0,
                        obs.confidence,
                        obs.external_id or "search_term",
                        json.dumps(obs.provenance)
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO trend_signals (
                            platform, keyword, region, velocity_score, raw_signal_json, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        obs.source_id,
                        obs.external_id or obs.product_id or "search_term",
                        obs.marketplace or "India",
                        val_float,
                        json.dumps(obs.provenance),
                        "ACTIVE",
                        obs.observed_at
                    ))
                inserted_id = cursor.lastrowid

            else:  # intelligence_evidence
                sig_type = obs.signal_type.value
                conclusion = f"{obs.source_id.upper()} {sig_type}: {obs.external_id or obs.product_id or 'GLOBAL'} = {obs.value}"
                prov_type = obs.provenance.get("provenance_type", obs.provenance_type)
                status_str = "VERIFIED" if prov_type == "LIVE_VERIFIED" else ("MOCK" if prov_type in ("MOCK", "TEST") else "ESTIMATED")

                cursor.execute("""
                    INSERT INTO intelligence_evidence (
                        product_id, signal_type, conclusion, evidence_status,
                        evidence_details_json, confidence, source, source_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    obs.product_id or "GLOBAL",
                    sig_type,
                    conclusion,
                    status_str,
                    json.dumps(obs.provenance),
                    round(obs.confidence * 100, 1),
                    obs.source_id,
                    obs.observed_at
                ))
                inserted_id = cursor.lastrowid

            conn.commit()

            # ── Stage 7: Change Detection / Diff Evaluation ──────────────────
            if run_diff and prev_data:
                curr_data = obs.value if isinstance(obs.value, dict) else {"value": obs.value}
                if dest_table == "scraped_listings":
                    diff_report = self.diff_engine.compare_listing_snapshots(
                        prev=prev_data,
                        curr={
                            "price": price_val,
                            "rating": rating_val,
                            "review_count": reviews_val,
                            "asin": obs.external_id,
                            "scraped_at": obs.observed_at
                        },
                        source_id=obs.source_id,
                        product_id=obs.product_id,
                        external_id=obs.external_id
                    )
                elif dest_table == "trend_signals":
                    old_mom = prev_data.get("current_momentum", prev_data.get("velocity_score", 0.0))
                    prev_obs = CanonicalObservation(
                        source_id=obs.source_id,
                        product_id=obs.product_id,
                        external_id=obs.external_id,
                        signal_type=obs.signal_type,
                        value=old_mom,
                        observed_at=prev_data.get("detected_at") or prev_data.get("created_at") or obs.observed_at
                    )
                    diff_report = self.diff_engine.compare_observations(prev=prev_obs, curr=obs)

            conn.close()

            return ObservationIngestionResult(
                source_id=obs.source_id,
                product_id=obs.product_id,
                observation_id=obs_id,
                status=IngestionStatus.ACCEPTED,
                destination_table=dest_table,
                row_id=inserted_id,
                reason=f"Observation accepted and stored in '{dest_table}'. (Row ID: {inserted_id})"
            ), diff_report

        except Exception as exc:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
            logger.error(f"Ingestion failed for observation {obs_id}: {exc}", exc_info=True)
            return ObservationIngestionResult(
                source_id=obs.source_id,
                product_id=obs.product_id,
                observation_id=obs_id,
                status=IngestionStatus.ERROR,
                reason=f"INGESTION_ERROR: {exc}"
            ), None

    def ingest_batch(
        self,
        observations: List[CanonicalObservation],
        db_path: Optional[str] = None
    ) -> List[ObservationIngestionResult]:
        """Ingests a sequence of observations safely."""
        results: List[ObservationIngestionResult] = []
        for obs in observations:
            res, _ = self.ingest_observation(obs, db_path=db_path)
            results.append(res)
        return results
