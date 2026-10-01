import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root before any key reads
_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")

BASE_DIR = _BASE_DIR

# ── NVIDIA NIM Cluster (keys loaded from .env) ───────────────────────────
NIM_API_KEYS = [
    k for k in [
        os.getenv(f"NIM_API_KEY_{i}", "") for i in range(1, 11)
    ] if k.strip()
]
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# ── NIM Model Matrix (configured for verified active endpoints) ─────────
NIM_MODELS = {
    "deep_reasoning":         "meta/llama-3.2-11b-vision-instruct",
    "ultra_reasoning":        "meta/llama-3.2-11b-vision-instruct",
    "long_context_synthesis": "meta/llama-3.2-11b-vision-instruct",
    "fast_triage":            "meta/llama-3.2-11b-vision-instruct",
    "vision_multimodal":      "meta/llama-3.2-11b-vision-instruct",
    "adversarial_critic":     "meta/llama-3.2-11b-vision-instruct",
    "nemotron_scout":         "nvidia/nemotron-3-ultra-550b-a55b",
    "nemotron_arbiter":       "nvidia/nemotron-3-ultra-550b-a55b",
    "nemotron_ultra":         "nvidia/nemotron-3-ultra-550b-a55b",
    "lightning_fast":         "meta/llama-3.2-11b-vision-instruct",
}

# ── Swarm Agent Role Matrix ───────────────────────────────────────────────
SWARM_ROLES = {
    "trend_scout": {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "task_type": "nemotron_scout",
        "system_prompt": "You are the Lead Open-Web Trend Scout. Identify emerging high-velocity viral products and evaluate search momentum."
    },
    "marketplace_harvester": {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "task_type": "ultra_reasoning",
        "system_prompt": "You are the Multi-Marketplace Catalog Harvester. Match trend signals to active high-velocity listings on Amazon, Flipkart, Meesho, and Shopify."
    },
    "defect_analyst": {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "task_type": "deep_reasoning",
        "system_prompt": "You are the Chief Quality Engineer & Defect Miner. Synthesize multi-source 3-star reviews into structural BOM upgrades."
    },
    "economics_auditor": {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "task_type": "long_context_synthesis",
        "system_prompt": "You are the 15-Factor Unit Economics Lead. Validate landed COGS, RTO reserves, FBA fees, and stress resilience."
    },
    "chief_arbiter": {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "task_type": "nemotron_arbiter",
        "system_prompt": "You are the Supreme Investment Arbiter. Issue final consensus verdicts and flag false-positive backtrack alerts."
    }
}

# ── Subscription Plans Configuration (Centralized) ───────────────────────────
PLAN_CONFIG = {
    "STARTER": {
        "display_name": "Starter",
        "description": "For occasional additional usage",
        "price": 149,
        "currency": "INR",
        "billing_period": "monthly",
        "usage_limit": 10,
        "features": [
            "10 paid uses per month",
            "Access to all AI agents",
            "Priority processing",
            "Email support"
        ],
        "sort_order": 1
    },
    "PRO": {
        "display_name": "Pro",
        "description": "For regular users",
        "price": 299,
        "currency": "INR",
        "billing_period": "monthly",
        "usage_limit": 50,
        "features": [
            "50 paid uses per month",
            "Access to all AI agents",
            "Priority processing",
            "Email + chat support",
            "Advanced analytics"
        ],
        "sort_order": 2
    },
    "PREMIUM": {
        "display_name": "Premium",
        "description": "For heavy/frequent users",
        "price": 499,
        "currency": "INR",
        "billing_period": "monthly",
        "usage_limit": 200,
        "features": [
            "200 paid uses per month",
            "Access to all AI agents",
            "Priority processing",
            "Dedicated support",
            "Advanced analytics",
            "Custom integrations"
        ],
        "sort_order": 3
    }
}

# ── Free Weekly Usage Configuration ─────────────────────────────────────────
FREE_WEEKLY_LIMIT = 3
FREE_WEEK_START_DAY = 0  # Monday (0=Monday, 6=Sunday)
TIMEZONE = "Asia/Kolkata"

