# APRS — SYSTEM REQUIREMENTS, DEPENDENCIES & CREDENTIAL AUDIT

**Audit Date:** September 2026  
**Auditor:** Principal Infrastructure & Security Auditor  
**System:** APRS — Autonomous Product Research System

---

## 1. Operating Environment & System Requirements

### Hardware Requirements
- **Processor:** 64-bit multi-core CPU (x86_64 / AMD64 or Apple Silicon ARM64).
- **RAM:** Minimum 8 GB (16 GB recommended when running multi-agent simulations or local embeddings).
- **Disk Storage:** Minimum 1 GB available space for SQLite databases, Keepa cache, and Playwright browser binaries.

### Software & Runtime Dependencies
- **Operating System:** Windows 10/11, macOS 12+, or Ubuntu Linux 22.04+ LTS.
- **Python Environment:** Python 3.10 to 3.12 (Audited on **Python 3.12.14** in `.venv`).
- **Web Browser Automation:** Chromium binary managed via Playwright (Installed & verified).
- **Database Engine:** Embedded SQLite 3.35+ with trigger support (Built into Python standard library).

---

## 2. Python Package Dependencies

Based on inspection of `pyproject.toml`, `requirements.txt`, and virtual environment packages:

| Package Category | Key Packages | Installed Version | Status / Usage |
|---|---|---|---|
| **Core Web Dashboard** | `streamlit`, `altair`, `pandas` | Streamlit 1.63.0, Pandas 2.2.3 | **ACTIVE** (Main UI application) |
| **Browser Automation** | `playwright` | Playwright 1.57.0 | **ACTIVE** (Chrome scraping & UI audit) |
| **Testing & Verification** | `pytest`, `pytest-asyncio` | Pytest 9.1.1 | **ACTIVE** (272 automated tests) |
| **LLM & Agent Framework** | `openai`, `google-genai`, `anthropic` | Installed in `.venv` | **ACTIVE** (Swarm arbiter inference) |
| **Network & Scraping** | `requests`, `urllib3`, `beautifulsoup4` | Requests 2.32.3 | **ACTIVE** (Keepa, Amazon, IndiaMART) |
| **Data & Plotting** | `numpy`, `scipy`, `matplotlib` | NumPy 2.2.3 | **ACTIVE** (Counterfactual calculations) |

---

## 3. External API Credentials & Key Inventory

Forensic audit of `.env` and environment variables revealed the following credential status:

| Credential Variable | Detected Status | Required or Optional? | Subsystem / Purpose |
|---|---|---|---|
| `NIM_API_KEY_1` | **PRESENT** (Redacted) | **REQUIRED** for AI Swarm | NVIDIA NIM Primary Key (Nemotron 70B inference) |
| `NIM_API_KEY_2` | **PRESENT** (Redacted) | **RECOMMENDED** | NVIDIA NIM Key 2 (Key rotation & rate limit avoidance) |
| `NIM_API_KEY_3` | **PRESENT** (Redacted) | **RECOMMENDED** | NVIDIA NIM Key 3 (Key rotation fallback) |
| `KEEPA_API_KEY` | **PRESENT** (Redacted) | **REQUIRED** for Amazon BSR | Keepa Data Access (BSR, pricing, buy box history) |
| `RAZORPAY_KEY_ID` | **PRESENT** (Redacted) | **LEGACY / INACTIVE** | Legacy payment system (subscription code purged) |
| `RAZORPAY_KEY_SECRET` | **PRESENT** (Redacted) | **LEGACY / INACTIVE** | Legacy payment system (subscription code purged) |
| `BROWSER_USE_API_KEY` | **NOT FOUND / EMPTY** | **OPTIONAL** | Optional Cloud Browser agent (Local Playwright used) |
| `OPENAI_API_KEY` | **NOT FOUND / EMPTY** | **OPTIONAL** | Optional fallback LLM provider |
| `ANTHROPIC_API_KEY` | **NOT FOUND / EMPTY** | **OPTIONAL** | Optional fallback LLM provider |
| `GOOGLE_API_KEY` | **NOT FOUND / EMPTY** | **OPTIONAL** | Optional fallback LLM provider (Gemini) |
| `SUPABASE_URL` | **PRESENT** | **LEGACY / INACTIVE** | Legacy cloud DB (APRS now operates local SQLite) |
| `SUPABASE_KEY` | **NOT FOUND / EMPTY** | **LEGACY / INACTIVE** | Legacy cloud DB (purged) |

---

## 4. Free Alternatives vs Paid Tiers Analysis

To ensure APRS can operate cost-effectively without vendor lock-in, the following free vs paid alternatives were evaluated:

### 1. LLM Agent Inference (Gate 5 Arbiter & Intelligence)
- **Current Setup:** NVIDIA NIM Free Community Credits (`meta/llama-3.1-70b-instruct`, `nvidia/nemotron-4-340b`). NVIDIA provides 1,000 free inference calls per registered developer account.
- **Paid Tier:** OpenAI API (`gpt-4o-mini` / `gpt-4o`) or Anthropic Claude 3.5 Sonnet.
- **100% Free Self-Hosted Alternative:** **Ollama** or **vLLM** running locally on an RTX GPU with `llama3.1:8b` or `qwen2.5:7b-instruct`. The codebase's OpenAI-compatible client allows switching `base_url="http://localhost:11434/v1"`.

### 2. Amazon Product & BSR Telemetry (Keepa)
- **Current Setup:** Paid Keepa API Key (token bucket model: ~300 tokens/min).
- **Free Alternative:** Local Playwright Chromium direct headless scraping of Amazon BSR and price history, or public open-source price tracking APIs (CamelCamelCamel public snapshots). Note: Direct scraping requires resilient proxy rotation to prevent CAPTCHAs.

### 3. Web & E-Commerce Scraping
- **Current Setup:** Local **Playwright** Chromium headless browser automation.
- **Cost:** **$0.00 (100% Free & Open Source)**. No paid third-party scraping services (like Browserless.io or ScrapingBee) are required.

### 4. Database & Storage
- **Current Setup:** Embedded **SQLite** (`data/research_engine.db`).
- **Cost:** **$0.00**. Completely local, zero monthly cloud database fees, ultra-low latency, and zero network configuration required.
