import sqlite3
import json
import datetime
import os
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Ensure project root is importable when running database.py standalone
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def get_db_path() -> Path:
    """Get database path, respecting environment variable for testing."""
    return Path(os.environ.get("APRS_DB_PATH", _PROJECT_ROOT / "data" / "research_engine.db"))


DB_PATH = get_db_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------
# PYDANTIC DATA SCHEMAS (STRICT VALIDATION LAYER)
# -------------------------------------------------------------
class SupplierModel(BaseModel):
    factory_name: str = Field(..., min_length=2)
    supplier_type: str = "Direct Manufacturer"
    industrial_address: str = "Industrial Zone"
    contact_person: str = "Export Manager"
    contact_details: str = "WhatsApp / Email"
    platform_profile_url: str = "https://alibaba.com"
    fob_unit_price: str = "$0.00"
    moq_units: int = Field(default=100, ge=1)
    sample_cost_leadtime: str = "$30 / 3 days"
    certifications: str = "ISO9001, CE"

class ProductEvaluationModel(BaseModel):
    product_id: str
    name: str = Field(..., min_length=3)
    category: str
    region: str = "USA"
    planned_msrp: float = Field(..., gt=0)
    landed_cogs: float = Field(..., ge=0)
    gross_margin_pct: float = Field(default=0.0)
    estimated_cac: float = Field(default=0.0)
    net_profit_pct: float = Field(default=0.0)
    worst_case_stress_margin_pct: float = Field(default=0.0)
    status: str = Field(default="PENDING")
    overall_score: float = Field(default=0.0, ge=0, le=100)
    consensus_status: str = "CONSENSUS_PASS"
    action_plan: str = ""
    sourcing_cluster: str = ""
    marketplace_url: str = ""
    competitor_3star_flaws: str = ""
    upgrade_v2_engineering: str = ""
    bsr_rank: int = Field(default=100)
    estimated_daily_units: int = Field(default=30)
    ad_active_days: int = Field(default=30)
    suppliers: List[SupplierModel] = []
    human_override_status: Optional[str] = None
    # APRS V6 Swarm Fields
    is_shortlisted: int = 0
    is_deleted: int = 0
    deletion_reason: Optional[str] = None
    trend_source: Optional[str] = None
    trend_confidence_score: float = 0.0
    platform_availability: Optional[str] = None
    # AI Supervision Fields for Archive/Rejection tracking
    ai_rejection_reason: Optional[str] = None
    ai_reasoning: Optional[str] = None
    ai_rejection_category: Optional[str] = None
    ai_confidence: float = 0.0