# ── Razorpay Configuration ──────────────────────────────────────────────────
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# ── LLM Routing Configuration (NIM primary, Gemini fallback) ─────────────────
# No Ollama — user does not have local LLM server
LLM_ROUTING = {
    "scout":        ["nim"],
    "harvester":    ["nim"],
    "defect_miner": ["nim"],
    "economics":    ["nim"],
    "arbiter":      ["nim"],
    "general":      ["nim"],
}

# ── Google Trends & Prediction Engine Configuration ──────────────────────────
GOOGLE_TRENDS_ENABLED = True
PREDICTION_ENABLED = True
TRENDING_LOOKBACK_DAYS = 15         # "Last N days" trending window
PREDICTION_HORIZONS = [15, 30, 90]  # 15 days, 1 month, 3 months

# ── Gemini API (fallback LLM if NIM exhausted) ───────────────────────────────
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── Data Storage Paths ──────────────────────────────────────────────────────
DATABASE_PATH      = BASE_DIR / "data" / "research_engine.db"
EXCEL_MASTER_PATH  = BASE_DIR / "APRS_Master_Product_Intelligence.xlsx"
RAW_DATA_DIR       = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
LOGS_DIR           = BASE_DIR / "logs"

# ── Supported Geographic Regions & Market Rules ────────────────────────────
REGIONAL_PROFILES = {
    "India": {
        "currency":           "INR",
        "symbol":             "₹",
        "target_aov_min":     799,
        "target_aov_max":     2499,
        "sweet_spot_msrp":    1299,
        "default_cod_pct":    0.35,
        "default_rto_pct":    0.18,
        "platform_fee_pct":   0.05,
        "sourcing_hubs":      ["Tirupur (Textiles)", "Surat (Apparel/Jewelry)", "Moradabad (Brass/Home)", "Jaipur (Handicrafts)", "Shenzhen (Electronics)", "Yiwu (Small Goods)"],
        "marketplaces":       ["Meesho", "Amazon IN", "Flipkart", "Myntra", "Blinkit Trends"],
    },
    "USA": {
        "currency":           "USD",
        "symbol":             "$",
        "target_aov_min":     35.00,
        "target_aov_max":     150.00,
        "sweet_spot_msrp":    59.99,
        "default_cod_pct":    0.0,
        "default_rto_pct":    0.04,
        "platform_fee_pct":   0.05,
        "sourcing_hubs":      ["Yiwu (Small Goods)", "Shenzhen (Electronics)", "Dongguan (Hardware)", "Ningbo (Appliances)", "Mexico (Nearshoring)"],
        "marketplaces":       ["Amazon US", "TikTok Shop", "Meta Ad Library", "Shopify DTC"],
    },
    "GCC_MiddleEast": {
        "currency":           "USD",
        "symbol":             "$",
        "target_aov_min":     65.00,
        "target_aov_max":     250.00,
        "sweet_spot_msrp":    95.00,
        "default_cod_pct":    0.25,
        "default_rto_pct":    0.12,
        "platform_fee_pct":   0.06,
        "sourcing_hubs":      ["Shenzhen (Electronics)", "Guangzhou (Beauty/Fragrance)", "Yiwu (Accessories)"],
        "marketplaces":       ["Amazon AE/SA", "Noon", "TikTok Shop GCC", "Snapchat Direct"],
    },
    "Europe": {
        "currency":           "EUR",
        "symbol":             "€",
        "target_aov_min":     40.00,
        "target_aov_max":     120.00,
        "sweet_spot_msrp":    65.00,
        "default_cod_pct":    0.0,
        "default_rto_pct":    0.08,
        "platform_fee_pct":   0.05,
        "sourcing_hubs":      ["Turkey (Textiles/Ceramics)", "Poland (Packaging)", "Ningbo (Appliances)", "Shenzhen (Electronics)"],
        "marketplaces":       ["Amazon DE/UK", "Otto", "Shopify EU", "Klarna Trends"],
    },
    "UK": {
        "currency":           "GBP",
        "symbol":             "£",
        "target_aov_min":     25.00,
        "target_aov_max":     100.00,
        "sweet_spot_msrp":    45.00,
        "default_cod_pct":    0.0,
        "default_rto_pct":    0.06,
        "platform_fee_pct":   0.05,
        "sourcing_hubs":      ["Shenzhen (Electronics)", "Ningbo (Appliances)", "Turkey (Textiles)"],
        "marketplaces":       ["Amazon UK", "eBay UK", "Shopify UK"],
    },
}
