"""
Supabase Client - Backend for authentication, database, and subscription management.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pytz

# Load environment from infooo
_ROOT = Path(__file__).resolve().parent.parent
_infooo = _ROOT / "infooo"
if _infooo.exists():
    from dotenv import load_dotenv
    load_dotenv(_infooo)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

_supabase_client: Optional[Client] = None
_supabase_admin: Optional[Client] = None


def get_supabase() -> Client:
    """Get or create Supabase client (anon key for user operations)."""
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_AVAILABLE:
            raise RuntimeError("supabase-py not installed. Run: pip install supabase")
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY required in environment")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase_client


def get_supabase_admin() -> Client:
    """Get or create Supabase admin client (service role for backend operations)."""
    global _supabase_admin
    if _supabase_admin is None:
        if not SUPABASE_AVAILABLE:
            raise RuntimeError("supabase-py not installed. Run: pip install supabase")
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY required for admin operations")
        _supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase_admin


# Database table names
USERS_TABLE = "users"
SUBSCRIPTION_PLANS_TABLE = "subscription_plans"
SUBSCRIPTIONS_TABLE = "subscriptions"
USAGE_PERIODS_TABLE = "usage_periods"
PAYMENTS_TABLE = "payments"
WEBHOOK_EVENTS_TABLE = "webhook_events"


# Plan configuration (matches infooo)
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

FREE_WEEKLY_LIMIT = 3
FREE_WEEK_START_DAY = 0  # Monday
TIMEZONE = "Asia/Kolkata"


def get_current_week_period() -> tuple[str, str]:
    """Get current week's start and end dates in IST."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    days_since_week_start = (now.weekday() - FREE_WEEK_START_DAY) % 7
    week_start = now - timedelta(days=days_since_week_start)
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")


