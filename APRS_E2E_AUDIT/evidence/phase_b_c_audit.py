import os
import sys
import re
import glob
import sqlite3
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path("D:/tools/APRS")
AUDIT_DIR = ROOT / "APRS_E2E_AUDIT"

# ---------------------------------------------------------------------------
# 1. DEPENDENCY AUDIT
# ---------------------------------------------------------------------------
def audit_dependencies():
    lines = []
    lines.append("# DEPENDENCY AUDIT INVENTORY\n")
    req_file = ROOT / "requirements.txt"
    with open(req_file, "r", encoding="utf-8") as f:
        req_lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    # Get installed packages from .venv
    import subprocess
    pip_res = subprocess.run([str(ROOT / ".venv" / "Scripts" / "pip.exe"), "list", "--format=json"], capture_output=True, text=True)
    import json
    installed = {}
    try:
        installed_list = json.loads(pip_res.stdout)
        installed = {pkg["name"].lower(): pkg["version"] for pkg in installed_list}
    except Exception as e:
        lines.append(f"Failed to parse pip list: {e}\n")

    lines.append("| Declared Requirement | Package Name | Specifier | Installed in .venv? | Installed Version | Classification |")
    lines.append("|---|---|---|---|---|---|")

    # Classifications map
    classification_map = {
        "pydantic": "REAL ACTIVE DEPENDENCY (Schema & Settings)",
        "pydantic-settings": "REAL ACTIVE DEPENDENCY (Settings Management)",
        "python-dotenv": "REAL ACTIVE DEPENDENCY (Env loading)",
        "streamlit": "REAL ACTIVE DEPENDENCY (Primary UI)",
        "pandas": "REAL ACTIVE DEPENDENCY (Dataframes & Tables)",
        "openpyxl": "REAL ACTIVE DEPENDENCY (Excel export)",
        "python-docx": "REAL ACTIVE DEPENDENCY (Word report generation)",
        "requests": "REAL ACTIVE DEPENDENCY (HTTP client)",
        "httpx": "REAL ACTIVE DEPENDENCY (Async HTTP)",
        "curl_cffi": "REAL ACTIVE DEPENDENCY (TLS impersonation scraper)",
        "beautifulsoup4": "REAL ACTIVE DEPENDENCY (HTML parsing)",
        "lxml": "REAL ACTIVE DEPENDENCY (XML/HTML backend)",
        "browser-use": "OPTIONAL / CONDITIONAL (Universal scraper / Cloud)",
        "sqlite-utils": "REAL ACTIVE DEPENDENCY (SQLite operations)",
        "supabase": "LEGACY / OPTIONAL (Subscription was purged; client exists)",
        "openai": "REAL ACTIVE DEPENDENCY (NIM client uses OpenAI protocol)",
        "anthropic": "OPTIONAL / FALLBACK (Secondary LLM provider)",
        "google-generativeai": "OPTIONAL / FALLBACK (Gemini API provider)",
        "pytrends": "OPTIONAL / ACTIVE (Google Trends scraper)",
        "statsmodels": "OPTIONAL (Trend regression & forecasting)",
        "scikit-learn": "OPTIONAL (Clustering & feature modeling)",
        "numpy": "REAL ACTIVE DEPENDENCY (Numeric calculations)",
        "asyncio-mqtt": "UNUSED / LEGACY (MQTT telemetry - no active broker)",
        "aiofiles": "REAL ACTIVE DEPENDENCY (Async file I/O)",
        "python-dateutil": "REAL ACTIVE DEPENDENCY (Date parsing)",
        "tqdm": "REAL ACTIVE DEPENDENCY (CLI progress bars)",
        "tenacity": "REAL ACTIVE DEPENDENCY (Retry decorator)",
        "pillow": "REAL ACTIVE DEPENDENCY (Image handling)",
        "pyyaml": "REAL ACTIVE DEPENDENCY (YAML config)",
        "jsonschema": "REAL ACTIVE DEPENDENCY (JSON Schema validation)",
        "structlog": "REAL ACTIVE DEPENDENCY (Structured logging)",
        "rich": "REAL ACTIVE DEPENDENCY (Terminal formatting)",
        "pytest": "REAL ACTIVE DEPENDENCY (Test framework)",
        "pytest-asyncio": "REAL ACTIVE DEPENDENCY (Async test runner)",
        "pytest-cov": "REAL ACTIVE DEPENDENCY (Coverage reporter)",
        "pytest-mock": "REAL ACTIVE DEPENDENCY (Mocking fixtures)",
        "pytest-xdist": "REAL ACTIVE DEPENDENCY (Parallel test execution)",
        "mypy": "DEV TOOL (Static type checker)",
        "types-requests": "DEV TOOL (Type stubs)",
        "types-python-dateutil": "DEV TOOL (Type stubs)",
        "razorpay": "LEGACY / UNUSED (Subscription payments purged in Phase 1)",
    }

    for req in req_lines:
        m = re.match(r"^([A-Za-z0-9_\-]+)(.*)$", req)
        if m:
            pkg, spec = m.group(1), m.group(2)
            pkg_lower = pkg.lower().replace("_", "-")
            inst_ver = installed.get(pkg_lower) or installed.get(pkg.lower(), "NOT INSTALLED")
            status = "YES" if inst_ver != "NOT INSTALLED" else "MISSING"
            cls_type = classification_map.get(pkg.lower(), "UNKNOWN")
            lines.append(f"| `{req}` | `{pkg}` | `{spec}` | **{status}** | `{inst_ver}` | {cls_type} |")

    with open(AUDIT_DIR / "evidence" / "dependencies_audit.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Dependency audit written.")

