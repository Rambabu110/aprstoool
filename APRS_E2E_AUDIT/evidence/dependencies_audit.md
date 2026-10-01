# DEPENDENCY AUDIT INVENTORY

| Declared Requirement | Package Name | Specifier | Installed in .venv? | Installed Version | Classification |
|---|---|---|---|---|---|
| `pydantic>=2.10.0` | `pydantic` | `>=2.10.0` | **YES** | `2.12.5` | REAL ACTIVE DEPENDENCY (Schema & Settings) |
| `pydantic-settings>=2.5.0` | `pydantic-settings` | `>=2.5.0` | **YES** | `2.15.0` | REAL ACTIVE DEPENDENCY (Settings Management) |
| `python-dotenv>=1.0.0` | `python-dotenv` | `>=1.0.0` | **YES** | `1.2.2` | REAL ACTIVE DEPENDENCY (Env loading) |
| `streamlit>=1.38.0` | `streamlit` | `>=1.38.0` | **YES** | `1.63.0` | REAL ACTIVE DEPENDENCY (Primary UI) |
| `pandas>=2.2.0` | `pandas` | `>=2.2.0` | **YES** | `3.0.5` | REAL ACTIVE DEPENDENCY (Dataframes & Tables) |
| `openpyxl>=3.1.0` | `openpyxl` | `>=3.1.0` | **YES** | `3.1.5` | REAL ACTIVE DEPENDENCY (Excel export) |
| `python-docx>=1.1.0` | `python-docx` | `>=1.1.0` | **YES** | `1.2.0` | REAL ACTIVE DEPENDENCY (Word report generation) |
| `requests>=2.31.0` | `requests` | `>=2.31.0` | **YES** | `2.33.0` | REAL ACTIVE DEPENDENCY (HTTP client) |
| `httpx>=0.27.0` | `httpx` | `>=0.27.0` | **YES** | `0.28.1` | REAL ACTIVE DEPENDENCY (Async HTTP) |
| `curl_cffi>=0.7.0` | `curl_cffi` | `>=0.7.0` | **YES** | `0.16.3` | REAL ACTIVE DEPENDENCY (TLS impersonation scraper) |
| `beautifulsoup4>=4.12.0` | `beautifulsoup4` | `>=4.12.0` | **YES** | `4.15.0` | REAL ACTIVE DEPENDENCY (HTML parsing) |
| `lxml>=5.2.0` | `lxml` | `>=5.2.0` | **YES** | `6.1.3` | REAL ACTIVE DEPENDENCY (XML/HTML backend) |
| `browser-use>=0.1.0` | `browser-use` | `>=0.1.0` | **YES** | `0.13.8` | OPTIONAL / CONDITIONAL (Universal scraper / Cloud) |
| `sqlite-utils>=3.37.0` | `sqlite-utils` | `>=3.37.0` | **YES** | `4.2.1` | REAL ACTIVE DEPENDENCY (SQLite operations) |
| `supabase>=2.0.0` | `supabase` | `>=2.0.0` | **MISSING** | `NOT INSTALLED` | LEGACY / OPTIONAL (Subscription was purged; client exists) |
| `openai>=1.50.0` | `openai` | `>=1.50.0` | **YES** | `2.26.0` | REAL ACTIVE DEPENDENCY (NIM client uses OpenAI protocol) |
| `anthropic>=0.39.0` | `anthropic` | `>=0.39.0` | **YES** | `0.76.0` | OPTIONAL / FALLBACK (Secondary LLM provider) |
| `google-generativeai>=0.8.0` | `google-generativeai` | `>=0.8.0` | **YES** | `0.8.6` | OPTIONAL / FALLBACK (Gemini API provider) |
| `pytrends>=4.9.0` | `pytrends` | `>=4.9.0` | **YES** | `4.9.2` | OPTIONAL / ACTIVE (Google Trends scraper) |
| `statsmodels>=0.14.0` | `statsmodels` | `>=0.14.0` | **YES** | `0.15.0` | OPTIONAL (Trend regression & forecasting) |
| `scikit-learn>=1.5.0` | `scikit-learn` | `>=1.5.0` | **YES** | `1.9.1` | OPTIONAL (Clustering & feature modeling) |
| `numpy>=1.26.0` | `numpy` | `>=1.26.0` | **YES** | `2.5.3` | REAL ACTIVE DEPENDENCY (Numeric calculations) |
| `asyncio-mqtt>=0.10.0` | `asyncio-mqtt` | `>=0.10.0` | **YES** | `0.16.2` | UNUSED / LEGACY (MQTT telemetry - no active broker) |
| `aiofiles>=24.0.0` | `aiofiles` | `>=24.0.0` | **YES** | `25.1.0` | REAL ACTIVE DEPENDENCY (Async file I/O) |
| `python-dateutil>=2.9.0` | `python-dateutil` | `>=2.9.0` | **YES** | `2.9.0.post0` | REAL ACTIVE DEPENDENCY (Date parsing) |
| `tqdm>=4.66.0` | `tqdm` | `>=4.66.0` | **YES** | `4.70.1` | REAL ACTIVE DEPENDENCY (CLI progress bars) |
| `tenacity>=8.3.0` | `tenacity` | `>=8.3.0` | **YES** | `9.1.4` | REAL ACTIVE DEPENDENCY (Retry decorator) |
| `pillow>=10.0.0` | `pillow` | `>=10.0.0` | **YES** | `12.3.0` | REAL ACTIVE DEPENDENCY (Image handling) |
| `pyyaml>=6.0.1` | `pyyaml` | `>=6.0.1` | **YES** | `6.0.3` | REAL ACTIVE DEPENDENCY (YAML config) |
| `jsonschema>=4.23.0` | `jsonschema` | `>=4.23.0` | **YES** | `4.26.0` | REAL ACTIVE DEPENDENCY (JSON Schema validation) |
| `structlog>=24.1.0` | `structlog` | `>=24.1.0` | **YES** | `26.1.0` | REAL ACTIVE DEPENDENCY (Structured logging) |
| `rich>=13.7.0` | `rich` | `>=13.7.0` | **YES** | `14.3.3` | REAL ACTIVE DEPENDENCY (Terminal formatting) |
| `pytest>=8.2.0` | `pytest` | `>=8.2.0` | **YES** | `9.1.1` | REAL ACTIVE DEPENDENCY (Test framework) |
| `pytest-asyncio>=0.23.0` | `pytest-asyncio` | `>=0.23.0` | **YES** | `1.4.0` | REAL ACTIVE DEPENDENCY (Async test runner) |
| `pytest-cov>=5.0.0` | `pytest-cov` | `>=5.0.0` | **YES** | `7.1.0` | REAL ACTIVE DEPENDENCY (Coverage reporter) |
| `pytest-mock>=3.13.0` | `pytest-mock` | `>=3.13.0` | **YES** | `3.15.1` | REAL ACTIVE DEPENDENCY (Mocking fixtures) |
| `pytest-xdist>=3.5.0` | `pytest-xdist` | `>=3.5.0` | **YES** | `3.8.0` | REAL ACTIVE DEPENDENCY (Parallel test execution) |
| `mypy>=1.10.0` | `mypy` | `>=1.10.0` | **YES** | `2.3.1` | DEV TOOL (Static type checker) |
| `types-requests>=2.31.0` | `types-requests` | `>=2.31.0` | **YES** | `2.33.0.20260906` | DEV TOOL (Type stubs) |
| `types-python-dateutil>=2.9.0` | `types-python-dateutil` | `>=2.9.0` | **YES** | `2.9.0.20260807` | DEV TOOL (Type stubs) |
| `razorpay>=2.0.0` | `razorpay` | `>=2.0.0` | **MISSING** | `NOT INSTALLED` | LEGACY / UNUSED (Subscription payments purged in Phase 1) |