def init_supabase_tables():
    """Initialize Supabase tables via SQL (run once via Supabase SQL Editor)."""
    # This is reference SQL - run in Supabase Dashboard > SQL Editor
    sql = f"""
    -- Enable UUID extension
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    -- Users table (extends Supabase auth.users)
    CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
        user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT,
        avatar_url TEXT,
        provider TEXT DEFAULT 'email',
        provider_id TEXT,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Subscription plans
    CREATE TABLE IF NOT EXISTS {SUBSCRIPTION_PLANS_TABLE} (
        plan_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        display_name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        currency TEXT DEFAULT 'INR',
        billing_period TEXT DEFAULT 'monthly',
        usage_limit INTEGER NOT NULL,
        features_json JSONB,
        is_active BOOLEAN DEFAULT true,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Subscriptions
    CREATE TABLE IF NOT EXISTS {SUBSCRIPTIONS_TABLE} (
        subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES {USERS_TABLE}(user_id) ON DELETE CASCADE,
        plan_id TEXT NOT NULL REFERENCES {SUBSCRIPTION_PLANS_TABLE}(plan_id),
        provider TEXT DEFAULT 'razorpay',
        provider_subscription_id TEXT,
        provider_customer_id TEXT,
        status TEXT NOT NULL DEFAULT 'inactive',
        price INTEGER NOT NULL,
        currency TEXT DEFAULT 'INR',
        current_period_start TIMESTAMPTZ,
        current_period_end TIMESTAMPTZ,
        cancel_at_period_end BOOLEAN DEFAULT false,
        cancelled_at TIMESTAMPTZ,
        trial_end TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Usage periods (weekly tracking)
    CREATE TABLE IF NOT EXISTS {USAGE_PERIODS_TABLE} (
        period_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES {USERS_TABLE}(user_id) ON DELETE CASCADE,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        free_limit INTEGER DEFAULT 3,
        free_used INTEGER DEFAULT 0,
        paid_limit INTEGER DEFAULT 0,
        paid_used INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, period_start)
    );

    -- Payments
    CREATE TABLE IF NOT EXISTS {PAYMENTS_TABLE} (
        payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES {USERS_TABLE}(user_id) ON DELETE CASCADE,
        subscription_id UUID REFERENCES {SUBSCRIPTIONS_TABLE}(subscription_id) ON DELETE SET NULL,
        provider TEXT DEFAULT 'razorpay',
        provider_order_id TEXT,
        provider_payment_id TEXT,
        provider_signature TEXT,
        amount INTEGER NOT NULL,
        currency TEXT DEFAULT 'INR',
        status TEXT NOT NULL DEFAULT 'pending',
        plan_id TEXT,
        plan_name TEXT,
        metadata_json JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Webhook events (idempotency)
    CREATE TABLE IF NOT EXISTS {WEBHOOK_EVENTS_TABLE} (
        event_id TEXT PRIMARY KEY,
        provider TEXT DEFAULT 'razorpay',
        event_type TEXT NOT NULL,
        payload_json JSONB NOT NULL,
        processed BOOLEAN DEFAULT false,
        processed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON {SUBSCRIPTIONS_TABLE}(user_id);
    CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON {SUBSCRIPTIONS_TABLE}(status);
    CREATE INDEX IF NOT EXISTS idx_usage_periods_user_id ON {USAGE_PERIODS_TABLE}(user_id);
    CREATE INDEX IF NOT EXISTS idx_usage_periods_dates ON {USAGE_PERIODS_TABLE}(period_start, period_end);
    CREATE INDEX IF NOT EXISTS idx_payments_user_id ON {PAYMENTS_TABLE}(user_id);
    CREATE INDEX IF NOT EXISTS idx_payments_subscription_id ON {PAYMENTS_TABLE}(subscription_id);
    CREATE INDEX IF NOT EXISTS idx_webhook_events_provider_id ON {WEBHOOK_EVENTS_TABLE}(provider, event_id);

    -- RLS Policies
    ALTER TABLE {USERS_TABLE} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {SUBSCRIPTION_PLANS_TABLE} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {SUBSCRIPTIONS_TABLE} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {USAGE_PERIODS_TABLE} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {PAYMENTS_TABLE} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {WEBHOOK_EVENTS_TABLE} ENABLE ROW LEVEL SECURITY;

    -- Users can read/update their own profile
    CREATE POLICY "Users can read own profile" ON {USERS_TABLE}
        FOR SELECT USING (auth.uid() = user_id);
    CREATE POLICY "Users can update own profile" ON {USERS_TABLE}
        FOR UPDATE USING (auth.uid() = user_id);

    -- Plans are readable by all authenticated users
    CREATE POLICY "Plans readable by all" ON {SUBSCRIPTION_PLANS_TABLE}
        FOR SELECT USING (auth.role() = 'authenticated');

    -- Users can read their own subscriptions
    CREATE POLICY "Users read own subscriptions" ON {SUBSCRIPTIONS_TABLE}
        FOR SELECT USING (auth.uid() = user_id);

    -- Users can read their own usage periods
    CREATE POLICY "Users read own usage" ON {USAGE_PERIODS_TABLE}
        FOR SELECT USING (auth.uid() = user_id);
    CREATE POLICY "Users upsert own usage" ON {USAGE_PERIODS_TABLE}
        FOR INSERT WITH CHECK (auth.uid() = user_id);
    CREATE POLICY "Users update own usage" ON {USAGE_PERIODS_TABLE}
        FOR UPDATE USING (auth.uid() = user_id);

    -- Users can read their own payments
    CREATE POLICY "Users read own payments" ON {PAYMENTS_TABLE}
        FOR SELECT USING (auth.uid() = user_id);

    -- Seed plans
    INSERT INTO {SUBSCRIPTION_PLANS_TABLE} (plan_id, name, display_name, description, price, currency, billing_period, usage_limit, features_json, sort_order)
    VALUES
    ('STARTER', 'starter', 'Starter', 'For occasional additional usage', 149, 'INR', 'monthly', 10,
     '["10 paid uses per month", "Access to all AI agents", "Priority processing", "Email support"]'::jsonb, 1),
    ('PRO', 'pro', 'Pro', 'For regular users', 299, 'INR', 'monthly', 50,
     '["50 paid uses per month", "Access to all AI agents", "Priority processing", "Email + chat support", "Advanced analytics"]'::jsonb, 2),
    ('PREMIUM', 'premium', 'Premium', 'For heavy/frequent users', 499, 'INR', 'monthly', 200,
     '["200 paid uses per month", "Access to all AI agents", "Priority processing", "Dedicated support", "Advanced analytics", "Custom integrations"]'::jsonb, 3)
    ON CONFLICT (plan_id) DO UPDATE SET
        display_name = EXCLUDED.display_name,
        price = EXCLUDED.price,
        usage_limit = EXCLUDED.usage_limit,
        features_json = EXCLUDED.features_json;
    """
    return sql


# Initialize plans in Supabase
async def seed_plans():
    """Seed subscription plans in Supabase."""
    admin = get_supabase_admin()
    for plan_key, config in PLAN_CONFIG.items():
        admin.table(SUBSCRIPTION_PLANS_TABLE).upsert({
            "plan_id": plan_key,
            "name": plan_key.lower(),
            "display_name": config["display_name"],
            "description": config["description"],
            "price": config["price"],
            "currency": config["currency"],
            "billing_period": config["billing_period"],
            "usage_limit": config["usage_limit"],
            "features_json": config["features"],
            "sort_order": config["sort_order"]
        }).execute()


# Import datetime at the top
from datetime import datetime
import pytz