# ---------------------------------------------------------------------------
# 2. API & CREDENTIALS AUDIT
# ---------------------------------------------------------------------------
def audit_apis_and_credentials():
    lines = []
    lines.append("# API & CREDENTIAL AUDIT\n")
    lines.append("Auditing all external integrations across the repository without revealing secrets.\n")

    # Read .env if present
    env_vars = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    v_clean = v.strip().strip("'").strip('"')
                    env_vars[k.strip()] = "PRESENT" if len(v_clean) > 0 else "EMPTY"

    api_catalog = [
        {
            "provider": "NVIDIA NIM",
            "purpose": "LLM inference for War Room 2.0 swarm agents (Scout, Harvester, DefectMiner, Economics, Arbiter)",
            "module": "models/nim_cluster.py, core/war_room_2.py",
            "required": "Yes (for live AI swarm)",
            "credential_keys": ["NIM_API_KEY_1", "NIM_API_KEY_2", "NIM_API_KEY_3"],
            "free_tier": "Yes (1,000 req/day per key with free developer account at build.nvidia.com)",
            "paid_tier": "Pay-per-token after trial quota or Enterprise NIM credits",
            "fallback": "Mock / Fallback mode in tools / Rule-based heuristics",
        },
        {
            "provider": "Keepa API",
            "purpose": "Amazon BSR and historical pricing / sales rank telemetry",
            "module": "tools/scrapers/keepa_client.py",
            "required": "Optional / Recommended for Amazon telemetry",
            "credential_keys": ["KEEPA_API_KEY"],
            "free_tier": "Limited free access (token bucket / heavily throttled)",
            "paid_tier": "Subscription approx €19 - €39/month",
            "fallback": "Fallback to direct web scraping or cached listing data",
        },
        {
            "provider": "Browser-Use Cloud",
            "purpose": "Cloud browser automation with residential proxy & captcha solving",
            "module": "tools/browser_use_cloud_client.py",
            "required": "Optional (for high-volume stealth scraping)",
            "credential_keys": ["BROWSER_USE_API_KEY"],
            "free_tier": "Free trial with limited cloud browser minutes",
            "paid_tier": "Usage-based cloud pricing",
            "fallback": "Local headless Playwright / curl_cffi direct scraper",
        },
        {
            "provider": "Google Trends (pytrends)",
            "purpose": "Keyword trend interest and directional trajectory",
            "module": "tools/trend_scout.py",
            "required": "Optional / Active",
            "credential_keys": [],
            "free_tier": "Free public web interface (subject to Google rate limits / HTTP 429)",
            "paid_tier": "SerpApi / DataForSEO paid APIs for reliable high-volume proxies",
            "fallback": "Static / default trend scores when rate limited",
        },
        {
            "provider": "OpenAI / Anthropic / Google Gemini",
            "purpose": "Alternative LLM providers for AI supervisor / fallback generation",
            "module": "config/settings.py",
            "required": "Optional fallback",
            "credential_keys": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"],
            "free_tier": "Gemini has free tier (15 RPM); OpenAI/Anthropic require paid credits",
            "paid_tier": "Pay-per-token API",
            "fallback": "NIM cluster or local heuristic scoring",
        },
        {
            "provider": "Supabase",
            "purpose": "Legacy SaaS authentication & cloud user database",
            "module": "core/supabase_subscription_service.py",
            "required": "Legacy / Purged in Phase 1 (APRS is now single-user desktop architecture)",
            "credential_keys": ["SUPABASE_URL", "SUPABASE_KEY"],
            "free_tier": "Free tier available",
            "paid_tier": "Pro tier $25/mo",
            "fallback": "Local SQLite database data/research_engine.db",
        },
        {
            "provider": "Razorpay",
            "purpose": "Legacy payment processing for subscriptions",
            "module": "requirements.txt (historical)",
            "required": "Legacy / Purged in Phase 1",
            "credential_keys": ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"],
            "free_tier": "Per-transaction fee (2%)",
            "paid_tier": "Standard processing fees",
            "fallback": "Not applicable — subscriptions decommissioned",
        },
    ]

    lines.append("| Provider | Purpose | Module | Required? | Credential Keys | Env Status | Free Tier | Paid Alternative | Fallback |")
    lines.append("|---|---|---|---|---|---|---|---|---|")

    for api in api_catalog:
        statuses = []
        if not api["credential_keys"]:
            status_str = "NO KEY REQUIRED"
        else:
            for k in api["credential_keys"]:
                st = env_vars.get(k, "MISSING")
                statuses.append(f"`{k}`: **{st}**")
            status_str = "<br>".join(statuses)

        keys_str = ", ".join(f"`{k}`" for k in api["credential_keys"]) if api["credential_keys"] else "None"
        lines.append(f"| {api['provider']} | {api['purpose']} | `{api['module']}` | {api['required']} | {keys_str} | {status_str} | {api['free_tier']} | {api['paid_tier']} | {api['fallback']} |")

    with open(AUDIT_DIR / "evidence" / "api_credential_audit.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("API audit written.")

# ---------------------------------------------------------------------------
# 3. DATABASE BASELINE AUDIT
# ---------------------------------------------------------------------------
def audit_database_baseline():
    lines = []
    lines.append("# DATABASE FORENSIC BASELINE AUDIT\n")
    db_path = ROOT / "data" / "research_engine.db"
    lines.append(f"Database File: `{db_path}`\n")
    lines.append(f"File Size: {db_path.stat().st_size} bytes\n")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r["name"] for r in cur.fetchall()]
    lines.append(f"Total Tables Found: {len(tables)}\n")

    lines.append("## Table Inventory & Row Counts\n")
    lines.append("| Table Name | Row Count | Primary Key | Column Count | Foreign Keys | Category / Purpose |")
    lines.append("|---|---|---|---|---|---|")

    v8_tables = {"decision_ledger", "product_outcomes", "prediction_calibrations", "outcome_corrections_log", "learning_bias_summaries", "learning_recommendations"}
    v7_tables = {"product_intelligence", "intelligence_evidence", "intelligence_timeline", "opportunity_alerts", "product_watchlist", "research_runs", "source_health", "data_conflicts", "defect_clusters"}
    v6_tables = {"master_products", "launchpad_items", "economics_assessments", "product_suppliers", "scraped_listings", "multi_platform_listings", "dynamic_niches", "dynamic_seed_keywords", "product_gate_progress", "arbiter_decision_log"}

    for t in tables:
        # count
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]

        # table info
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        col_count = len(cols)
        pks = [c["name"] for c in cols if c["pk"] > 0]
        pk_str = ", ".join(pks) if pks else "None"

        # fks
        cur.execute(f"PRAGMA foreign_key_list({t})")
        fks = cur.fetchall()
        fk_str = f"{len(fks)} FK(s)" if fks else "None"

        if t in v8_tables:
            cat = "V8 Outcome & Learning"
        elif t in v7_tables:
            cat = "V7 Autonomous Intelligence"
        elif t in v6_tables:
            cat = "V6 Gated Research Pipeline"
        else:
            cat = "System / Utility"

        lines.append(f"| `{t}` | {cnt} | `{pk_str}` | {col_count} | {fk_str} | {cat} |")

    # Integrity & Foreign Keys
    cur.execute("PRAGMA foreign_key_check")
    fk_violations = cur.fetchall()
    lines.append(f"\n## Foreign Key Check\n`PRAGMA foreign_key_check;` returned: **{len(fk_violations)} violations**\n")

    cur.execute("PRAGMA integrity_check")
    integrity = cur.fetchall()
    lines.append(f"## SQLite Integrity Check\n`PRAGMA integrity_check;` returned: **{integrity[0][0]}**\n")

    # Triggers
    cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name")
    triggers = cur.fetchall()
    lines.append(f"## Database Triggers ({len(triggers)})\n")
    for trg in triggers:
        lines.append(f"- **{trg['name']}** on table `{trg['tbl_name']}`:\n  ```sql\n  {trg['sql'].strip()}\n  ```\n")

    with open(AUDIT_DIR / "evidence" / "database_baseline.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Database audit written.")