# -------------------------------------------------------------
# DATABASE CONNECTION (WAL MODE & BUSY TIMEOUT)
# -------------------------------------------------------------
def get_connection(db_path: Optional[Any] = None) -> sqlite3.Connection:
    """Returns connection with WAL mode, busy timeout, and foreign keys ON."""
    target = Path(db_path) if db_path else get_db_path()
    conn = sqlite3.connect(str(target), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def _column_exists(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())

def init_db():
    """Initializes tables, meeting audit log, and performs schema migrations."""
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Master Products Table — ALL COLUMNS EXPLICIT
    cur.execute('''
        CREATE TABLE IF NOT EXISTS master_products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            region TEXT NOT NULL,
            planned_msrp REAL NOT NULL,
            landed_cogs REAL NOT NULL DEFAULT 0.0,
            gross_margin_pct REAL NOT NULL DEFAULT 0.0,
            estimated_cac REAL NOT NULL DEFAULT 0.0,
            net_profit_pct REAL NOT NULL DEFAULT 0.0,
            worst_case_stress_margin_pct REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'PENDING',
            overall_score REAL NOT NULL DEFAULT 0.0,
            consensus_status TEXT NOT NULL DEFAULT 'CONSENSUS_PASS',
            action_plan TEXT,
            sourcing_cluster TEXT,
            marketplace_url TEXT,
            competitor_3star_flaws TEXT,
            upgrade_v2_engineering TEXT,
            bsr_rank INTEGER DEFAULT 100,
            estimated_daily_units INTEGER DEFAULT 30,
            ad_active_days INTEGER DEFAULT 30,
            human_override_status TEXT,
            first_discovered_date TEXT,
            last_evaluated_date TEXT,
            keepa_price_stability REAL DEFAULT 85.0,
            helium_monthly_revenue REAL,
            factory_cogs REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            -- AI Supervision columns for Archive/Rejection tracking
            ai_rejection_reason TEXT,
            ai_reasoning TEXT,
            ai_rejection_category TEXT,
            ai_confidence REAL DEFAULT 0.0
        )
    ''')
    
    # 2. Schema Migrations: Ensure all expected columns exist on legacy tables
    required_cols = [
        ("bsr_rank", "INTEGER DEFAULT 100"),
        ("estimated_daily_units", "INTEGER DEFAULT 30"),
        ("ad_active_days", "INTEGER DEFAULT 30"),
        ("human_override_status", "TEXT"),
        ("created_at", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP"),
        ("first_discovered_date", "TEXT"),
        ("last_evaluated_date", "TEXT"),
        ("keepa_price_stability", "REAL DEFAULT 85.0"),
        ("helium_monthly_revenue", "REAL"),
        ("factory_cogs", "REAL"),
        ("landed_cogs", "REAL NOT NULL DEFAULT 0.0"),
        ("estimated_cac", "REAL NOT NULL DEFAULT 0.0"),
        ("gross_margin_pct", "REAL NOT NULL DEFAULT 0.0"),
        ("net_profit_pct", "REAL NOT NULL DEFAULT 0.0"),
        ("worst_case_stress_margin_pct", "REAL NOT NULL DEFAULT 0.0"),
        ("overall_score", "REAL NOT NULL DEFAULT 0.0"),
        ("consensus_status", "TEXT NOT NULL DEFAULT 'CONSENSUS_PASS'"),
        ("status", "TEXT NOT NULL DEFAULT 'PENDING'"),
        ("action_plan", "TEXT"),
        ("ai_rejection_reason", "TEXT"),
        ("ai_reasoning", "TEXT"),
        ("ai_rejection_category", "TEXT"),
        ("ai_confidence", "REAL DEFAULT 0.0"),
        ("sourcing_cluster", "TEXT"),
        ("marketplace_url", "TEXT"),
        ("competitor_3star_flaws", "TEXT"),
        ("upgrade_v2_engineering", "TEXT"),
        # APRS V6 Swarm & Shortlist Fields
        ("is_shortlisted", "INTEGER DEFAULT 0"),
        ("shortlisted_at", "TIMESTAMP"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deletion_reason", "TEXT"),
        ("deleted_at", "TIMESTAMP"),
        ("trend_source", "TEXT"),
        ("trend_confidence_score", "REAL DEFAULT 0.0"),
        ("platform_availability", "TEXT"),
        ("custom_tags", "TEXT"),
    ]
    for col_name, col_type in required_cols:
        if not _column_exists(cur, "master_products", col_name):
            try:
                cur.execute(f"ALTER TABLE master_products ADD COLUMN {col_name} {col_type};")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    continue
                raise
    
    # 3. Product Suppliers Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS product_suppliers (
            supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            factory_name TEXT NOT NULL,
            supplier_type TEXT,
            industrial_address TEXT,
            contact_person TEXT,
            contact_details TEXT,
            platform_profile_url TEXT,
            fob_unit_price TEXT,
            moq_units INTEGER,
            sample_cost_leadtime TEXT,
            certifications TEXT,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')
    
    # 4. Daily Rolling Snapshots
    cur.execute('''
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            date DATE NOT NULL,
            current_price REAL,
            bsr_rank INTEGER,
            estimated_daily_units INTEGER,
            velocity_wow_pct REAL,
            status TEXT,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id)
        )
    ''')
    
    # 5. ZERO-LAG WAR ROOM AUDIT LOG TABLE
    cur.execute('''
        CREATE TABLE IF NOT EXISTS meeting_audit_log (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            speaker_name TEXT NOT NULL,
            speaker_role TEXT NOT NULL,
            avatar TEXT NOT NULL,
            user_prompt TEXT NOT NULL,
            response_text TEXT NOT NULL
        )
    ''')
    
    # 6. PRODUCT GATE PROGRESS TABLE — WITH UNIQUE CONSTRAINT
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS product_gate_progress (
                progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                gate_number INTEGER NOT NULL CHECK(gate_number BETWEEN 1 AND 6),
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'IN_PROGRESS', 'PASS', 'FAIL', 'BLOCKED', 'OVERRIDDEN')),
                blocked_reason TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                completed_by TEXT,
                metadata_json TEXT,
                FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
            )
        ''')
        # Add unique index explicitly after table creation (only if table is empty)
        cur.execute('SELECT COUNT(*) FROM product_gate_progress')
        if cur.fetchone()[0] == 0:
            cur.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS uq_prod_gate 
                ON product_gate_progress (product_id, gate_number)
            ''')
            print("[DEBUG] product_gate_progress table and unique index created successfully")
        else:
            print("[DEBUG] product_gate_progress table exists with data, skipping unique index creation")
    except Exception as e:
        print(f"[ERROR] Failed to create product_gate_progress table: {e}")
        raise
    
    # 7. ARBITER DECISION LOG TABLE
    cur.execute('''
        CREATE TABLE IF NOT EXISTS arbiter_decision_log (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            model_name TEXT,
            stage_name TEXT,
            decision_json TEXT,
            latency_sec REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 8. OPEN-WEB TREND SIGNALS TABLE (Instagram, TikTok, Meta Ads, Google Trends, Reddit)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS trend_signals (
            signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            keyword TEXT NOT NULL,
            trend_category TEXT,
            region TEXT DEFAULT 'India',
            search_volume_est INTEGER DEFAULT 0,
            velocity_score REAL DEFAULT 0.0,
            longevity_days INTEGER DEFAULT 7,
            raw_signal_json TEXT,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 9. MULTI-PLATFORM LISTINGS TABLE (Flipkart, Meesho, Myntra, Amazon, Shopify)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS multi_platform_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            rating REAL,
            review_count INTEGER DEFAULT 0,
            listing_url TEXT NOT NULL,
            seller_name TEXT,
            in_stock INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 10. SWARM MULTI-AGENT AUDIT & BACKTRACK LOG TABLE
    cur.execute('''
        CREATE TABLE IF NOT EXISTS swarm_audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            agent_role TEXT NOT NULL,
            action TEXT NOT NULL,
            input_summary TEXT,
            reasoning TEXT NOT NULL,
            backtrack_target_stage TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 11. FORMAL NEGATIVE FINDING BACKTRACKING EVENTS TABLE
    cur.execute('''
        CREATE TABLE IF NOT EXISTS negative_findings (
            finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            origin_stage TEXT NOT NULL,
            target_stage TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            human_readable_reason TEXT NOT NULL,
            evidence_summary TEXT,
            severity TEXT DEFAULT 'HIGH',
            recommended_action TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 12. SOURCING LAUNCHPAD & RFQ WORKSPACE TABLE
    cur.execute('''
        CREATE TABLE IF NOT EXISTS launchpad_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            target_launch_date TEXT,
            target_moq INTEGER DEFAULT 300,
            target_fob REAL DEFAULT 0.0,
            confirmed_factory_name TEXT,
            sample_ordered INTEGER DEFAULT 0,
            sample_approved INTEGER DEFAULT 0,
            qc_aql_standard TEXT DEFAULT 'ISO 2859-1 (AQL 2.5 Major / 4.0 Minor)',
            compliance_checklist_passed INTEGER DEFAULT 0,
            purchase_order_generated INTEGER DEFAULT 0,
            launch_status TEXT DEFAULT 'SOURCING_NEGOTIATION',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')
    
    # 13. DEFECT CLUSTERS TABLE — Structured complaint clustering from reviews
    cur.execute('''
        CREATE TABLE IF NOT EXISTS defect_clusters (
            cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            defect_category TEXT NOT NULL,
            defect_description TEXT NOT NULL,
            source_platform TEXT DEFAULT 'amazon',
            source_url TEXT,
            review_rating REAL DEFAULT 3.0,
            frequency_count INTEGER DEFAULT 1,
            severity TEXT DEFAULT 'MEDIUM' CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
            is_fixable INTEGER DEFAULT 1,
            v2_fix_description TEXT,
            v2_bom_delta_usd REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 14. ECONOMICS ASSESSMENTS TABLE — 15-factor 3-scenario unit economics results
    cur.execute('''
        CREATE TABLE IF NOT EXISTS economics_assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            scenario TEXT NOT NULL CHECK(scenario IN ('CONSERVATIVE', 'EXPECTED', 'UPSIDE')),
            msrp REAL DEFAULT 0.0,
            fob_cost REAL DEFAULT 0.0,
            packaging_cost REAL DEFAULT 0.0,
            volumetric_freight REAL DEFAULT 0.0,
            customs_duty REAL DEFAULT 0.0,
            marketplace_commission REAL DEFAULT 0.0,
            fulfillment_fee REAL DEFAULT 0.0,
            payment_gateway_fee REAL DEFAULT 0.0,
            rto_reserve REAL DEFAULT 0.0,
            return_fraud_reserve REAL DEFAULT 0.0,
            ad_spend_reserve REAL DEFAULT 0.0,
            damage_reserve REAL DEFAULT 0.0,
            tooling_amortization REAL DEFAULT 0.0,
            net_gst_burden REAL DEFAULT 0.0,
            contribution_margin REAL DEFAULT 0.0,
            contribution_margin_pct REAL DEFAULT 0.0,
            lead_time_pass INTEGER DEFAULT 1,
            overall_pass INTEGER DEFAULT 0,
            composite_score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 15. Discovered Sources — NIM Discovery AI finds websites/platforms dynamically
    cur.execute('''
        CREATE TABLE IF NOT EXISTS discovered_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            domain TEXT,
            source_type TEXT NOT NULL DEFAULT 'trend',
            source_name TEXT,
            description TEXT,
            region TEXT DEFAULT 'Global',
            reliability_score REAL DEFAULT 70.0,
            times_used INTEGER DEFAULT 0,
            times_yielded_results INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            last_crawled_at TIMESTAMP,
            discovered_by TEXT DEFAULT 'nim_discovery',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url, source_type)
        )
    ''')

    # 16. Dynamic Niches — replaces hardcoded DAEMON_NICHES, auto-expanded by NIM
    cur.execute('''
        CREATE TABLE IF NOT EXISTS dynamic_niches (
            niche_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            region TEXT NOT NULL DEFAULT 'India',
            search_limit INTEGER DEFAULT 3,
            priority_score REAL DEFAULT 50.0,
            discovered_by TEXT DEFAULT 'nim_discovery',
            source_signal TEXT,
            times_scanned INTEGER DEFAULT 0,
            products_found INTEGER DEFAULT 0,
            last_scanned_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, region)
        )
    ''')

    # 17. Dynamic Seed Keywords — replaces hardcoded VIRAL_SEED_ROOTS
    cur.execute('''
        CREATE TABLE IF NOT EXISTS dynamic_seed_keywords (
            seed_id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            region TEXT NOT NULL DEFAULT 'India',
            source_platform TEXT DEFAULT 'nim_generated',
            parent_keyword TEXT,
            velocity_score REAL DEFAULT 50.0,
            times_used INTEGER DEFAULT 0,
            last_used_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(keyword, region)
        )
    ''')

    # 18. Universal Marketplace Scraper Configuration — data-driven scraper for ANY site
    cur.execute('''
        CREATE TABLE IF NOT EXISTS marketplace_config (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            marketplace_name TEXT NOT NULL,
            region TEXT NOT NULL DEFAULT 'Global',
            base_url TEXT NOT NULL,
            search_url_pattern TEXT NOT NULL,
            search_param_name TEXT DEFAULT 'q',
            pagination_type TEXT DEFAULT 'page_param',
            pagination_param TEXT DEFAULT 'page',
            max_pages INTEGER DEFAULT 5,
            results_per_page INTEGER DEFAULT 20,
            requires_js INTEGER DEFAULT 1,
            anti_bot_level TEXT DEFAULT 'medium',
            login_required INTEGER DEFAULT 0,
            login_url TEXT,
            cookie_domain TEXT,
            product_list_selector TEXT,
            product_title_selector TEXT,
            product_price_selector TEXT,
            product_rating_selector TEXT,
            product_review_count_selector TEXT,
            product_url_selector TEXT,
            product_image_selector TEXT,
            next_page_selector TEXT,
            custom_headers_json TEXT,
            extraction_prompt TEXT,
            is_active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 50,
            last_scraped_at TIMESTAMP,
            success_rate REAL DEFAULT 100.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(marketplace_name, region)
        )
    ''')

    # 19. Scraped Product Listings — universal storage for all marketplace results
    cur.execute('''
        CREATE TABLE IF NOT EXISTS scraped_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            product_id TEXT,
            marketplace TEXT NOT NULL,
            region TEXT NOT NULL,
            search_query TEXT,
            title TEXT NOT NULL,
            price REAL,
            currency TEXT DEFAULT 'INR',
            original_price REAL,
            discount_pct REAL,
            rating REAL,
            review_count INTEGER DEFAULT 0,
            availability TEXT,
            product_url TEXT NOT NULL,
            image_url TEXT,
            seller_name TEXT,
            seller_rating REAL,
            raw_data_json TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (config_id) REFERENCES marketplace_config(config_id) ON DELETE CASCADE
        )
    ''')

    # 20. Indexes for marketplace scraper
    cur.execute('CREATE INDEX IF NOT EXISTS idx_mkt_config_region ON marketplace_config(region, is_active);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_scraped_listings_query ON scraped_listings(search_query, marketplace);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_scraped_listings_product ON scraped_listings(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_scraped_listings_marketplace ON scraped_listings(marketplace, region);')

    # 21. Indexes for fast queries & deduplication
    cur.execute('CREATE INDEX IF NOT EXISTS idx_prod_region ON master_products(region);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_prod_url ON master_products(marketplace_url);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_prod_shortlist ON master_products(is_shortlisted);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_prod_deleted ON master_products(is_deleted);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_meeting_session ON meeting_audit_log(session_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_gate_progress ON product_gate_progress(product_id, gate_number);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_arbiter_log ON arbiter_decision_log(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_trend_platform ON trend_signals(platform, status);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_multi_listing_prod ON multi_platform_listings(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_swarm_audit_prod ON swarm_audit_log(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_negative_findings_prod ON negative_findings(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_launchpad_prod ON launchpad_items(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_defect_clusters_prod ON defect_clusters(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_econ_assess_prod ON economics_assessments(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_disc_sources_type ON discovered_sources(source_type, is_active);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_disc_sources_region ON discovered_sources(region, source_type);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_dyn_niches_region ON dynamic_niches(region, is_active);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_dyn_seeds_region ON dynamic_seed_keywords(region, is_active);')

    # ── AI Supervisor tables: scraper_validations, ai_supervisor_logs, ai_task_improvements ──
    cur.execute('''
        CREATE TABLE IF NOT EXISTS scraper_validations (
            validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            marketplace TEXT NOT NULL,
            region TEXT NOT NULL,
            is_valid INTEGER DEFAULT 1,
            confidence REAL DEFAULT 50.0,
            issues TEXT,
            auto_soft_delete INTEGER DEFAULT 0,
            rejection_reason TEXT,
            rejection_category TEXT,
            ai_notes TEXT,
            ai_suggested_fix TEXT,
            raw_product_data TEXT,
            validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ai_supervisor_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active_tasks INTEGER DEFAULT 0,
            total_validations INTEGER DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ai_task_improvements (
            improvement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            task_type TEXT,
            marketplace TEXT,
            region TEXT,
            improvement_type TEXT,
            description TEXT,
            priority TEXT,
            target TEXT,
            triggered_by TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Ensure AI rejection columns exist in master_products
    _ai_cols = [
        ("ai_rejection_reason",    "TEXT"),
        ("ai_rejection_category",  "TEXT"),
        ("ai_reasoning",           "TEXT"),
        ("ai_confidence",          "REAL DEFAULT 0.0"),
    ]
    for _col, _dtype in _ai_cols:
        if not _column_exists(cur, "master_products", _col):
            try:
                cur.execute(f"ALTER TABLE master_products ADD COLUMN {_col} {_dtype}")
            except Exception:
                pass

    # 22. USERS TABLE — Authentication (preserved; billing removed)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            full_name TEXT,
            avatar_url TEXT,
            provider TEXT DEFAULT 'email',
            provider_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);')

    # ── APRS V7 AUTONOMOUS PRODUCT INTELLIGENCE ENGINE TABLES ────────────────
    # 23. Product Opportunity Intelligence Profiles
    cur.execute('''
        CREATE TABLE IF NOT EXISTS product_intelligence (
            intelligence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL UNIQUE,
            opportunity_score REAL DEFAULT 0.0,
            kill_status TEXT DEFAULT 'INSUFFICIENT_EVIDENCE',
            kill_reasons_json TEXT,
            kill_evidence_json TEXT,
            scorecard_json TEXT,
            signals_json TEXT,
            explanations_json TEXT,
            counterfactual_json TEXT,
            gaps_json TEXT,
            pain_map_json TEXT,
            trend_analysis_json TEXT,
            freshness_status TEXT DEFAULT 'FRESH',
            confidence_score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 24. Intelligence Evidence Trail
    cur.execute('''
        CREATE TABLE IF NOT EXISTS intelligence_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            conclusion TEXT NOT NULL,
            evidence_status TEXT DEFAULT 'VERIFIED',
            evidence_details_json TEXT,
            confidence REAL DEFAULT 0.0,
            source TEXT,
            source_timestamp TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 25. Opportunity Alert Center
    cur.execute('''
        CREATE TABLE IF NOT EXISTS opportunity_alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            alert_type TEXT NOT NULL,
            severity TEXT DEFAULT 'MEDIUM',
            title TEXT NOT NULL,
            what_happened TEXT NOT NULL,
            why_it_matters TEXT NOT NULL,
            evidence_summary TEXT,
            recommended_action TEXT,
            is_dismissed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 26. Product Watchlist (Local-first)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS product_watchlist (
            watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL UNIQUE,
            priority_status TEXT DEFAULT 'WATCH',
            notes TEXT,
            monitored_metrics_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 27. Autonomous Research Runs
    cur.execute('''
        CREATE TABLE IF NOT EXISTS research_runs (
            research_run_id TEXT PRIMARY KEY,
            run_status TEXT DEFAULT 'RUNNING',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            products_processed INTEGER DEFAULT 0,
            sources_consulted_count INTEGER DEFAULT 0,
            signals_generated_count INTEGER DEFAULT 0,
            alerts_generated_count INTEGER DEFAULT 0,
            gate_transitions_count INTEGER DEFAULT 0,
            errors_json TEXT,
            summary_json TEXT
        )
    ''')

    # 28. Source Reliability & Telemetry
    cur.execute('''
        CREATE TABLE IF NOT EXISTS source_health (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL UNIQUE,
            data_type TEXT NOT NULL,
            last_successful_fetch TIMESTAMP,
            failure_count INTEGER DEFAULT 0,
            freshness_status TEXT DEFAULT 'HEALTHY',
            response_time_ms REAL DEFAULT 0.0,
            details_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 29. Multi-Source Conflict Detection
    cur.execute('''
        CREATE TABLE IF NOT EXISTS data_conflicts (
            conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            source_a TEXT NOT NULL,
            value_a TEXT NOT NULL,
            timestamp_a TIMESTAMP,
            source_b TEXT NOT NULL,
            value_b TEXT NOT NULL,
            timestamp_b TIMESTAMP,
            severity TEXT DEFAULT 'MEDIUM',
            resolution_status TEXT DEFAULT 'UNRESOLVED',
            explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # 30. Historical Intelligence Audit Timeline
    cur.execute('''
        CREATE TABLE IF NOT EXISTS intelligence_timeline (
            timeline_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_title TEXT NOT NULL,
            event_description TEXT NOT NULL,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE
        )
    ''')

    # V7 Indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_intel_prod ON product_intelligence(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_evidence_prod ON intelligence_evidence(product_id, signal_type);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_alerts_prod ON opportunity_alerts(product_id, is_dismissed);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_prod ON product_watchlist(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_conflicts_prod ON data_conflicts(product_id, resolution_status);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_timeline_prod ON intelligence_timeline(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_source_health_name ON source_health(source_name);')

    # ── APRS V8 CLOSED-LOOP OUTCOME INTELLIGENCE FOUNDATION ──────────────────
    # 31. Immutable Decision Ledger
    cur.execute('''
        CREATE TABLE IF NOT EXISTS decision_ledger (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            research_run_id TEXT,
            decision_type TEXT NOT NULL DEFAULT 'LAUNCHPAD_COMMITMENT',
            decision_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            frozen_score REAL NOT NULL,
            frozen_confidence REAL NOT NULL,
            frozen_kill_status TEXT NOT NULL,
            predicted_daily_units INTEGER,
            predicted_selling_price REAL,
            predicted_cogs REAL,
            predicted_cm_pct REAL,
            predicted_rto_pct REAL,
            predicted_cac REAL,
            policy_version TEXT NOT NULL DEFAULT 'V7.2',
            model_version TEXT NOT NULL DEFAULT 'V7.2_HEURISTIC',
            snapshot_payload_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE,
            FOREIGN KEY (research_run_id) REFERENCES research_runs(research_run_id) ON DELETE SET NULL
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_decision_ledger_prod_time ON decision_ledger(product_id, decision_timestamp);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_decision_ledger_type ON decision_ledger(decision_type);')

    # Immutability safeguard trigger
    cur.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_decision_ledger_immutable
        BEFORE UPDATE ON decision_ledger
        BEGIN
            SELECT RAISE(ABORT, 'decision_ledger records are immutable and cannot be updated');
        END;
    ''')

    # 32. Product Outcomes (Observed Real-World Performance)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS product_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            decision_id INTEGER,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            period_type TEXT NOT NULL CHECK(period_type IN ('DAY_30', 'DAY_60', 'DAY_90', 'LIFETIME', 'CUSTOM')),
            actual_units_sold INTEGER,
            actual_revenue REAL,
            actual_avg_selling_price REAL,
            actual_landed_cogs REAL,
            actual_contribution_margin REAL,
            actual_cm_pct REAL,
            actual_returns_count INTEGER,
            actual_return_rate_pct REAL,
            actual_rto_count INTEGER,
            actual_rto_rate_pct REAL,
            actual_ad_spend REAL,
            actual_cac REAL,
            actual_inventory INTEGER,
            actual_stockout_days INTEGER,
            data_source TEXT NOT NULL DEFAULT 'MANUAL',
            source_record_id TEXT,
            notes TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE,
            FOREIGN KEY (decision_id) REFERENCES decision_ledger(decision_id) ON DELETE SET NULL,
            UNIQUE(product_id, period_type, period_start, period_end)
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_product_outcomes_prod_start ON product_outcomes(product_id, period_start);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_product_outcomes_decision ON product_outcomes(decision_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_product_outcomes_period ON product_outcomes(period_type);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_product_outcomes_source ON product_outcomes(product_id, source_record_id);')

    # 33. Prediction Calibrations (Observed Reality vs Frozen Decisions)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS prediction_calibrations (
            calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id INTEGER NOT NULL,
            outcome_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            calibration_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            demand_predicted REAL,
            demand_actual REAL,
            demand_signed_error REAL,
            demand_absolute_error REAL,
            demand_percentage_error REAL,
            cm_predicted_pct REAL,
            cm_actual_pct REAL,
            cm_signed_error_pct_points REAL,
            cm_absolute_error_pct_points REAL,
            rto_predicted_pct REAL,
            rto_actual_pct REAL,
            rto_signed_error_pct_points REAL,
            rto_absolute_error_pct_points REAL,
            cac_predicted REAL,
            cac_actual REAL,
            cac_signed_error REAL,
            cac_absolute_error REAL,
            cac_percentage_error REAL,
            price_predicted REAL,
            price_actual REAL,
            price_signed_error REAL,
            directional_accuracy TEXT NOT NULL DEFAULT 'UNKNOWN',
            data_completeness_pct REAL DEFAULT 0.0,
            calibration_status TEXT NOT NULL DEFAULT 'CALIBRATED',
            calculation_version TEXT NOT NULL DEFAULT 'V8_CALIBRATION_V1',
            details_json TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (decision_id) REFERENCES decision_ledger(decision_id) ON DELETE CASCADE,
            FOREIGN KEY (outcome_id) REFERENCES product_outcomes(outcome_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE,
            UNIQUE(decision_id, outcome_id, calculation_version)
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_calib_decision ON prediction_calibrations(decision_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_calib_outcome ON prediction_calibrations(outcome_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_calib_product ON prediction_calibrations(product_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_calib_version ON prediction_calibrations(calculation_version);')

    # 34. Outcome Corrections Log (Auditable corrections to post-launch observations)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS outcome_corrections_log (
            correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            outcome_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            decision_id INTEGER,
            field_name TEXT NOT NULL,
            previous_value TEXT,
            new_value TEXT,
            correction_reason TEXT NOT NULL,
            corrected_by TEXT NOT NULL DEFAULT 'SYSTEM_OPERATOR',
            correction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (outcome_id) REFERENCES product_outcomes(outcome_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id) ON DELETE CASCADE,
            FOREIGN KEY (decision_id) REFERENCES decision_ledger(decision_id) ON DELETE SET NULL
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_outcome_corr_outcome ON outcome_corrections_log(outcome_id);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_outcome_corr_prod ON outcome_corrections_log(product_id);')

    # -------------------------------------------------------------------------
    # V8 PHASE 7: LEARNING EVIDENCE TABLES
    # -------------------------------------------------------------------------
    # learning_bias_summaries — Persisted auditable aggregate bias evidence.
    # Versioned and fingerprinted so provenance is traceable across recalculations.
    cur.execute('''
        CREATE TABLE IF NOT EXISTS learning_bias_summaries (
            bias_summary_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_type          TEXT NOT NULL CHECK(scope_type IN ('PORTFOLIO','CATEGORY','PRODUCT','SOURCE','MODEL_VERSION')),
            scope_key           TEXT NOT NULL,
            metric_name         TEXT NOT NULL,
            sample_size         INTEGER NOT NULL DEFAULT 0,
            valid_observations  INTEGER NOT NULL DEFAULT 0,
            mean_signed_error   REAL,
            mean_absolute_error REAL,
            mean_absolute_percentage_error REAL,
            median_signed_error REAL,
            directional_bias    TEXT NOT NULL DEFAULT 'INSUFFICIENT_EVIDENCE',
            reliability_tier    TEXT NOT NULL DEFAULT 'INSUFFICIENT_SAMPLE',
            evidence_status     TEXT NOT NULL DEFAULT 'NO_OBSERVATION_DATA',
            first_observation_date TEXT,
            last_observation_date  TEXT,
            calculation_version TEXT NOT NULL DEFAULT 'V8_LEARNING_V1',
            source_data_fingerprint TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_bias_summ_scope ON learning_bias_summaries(scope_type, scope_key);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_bias_summ_metric ON learning_bias_summaries(metric_name);')

    # learning_recommendations — Human-auditable learning proposals (NOT automatic changes).
    # A recommendation is a hypothesis for investigation. It does NOT modify any policy.
    cur.execute('''
        CREATE TABLE IF NOT EXISTS learning_recommendations (
            recommendation_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_type          TEXT NOT NULL,
            scope_key           TEXT NOT NULL,
            metric_name         TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            evidence_status     TEXT NOT NULL DEFAULT 'NO_OBSERVATION_DATA',
            sample_size         INTEGER NOT NULL DEFAULT 0,
            observed_bias       REAL,
            confidence_note     TEXT,
            reason              TEXT,
            supporting_summary_id INTEGER REFERENCES learning_bias_summaries(bias_summary_id) ON DELETE SET NULL,
            status              TEXT NOT NULL DEFAULT 'PROPOSED'
                                     CHECK(status IN ('PROPOSED','UNDER_REVIEW','ACCEPTED','REJECTED','DEFERRED','SUPERSEDED')),
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at         TIMESTAMP,
            reviewed_by         TEXT,
            review_notes        TEXT
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_learn_rec_scope ON learning_recommendations(scope_type, scope_key);')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_learn_rec_status ON learning_recommendations(status);')

    # Drop legacy subscription tables if present in existing database
    for _legacy_tbl in ("subscription_plans", "subscriptions", "usage_periods", "payments", "webhook_events"):
        cur.execute(f"DROP TABLE IF EXISTS {_legacy_tbl}")

    conn.commit()
    conn.close()


def is_duplicate_product(product_id: str, marketplace_url: str) -> bool:
    """Checks if product or ASIN URL already exists in database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id FROM master_products WHERE product_id = ? OR marketplace_url = ?", (product_id, marketplace_url))
    exists = cur.fetchone() is not None
    conn.close()
    return exists

def record_product_evaluation(prod_dict: dict, eval_dict: dict, model_name: str = "Nemotron-3-Ultra-550B") -> bool:
    """Inserts or updates a validated product dossier into the SSOT database."""
    if not eval_dict:
        raise ValueError("eval_dict cannot be empty. Gate 3 must produce real economics before DB write.")
    
    try:
        merged_data = {
            "product_id": prod_dict["id"],
            "name": prod_dict["name"],
            "category": prod_dict["category"],
            "region": prod_dict.get("region", "USA"),
            "planned_msrp": float(prod_dict.get("retail_msrp", 49.99)),
            "landed_cogs": float(eval_dict.get("landed_cogs", prod_dict.get("factory_cogs", 0.0))),
            "gross_margin_pct": float(eval_dict.get("gross_margin_pct", 0.0)),
            "estimated_cac": float(prod_dict.get("est_cac", 0.0)),
            "net_profit_pct": float(eval_dict.get("net_profit_pct", 0.0)),
            "worst_case_stress_margin_pct": float(eval_dict.get("worst_case_stress_margin_pct", eval_dict.get("stress_margin_pct", 0.0))),
            "status": eval_dict.get("status", "PENDING"),
            "overall_score": float(eval_dict.get("score", 0.0)),
            "consensus_status": eval_dict.get("consensus_status", "CONSENSUS_PASS"),
            "action_plan": eval_dict.get("action_plan", "Awaiting Gate 2 manual defect review"),
            "sourcing_cluster": prod_dict.get("sourcing_hub", ""),
            "marketplace_url": prod_dict.get("marketplace_url", ""),
            "competitor_3star_flaws": prod_dict.get("competitor_flaw", ""),
            "upgrade_v2_engineering": prod_dict.get("upgrade_v2", ""),
            "bsr_rank": int(prod_dict.get("bsr_rank", 100)),
            "estimated_daily_units": int(prod_dict.get("estimated_daily_units", 30)),
            "ad_active_days": int(prod_dict.get("ad_active_days", 0)),
            "suppliers": prod_dict.get("suppliers", [])
        }
        
        validated = ProductEvaluationModel(**merged_data)
        
        conn = get_connection()
        cur = conn.cursor()
        
        today_str = datetime.date.today().isoformat()
        
        # Upsert into master_products (including V6 trend & shortlist fields + AI Supervision fields)
        cur.execute('''
            INSERT INTO master_products (
                product_id, name, category, region, planned_msrp, landed_cogs,
                gross_margin_pct, estimated_cac, net_profit_pct, worst_case_stress_margin_pct,
                status, overall_score, consensus_status, action_plan, sourcing_cluster,
                marketplace_url, competitor_3star_flaws, upgrade_v2_engineering,
                bsr_rank, estimated_daily_units, ad_active_days,
                is_shortlisted, is_deleted, trend_source, trend_confidence_score, platform_availability,
                first_discovered_date, last_evaluated_date, updated_at,
                -- AI Supervision columns
                ai_rejection_reason, ai_reasoning, ai_rejection_category, ai_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                name=excluded.name,
                planned_msrp=excluded.planned_msrp,
                landed_cogs=excluded.landed_cogs,
                gross_margin_pct=excluded.gross_margin_pct,
                estimated_cac=excluded.estimated_cac,
                net_profit_pct=excluded.net_profit_pct,
                worst_case_stress_margin_pct=excluded.worst_case_stress_margin_pct,
                status=excluded.status,
                overall_score=excluded.overall_score,
                consensus_status=excluded.consensus_status,
                action_plan=excluded.action_plan,
                marketplace_url=excluded.marketplace_url,
                bsr_rank=excluded.bsr_rank,
                estimated_daily_units=excluded.estimated_daily_units,
                ad_active_days=excluded.ad_active_days,
                trend_source=COALESCE(excluded.trend_source, master_products.trend_source),
                trend_confidence_score=COALESCE(excluded.trend_confidence_score, master_products.trend_confidence_score),
                platform_availability=COALESCE(excluded.platform_availability, master_products.platform_availability),
                last_evaluated_date=excluded.last_evaluated_date,
                updated_at=CURRENT_TIMESTAMP,
                -- AI Supervision columns
                ai_rejection_reason=COALESCE(excluded.ai_rejection_reason, master_products.ai_rejection_reason),
                ai_reasoning=COALESCE(excluded.ai_reasoning, master_products.ai_reasoning),
                ai_rejection_category=COALESCE(excluded.ai_rejection_category, master_products.ai_rejection_category),
                ai_confidence=COALESCE(excluded.ai_confidence, master_products.ai_confidence)
        ''', (
            validated.product_id, validated.name, validated.category, validated.region,
            validated.planned_msrp, validated.landed_cogs, validated.gross_margin_pct,
            validated.estimated_cac, validated.net_profit_pct, validated.worst_case_stress_margin_pct,
            validated.status, validated.overall_score, validated.consensus_status, validated.action_plan,
            validated.sourcing_cluster, validated.marketplace_url, validated.competitor_3star_flaws,
            validated.upgrade_v2_engineering, validated.bsr_rank, validated.estimated_daily_units,
            validated.ad_active_days, validated.is_shortlisted, validated.is_deleted,
            validated.trend_source, validated.trend_confidence_score, validated.platform_availability,
            today_str, today_str,
            # AI Supervision columns
            validated.ai_rejection_reason, validated.ai_reasoning, validated.ai_rejection_category, validated.ai_confidence
        ))
        
        # Initialize gate progress for new products
        cur.execute("SELECT COUNT(*) FROM product_gate_progress WHERE product_id = ?", (validated.product_id,))
        if cur.fetchone()[0] == 0:
            for g in range(1, 7):
                cur.execute('''
                    INSERT INTO product_gate_progress (product_id, gate_number, status, started_at)
                    VALUES (?, ?, 'PENDING', CURRENT_TIMESTAMP)
                ''', (validated.product_id, g))
        
        # Refresh suppliers for this product
        cur.execute("DELETE FROM product_suppliers WHERE product_id = ?", (validated.product_id,))
        for s in validated.suppliers:
            cur.execute('''
                INSERT INTO product_suppliers (
                    product_id, factory_name, supplier_type, industrial_address,
                    contact_person, contact_details, platform_profile_url,
                    fob_unit_price, moq_units, sample_cost_leadtime, certifications
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                validated.product_id, s.factory_name, s.supplier_type, s.industrial_address,
                s.contact_person, s.contact_details, s.platform_profile_url,
                s.fob_unit_price, s.moq_units, s.sample_cost_leadtime, s.certifications
            ))
            
        conn.commit()
        conn.close()
        return True
    except (ValueError, TypeError) as e:
        print(f"[DB VALIDATION ERROR in record_product_evaluation]: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"[DB ERROR in record_product_evaluation]: {e}")
        traceback.print_exc()
        raise

def get_all_products(include_deleted: bool = False, shortlisted_only: bool = False) -> List[Dict[str, Any]]:
    """Fetches products with attached suppliers from SQLite SSOT, filtering soft-deleted by default."""
    conn = get_connection()
    cur = conn.cursor()
    
    query = "SELECT * FROM master_products"
    clauses = []
    params = []
    
    if not include_deleted:
        clauses.append("COALESCE(is_deleted, 0) = 0")
    if shortlisted_only:
        clauses.append("COALESCE(is_shortlisted, 0) = 1")
        
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
        
    query += " ORDER BY overall_score DESC"
    
    cur.execute(query, params)
    products = [dict(row) for row in cur.fetchall()]
    
    for p in products:
        cur.execute("SELECT * FROM product_suppliers WHERE product_id = ?", (p["product_id"],))
        p["suppliers"] = [dict(s) for s in cur.fetchall()]
        # Attach multi-platform listings if available
        cur.execute("SELECT platform, title, price, currency, rating, review_count, listing_url, in_stock FROM multi_platform_listings WHERE product_id = ?", (p["product_id"],))
        p["multi_platform_listings"] = [dict(l) for l in cur.fetchall()]
        
    conn.close()
    return products

def soft_delete_product(product_id: str, deletion_reason: str, deleted_by: str = "human", 
                         ai_rejection_reason: Optional[str] = None, ai_reasoning: Optional[str] = None,
                         ai_rejection_category: Optional[str] = None, ai_confidence: float = 0.0) -> bool:
    """Soft-deletes a product with mandatory audit rationale, preserving history.
    Optionally accepts AI Supervisor rejection details for Archive tracking."""
    if not deletion_reason or not deletion_reason.strip():
        raise ValueError("A deletion reason is mandatory for auditing purposes.")
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE master_products
            SET is_deleted = 1, 
                deletion_reason = ?, 
                deleted_at = CURRENT_TIMESTAMP, 
                updated_at = CURRENT_TIMESTAMP,
                ai_rejection_reason = COALESCE(?, ai_rejection_reason),
                ai_reasoning = COALESCE(?, ai_reasoning),
                ai_rejection_category = COALESCE(?, ai_rejection_category),
                ai_confidence = COALESCE(?, ai_confidence)
            WHERE product_id = ?
        ''', (deletion_reason.strip(), ai_rejection_reason, ai_reasoning, 
              ai_rejection_category, ai_confidence, product_id))
        
        # Log to swarm audit log
        cur.execute('''
            INSERT INTO swarm_audit_log (product_id, agent_role, action, input_summary, reasoning)
            VALUES (?, ?, 'SOFT_DELETE', 'User/AI requested deletion', ?)
        ''', (product_id, deleted_by, deletion_reason.strip()))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Soft Delete Error]: {e}")
        return False

def restore_product(product_id: str) -> bool:
    """Restores a soft-deleted product back to the active catalogue."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE master_products
            SET is_deleted = 0, deletion_reason = NULL, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP,
                ai_rejection_reason = NULL, ai_reasoning = NULL, ai_rejection_category = NULL, ai_confidence = 0.0
            WHERE product_id = ?
        ''', (product_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Restore Error]: {e}")
        return False

def write_ai_rejection(product_id: str, ai_rejection_reason: str, ai_reasoning: str, 
                       ai_rejection_category: str, ai_confidence: float = 0.0) -> bool:
    """Write AI Supervisor rejection details to a product for Archive tracking.
    Used when AI Supervisor validates and rejects a scraped product."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE master_products
            SET is_deleted = 1,
                deletion_reason = ?,
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                ai_rejection_reason = ?,
                ai_reasoning = ?,
                ai_rejection_category = ?,
                ai_confidence = ?
            WHERE product_id = ?
        ''', (f"AI Validation Rejected: {ai_rejection_reason}", ai_rejection_reason, ai_reasoning, 
              ai_rejection_category, ai_confidence, product_id))
        
        # Log to swarm audit log
        cur.execute('''
            INSERT INTO swarm_audit_log (product_id, agent_role, action, input_summary, reasoning)
            VALUES (?, ?, 'AI_VALIDATION_REJECTED', 'AI Supervisor validation failed', ?)
        ''', (product_id, "ai_supervisor", ai_reasoning[:500]))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Write AI Rejection Error]: {e}")
        return False

def toggle_shortlist(product_id: str, is_shortlisted: bool = True) -> bool:
    """Marks or unmarks a product as shortlisted for active selling/sourcing."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        shortlist_val = 1 if is_shortlisted else 0
        cur.execute('''
            UPDATE master_products
            SET is_shortlisted = ?, shortlisted_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE NULL END, updated_at = CURRENT_TIMESTAMP
            WHERE product_id = ?
        ''', (shortlist_val, shortlist_val, product_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Shortlist Error]: {e}")
        return False

def get_shortlisted_products() -> List[Dict[str, Any]]:
    """Returns only active products marked as shortlisted for selling."""
    return get_all_products(include_deleted=False, shortlisted_only=True)

# -------------------------------------------------------------
# OPEN-WEB TREND SIGNALS & MULTI-PLATFORM RECORDING
# -------------------------------------------------------------
def record_trend_signal(platform: str, keyword: str, category: str = "General", region: str = "India",
                        search_volume_est: int = 0, velocity_score: float = 0.0,
                        longevity_days: int = 7, raw_json: dict = None) -> int:
    """Records an emerging social/search trend signal from Instagram, TikTok, Meta, Google, or Reddit."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        raw_str = json.dumps(raw_json or {})
        cur.execute('''
            INSERT INTO trend_signals (platform, keyword, trend_category, region, search_volume_est, velocity_score, longevity_days, raw_signal_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (platform, keyword, category, region, search_volume_est, velocity_score, longevity_days, raw_str))
        signal_id = cur.lastrowid
        conn.commit()
        conn.close()
        return signal_id
    except Exception as e:
        print(f"[DB Record Trend Error]: {e}")
        return 0

def get_active_trend_signals(region: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches active trend signals sorted by velocity and longevity."""
    conn = get_connection()
    cur = conn.cursor()
    if region:
        cur.execute("SELECT * FROM trend_signals WHERE status = 'ACTIVE' AND region = ? ORDER BY velocity_score DESC, created_at DESC LIMIT ?", (region, limit))
    else:
        cur.execute("SELECT * FROM trend_signals WHERE status = 'ACTIVE' ORDER BY velocity_score DESC, created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def record_multi_platform_listing(product_id: str, platform: str, title: str, price: float,
                                  listing_url: str, rating: float = None, review_count: int = 0,
                                  currency: str = "INR", seller_name: str = None, in_stock: int = 1, **kwargs) -> bool:
    """Stores cross-platform listings (Flipkart, Meesho, Myntra, Amazon, Shopify)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO multi_platform_listings (product_id, platform, title, price, currency, rating, review_count, listing_url, seller_name, in_stock)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, platform, title, float(price), currency, rating, int(review_count), listing_url, seller_name, int(in_stock)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Multi-Platform Listing Error]: {e}")
        return False

def record_swarm_audit_log(product_id: str, agent_role: str, action: str, reasoning: str,
                           input_summary: str = "", backtrack_target_stage: str = None) -> bool:
    """Records an AI swarm audit decision, verification step, or false-positive backtrack alarm."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO swarm_audit_log (product_id, agent_role, action, input_summary, reasoning, backtrack_target_stage)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (product_id, agent_role, action, input_summary, reasoning, backtrack_target_stage))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Swarm Audit Log Error]: {e}")
        return False

def get_swarm_audit_logs(product_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetches swarm audit decisions and backtrack logs."""
    conn = get_connection()
    cur = conn.cursor()
    if product_id:
        cur.execute("SELECT * FROM swarm_audit_log WHERE product_id = ? ORDER BY audit_id DESC LIMIT ?", (product_id, limit))
    else:
        cur.execute("SELECT * FROM swarm_audit_log ORDER BY audit_id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# -------------------------------------------------------------
# UNIFIED DATABASE EXPLORER INSPECTOR (APRS V6)
# -------------------------------------------------------------
def get_all_table_names() -> List[str]:
    """Returns all user table names present in SQLite database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name ASC;")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables

def get_table_data(table_name: str, limit: int = 200, search_query: str = None) -> List[Dict[str, Any]]:
    """Safely retrieves raw records from any SQLite table for the Unified SSOT Explorer."""
    # Whitelist table names to prevent SQL injection
    valid_tables = get_all_table_names()
    if table_name not in valid_tables:
        return []
    
    conn = get_connection()
    cur = conn.cursor()
    
    if search_query and search_query.strip():
        # Generic text search across table columns
        cur.execute(f"PRAGMA table_info({table_name});")
        text_cols = [r[1] for r in cur.fetchall() if "TEXT" in str(r[2]).upper() or "CHAR" in str(r[2]).upper()]
        if text_cols:
            where_clause = " OR ".join([f"{col} LIKE ?" for col in text_cols])
            params = [f"%{search_query.strip()}%"] * len(text_cols)
            cur.execute(f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT {int(limit)}", params)
        else:
            cur.execute(f"SELECT * FROM {table_name} LIMIT {int(limit)}")
    else:
        cur.execute(f"SELECT * FROM {table_name} LIMIT {int(limit)}")
        
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def set_human_override(product_id: str, new_status: Optional[str]) -> bool:
    """Allows human user to override algorithmic verdicts AND sync all gates."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        if new_status:
            cur.execute('''
                UPDATE master_products
                SET human_override_status = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE product_id = ?
            ''', (new_status, new_status, product_id))
        else:
            cur.execute('''
                UPDATE master_products
                SET human_override_status = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE product_id = ?
            ''', (product_id,))
        
        # SYNC: Override all gates
        if new_status in ("PASS", "OVERRIDDEN"):
            for g in range(1, 7):
                cur.execute('''
                    UPDATE product_gate_progress
                    SET status = 'OVERRIDDEN', completed_by = 'human_override', completed_at = CURRENT_TIMESTAMP
                    WHERE product_id = ? AND gate_number = ?
                ''', (product_id, g))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Override Error]: {e}")
        return False

# -------------------------------------------------------------
# ZERO-LAG MEETING AUDIT LOGGING
# -------------------------------------------------------------
def log_meeting_turn(session_id: str, speaker_name: str, speaker_role: str, avatar: str, user_prompt: str, response_text: str):
    """Inserts a single chat message turn into SQLite audit table instantly (O(1))."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO meeting_audit_log (session_id, speaker_name, speaker_role, avatar, user_prompt, response_text)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, speaker_name, speaker_role, avatar, user_prompt, response_text))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Meeting Log Error]: {e}")

def get_meeting_history(session_id: str = None, limit: int = None) -> List[Dict[str, Any]]:
    """Fetches all logged meeting dialogue from SQLite."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM meeting_audit_log"
    params = []
    if session_id:
        query += " WHERE session_id = ?"
        params.append(session_id)
    query += " ORDER BY message_id ASC"
    if limit:
        query += f" LIMIT {int(limit)}"
    cur.execute(query, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# -------------------------------------------------------------
# GATE STATE MACHINE (6-Stage Workflow)
# -------------------------------------------------------------
GATE_NAMES = {
    1: "SIGNAL_DISCOVERY",
    2: "DEFECT_MINING",
    3: "ECONOMICS_VALIDATION",
    4: "SOURCING_QUOTE",
    5: "WAR_ROOM_CONSENSUS",
    6: "SIGN_OFF_ARTIFACTS"
}

GATE_ORDER = [1, 2, 3, 4, 5, 6]

def init_product_gates(product_id: str) -> bool:
    """Initialize all 6 gates for a new product as PENDING."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        for gate_num in GATE_ORDER:
            cur.execute('''
                INSERT OR IGNORE INTO product_gate_progress (product_id, gate_number, status, started_at)
                VALUES (?, ?, 'PENDING', CURRENT_TIMESTAMP)
            ''', (product_id, gate_num))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[GATE INIT ERROR]: {e}")
        return False

def get_gate_status(product_id: str, gate_number: int = None) -> List[Dict[str, Any]]:
    """Get gate progress for a product. If gate_number is None, returns all gates."""
    conn = get_connection()
    cur = conn.cursor()
    if gate_number:
        cur.execute("SELECT * FROM product_gate_progress WHERE product_id = ? AND gate_number = ?", (product_id, gate_number))
    else:
        cur.execute("SELECT * FROM product_gate_progress WHERE product_id = ? ORDER BY gate_number", (product_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def update_gate_status(product_id: str, gate_number: int, status: str, blocked_reason: str = None, metadata: Dict = None, completed_by: str = "system", metadata_json: Any = None) -> bool:
    """Update a gate's status with timestamp and metadata (accepts metadata dict or metadata_json)."""
    valid_statuses = ['PENDING', 'IN_PROGRESS', 'PASS', 'FAIL', 'BLOCKED', 'OVERRIDDEN']
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
    if gate_number not in GATE_ORDER:
        raise ValueError(f"Invalid gate_number: {gate_number}. Must be 1-6")
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        now = datetime.datetime.now().isoformat()
        if metadata_json is not None:
            if isinstance(metadata_json, dict):
                meta_str = json.dumps(metadata_json)
            else:
                meta_str = str(metadata_json)
        else:
            meta_str = json.dumps(metadata or {})
        
        if status == 'IN_PROGRESS':
            cur.execute('''
                UPDATE product_gate_progress
                SET status = ?, started_at = COALESCE(started_at, ?), blocked_reason = ?, metadata_json = ?, completed_by = ?
                WHERE product_id = ? AND gate_number = ?
            ''', (status, now, blocked_reason, meta_str, completed_by, product_id, gate_number))
        elif status in ('PASS', 'FAIL', 'OVERRIDDEN'):
            cur.execute('''
                UPDATE product_gate_progress
                SET status = ?, completed_at = ?, blocked_reason = ?, metadata_json = ?, completed_by = ?
                WHERE product_id = ? AND gate_number = ?
            ''', (status, now, blocked_reason, meta_str, completed_by, product_id, gate_number))
        elif status == 'BLOCKED':
            cur.execute('''
                UPDATE product_gate_progress
                SET status = ?, blocked_reason = ?, metadata_json = ?, completed_by = ?
                WHERE product_id = ? AND gate_number = ?
            ''', (status, blocked_reason, meta_str, completed_by, product_id, gate_number))
        else:  # PENDING
            cur.execute('''
                UPDATE product_gate_progress
                SET status = ?, started_at = NULL, completed_at = NULL, blocked_reason = NULL, metadata_json = '{}', completed_by = NULL
                WHERE product_id = ? AND gate_number = ?
            ''', (status, product_id, gate_number))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[GATE UPDATE ERROR]: {e}")
        return False

def can_enter_gate(product_id: str, gate_number: int) -> tuple[bool, str]:
    """
    Check if a product can enter a specific gate.
    Returns (can_enter: bool, reason: str)
    """
    if gate_number == 1:
        return True, "Gate 1 always open"
    
    # Gates 3 and 4 both require Gate 2 PASS (not sequential)
    # Gate 3: Economics with estimated FOB
    # Gate 4: Manual FOB entry
    if gate_number in (3, 4):
        prev_gate = 2
        gates = get_gate_status(product_id)
        prev_gate_info = next((g for g in gates if g['gate_number'] == prev_gate), None)
        
        if not prev_gate_info:
            return False, f"Gate 2 not initialized"
        
        if prev_gate_info['status'] == 'PASS':
            return True, f"Gate 2 passed"
        elif prev_gate_info['status'] == 'OVERRIDDEN':
            return True, f"Gate 2 overridden by human"
        elif prev_gate_info['status'] == 'FAIL':
            return False, f"Gate 2 failed: {prev_gate_info.get('blocked_reason', 'No reason recorded')}"
        elif prev_gate_info['status'] == 'BLOCKED':
            return False, f"Gate 2 blocked: {prev_gate_info.get('blocked_reason', 'No reason recorded')}"
        else:
            return False, f"Gate 2 is {prev_gate_info['status']} (must be PASS or OVERRIDDEN)"
    
    # Gate 5 (War Room NIM Swarm) requires BOTH Gate 3 (Economics) AND Gate 4 (Sourcing/FOB) to PASS or be OVERRIDDEN
    if gate_number == 5:
        gates = get_gate_status(product_id)
        gate3_info = next((g for g in gates if g['gate_number'] == 3), None)
        gate4_info = next((g for g in gates if g['gate_number'] == 4), None)
        
        if not gate3_info or not gate4_info:
            return False, "Gate 3 and Gate 4 must be initialized before Gate 5"
            
        gate3_ok = gate3_info['status'] in ('PASS', 'OVERRIDDEN')
        gate4_ok = gate4_info['status'] in ('PASS', 'OVERRIDDEN')
        
        if not gate3_ok and not gate4_ok:
            return False, f"Both Gate 3 ({gate3_info['status']}) and Gate 4 ({gate4_info['status']}) must pass before Gate 5 War Room"
        elif not gate3_ok:
            return False, f"Gate 3 (Economics) is {gate3_info['status']}: {gate3_info.get('blocked_reason', 'Not passed')} (must pass before Gate 5)"
        elif not gate4_ok:
            return False, f"Gate 4 (Sourcing) is {gate4_info['status']}: {gate4_info.get('blocked_reason', 'Not passed')} (must pass before Gate 5)"
        return True, "Gates 3 & 4 passed — eligible for Gate 5 War Room Swarm"
    
    # Gate 6 requires previous gate 5 PASS or OVERRIDDEN
    prev_gate = gate_number - 1
    gates = get_gate_status(product_id)
    prev_gate_info = next((g for g in gates if g['gate_number'] == prev_gate), None)
    
    if not prev_gate_info:
        return False, f"Previous gate {prev_gate} not initialized"
    
    if prev_gate_info['status'] == 'PASS':
        return True, f"Gate {prev_gate} passed"
    elif prev_gate_info['status'] == 'OVERRIDDEN':
        return True, f"Gate {prev_gate} overridden by human"
    elif prev_gate_info['status'] == 'FAIL':
        return False, f"Gate {prev_gate} failed: {prev_gate_info.get('blocked_reason', 'No reason recorded')}"
    elif prev_gate_info['status'] == 'BLOCKED':
        return False, f"Gate {prev_gate} blocked: {prev_gate_info.get('blocked_reason', 'No reason recorded')}"
    else:
        return False, f"Gate {prev_gate} is {prev_gate_info['status']} (must be PASS or OVERRIDDEN)"

def get_current_gate(product_id: str) -> int:
    """Get the current active gate for a product (first non-PASS gate)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT gate_number, status FROM product_gate_progress WHERE product_id = ? ORDER BY gate_number ASC", (product_id,))
    gates = cur.fetchall()
    conn.close()
    
    if not gates:
        # Auto-initialize if missing
        init_product_gates(product_id)
        return 1
        
    for g in gates:
        if g["status"] not in ("PASS", "OVERRIDDEN"):
            return g["gate_number"]
    return 7  # All passed

def get_products_stuck_at_gate(gate_number: int) -> List[Dict[str, Any]]:
    """Get all products currently stuck at a specific gate."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT mp.product_id, mp.name, mp.category, mp.region, pgp.blocked_reason, pgp.status, pgp.metadata_json
        FROM master_products mp
        JOIN product_gate_progress pgp ON mp.product_id = pgp.product_id
        WHERE pgp.gate_number = ? AND pgp.status IN ('BLOCKED', 'IN_PROGRESS', 'PENDING')
        ORDER BY mp.updated_at DESC
    ''', (gate_number,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def record_negative_finding(
    product_id: str,
    origin_stage: str,
    target_stage: str,
    reason_code: str,
    human_readable_reason: str,
    evidence_summary: str = "",
    severity: str = "HIGH",
    recommended_action: str = "Branch to next candidate"
) -> int:
    """Records a formal backtracking NegativeFinding event."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO negative_findings (
            product_id, origin_stage, target_stage, reason_code,
            human_readable_reason, evidence_summary, severity, recommended_action
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        product_id, origin_stage, target_stage, reason_code,
        human_readable_reason, evidence_summary, severity, recommended_action
    ))
    fid = cur.lastrowid
    conn.commit()
    conn.close()
    return fid

def get_negative_findings(product_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches negative finding events for auditing and false-positive backtracking."""
    conn = get_connection()
    cur = conn.cursor()
    if product_id:
        cur.execute("SELECT * FROM negative_findings WHERE product_id = ? ORDER BY created_at DESC LIMIT ?", (product_id, limit))
    else:
        cur.execute("SELECT * FROM negative_findings ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def add_to_launchpad(
    product_id: str,
    product_name: str,
    target_moq: int = 300,
    target_fob: float = 0.0,
    target_launch_date: Optional[str] = None,
    confirmed_factory_name: Optional[str] = None
) -> int:
    """Adds a shortlisted product to the Sourcing & Launchpad workspace."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO launchpad_items (
            product_id, product_name, target_moq, target_fob,
            target_launch_date, confirmed_factory_name
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        product_id, product_name, target_moq, target_fob,
        target_launch_date, confirmed_factory_name
    ))
    lid = cur.lastrowid
    conn.commit()
    conn.close()

    # V8 Phase 1: Authoritative Launchpad Commitment Snapshot
    try:
        record_decision_snapshot(
            product_id=product_id,
            decision_type="LAUNCHPAD_COMMITMENT",
            override_predictions={
                "predicted_cogs": target_fob if (target_fob is not None and target_fob > 0) else None,
            }
        )
    except Exception as e:
        print(f"[DECISION LEDGER WARNING]: Launchpad snapshot capture for {product_id}: {e}")

    return lid

def get_launchpad_items() -> List[Dict[str, Any]]:
    """Fetches all items in the Sourcing & Launchpad pipeline."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM launchpad_items ORDER BY updated_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def update_launchpad_status(
    item_id: int,
    launch_status: str,
    sample_ordered: Optional[bool] = None,
    sample_approved: Optional[bool] = None,
    qc_passed: Optional[bool] = None,
    po_generated: Optional[bool] = None
) -> bool:
    """Updates the status and milestone checkboxes of a launchpad SKU."""
    conn = get_connection()
    cur = conn.cursor()
    updates = ["launch_status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params = [launch_status]
    if sample_ordered is not None:
        updates.append("sample_ordered = ?")
        params.append(1 if sample_ordered else 0)
    if sample_approved is not None:
        updates.append("sample_approved = ?")
        params.append(1 if sample_approved else 0)
    if qc_passed is not None:
        updates.append("compliance_checklist_passed = ?")
        params.append(1 if qc_passed else 0)
    if po_generated is not None:
        updates.append("purchase_order_generated = ?")
        params.append(1 if po_generated else 0)
    params.append(item_id)
    cur.execute(f"UPDATE launchpad_items SET {', '.join(updates)} WHERE item_id = ?", tuple(params))
    conn.commit()
    conn.close()
    return True


def get_launched_products() -> List[Dict[str, Any]]:
    """
    Retrieves all products that have entered launched status either in
    master_products or in launchpad_items.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT mp.product_id, mp.name, mp.category, mp.region, mp.status as master_status,
               mp.created_at as product_created_at,
               li.item_id as launchpad_item_id, li.launch_status, li.target_launch_date,
               li.purchase_order_generated, li.updated_at as launchpad_updated_at
        FROM master_products mp
        LEFT JOIN launchpad_items li ON mp.product_id = li.product_id
        WHERE UPPER(mp.status) IN ('LAUNCHED', 'LIVE', 'ACTIVE', 'POST_LAUNCH')
           OR UPPER(li.launch_status) IN ('LAUNCHED', 'LIVE', 'ACTIVE', 'SHIPPED', 'POST_LAUNCH')
           OR li.purchase_order_generated = 1
        ORDER BY COALESCE(li.target_launch_date, li.updated_at, mp.created_at) DESC
    ''')
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# ──────────────────────────────────────────────────────────────────────────────
# DEFECT CLUSTERS CRUD
# ──────────────────────────────────────────────────────────────────────────────

def record_defect_cluster(
    product_id: str,
    defect_category: str,
    defect_description: str,
    source_platform: str = "amazon",
    source_url: str = "",
    review_rating: float = 3.0,
    frequency_count: int = 1,
    severity: str = "MEDIUM",
    is_fixable: bool = True,
    v2_fix_description: str = "",
    v2_bom_delta_usd: float = 0.0
) -> int:
    """Records a clustered defect finding from review mining."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO defect_clusters (
            product_id, defect_category, defect_description, source_platform,
            source_url, review_rating, frequency_count, severity, is_fixable,
            v2_fix_description, v2_bom_delta_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        product_id, defect_category, defect_description, source_platform,
        source_url, review_rating, frequency_count, severity,
        1 if is_fixable else 0, v2_fix_description, v2_bom_delta_usd
    ))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid

def get_defect_clusters(product_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetches defect clusters, optionally filtered by product."""
    conn = get_connection()
    cur = conn.cursor()
    if product_id:
        cur.execute('''
            SELECT * FROM defect_clusters WHERE product_id = ?
            ORDER BY frequency_count DESC, severity DESC LIMIT ?
        ''', (product_id, limit))
    else:
        cur.execute('SELECT * FROM defect_clusters ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# ──────────────────────────────────────────────────────────────────────────────
# ECONOMICS ASSESSMENTS CRUD
# ──────────────────────────────────────────────────────────────────────────────

def record_economics_assessment(
    product_id: str,
    scenario: str,
    msrp: float = 0.0,
    fob_cost: float = 0.0,
    packaging_cost: float = 0.0,
    volumetric_freight: float = 0.0,
    customs_duty: float = 0.0,
    marketplace_commission: float = 0.0,
    fulfillment_fee: float = 0.0,
    payment_gateway_fee: float = 0.0,
    rto_reserve: float = 0.0,
    return_fraud_reserve: float = 0.0,
    ad_spend_reserve: float = 0.0,
    damage_reserve: float = 0.0,
    tooling_amortization: float = 0.0,
    net_gst_burden: float = 0.0,
    contribution_margin: float = 0.0,
    contribution_margin_pct: float = 0.0,
    lead_time_pass: bool = True,
    overall_pass: bool = False,
    composite_score: float = 0.0
) -> int:
    """Records a single scenario economics assessment (CONSERVATIVE/EXPECTED/UPSIDE)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO economics_assessments (
            product_id, scenario, msrp, fob_cost, packaging_cost,
            volumetric_freight, customs_duty, marketplace_commission,
            fulfillment_fee, payment_gateway_fee, rto_reserve,
            return_fraud_reserve, ad_spend_reserve, damage_reserve,
            tooling_amortization, net_gst_burden, contribution_margin,
            contribution_margin_pct, lead_time_pass, overall_pass, composite_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        product_id, scenario, msrp, fob_cost, packaging_cost,
        volumetric_freight, customs_duty, marketplace_commission,
        fulfillment_fee, payment_gateway_fee, rto_reserve,
        return_fraud_reserve, ad_spend_reserve, damage_reserve,
        tooling_amortization, net_gst_burden, contribution_margin,
        contribution_margin_pct, 1 if lead_time_pass else 0,
        1 if overall_pass else 0, composite_score
    ))
    aid = cur.lastrowid
    conn.commit()
    conn.close()
    return aid

def get_economics_assessments(product_id: str) -> List[Dict[str, Any]]:
    """Fetches all 3-scenario economics assessments for a product."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM economics_assessments WHERE product_id = ?
        ORDER BY CASE scenario
            WHEN 'CONSERVATIVE' THEN 1
            WHEN 'EXPECTED' THEN 2
            WHEN 'UPSIDE' THEN 3
        END
    ''', (product_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def persist_full_economics_assessment(product_id: str, assessment_result: dict) -> None:
    """Persists a complete EconomicsAssessment (all 3 scenarios) from the 15-factor engine."""
    scenarios = assessment_result.get("scenarios", {})
    for scenario_name, scenario_data in scenarios.items():
        record_economics_assessment(
            product_id=product_id,
            scenario=scenario_name.upper(),
            msrp=scenario_data.get("msrp", 0.0),
            fob_cost=scenario_data.get("fob_cost", 0.0),
            packaging_cost=scenario_data.get("packaging_cost", 0.0),
            volumetric_freight=scenario_data.get("volumetric_freight", 0.0),
            customs_duty=scenario_data.get("customs_duty", 0.0),
            marketplace_commission=scenario_data.get("marketplace_commission", 0.0),
            fulfillment_fee=scenario_data.get("fulfillment_fee", 0.0),
            payment_gateway_fee=scenario_data.get("payment_gateway_fee", 0.0),
            rto_reserve=scenario_data.get("rto_reserve", 0.0),
            return_fraud_reserve=scenario_data.get("return_fraud_reserve", 0.0),
            ad_spend_reserve=scenario_data.get("ad_spend_reserve", 0.0),
            damage_reserve=scenario_data.get("damage_reserve", 0.0),
            tooling_amortization=scenario_data.get("tooling_amortization", 0.0),
            net_gst_burden=scenario_data.get("net_gst_burden", 0.0),
            contribution_margin=scenario_data.get("contribution_margin", 0.0),
            contribution_margin_pct=scenario_data.get("contribution_margin_pct", 0.0),
            lead_time_pass=assessment_result.get("lead_time_pass", True),
            overall_pass=assessment_result.get("financially_viable", False),
            composite_score=assessment_result.get("composite_score", 0.0)
        )

# ── DISCOVERED SOURCES CRUD ──────────────────────────────────────────────────

def record_discovered_source(url: str, source_type: str = "trend", source_name: str = "",
                              description: str = "", region: str = "Global",
                              reliability_score: float = 70.0, discovered_by: str = "nim_discovery") -> Optional[int]:
    """Insert or update a discovered source URL. Returns source_id or None if duplicate."""
    conn = get_connection()
    cur = conn.cursor()
    domain = url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0]
    try:
        cur.execute('''
            INSERT INTO discovered_sources (url, domain, source_type, source_name, description, region, reliability_score, discovered_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url, source_type) DO UPDATE SET
                reliability_score = MAX(discovered_sources.reliability_score, excluded.reliability_score),
                description = CASE WHEN excluded.description != '' THEN excluded.description ELSE discovered_sources.description END,
                is_active = 1
        ''', (url, domain, source_type, source_name, description, region, reliability_score, discovered_by))
        conn.commit()
        sid = cur.lastrowid
        conn.close()
        return sid
    except Exception as e:
        conn.close()
        return None


def get_discovered_sources(source_type: str = None, region: str = None, active_only: bool = True) -> List[Dict]:
    """Get discovered sources, optionally filtered by type and region."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM discovered_sources WHERE 1=1"
    params = []
    if active_only:
        query += " AND is_active = 1"
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    if region:
        query += " AND (region = ? OR region = 'Global')"
        params.append(region)
    query += " ORDER BY reliability_score DESC, times_yielded_results DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_source_usage(source_id: int, yielded_results: bool = False):
    """Increment usage counter and optionally yield counter for a source."""
    conn = get_connection()
    cur = conn.cursor()
    if yielded_results:
        cur.execute("UPDATE discovered_sources SET times_used = times_used + 1, times_yielded_results = times_yielded_results + 1, last_crawled_at = CURRENT_TIMESTAMP WHERE source_id = ?", (source_id,))
    else:
        cur.execute("UPDATE discovered_sources SET times_used = times_used + 1, last_crawled_at = CURRENT_TIMESTAMP WHERE source_id = ?", (source_id,))
    conn.commit()
    conn.close()


# ── DYNAMIC NICHES CRUD ──────────────────────────────────────────────────────

def record_dynamic_niche(category: str, region: str = "India", search_limit: int = 3,
                          priority_score: float = 50.0, discovered_by: str = "nim_discovery",
                          source_signal: str = "") -> Optional[int]:
    """Insert a dynamic niche. Skips duplicates silently."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO dynamic_niches (category, region, search_limit, priority_score, discovered_by, source_signal)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(category, region) DO UPDATE SET
                priority_score = MAX(dynamic_niches.priority_score, excluded.priority_score),
                is_active = 1
        ''', (category, region, search_limit, priority_score, discovered_by, source_signal))
        conn.commit()
        nid = cur.lastrowid
        conn.close()
        return nid
    except Exception as e:
        conn.close()
        return None


def get_dynamic_niches(region: str = None, active_only: bool = True, limit: int = 200) -> List[Dict]:
    """Get dynamic niches, optionally filtered by region."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM dynamic_niches WHERE 1=1"
    params = []
    if active_only:
        query += " AND is_active = 1"
    if region:
        query += " AND region = ?"
        params.append(region)
    query += " ORDER BY priority_score DESC, products_found DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_niche_scan(niche_id: int, products_found: int = 0):
    """Update scan counter and products found for a niche."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""UPDATE dynamic_niches SET times_scanned = times_scanned + 1,
                   products_found = products_found + ?, last_scanned_at = CURRENT_TIMESTAMP
                   WHERE niche_id = ?""", (products_found, niche_id))
    conn.commit()
    conn.close()


# ── DYNAMIC SEED KEYWORDS CRUD ───────────────────────────────────────────────

def record_seed_keyword(keyword: str, region: str = "India", source_platform: str = "nim_generated",
                         parent_keyword: str = "", velocity_score: float = 50.0) -> Optional[int]:
    """Insert a dynamic seed keyword. Skips duplicates silently."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO dynamic_seed_keywords (keyword, region, source_platform, parent_keyword, velocity_score)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(keyword, region) DO UPDATE SET
                velocity_score = MAX(dynamic_seed_keywords.velocity_score, excluded.velocity_score),
                is_active = 1
        ''', (keyword, region, source_platform, parent_keyword, velocity_score))
        conn.commit()
        sid = cur.lastrowid
        conn.close()
        return sid
    except Exception as e:
        conn.close()
        return None


def get_seed_keywords(region: str = "India", active_only: bool = True, limit: int = 50) -> List[Dict]:
    """Get dynamic seed keywords for a region."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM dynamic_seed_keywords WHERE region = ?"
    params = [region]
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY velocity_score DESC, times_used ASC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_seed_usage(seed_id: int):
    """Increment usage counter for a seed keyword."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE dynamic_seed_keywords SET times_used = times_used + 1, last_used_at = CURRENT_TIMESTAMP WHERE seed_id = ?", (seed_id,))
    conn.commit()
    conn.close()


# ── UNIVERSAL MARKETPLACE SCRAPER CONFIG CRUD ───────────────────────────────────

def upsert_marketplace_config(config: dict) -> Optional[int]:
    """Insert or update a marketplace scraper configuration."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO marketplace_config (
                marketplace_name, region, base_url, search_url_pattern, search_param_name,
                pagination_type, pagination_param, max_pages, results_per_page,
                requires_js, anti_bot_level, login_required, login_url, cookie_domain,
                product_list_selector, product_title_selector, product_price_selector,
                product_rating_selector, product_review_count_selector, product_url_selector,
                product_image_selector, next_page_selector, custom_headers_json,
                extraction_prompt, is_active, priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(marketplace_name, region) DO UPDATE SET
                base_url=excluded.base_url,
                search_url_pattern=excluded.search_url_pattern,
                search_param_name=excluded.search_param_name,
                pagination_type=excluded.pagination_type,
                pagination_param=excluded.pagination_param,
                max_pages=excluded.max_pages,
                results_per_page=excluded.results_per_page,
                requires_js=excluded.requires_js,
                anti_bot_level=excluded.anti_bot_level,
                login_required=excluded.login_required,
                login_url=excluded.login_url,
                cookie_domain=excluded.cookie_domain,
                product_list_selector=excluded.product_list_selector,
                product_title_selector=excluded.product_title_selector,
                product_price_selector=excluded.product_price_selector,
                product_rating_selector=excluded.product_rating_selector,
                product_review_count_selector=excluded.product_review_count_selector,
                product_url_selector=excluded.product_url_selector,
                product_image_selector=excluded.product_image_selector,
                next_page_selector=excluded.next_page_selector,
                custom_headers_json=excluded.custom_headers_json,
                extraction_prompt=excluded.extraction_prompt,
                is_active=excluded.is_active,
                priority=excluded.priority,
                updated_at=CURRENT_TIMESTAMP
        ''', (
            config.get("marketplace_name"),
            config.get("region", "Global"),
            config.get("base_url"),
            config.get("search_url_pattern"),
            config.get("search_param_name", "q"),
            config.get("pagination_type", "page_param"),
            config.get("pagination_param", "page"),
            config.get("max_pages", 5),
            config.get("results_per_page", 20),
            config.get("requires_js", 1),
            config.get("anti_bot_level", "medium"),
            config.get("login_required", 0),
            config.get("login_url"),
            config.get("cookie_domain"),
            config.get("product_list_selector"),
            config.get("product_title_selector"),
            config.get("product_price_selector"),
            config.get("product_rating_selector"),
            config.get("product_review_count_selector"),
            config.get("product_url_selector"),
            config.get("product_image_selector"),
            config.get("next_page_selector"),
            config.get("custom_headers_json"),
            config.get("extraction_prompt"),
            config.get("is_active", 1),
            config.get("priority", 50)
        ))
        conn.commit()
        cid = cur.lastrowid
        conn.close()
        return cid
    except Exception as e:
        logger.warning(f"upsert_marketplace_config error: {e}")
        conn.close()
        return None


def get_marketplace_configs(region: str = None, active_only: bool = True) -> List[Dict]:
    """Get marketplace scraper configurations."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM marketplace_config WHERE 1=1"
    params = []
    if active_only:
        query += " AND is_active = 1"
    if region:
        query += " AND (region = ? OR region = 'Global')"
        params.append(region)
    query += " ORDER BY priority DESC, success_rate DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_marketplace_config(config_id: int) -> Optional[Dict]:
    """Get a single marketplace config by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM marketplace_config WHERE config_id = ?", (config_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_marketplace_config_stats(config_id: int, success: bool):
    """Update success rate and last scraped timestamp."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE marketplace_config 
        SET success_rate = (success_rate * 0.9) + (? * 100 * 0.1),
            last_scraped_at = CURRENT_TIMESTAMP
        WHERE config_id = ?
    """, (1.0 if success else 0.0, config_id))
    conn.commit()
    conn.close()


# ── SCRAPED LISTINGS CRUD ──────────────────────────────────────────────────────

def record_scraped_listing(config_id: int, listing: dict) -> Optional[int]:
    """Store a scraped product listing."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO scraped_listings (
                config_id, product_id, marketplace, region, search_query,
                title, price, currency, original_price, discount_pct,
                rating, review_count, availability, product_url, image_url,
                seller_name, seller_rating, raw_data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            config_id,
            listing.get("product_id"),
            listing.get("marketplace"),
            listing.get("region"),
            listing.get("search_query"),
            listing.get("title"),
            listing.get("price"),
            listing.get("currency", "INR"),
            listing.get("original_price"),
            listing.get("discount_pct"),
            listing.get("rating"),
            listing.get("review_count", 0),
            listing.get("availability"),
            listing.get("product_url"),
            listing.get("image_url"),
            listing.get("seller_name"),
            listing.get("seller_rating"),
            json.dumps(listing.get("raw_data", {}), default=str)
        ))
        conn.commit()
        lid = cur.lastrowid
        conn.close()
        return lid
    except Exception as e:
        logger.warning(f"record_scraped_listing error: {e}")
        conn.close()
        return None


def get_scraped_listings(search_query: str = None, marketplace: str = None, region: str = None, limit: int = 100) -> List[Dict]:
    """Get scraped listings with optional filters."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM scraped_listings WHERE 1=1"
    params = []
    if search_query:
        query += " AND search_query = ?"
        params.append(search_query)
    if marketplace:
        query += " AND marketplace = ?"
        params.append(marketplace)
    if region:
        query += " AND region = ?"
        params.append(region)
    query += " ORDER BY extracted_at DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── SEED INITIAL MARKETPLACE CONFIGS ──────────────────────────────────────────

def seed_initial_marketplace_configs():
    """Bootstrap marketplace configurations for major platforms."""
    configs = [
        {
            "marketplace_name": "Amazon India",
            "region": "India",
            "base_url": "https://www.amazon.in",
            "search_url_pattern": "https://www.amazon.in/s",
            "search_param_name": "k",
            "pagination_type": "page_param",
            "pagination_param": "page",
            "max_pages": 3,
            "results_per_page": 24,
            "requires_js": 1,
            "anti_bot_level": "high",
            "login_required": 0,
            "product_list_selector": "[data-component-type='s-search-result']",
            "product_title_selector": "h2 a.a-link-normal span",
            "product_price_selector": ".a-price-whole",
            "product_rating_selector": "[aria-label*='stars']",
            "product_review_count_selector": "[aria-label*='reviews']",
            "product_url_selector": "h2 a.a-link-normal",
            "product_image_selector": ".s-image",
            "next_page_selector": ".s-pagination-next",
            "extraction_prompt": "Extract product title, price (INR), rating, review count, product URL, image URL, and availability from Amazon India search results.",
            "priority": 100
        },
        {
            "marketplace_name": "Flipkart",
            "region": "India",
            "base_url": "https://www.flipkart.com",
            "search_url_pattern": "https://www.flipkart.com/search",
            "search_param_name": "q",
            "pagination_type": "page_param",
            "pagination_param": "page",
            "max_pages": 3,
            "results_per_page": 24,
            "requires_js": 1,
            "anti_bot_level": "high",
            "login_required": 0,
            "product_list_selector": "[data-id]",
            "product_title_selector": "a[title]",
            "product_price_selector": "._30jeq3",
            "product_rating_selector": "._3LWZlK",
            "product_review_count_selector": "span:contains('reviews')",
            "product_url_selector": "a[title]",
            "product_image_selector": "img[src*='flipkart']",
            "next_page_selector": "a[aria-label='Next']",
            "extraction_prompt": "Extract product title, price (INR), rating, review count, product URL, image URL, and availability from Flipkart search results.",
            "priority": 95
        },
        {
            "marketplace_name": "Meesho",
            "region": "India",
            "base_url": "https://www.meesho.com",
            "search_url_pattern": "https://www.meesho.com/search",
            "search_param_name": "q",
            "pagination_type": "scroll",
            "pagination_param": "",
            "max_pages": 5,
            "results_per_page": 40,
            "requires_js": 1,
            "anti_bot_level": "high",
            "login_required": 0,
            "product_list_selector": "[data-testid='product-card']",
            "product_title_selector": "h3, [data-testid='product-title']",
            "product_price_selector": "[data-testid='price'], .sc-eDvSVe",
            "product_rating_selector": "[data-testid='rating']",
            "product_review_count_selector": "[data-testid='review-count']",
            "product_url_selector": "a[href*='/product/']",
            "product_image_selector": "img[src*='meesho']",
            "next_page_selector": "",
            "extraction_prompt": "Extract product title, price (INR), rating, review count, product URL, image URL, and availability from Meesho search results. Handle infinite scroll.",
            "priority": 90
        },
        {
            "marketplace_name": "Myntra",
            "region": "India",
            "base_url": "https://www.myntra.com",
            "search_url_pattern": "https://www.myntra.com/gateway/v2/search",
            "search_param_name": "q",
            "pagination_type": "api_offset",
            "pagination_param": "offset",
            "max_pages": 3,
            "results_per_page": 50,
            "requires_js": 1,
            "anti_bot_level": "high",
            "login_required": 0,
            "product_list_selector": ".product-base",
            "product_title_selector": ".product-brand, .product-product",
            "product_price_selector": ".product-discountedPrice, .product-strike",
            "product_rating_selector": ".product-ratingsContainer",
            "product_review_count_selector": ".product-ratingsCount",
            "product_url_selector": "a[href*='/buy/']",
            "product_image_selector": "img[src*='myntra']",
            "next_page_selector": "",
            "extraction_prompt": "Extract product title, price (INR), rating, review count, product URL, image URL, and availability from Myntra search results. Note: Myntra uses API-based search.",
            "priority": 85
        },
        {
            "marketplace_name": "Amazon US",
            "region": "USA",
            "base_url": "https://www.amazon.com",
            "search_url_pattern": "https://www.amazon.com/s",
            "search_param_name": "k",
            "pagination_type": "page_param",
            "pagination_param": "page",
            "max_pages": 3,
            "results_per_page": 24,
            "requires_js": 1,
            "anti_bot_level": "high",
            "login_required": 0,
            "product_list_selector": "[data-component-type='s-search-result']",
            "product_title_selector": "h2 a.a-link-normal span",
            "product_price_selector": ".a-price-whole",
            "product_rating_selector": "[aria-label*='stars']",
            "product_review_count_selector": "[aria-label*='reviews']",
            "product_url_selector": "h2 a.a-link-normal",
            "product_image_selector": ".s-image",
            "next_page_selector": ".s-pagination-next",
            "extraction_prompt": "Extract product title, price (USD), rating, review count, product URL, image URL, and availability from Amazon US search results.",
            "priority": 100
        },
        {
            "marketplace_name": "Shopify Generic",
            "region": "Global",
            "base_url": "",
            "search_url_pattern": "{base_url}/search",
            "search_param_name": "q",
            "pagination_type": "page_param",
            "pagination_param": "page",
            "max_pages": 3,
            "results_per_page": 20,
            "requires_js": 1,
            "anti_bot_level": "low",
            "login_required": 0,
            "product_list_selector": ".product-item, .grid-view-item, [data-product-id]",
            "product_title_selector": ".product-title, .grid-view-item__title, h3",
            "product_price_selector": ".price-item--regular, .product-price",
            "product_rating_selector": ".rating, .spr-badge",
            "product_review_count_selector": ".review-count, .spr-summary-count",
            "product_url_selector": "a[href*='/products/']",
            "product_image_selector": "img[src*='product']",
            "next_page_selector": ".pagination__next, a[rel='next']",
            "extraction_prompt": "Extract product title, price, currency, rating, review count, product URL, image URL, and availability from Shopify store search results. Adapt selectors to the specific theme.",
            "priority": 70
        }
    ]
    
    for config in configs:
        upsert_marketplace_config(config)
    
    import logging
    logging.getLogger("aprs.db").info("Marketplace configs seeded/updated")


# ── AI SUPERVISOR: SCRAPER VALIDATIONS ──────────────────────────────────────────

def record_scraper_validation(validation_data: dict) -> Optional[int]:
    """Record AI validation result for scraped product."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO scraper_validations (
                product_id, marketplace, region, is_valid, confidence,
                issues, auto_soft_delete, rejection_reason, rejection_category,
                ai_notes, ai_suggested_fix, raw_product_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            validation_data.get("product_id", ""),
            validation_data.get("marketplace", ""),
            validation_data.get("region", ""),
            1 if validation_data.get("is_valid", True) else 0,
            validation_data.get("confidence", 50.0),
            validation_data.get("issues", "[]"),
            1 if validation_data.get("auto_soft_delete", False) else 0,
            validation_data.get("rejection_reason", ""),
            validation_data.get("rejection_category", ""),
            validation_data.get("ai_notes", ""),
            validation_data.get("ai_suggested_fix", ""),
            validation_data.get("raw_product_data", "")
        ))
        conn.commit()
        vid = cur.lastrowid
        conn.close()
        return vid
    except Exception as e:
        conn.close()
        logger.warning(f"record_scraper_validation error: {e}")
        return None


def get_scraper_validations(product_id: str = None, marketplace: str = None, region: str = None, limit: int = 100) -> List[Dict]:
    """Get scraper validations with optional filters."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM scraper_validations WHERE 1=1"
    params = []
    if product_id:
        query += " AND product_id = ?"
        params.append(product_id)
    if marketplace:
        query += " AND marketplace = ?"
        params.append(marketplace)
    if region:
        query += " AND region = ?"
        params.append(region)
    query += " ORDER BY validated_at DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── AI SUPERVISOR LOGS ──────────────────────────────────────────────────────────

def record_ai_supervisor_log(log_data: dict) -> Optional[int]:
    """Record AI Supervisor activity log."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO ai_supervisor_logs (event_type, details, active_tasks, total_validations)
            VALUES (?, ?, ?, ?)
        ''', (
            log_data.get("event_type", ""),
            log_data.get("details", ""),
            log_data.get("active_tasks", 0),
            log_data.get("total_validations", 0)
        ))
        conn.commit()
        lid = cur.lastrowid
        conn.close()
        return lid
    except Exception as e:
        conn.close()
        return None


def get_ai_supervisor_logs(limit: int = 100) -> List[Dict]:
    """Get AI Supervisor activity logs."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ai_supervisor_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── AI TASK IMPROVEMENTS ────────────────────────────────────────────────────────

def record_ai_task_improvement(improvement_data: dict) -> Optional[int]:
    """Record AI-suggested task improvement."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO ai_task_improvements (
                task_id, task_type, marketplace, region, improvement_type,
                description, priority, target, triggered_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            improvement_data.get("task_id", ""),
            improvement_data.get("task_type", ""),
            improvement_data.get("marketplace", ""),
            improvement_data.get("region", ""),
            improvement_data.get("improvement_type", ""),
            improvement_data.get("description", ""),
            improvement_data.get("priority", "medium"),
            improvement_data.get("target", ""),
            improvement_data.get("triggered_by", "")
        ))
        conn.commit()
        iid = cur.lastrowid
        conn.close()
        return iid
    except Exception as e:
        conn.close()
        return None


def get_ai_task_improvements(limit: int = 100) -> List[Dict]:
    """Get AI task improvements history."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ai_task_improvements ORDER BY applied_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── SUBSCRIPTION TABLES REMOVED (Phase 1) ──────────────────────────────────
# Billing, Razorpay, subscription_plans, subscriptions, usage_periods,
# payments, and webhook_events tables have been removed.
# The users table and all auth functions below are PRESERVED.
# ─────────────────────────────────────────────────────────────────────────────

# ── USER MANAGEMENT ────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str = None, full_name: str = None, 
                provider: str = "email", provider_id: str = None) -> Optional[str]:
    """Create a new user. Returns user_id on success."""
    import uuid
    user_id = str(uuid.uuid4())
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO users (user_id, email, password_hash, full_name, provider, provider_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, email, password_hash, full_name, provider, provider_id))
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        # Email already exists
        conn.close()
        return None
    except Exception as e:
        print(f"[DB ERROR create_user]: {e}")
        conn.close()
        raise


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ? AND is_active = 1", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(user_id: str, **kwargs) -> bool:
    """Update user fields."""
    if not kwargs:
        return True
    try:
        conn = get_connection()
        cur = conn.cursor()
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(kwargs.values()) + [user_id]
        cur.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        conn.commit()
        conn.close()
        return cur.rowcount > 0
    except Exception as e:
        print(f"[DB ERROR update_user]: {e}")
        conn.close()
        return False


# -------------------------------------------------------------
# APRS V7 INTELLIGENCE ENGINE DATABASE HELPERS
# -------------------------------------------------------------

def save_product_intelligence(
    product_id: str,
    opportunity_score: float = 0.0,
    kill_status: str = "INSUFFICIENT_EVIDENCE",
    kill_reasons: Optional[List[str]] = None,
    kill_evidence: Optional[Dict[str, Any]] = None,
    scorecard: Optional[Dict[str, Any]] = None,
    signals: Optional[Dict[str, Any]] = None,
    explanations: Optional[Dict[str, Any]] = None,
    counterfactual: Optional[Dict[str, Any]] = None,
    gaps: Optional[Dict[str, Any]] = None,
    pain_map: Optional[Dict[str, Any]] = None,
    trend_analysis: Optional[Dict[str, Any]] = None,
    freshness_status: str = "FRESH",
    confidence_score: float = 0.0
) -> bool:
    """Inserts or updates a comprehensive product intelligence dossier."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO product_intelligence (
                product_id, opportunity_score, kill_status,
                kill_reasons_json, kill_evidence_json, scorecard_json,
                signals_json, explanations_json, counterfactual_json,
                gaps_json, pain_map_json, trend_analysis_json,
                freshness_status, confidence_score, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(product_id) DO UPDATE SET
                opportunity_score = excluded.opportunity_score,
                kill_status = excluded.kill_status,
                kill_reasons_json = excluded.kill_reasons_json,
                kill_evidence_json = excluded.kill_evidence_json,
                scorecard_json = excluded.scorecard_json,
                signals_json = excluded.signals_json,
                explanations_json = excluded.explanations_json,
                counterfactual_json = excluded.counterfactual_json,
                gaps_json = excluded.gaps_json,
                pain_map_json = excluded.pain_map_json,
                trend_analysis_json = excluded.trend_analysis_json,
                freshness_status = excluded.freshness_status,
                confidence_score = excluded.confidence_score,
                updated_at = CURRENT_TIMESTAMP
        """, (
            product_id,
            opportunity_score,
            kill_status,
            json.dumps(kill_reasons or []),
            json.dumps(kill_evidence or {}),
            json.dumps(scorecard or {}),
            json.dumps(signals or {}),
            json.dumps(explanations or {}),
            json.dumps(counterfactual or {}),
            json.dumps(gaps or {}),
            json.dumps(pain_map or {}),
            json.dumps(trend_analysis or {}),
            freshness_status,
            confidence_score
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR save_product_intelligence]: {e}")
        conn.close()
        return False


def get_product_intelligence(product_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves intelligence profile for a specific product with parsed JSON fields."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM product_intelligence WHERE product_id = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for field in [
        "kill_reasons_json", "kill_evidence_json", "scorecard_json",
        "signals_json", "explanations_json", "counterfactual_json",
        "gaps_json", "pain_map_json", "trend_analysis_json"
    ]:
        try:
            d[field.replace("_json", "")] = json.loads(d.get(field) or "{}")
        except Exception:
            d[field.replace("_json", "")] = {}
    return d


def get_all_product_intelligence(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieves all product intelligence records joined with master product metadata."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pi.*, mp.name, mp.category, mp.region, mp.planned_msrp, mp.status as gate_status,
               mp.overall_score as mp_overall_score, mp.is_shortlisted
        FROM product_intelligence pi
        LEFT JOIN master_products mp ON pi.product_id = mp.product_id
        ORDER BY pi.opportunity_score DESC, pi.updated_at DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        for field in ["scorecard_json", "kill_reasons_json", "kill_evidence_json", "explanations_json"]:
            try:
                d[field.replace("_json", "")] = json.loads(d.get(field) or "{}")
            except Exception:
                d[field.replace("_json", "")] = {}
        result.append(d)
    return result


def record_intelligence_evidence(
    product_id: str,
    signal_type: str,
    conclusion: str,
    evidence_status: str = "VERIFIED",
    evidence_details: Optional[List[str]] = None,
    confidence: float = 0.0,
    source: str = "",
    source_timestamp: Optional[str] = None
) -> int:
    """Appends an evidence trail record for an opportunity signal conclusion."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO intelligence_evidence (
                product_id, signal_type, conclusion, evidence_status,
                evidence_details_json, confidence, source, source_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
        """, (
            product_id,
            signal_type,
            conclusion,
            evidence_status,
            json.dumps(evidence_details or []),
            confidence,
            source,
            source_timestamp
        ))
        evidence_id = cur.lastrowid
        conn.commit()
        conn.close()
        return evidence_id
    except Exception as e:
        print(f"[DB ERROR record_intelligence_evidence]: {e}")
        conn.close()
        return -1


def get_intelligence_evidence(product_id: str, signal_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all evidence records for a product, optionally filtered by signal type."""
    conn = get_connection()
    cur = conn.cursor()
    if signal_type:
        cur.execute("""
            SELECT * FROM intelligence_evidence
            WHERE product_id = ? AND signal_type = ?
            ORDER BY created_at DESC
        """, (product_id, signal_type))
    else:
        cur.execute("""
            SELECT * FROM intelligence_evidence
            WHERE product_id = ?
            ORDER BY created_at DESC
        """, (product_id,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["evidence_details"] = json.loads(d.get("evidence_details_json") or "[]")
        except Exception:
            d["evidence_details"] = []
        result.append(d)
    return result


def create_opportunity_alert(
    product_id: Optional[str],
    alert_type: str,
    title: str,
    what_happened: str,
    why_it_matters: str,
    evidence_summary: str = "",
    recommended_action: str = "",
    severity: str = "MEDIUM"
) -> int:
    """Creates a new actionable opportunity alert in the Intelligence Alert Center."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Deduplication: return existing active alert ID if not dismissed
        if product_id:
            cur.execute("""
                SELECT alert_id FROM opportunity_alerts
                WHERE product_id = ? AND alert_type = ? AND is_dismissed = 0
                ORDER BY created_at DESC LIMIT 1
            """, (product_id, alert_type))
            existing_active = cur.fetchone()
            if existing_active:
                conn.close()
                return existing_active[0]

            # Dismissed alert deduplication: do not resurrect dismissed alert if both what_happened and evidence_summary are identical
            cur.execute("""
                SELECT alert_id FROM opportunity_alerts
                WHERE product_id = ? AND alert_type = ? AND what_happened = ? AND evidence_summary = ? AND is_dismissed = 1
                ORDER BY created_at DESC LIMIT 1
            """, (product_id, alert_type, what_happened, evidence_summary))
            existing_dismissed = cur.fetchone()
            if existing_dismissed:
                conn.close()
                return existing_dismissed[0]

        cur.execute("""
            INSERT INTO opportunity_alerts (
                product_id, alert_type, severity, title,
                what_happened, why_it_matters, evidence_summary,
                recommended_action
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id, alert_type, severity, title,
            what_happened, why_it_matters, evidence_summary,
            recommended_action
        ))
        alert_id = cur.lastrowid
        conn.commit()
        conn.close()
        return alert_id
    except Exception as e:
        print(f"[DB ERROR create_opportunity_alert]: {e}")
        conn.close()
        return -1


def get_active_alerts(product_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves non-dismissed alerts with product names."""
    conn = get_connection()
    cur = conn.cursor()
    if product_id:
        cur.execute("""
            SELECT a.*, mp.name as product_name
            FROM opportunity_alerts a
            LEFT JOIN master_products mp ON a.product_id = mp.product_id
            WHERE a.product_id = ? AND a.is_dismissed = 0
            ORDER BY a.created_at DESC LIMIT ?
        """, (product_id, limit))
    else:
        cur.execute("""
            SELECT a.*, mp.name as product_name
            FROM opportunity_alerts a
            LEFT JOIN master_products mp ON a.product_id = mp.product_id
            WHERE a.is_dismissed = 0
            ORDER BY a.created_at DESC LIMIT ?
        """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dismiss_alert(alert_id: int) -> bool:
    """Marks an alert as dismissed."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE opportunity_alerts SET is_dismissed = 1 WHERE alert_id = ?", (alert_id,))
        conn.commit()
        conn.close()
        return cur.rowcount > 0
    except Exception as e:
        print(f"[DB ERROR dismiss_alert]: {e}")
        conn.close()
        return False


def add_to_watchlist(
    product_id: str,
    priority_status: str = "WATCH",
    notes: str = "",
    monitored_metrics: Optional[Dict[str, Any]] = None
) -> bool:
    """Adds or updates a product in the local-first watchlist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO product_watchlist (product_id, priority_status, notes, monitored_metrics_json, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(product_id) DO UPDATE SET
                priority_status = excluded.priority_status,
                notes = excluded.notes,
                monitored_metrics_json = excluded.monitored_metrics_json,
                updated_at = CURRENT_TIMESTAMP
        """, (product_id, priority_status, notes, json.dumps(monitored_metrics or {})))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR add_to_watchlist]: {e}")
        conn.close()
        return False


def remove_from_watchlist(product_id: str) -> bool:
    """Removes a product from the watchlist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM product_watchlist WHERE product_id = ?", (product_id,))
        conn.commit()
        conn.close()
        return cur.rowcount > 0
    except Exception as e:
        print(f"[DB ERROR remove_from_watchlist]: {e}")
        conn.close()
        return False


def get_watchlist() -> List[Dict[str, Any]]:
    """Retrieves all watched products with real-time metadata."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.*, mp.name, mp.category, mp.region, mp.planned_msrp, mp.status, mp.overall_score
        FROM product_watchlist w
        LEFT JOIN master_products mp ON w.product_id = mp.product_id
        ORDER BY w.updated_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["monitored_metrics"] = json.loads(d.get("monitored_metrics_json") or "{}")
        except Exception:
            d["monitored_metrics"] = {}
        result.append(d)
    return result


def is_in_watchlist(product_id: str) -> bool:
    """Checks if a product is in the watchlist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM product_watchlist WHERE product_id = ?", (product_id,))
    res = cur.fetchone() is not None
    conn.close()
    return res


def record_timeline_event(
    product_id: str,
    event_type: str,
    event_title: str,
    event_description: str,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """Appends an event to the historical intelligence audit timeline."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO intelligence_timeline (
                product_id, event_type, event_title, event_description, metadata_json
            ) VALUES (?, ?, ?, ?, ?)
        """, (product_id, event_type, event_title, event_description, json.dumps(metadata or {})))
        event_id = cur.lastrowid
        conn.commit()
        conn.close()
        return event_id
    except Exception as e:
        print(f"[DB ERROR record_timeline_event]: {e}")
        conn.close()
        return -1


def get_product_timeline(product_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves chronological timeline for a product."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM intelligence_timeline
        WHERE product_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (product_id, limit))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            d["metadata"] = {}
        result.append(d)
    return result


def record_data_conflict(
    product_id: str,
    field_name: str,
    source_a: str,
    value_a: str,
    source_b: str,
    value_b: str,
    severity: str = "MEDIUM",
    explanation: str = ""
) -> int:
    """Records a data conflict when two sources disagree."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Deduplication: return existing unresolved conflict ID if present
        cur.execute("""
            SELECT conflict_id FROM data_conflicts
            WHERE product_id = ? AND field_name = ? AND source_a = ? AND source_b = ? AND resolution_status = 'UNRESOLVED'
            LIMIT 1
        """, (product_id, field_name, source_a, source_b))
        existing = cur.fetchone()
        if existing:
            conn.close()
            return existing[0]

        cur.execute("""
            INSERT INTO data_conflicts (
                product_id, field_name, source_a, value_a,
                source_b, value_b, severity, explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (product_id, field_name, source_a, value_a, source_b, value_b, severity, explanation))
        conflict_id = cur.lastrowid
        conn.commit()
        conn.close()
        return conflict_id
    except Exception as e:
        print(f"[DB ERROR record_data_conflict]: {e}")
        conn.close()
        return -1


def get_data_conflicts(product_id: Optional[str] = None, unresolved_only: bool = True) -> List[Dict[str, Any]]:
    """Retrieves recorded data conflicts."""
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT dc.*, mp.name as product_name FROM data_conflicts dc LEFT JOIN master_products mp ON dc.product_id = mp.product_id WHERE 1=1"
    params = []
    if product_id:
        query += " AND dc.product_id = ?"
        params.append(product_id)
    if unresolved_only:
        query += " AND dc.resolution_status = 'UNRESOLVED'"
    query += " ORDER BY dc.created_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_data_conflict(conflict_id: int, resolution_status: str = "RESOLVED", explanation: str = "") -> bool:
    """Resolves or explains a data conflict."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE data_conflicts
            SET resolution_status = ?, explanation = ?
            WHERE conflict_id = ?
        """, (resolution_status, explanation, conflict_id))
        conn.commit()
        conn.close()
        return cur.rowcount > 0
    except Exception as e:
        print(f"[DB ERROR resolve_data_conflict]: {e}")
        conn.close()
        return False


def start_research_run(research_run_id: Optional[str] = None) -> str:
    """Starts a new autonomous research cycle and logs research_run_id."""
    import uuid
    run_id = research_run_id or f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO research_runs (research_run_id, run_status, started_at)
            VALUES (?, 'RUNNING', CURRENT_TIMESTAMP)
        """, (run_id,))
        conn.commit()
    except Exception as e:
        print(f"[DB ERROR start_research_run]: {e}")
    finally:
        conn.close()
    return run_id


def complete_research_run(
    research_run_id: str,
    products_processed: int = 0,
    sources_consulted_count: int = 0,
    signals_generated_count: int = 0,
    alerts_generated_count: int = 0,
    gate_transitions_count: int = 0,
    errors: Optional[List[str]] = None,
    summary: Optional[Dict[str, Any]] = None,
    status: str = "COMPLETED"
) -> bool:
    """Completes an autonomous research cycle with execution metrics."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE research_runs SET
                run_status = ?,
                ended_at = CURRENT_TIMESTAMP,
                products_processed = ?,
                sources_consulted_count = ?,
                signals_generated_count = ?,
                alerts_generated_count = ?,
                gate_transitions_count = ?,
                errors_json = ?,
                summary_json = ?
            WHERE research_run_id = ?
        """, (
            status,
            products_processed,
            sources_consulted_count,
            signals_generated_count,
            alerts_generated_count,
            gate_transitions_count,
            json.dumps(errors or []),
            json.dumps(summary or {}),
            research_run_id
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR complete_research_run]: {e}")
        conn.close()
        return False


def get_research_runs(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves recent autonomous research runs."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM research_runs ORDER BY started_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["errors"] = json.loads(d.get("errors_json") or "[]")
            d["summary"] = json.loads(d.get("summary_json") or "{}")
        except Exception:
            d["errors"] = []
            d["summary"] = {}
        result.append(d)
    return result


def update_source_health(
    source_name: str,
    data_type: str,
    success: bool = True,
    response_time_ms: float = 0.0,
    details: Optional[Dict[str, Any]] = None
) -> bool:
    """Tracks source reliability telemetry from actual runtime observations."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT failure_count FROM source_health WHERE source_name = ?", (source_name,))
        row = cur.fetchone()
        if row:
            fail_count = row[0]
            if success:
                new_status = "HEALTHY" if fail_count < 3 else "DEGRADED"
                cur.execute("""
                    UPDATE source_health SET
                        data_type = ?,
                        last_successful_fetch = CURRENT_TIMESTAMP,
                        freshness_status = ?,
                        response_time_ms = ?,
                        details_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_name = ?
                """, (data_type, new_status, response_time_ms, json.dumps(details or {}), source_name))
            else:
                fail_count += 1
                new_status = "FAILING" if fail_count >= 5 else "DEGRADED"
                cur.execute("""
                    UPDATE source_health SET
                        failure_count = ?,
                        freshness_status = ?,
                        response_time_ms = ?,
                        details_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_name = ?
                """, (fail_count, new_status, response_time_ms, json.dumps(details or {}), source_name))
        else:
            status = "HEALTHY" if success else "DEGRADED"
            cur.execute("""
                INSERT INTO source_health (
                    source_name, data_type, last_successful_fetch, failure_count,
                    freshness_status, response_time_ms, details_json
                ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
            """, (source_name, data_type, 0 if success else 1, status, response_time_ms, json.dumps(details or {})))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB ERROR update_source_health]: {e}")
        conn.close()
        return False


def get_source_health_summary() -> List[Dict[str, Any]]:
    """Retrieves source reliability overview."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM source_health ORDER BY updated_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# -------------------------------------------------------------
# APRS V8 PHASE 1: DECISION LEDGER & OUTCOME DATA FOUNDATION
# -------------------------------------------------------------

def record_decision_snapshot(
    product_id: str,
    decision_type: str = "LAUNCHPAD_COMMITMENT",
    research_run_id: Optional[str] = None,
    policy_version: str = "V7.2",
    model_version: str = "V7.2_HEURISTIC",
    override_predictions: Optional[Dict[str, Any]] = None,
    decision_timestamp: Optional[str] = None
) -> int:
    """
    Freezes what APRS believed at the moment a meaningful launch/approval decision was made.
    Behaves as an append-only historical snapshot.
    Deterministic deduplication: If an identical snapshot exists for the same product and
    decision_type, returns the existing decision_id.
    """
    conn = get_connection()
    cur = conn.cursor()

    # 1. Fetch product from master_products
    cur.execute("SELECT * FROM master_products WHERE product_id = ?", (product_id,))
    prod_row = cur.fetchone()
    if not prod_row:
        conn.close()
        raise ValueError(f"Product '{product_id}' does not exist in master_products.")
    prod = dict(prod_row)

    # 2. Fetch product_intelligence (if available)
    cur.execute("SELECT * FROM product_intelligence WHERE product_id = ?", (product_id,))
    intel_row = cur.fetchone()
    intel = dict(intel_row) if intel_row else None

    # 3. Fetch economics assessment (EXPECTED or latest scenario)
    cur.execute(
        "SELECT * FROM economics_assessments WHERE product_id = ? ORDER BY CASE scenario WHEN 'EXPECTED' THEN 1 WHEN 'CONSERVATIVE' THEN 2 ELSE 3 END LIMIT 1",
        (product_id,)
    )
    econ_row = cur.fetchone()
    econ = dict(econ_row) if econ_row else None

    # 4. Extract frozen baseline metrics
    frozen_score = float(intel["opportunity_score"]) if (intel and intel.get("opportunity_score") is not None) else float(prod.get("overall_score", 0.0))
    frozen_confidence = float(intel["confidence_score"]) if (intel and intel.get("confidence_score") is not None) else 0.0
    frozen_kill_status = str(intel["kill_status"]) if (intel and intel.get("kill_status")) else str(prod.get("status", "PENDING"))

    # Nullable prediction fields - unknown is strictly None
    predicted_daily_units = int(prod["estimated_daily_units"]) if prod.get("estimated_daily_units") is not None else None
    predicted_selling_price = float(prod["planned_msrp"]) if (prod.get("planned_msrp") is not None and float(prod["planned_msrp"]) > 0) else None

    predicted_cogs = None
    if prod.get("landed_cogs") is not None and float(prod["landed_cogs"]) > 0:
        predicted_cogs = float(prod["landed_cogs"])
    elif econ and econ.get("fob_cost") is not None and float(econ["fob_cost"]) > 0:
        predicted_cogs = float(econ["fob_cost"])

    predicted_cm_pct = None
    if econ and econ.get("contribution_margin_pct") is not None:
        predicted_cm_pct = float(econ["contribution_margin_pct"])
    elif prod.get("gross_margin_pct") is not None and float(prod["gross_margin_pct"]) > 0:
        predicted_cm_pct = float(prod["gross_margin_pct"])

    predicted_rto_pct = None
    if econ and econ.get("rto_reserve") is not None and predicted_selling_price and predicted_selling_price > 0:
        predicted_rto_pct = round((float(econ["rto_reserve"]) / predicted_selling_price) * 100.0, 2)

    predicted_cac = float(prod["estimated_cac"]) if (prod.get("estimated_cac") is not None and float(prod["estimated_cac"]) > 0) else None

    # Apply explicit overrides if provided
    overrides = override_predictions or {}
    if "predicted_daily_units" in overrides:
        predicted_daily_units = overrides["predicted_daily_units"]
    if "predicted_selling_price" in overrides:
        predicted_selling_price = overrides["predicted_selling_price"]
    if "predicted_cogs" in overrides:
        predicted_cogs = overrides["predicted_cogs"]
    if "predicted_cm_pct" in overrides:
        predicted_cm_pct = overrides["predicted_cm_pct"]
    if "predicted_rto_pct" in overrides:
        predicted_rto_pct = overrides["predicted_rto_pct"]
    if "predicted_cac" in overrides:
        predicted_cac = overrides["predicted_cac"]
    if "frozen_score" in overrides:
        frozen_score = float(overrides["frozen_score"])
    if "frozen_confidence" in overrides:
        frozen_confidence = float(overrides["frozen_confidence"])
    if "frozen_kill_status" in overrides:
        frozen_kill_status = str(overrides["frozen_kill_status"])

    # Construct complete frozen snapshot payload
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snapshot_payload = {
        "product_id": product_id,
        "decision_type": decision_type,
        "captured_at": now_iso,
        "policy_version": policy_version,
        "model_version": model_version,
        "metrics": {
            "score": frozen_score,
            "confidence": frozen_confidence,
            "kill_status": frozen_kill_status,
            "daily_units": predicted_daily_units,
            "selling_price": predicted_selling_price,
            "cogs": predicted_cogs,
            "cm_pct": predicted_cm_pct,
            "rto_pct": predicted_rto_pct,
            "cac": predicted_cac,
        },
        "product_snapshot": {
            k: v for k, v in prod.items() 
            if k not in ("created_at", "updated_at")
        },
        "intelligence_snapshot": {
            k: v for k, v in intel.items() 
            if k not in ("created_at", "updated_at")
        } if intel else None,
        "economics_snapshot": {
            k: v for k, v in econ.items() 
            if k not in ("created_at",)
        } if econ else None,
    }

    payload_json = json.dumps(snapshot_payload, sort_keys=True)

    # 5. Deterministic duplicate check
    cur.execute('''
        SELECT decision_id, frozen_score, frozen_confidence, frozen_kill_status,
               predicted_daily_units, predicted_selling_price, predicted_cogs,
               predicted_cm_pct, predicted_rto_pct, predicted_cac,
               policy_version, model_version
        FROM decision_ledger
        WHERE product_id = ? AND decision_type = ?
        ORDER BY decision_id DESC LIMIT 1
    ''', (product_id, decision_type))
    existing = cur.fetchone()
    if existing:
        if (
            abs(float(existing[1]) - float(frozen_score)) < 1e-4 and
            abs(float(existing[2]) - float(frozen_confidence)) < 1e-4 and
            str(existing[3]) == str(frozen_kill_status) and
            existing[4] == predicted_daily_units and
            existing[5] == predicted_selling_price and
            existing[6] == predicted_cogs and
            existing[7] == predicted_cm_pct and
            existing[8] == predicted_rto_pct and
            existing[9] == predicted_cac and
            str(existing[10]) == str(policy_version) and
            str(existing[11]) == str(model_version)
        ):
            conn.close()
            return existing[0]

    # 6. Insert new immutable snapshot
    if decision_timestamp:
        cur.execute('''
            INSERT INTO decision_ledger (
                product_id, research_run_id, decision_type, frozen_score,
                frozen_confidence, frozen_kill_status, predicted_daily_units,
                predicted_selling_price, predicted_cogs, predicted_cm_pct,
                predicted_rto_pct, predicted_cac, policy_version, model_version,
                snapshot_payload_json, decision_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product_id, research_run_id, decision_type, frozen_score,
            frozen_confidence, frozen_kill_status, predicted_daily_units,
            predicted_selling_price, predicted_cogs, predicted_cm_pct,
            predicted_rto_pct, predicted_cac, policy_version, model_version,
            payload_json, decision_timestamp
        ))
    else:
        cur.execute('''
            INSERT INTO decision_ledger (
                product_id, research_run_id, decision_type, frozen_score,
                frozen_confidence, frozen_kill_status, predicted_daily_units,
                predicted_selling_price, predicted_cogs, predicted_cm_pct,
                predicted_rto_pct, predicted_cac, policy_version, model_version,
                snapshot_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product_id, research_run_id, decision_type, frozen_score,
            frozen_confidence, frozen_kill_status, predicted_daily_units,
            predicted_selling_price, predicted_cogs, predicted_cm_pct,
            predicted_rto_pct, predicted_cac, policy_version, model_version,
            payload_json
        ))
    decision_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Log timeline event
    try:
        record_timeline_event(
            product_id=product_id,
            event_type="DECISION_FROZEN",
            event_title=f"Decision Snapshot Recorded: {decision_type}",
            event_description=f"Frozen Score: {frozen_score:.1f}, Confidence: {frozen_confidence:.1f}%, Status: {frozen_kill_status}",
            metadata={"decision_id": decision_id, "decision_type": decision_type, "policy_version": policy_version}
        )
    except Exception:
        pass

    return decision_id


def get_decision_snapshot(decision_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single immutable decision snapshot by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM decision_ledger WHERE decision_id = ?", (decision_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    try:
        res["snapshot_payload"] = json.loads(res.get("snapshot_payload_json", "{}"))
    except Exception:
        res["snapshot_payload"] = {}
    return res


def get_decision_snapshots_for_product(product_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves all historical decision snapshots for a product in reverse chronological order."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM decision_ledger
        WHERE product_id = ?
        ORDER BY decision_timestamp DESC, decision_id DESC
        LIMIT ?
    ''', (product_id, limit))
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["snapshot_payload"] = json.loads(d.get("snapshot_payload_json", "{}"))
        except Exception:
            d["snapshot_payload"] = {}
        results.append(d)
    return results


def get_latest_decision_snapshot(product_id: str, decision_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves the most recent decision snapshot for a product."""
    conn = get_connection()
    cur = conn.cursor()
    if decision_type:
        cur.execute('''
            SELECT * FROM decision_ledger
            WHERE product_id = ? AND decision_type = ?
            ORDER BY decision_timestamp DESC, decision_id DESC
            LIMIT 1
        ''', (product_id, decision_type))
    else:
        cur.execute('''
            SELECT * FROM decision_ledger
            WHERE product_id = ?
            ORDER BY decision_timestamp DESC, decision_id DESC
            LIMIT 1
        ''', (product_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    res = dict(row)
    try:
        res["snapshot_payload"] = json.loads(res.get("snapshot_payload_json", "{}"))
    except Exception:
        res["snapshot_payload"] = {}
    return res


def validate_outcome_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates observed product outcome data against strict business integrity rules.
    Detects impossible or corrupted data states:
    - Period end before start or invalid date strings
    - Invalid period types
    - Negative units, revenue, returns, RTO, costs, CAC, ad spend
    - Returns or RTO exceeding units sold
    - Rates exceeding 100%
    Preserves NULLs (UNKNOWN != ZERO).
    """
    if not isinstance(data, dict):
        raise ValueError("Outcome data must be a dictionary.")

    product_id = data.get("product_id")
    if not product_id or not isinstance(product_id, str):
        raise ValueError("Missing or invalid 'product_id'. Must be a non-empty string.")

    period_start = data.get("period_start")
    period_end = data.get("period_end")
    if not period_start or not period_end:
        raise ValueError("Both 'period_start' and 'period_end' are required.")

    try:
        d_start = datetime.date.fromisoformat(str(period_start))
        d_end = datetime.date.fromisoformat(str(period_end))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid period date format (expected YYYY-MM-DD): {e}")

    if d_end < d_start:
        raise ValueError(f"period_end ({period_end}) cannot be before period_start ({period_start}).")

    valid_periods = {"DAY_30", "DAY_60", "DAY_90", "LIFETIME", "CUSTOM"}
    period_type = data.get("period_type", "DAY_30")
    if period_type not in valid_periods:
        raise ValueError(f"Invalid period_type '{period_type}'. Must be one of: {sorted(list(valid_periods))}")

    def _validate_non_negative_int(field_name: str) -> Optional[int]:
        val = data.get(field_name)
        if val is None:
            return None
        try:
            val_int = int(val)
        except (ValueError, TypeError):
            raise ValueError(f"Field '{field_name}' must be an integer, got {val}.")
        if val_int < 0:
            raise ValueError(f"Field '{field_name}' cannot be negative ({val_int}).")
        return val_int

    def _validate_non_negative_float(field_name: str) -> Optional[float]:
        val = data.get(field_name)
        if val is None:
            return None
        try:
            val_flt = float(val)
        except (ValueError, TypeError):
            raise ValueError(f"Field '{field_name}' must be a number, got {val}.")
        if val_flt < 0.0:
            raise ValueError(f"Field '{field_name}' cannot be negative ({val_flt}).")
        return val_flt

    def _validate_pct(field_name: str) -> Optional[float]:
        val = data.get(field_name)
        if val is None:
            return None
        try:
            val_flt = float(val)
        except (ValueError, TypeError):
            raise ValueError(f"Field '{field_name}' must be a percentage number, got {val}.")
        if val_flt < 0.0 or val_flt > 100.0:
            raise ValueError(f"Field '{field_name}' must be between 0.0% and 100.0% ({val_flt}%).")
        return val_flt

    clean_units_sold = _validate_non_negative_int("actual_units_sold")
    clean_revenue = _validate_non_negative_float("actual_revenue")
    clean_avg_price = _validate_non_negative_float("actual_avg_selling_price")
    clean_landed_cogs = _validate_non_negative_float("actual_landed_cogs")
    clean_cm = data.get("actual_contribution_margin")
    if clean_cm is not None:
        try:
            clean_cm = float(clean_cm)
        except (ValueError, TypeError):
            raise ValueError(f"Field 'actual_contribution_margin' must be a number, got {clean_cm}.")
    clean_cm_pct = data.get("actual_cm_pct")
    if clean_cm_pct is not None:
        try:
            clean_cm_pct = float(clean_cm_pct)
        except (ValueError, TypeError):
            raise ValueError(f"Field 'actual_cm_pct' must be a number, got {clean_cm_pct}.")

    clean_returns = _validate_non_negative_int("actual_returns_count")
    clean_return_pct = _validate_pct("actual_return_rate_pct")
    clean_rto = _validate_non_negative_int("actual_rto_count")
    clean_rto_pct = _validate_pct("actual_rto_rate_pct")
    clean_ad_spend = _validate_non_negative_float("actual_ad_spend")
    clean_cac = _validate_non_negative_float("actual_cac")
    clean_inv = _validate_non_negative_int("actual_inventory")
    clean_stockouts = _validate_non_negative_int("actual_stockout_days")

    # Cross-field logical constraints
    observation_period_days = (d_end - d_start).days + 1
    if clean_stockouts is not None and clean_stockouts > observation_period_days:
        raise ValueError(
            f"actual_stockout_days ({clean_stockouts}) cannot exceed observation period days ({observation_period_days})."
        )

    if clean_returns is not None and clean_units_sold is not None:
        if clean_returns > clean_units_sold:
            raise ValueError(f"actual_returns_count ({clean_returns}) cannot exceed actual_units_sold ({clean_units_sold}).")

    if clean_rto is not None and clean_units_sold is not None:
        if clean_rto > clean_units_sold:
            raise ValueError(f"actual_rto_count ({clean_rto}) cannot exceed actual_units_sold ({clean_units_sold}).")

    # Scraped research proxies rejection (Section 16: Not real seller outcomes)
    SCRAPED_RESEARCH_PROXIES = {
        "GOOGLE_TRENDS", "COMPETITOR_BSR", "SCRAPED_ESTIMATE",
        "HELIUM_ESTIMATE", "MARKETPLACE_ESTIMATE", "MARKET_RESEARCH"
    }
    data_src = str(data.get("data_source", "MANUAL")).strip()
    if data_src.upper() in SCRAPED_RESEARCH_PROXIES:
        raise ValueError(
            f"Data source '{data_src}' represents pre-launch research/scraped estimates, "
            "not real observed seller business outcomes. Rejecting outcome ingestion."
        )

    decision_id = data.get("decision_id")
    if decision_id is not None:
        try:
            decision_id = int(decision_id)
        except (ValueError, TypeError):
            raise ValueError(f"Field 'decision_id' must be an integer, got {decision_id}.")

    return {
        "product_id": product_id,
        "decision_id": decision_id,
        "period_start": d_start.isoformat(),
        "period_end": d_end.isoformat(),
        "period_type": period_type,
        "actual_units_sold": clean_units_sold,
        "actual_revenue": clean_revenue,
        "actual_avg_selling_price": clean_avg_price,
        "actual_landed_cogs": clean_landed_cogs,
        "actual_contribution_margin": clean_cm,
        "actual_cm_pct": clean_cm_pct,
        "actual_returns_count": clean_returns,
        "actual_return_rate_pct": clean_return_pct,
        "actual_rto_count": clean_rto,
        "actual_rto_rate_pct": clean_rto_pct,
        "actual_ad_spend": clean_ad_spend,
        "actual_cac": clean_cac,
        "actual_inventory": clean_inv,
        "actual_stockout_days": clean_stockouts,
        "data_source": str(data.get("data_source", "MANUAL")),
        "source_record_id": str(data.get("source_record_id")) if data.get("source_record_id") is not None else None,
        "notes": str(data.get("notes")) if data.get("notes") is not None else None,
    }


def record_product_outcome(outcome_data: Dict[str, Any], update_if_exists: bool = False, enforce_temporal: bool = False) -> Dict[str, Any]:
    """
    Ingests and stores observed post-launch business outcomes.
    Enforces validation and deterministic duplicate prevention.
    Returns dict: {'outcome_id': int, 'status': 'CREATED' | 'UPDATED' | 'IDEMPOTENT_DUPLICATE'}
    """
    clean_data = validate_outcome_payload(outcome_data)
    product_id = clean_data["product_id"]

    conn = get_connection()
    cur = conn.cursor()

    # 1. Verify foreign key: product exists in master_products
    cur.execute("SELECT product_id FROM master_products WHERE product_id = ?", (product_id,))
    if not cur.fetchone():
        conn.close()
        raise ValueError(f"Foreign Key Error: Product '{product_id}' does not exist in master_products.")

    # 2. Verify foreign key, product match, and temporal integrity for decision_id
    decision_id = clean_data["decision_id"]
    if decision_id is not None:
        cur.execute("SELECT decision_id, product_id, decision_timestamp FROM decision_ledger WHERE decision_id = ?", (decision_id,))
        dec_row = cur.fetchone()
        if not dec_row:
            conn.close()
            raise ValueError(f"Foreign Key Error: Decision '{decision_id}' does not exist in decision_ledger.")
        dec_dict = dict(dec_row)
        if dec_dict["product_id"] != product_id:
            conn.close()
            raise ValueError(f"Decision mismatch: Decision '{decision_id}' belongs to product '{dec_dict['product_id']}', not '{product_id}'.")
        if enforce_temporal:
            dec_date_str = str(dec_dict["decision_timestamp"]).split("T")[0].split(" ")[0]
            if dec_date_str > clean_data["period_start"]:
                conn.close()
                raise ValueError(f"Temporal Integrity Error: Decision timestamp ({dec_dict['decision_timestamp']}) occurs after outcome period_start ({clean_data['period_start']}).")

    # 3. Check for existing outcome by unique period tuple or source_record_id
    existing_row = None
    if clean_data.get("source_record_id"):
        cur.execute('''
            SELECT * FROM product_outcomes
            WHERE product_id = ? AND source_record_id = ?
        ''', (product_id, clean_data["source_record_id"]))
        existing_row = cur.fetchone()

    if not existing_row:
        cur.execute('''
            SELECT * FROM product_outcomes
            WHERE product_id = ? AND period_type = ? AND period_start = ? AND period_end = ?
        ''', (product_id, clean_data["period_type"], clean_data["period_start"], clean_data["period_end"]))
        existing_row = cur.fetchone()

    if existing_row:
        existing = dict(existing_row)
        existing_id = existing["outcome_id"]

        # Check if identical (all metrics and decision_id match)
        is_identical = True
        for k in (
            "decision_id", "actual_units_sold", "actual_revenue", "actual_avg_selling_price",
            "actual_landed_cogs", "actual_contribution_margin", "actual_cm_pct",
            "actual_returns_count", "actual_return_rate_pct", "actual_rto_count",
            "actual_rto_rate_pct", "actual_ad_spend", "actual_cac", "actual_inventory",
            "actual_stockout_days"
        ):
            if clean_data[k] != existing.get(k):
                is_identical = False
                break

        if is_identical:
            conn.close()
            return {"outcome_id": existing_id, "status": "IDEMPOTENT_DUPLICATE"}

        if not update_if_exists:
            conn.close()
            raise ValueError(
                f"Outcome record already exists for product '{product_id}' in period '{clean_data['period_type']}' "
                f"({clean_data['period_start']} to {clean_data['period_end']}). Set update_if_exists=True to update."
            )

        # Update existing record
        cur.execute('''
            UPDATE product_outcomes SET
                decision_id = ?,
                actual_units_sold = ?,
                actual_revenue = ?,
                actual_avg_selling_price = ?,
                actual_landed_cogs = ?,
                actual_contribution_margin = ?,
                actual_cm_pct = ?,
                actual_returns_count = ?,
                actual_return_rate_pct = ?,
                actual_rto_count = ?,
                actual_rto_rate_pct = ?,
                actual_ad_spend = ?,
                actual_cac = ?,
                actual_inventory = ?,
                actual_stockout_days = ?,
                data_source = ?,
                source_record_id = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE outcome_id = ?
        ''', (
            clean_data["decision_id"], clean_data["actual_units_sold"], clean_data["actual_revenue"],
            clean_data["actual_avg_selling_price"], clean_data["actual_landed_cogs"],
            clean_data["actual_contribution_margin"], clean_data["actual_cm_pct"],
            clean_data["actual_returns_count"], clean_data["actual_return_rate_pct"],
            clean_data["actual_rto_count"], clean_data["actual_rto_rate_pct"],
            clean_data["actual_ad_spend"], clean_data["actual_cac"],
            clean_data["actual_inventory"], clean_data["actual_stockout_days"],
            clean_data["data_source"], clean_data["source_record_id"],
            clean_data["notes"], existing_id
        ))
        conn.commit()
        conn.close()
        return {"outcome_id": existing_id, "status": "UPDATED"}

    # 4. Insert new outcome record
    cur.execute('''
        INSERT INTO product_outcomes (
            product_id, decision_id, period_start, period_end, period_type,
            actual_units_sold, actual_revenue, actual_avg_selling_price,
            actual_landed_cogs, actual_contribution_margin, actual_cm_pct,
            actual_returns_count, actual_return_rate_pct, actual_rto_count,
            actual_rto_rate_pct, actual_ad_spend, actual_cac, actual_inventory,
            actual_stockout_days, data_source, source_record_id, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        product_id, clean_data["decision_id"], clean_data["period_start"], clean_data["period_end"],
        clean_data["period_type"], clean_data["actual_units_sold"], clean_data["actual_revenue"],
        clean_data["actual_avg_selling_price"], clean_data["actual_landed_cogs"],
        clean_data["actual_contribution_margin"], clean_data["actual_cm_pct"],
        clean_data["actual_returns_count"], clean_data["actual_return_rate_pct"],
        clean_data["actual_rto_count"], clean_data["actual_rto_rate_pct"],
        clean_data["actual_ad_spend"], clean_data["actual_cac"], clean_data["actual_inventory"],
        clean_data["actual_stockout_days"], clean_data["data_source"],
        clean_data["source_record_id"], clean_data["notes"]
    ))
    outcome_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Log timeline event
    try:
        record_timeline_event(
            product_id=product_id,
            event_type="OUTCOME_RECORDED",
            event_title=f"Observed Outcome Recorded: {clean_data['period_type']}",
            event_description=f"Period: {clean_data['period_start']} to {clean_data['period_end']}, Source: {clean_data['data_source']}",
            metadata={"outcome_id": outcome_id, "period_type": clean_data["period_type"]}
        )
    except Exception:
        pass

    return {"outcome_id": outcome_id, "status": "CREATED"}


def get_product_outcomes(product_id: str, period_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all recorded post-launch outcomes for a given product."""
    conn = get_connection()
    cur = conn.cursor()
    if period_type:
        cur.execute('''
            SELECT * FROM product_outcomes
            WHERE product_id = ? AND period_type = ?
            ORDER BY period_start ASC, outcome_id ASC
        ''', (product_id, period_type))
    else:
        cur.execute('''
            SELECT * FROM product_outcomes
            WHERE product_id = ?
            ORDER BY period_start ASC, outcome_id ASC
        ''', (product_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_outcome_by_id(outcome_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single outcome by its outcome_id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM product_outcomes WHERE outcome_id = ?", (outcome_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_outcomes(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves a paginated list of all product outcomes across the system."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT po.*, mp.name as product_name, mp.category, mp.region
        FROM product_outcomes po
        LEFT JOIN master_products mp ON po.product_id = mp.product_id
        ORDER BY po.period_start DESC, po.outcome_id DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_outcome_correction(
    outcome_id: int,
    updates: Dict[str, Any],
    correction_reason: str,
    corrected_by: str = "SYSTEM_OPERATOR"
) -> Dict[str, Any]:
    """
    Explicitly corrects an existing post-launch outcome with auditable change tracking.
    Logs every changed field into `outcome_corrections_log` and updates `product_outcomes`.
    Raises ValueError if outcome_id not found, correction_reason is empty, or constraints violated.
    Returns dict: {'outcome_id': int, 'status': 'CORRECTED', 'corrections_logged': int}
    """
    if not correction_reason or not str(correction_reason).strip():
        raise ValueError("A non-empty 'correction_reason' is required for auditable outcome corrections.")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM product_outcomes WHERE outcome_id = ?", (outcome_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Outcome record {outcome_id} not found.")

    existing = dict(row)
    product_id = existing["product_id"]

    # Construct candidate merged payload for validation
    merged = dict(existing)
    for k, v in updates.items():
        if k in (
            "actual_units_sold", "actual_revenue", "actual_avg_selling_price",
            "actual_landed_cogs", "actual_contribution_margin", "actual_cm_pct",
            "actual_returns_count", "actual_return_rate_pct", "actual_rto_count",
            "actual_rto_rate_pct", "actual_ad_spend", "actual_cac",
            "actual_inventory", "actual_stockout_days", "data_source",
            "source_record_id", "notes", "decision_id", "period_start",
            "period_end", "period_type"
        ):
            merged[k] = v

    # Validate the full merged payload
    clean_data = validate_outcome_payload(merged)

    # Verify decision foreign key, product match, and temporal integrity if specified
    dec_id = clean_data["decision_id"]
    if dec_id is not None:
        cur.execute("SELECT decision_id, product_id, decision_timestamp FROM decision_ledger WHERE decision_id = ?", (dec_id,))
        dec_row = cur.fetchone()
        if not dec_row:
            conn.close()
            raise ValueError(f"Foreign Key Error: Decision '{dec_id}' does not exist in decision_ledger.")
        dec_dict = dict(dec_row)
        if dec_dict["product_id"] != product_id:
            conn.close()
            raise ValueError(f"Decision mismatch: Decision '{dec_id}' belongs to product '{dec_dict['product_id']}', not '{product_id}'.")
        dec_date_str = str(dec_dict["decision_timestamp"]).split("T")[0].split(" ")[0]
        if dec_date_str > clean_data["period_start"]:
            conn.close()
            raise ValueError(f"Temporal Integrity Error: Decision timestamp ({dec_dict['decision_timestamp']}) occurs after outcome period_start ({clean_data['period_start']}).")

    # Log diffs to outcome_corrections_log
    track_fields = (
        "actual_units_sold", "actual_revenue", "actual_avg_selling_price",
        "actual_landed_cogs", "actual_contribution_margin", "actual_cm_pct",
        "actual_returns_count", "actual_return_rate_pct", "actual_rto_count",
        "actual_rto_rate_pct", "actual_ad_spend", "actual_cac",
        "actual_inventory", "actual_stockout_days", "data_source",
        "source_record_id", "notes", "decision_id"
    )

    corrections_logged = 0
    for field in track_fields:
        old_val = existing.get(field)
        new_val = clean_data.get(field)
        if str(old_val) != str(new_val):
            cur.execute('''
                INSERT INTO outcome_corrections_log (
                    outcome_id, product_id, decision_id, field_name,
                    previous_value, new_value, correction_reason,
                    corrected_by, correction_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                outcome_id, product_id, dec_id, field,
                str(old_val) if old_val is not None else None,
                str(new_val) if new_val is not None else None,
                correction_reason.strip(),
                corrected_by
            ))
            corrections_logged += 1

    # Update product_outcomes
    cur.execute('''
        UPDATE product_outcomes SET
            decision_id = ?,
            actual_units_sold = ?,
            actual_revenue = ?,
            actual_avg_selling_price = ?,
            actual_landed_cogs = ?,
            actual_contribution_margin = ?,
            actual_cm_pct = ?,
            actual_returns_count = ?,
            actual_return_rate_pct = ?,
            actual_rto_count = ?,
            actual_rto_rate_pct = ?,
            actual_ad_spend = ?,
            actual_cac = ?,
            actual_inventory = ?,
            actual_stockout_days = ?,
            data_source = ?,
            source_record_id = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE outcome_id = ?
    ''', (
        clean_data["decision_id"], clean_data["actual_units_sold"], clean_data["actual_revenue"],
        clean_data["actual_avg_selling_price"], clean_data["actual_landed_cogs"],
        clean_data["actual_contribution_margin"], clean_data["actual_cm_pct"],
        clean_data["actual_returns_count"], clean_data["actual_return_rate_pct"],
        clean_data["actual_rto_count"], clean_data["actual_rto_rate_pct"],
        clean_data["actual_ad_spend"], clean_data["actual_cac"],
        clean_data["actual_inventory"], clean_data["actual_stockout_days"],
        clean_data["data_source"], clean_data["source_record_id"],
        clean_data["notes"], outcome_id
    ))
    conn.commit()
    conn.close()

    try:
        record_timeline_event(
            product_id=product_id,
            event_type="OUTCOME_CORRECTED",
            event_title="Observed Outcome Corrected",
            event_description=f"Outcome {outcome_id} corrected. Reason: {correction_reason.strip()}",
            metadata={"outcome_id": outcome_id, "changes_logged": corrections_logged, "reason": correction_reason.strip()}
        )
    except Exception:
        pass

    return {
        "outcome_id": outcome_id,
        "status": "CORRECTED",
        "corrections_logged": corrections_logged
    }


def get_outcome_corrections(
    outcome_id: Optional[int] = None,
    product_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves audit entries from outcome_corrections_log."""
    conn = get_connection()
    cur = conn.cursor()
    if outcome_id is not None:
        cur.execute('''
            SELECT * FROM outcome_corrections_log
            WHERE outcome_id = ?
            ORDER BY correction_timestamp DESC, correction_id DESC
        ''', (outcome_id,))
    elif product_id is not None:
        cur.execute('''
            SELECT * FROM outcome_corrections_log
            WHERE product_id = ?
            ORDER BY correction_timestamp DESC, correction_id DESC
        ''', (product_id,))
    else:
        cur.execute('''
            SELECT * FROM outcome_corrections_log
            ORDER BY correction_timestamp DESC, correction_id DESC
            LIMIT 100
        ''')
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# -------------------------------------------------------------
# APRS V8 PHASE 2: PREDICTION CALIBRATION DATABASE HELPERS
# -------------------------------------------------------------

def save_prediction_calibration(calib_data: Dict[str, Any]) -> int:
    """
    Saves or updates a prediction calibration record in the database.
    Deterministic: UNIQUE(decision_id, outcome_id, calculation_version) ensures idempotency.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        INSERT INTO prediction_calibrations (
            decision_id, outcome_id, product_id, demand_predicted, demand_actual,
            demand_signed_error, demand_absolute_error, demand_percentage_error,
            cm_predicted_pct, cm_actual_pct, cm_signed_error_pct_points, cm_absolute_error_pct_points,
            rto_predicted_pct, rto_actual_pct, rto_signed_error_pct_points, rto_absolute_error_pct_points,
            cac_predicted, cac_actual, cac_signed_error, cac_absolute_error, cac_percentage_error,
            price_predicted, price_actual, price_signed_error,
            directional_accuracy, data_completeness_pct, calibration_status, calculation_version,
            details_json, notes
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(decision_id, outcome_id, calculation_version) DO UPDATE SET
            demand_predicted = excluded.demand_predicted,
            demand_actual = excluded.demand_actual,
            demand_signed_error = excluded.demand_signed_error,
            demand_absolute_error = excluded.demand_absolute_error,
            demand_percentage_error = excluded.demand_percentage_error,
            cm_predicted_pct = excluded.cm_predicted_pct,
            cm_actual_pct = excluded.cm_actual_pct,
            cm_signed_error_pct_points = excluded.cm_signed_error_pct_points,
            cm_absolute_error_pct_points = excluded.cm_absolute_error_pct_points,
            rto_predicted_pct = excluded.rto_predicted_pct,
            rto_actual_pct = excluded.rto_actual_pct,
            rto_signed_error_pct_points = excluded.rto_signed_error_pct_points,
            rto_absolute_error_pct_points = excluded.rto_absolute_error_pct_points,
            cac_predicted = excluded.cac_predicted,
            cac_actual = excluded.cac_actual,
            cac_signed_error = excluded.cac_signed_error,
            cac_absolute_error = excluded.cac_absolute_error,
            cac_percentage_error = excluded.cac_percentage_error,
            price_predicted = excluded.price_predicted,
            price_actual = excluded.price_actual,
            price_signed_error = excluded.price_signed_error,
            directional_accuracy = excluded.directional_accuracy,
            data_completeness_pct = excluded.data_completeness_pct,
            calibration_status = excluded.calibration_status,
            details_json = excluded.details_json,
            notes = excluded.notes,
            calibration_timestamp = CURRENT_TIMESTAMP
    ''', (
        calib_data["decision_id"], calib_data["outcome_id"], calib_data["product_id"],
        calib_data.get("demand_predicted"), calib_data.get("demand_actual"),
        calib_data.get("demand_signed_error"), calib_data.get("demand_absolute_error"), calib_data.get("demand_percentage_error"),
        calib_data.get("cm_predicted_pct"), calib_data.get("cm_actual_pct"), calib_data.get("cm_signed_error_pct_points"), calib_data.get("cm_absolute_error_pct_points"),
        calib_data.get("rto_predicted_pct"), calib_data.get("rto_actual_pct"), calib_data.get("rto_signed_error_pct_points"), calib_data.get("rto_absolute_error_pct_points"),
        calib_data.get("cac_predicted"), calib_data.get("cac_actual"), calib_data.get("cac_signed_error"), calib_data.get("cac_absolute_error"), calib_data.get("cac_percentage_error"),
        calib_data.get("price_predicted"), calib_data.get("price_actual"), calib_data.get("price_signed_error"),
        calib_data.get("directional_accuracy", "UNKNOWN"), calib_data.get("data_completeness_pct", 0.0),
        calib_data.get("calibration_status", "CALIBRATED"), calib_data.get("calculation_version", "V8_CALIBRATION_V1"),
        calib_data.get("details_json", "{}"), calib_data.get("notes")
    ))
    calib_id = cur.lastrowid
    if not calib_id:
        cur.execute(
            "SELECT calibration_id FROM prediction_calibrations WHERE decision_id = ? AND outcome_id = ? AND calculation_version = ?",
            (calib_data["decision_id"], calib_data["outcome_id"], calib_data.get("calculation_version", "V8_CALIBRATION_V1"))
        )
        row = cur.fetchone()
        calib_id = row[0] if row else 0
    conn.commit()
    conn.close()
    return calib_id


def get_calibration_by_id(calibration_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single calibration record by ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM prediction_calibrations WHERE calibration_id = ?", (calibration_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_calibrations_for_product(product_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves all historical calibration records for a product."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM prediction_calibrations
        WHERE product_id = ?
        ORDER BY calibration_timestamp DESC, calibration_id DESC
        LIMIT ?
    ''', (product_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_calibrations(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves paginated calibration records across all products."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT pc.*, mp.name as product_name, mp.category, mp.region
        FROM prediction_calibrations pc
        LEFT JOIN master_products mp ON pc.product_id = mp.product_id
        ORDER BY pc.calibration_timestamp DESC, pc.calibration_id DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    seed_initial_marketplace_configs()
    print("[SUCCESS] SQLite database initialized with schema migrations and meeting audit log!")