# ---------------------------------------------------------------------------
# 4. HARDCODED & SYNTHETIC DATA AUDIT
# ---------------------------------------------------------------------------
def audit_hardcoded_and_synthetic_data():
    lines = []
    lines.append("# HARDCODED, FAKE, MOCK & SYNTHETIC DATA AUDIT\n")

    # Search python files for suspicious patterns
    patterns = [
        (r"random\.(choice|randint|uniform|random)", "Random generator (potentially synthetic data)"),
        (r"(mock|fake|dummy|synthetic|placeholder)", "Mock / Fake / Synthetic keywords"),
        (r"weights\s*=\s*\{", "Hardcoded weighting dict"),
        (r"DEFAULT_[A-Z0-9_]*\s*=\s*", "Default policy / constant declaration"),
    ]

    findings = []
    py_files = list(ROOT.glob("core/**/*.py")) + list(ROOT.glob("tools/**/*.py")) + list(ROOT.glob("web/**/*.py"))

    for pf in py_files:
        rel = pf.relative_to(ROOT)
        with open(pf, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                for pat, desc in patterns:
                    if re.search(pat, line, re.IGNORECASE):
                        # Filter out obvious test comments
                        clean = line.strip()
                        if len(clean) > 120:
                            clean = clean[:117] + "..."
                        findings.append((str(rel), idx, desc, clean))

    lines.append(f"Total suspicious pattern matches in core/tools/web: {len(findings)}\n")
    lines.append("| File | Line | Classification Category | Code Snippet |")
    lines.append("|---|---|---|---|")
    for f_path, l_num, cat, snip in findings[:100]:  # sample top 100
        snip_esc = snip.replace("|", "\\|")
        lines.append(f"| `{f_path}` | {l_num} | {cat} | `{snip_esc}` |")

    with open(AUDIT_DIR / "evidence" / "hardcoded_data_audit.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Hardcoded data audit written.")

if __name__ == "__main__":
    audit_dependencies()
    audit_apis_and_credentials()
    audit_database_baseline()
    audit_hardcoded_and_synthetic_data()
