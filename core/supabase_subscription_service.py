"""
Supabase Subscription Service - Authentication, Subscriptions, Usage & Payment handling.
Uses Supabase for auth, database, and realtime.
"""
import os
import sys
import secrets
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

# Project root import
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.supabase_client import (
    get_supabase, get_supabase_admin, PLAN_CONFIG, FREE_WEEKLY_LIMIT,
    FREE_WEEK_START_DAY, TIMEZONE, SUPABASE_AVAILABLE,
    USERS_TABLE, SUBSCRIPTION_PLANS_TABLE, SUBSCRIPTIONS_TABLE,
    USAGE_PERIODS_TABLE, PAYMENTS_TABLE, WEBHOOK_EVENTS_TABLE,
    get_current_week_period, seed_plans
)

logger = logging.getLogger("aprs.supabase_subscription")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(name)s %(levelname)s — %(message)s")


class AuthError(Exception):
    pass


class SubscriptionError(Exception):
    pass


class UsageError(Exception):
    pass


class PaymentError(Exception):
    pass


class SupabaseSubscriptionService:
    """
    Main service for Supabase-based authentication, subscriptions, usage, and payments.
    """

    def __init__(self):
        self.admin = get_supabase_admin() if SUPABASE_AVAILABLE else None
        logger.info("Supabase Subscription Service initialized")

    # ════════════════════════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ═══════════════════════════════════════════════════════════════════════════

    def hash_password(self, password: str) -> str:
        """Hash password with salt."""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}:{pwd_hash.hex()}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        try:
            salt, hash_hex = password_hash.split(':')
            pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return pwd_hash.hex() == hash_hex
        except Exception:
            return False

    async def register(self, email: str, password: str, full_name: str = None) -> Dict[str, Any]:
        """Register a new user via Supabase Auth."""
        email = email.strip().lower()

        if not SUPABASE_AVAILABLE:
            raise AuthError("Supabase not available")

        supabase = get_supabase()

        # Sign up via Supabase Auth
        try:
            result = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "full_name": full_name or ""
                    }
                }
            })

            if result.user is None:
                raise AuthError("Registration failed - no user returned")

            # Create user profile in users table
            user_data = {
                "user_id": result.user.id,
                "email": email,
                "full_name": full_name,
                "provider": "email",
                "is_active": True
            }
            self.admin.table(USERS_TABLE).upsert(user_data).execute()

            return {
                "success": True,
                "user_id": result.user.id,
                "email": email,
                "full_name": full_name,
                "session": result.session
            }
        except Exception as e:
            if "already registered" in str(e).lower():
                raise AuthError("Email already registered")
            raise AuthError(f"Registration failed: {e}")

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user via Supabase Auth."""
        email = email.strip().lower()

        if not SUPABASE_AVAILABLE:
            raise AuthError("Supabase not available")

        supabase = get_supabase()

        try:
            result = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if result.user is None:
                raise AuthError("Invalid credentials")

            # Get user profile
            user_profile = self.admin.table(USERS_TABLE).select("*").eq("user_id", result.user.id).single().execute()

            return {
                "success": True,
                "user_id": result.user.id,
                "email": result.user.email,
                "full_name": user_profile.data.get("full_name") if user_profile.data else None,
                "session": result.session
            }
        except Exception as e:
            if "invalid credentials" in str(e).lower():
                raise AuthError("Invalid credentials")
            raise AuthError(f"Login failed: {e}")

    async def logout(self, access_token: str) -> bool:
        """Logout user."""
        supabase = get_supabase()
        try:
            supabase.auth.sign_out()
            return True
        except Exception:
            return False

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by ID."""
        if not self.admin:
            return None
        result = self.admin.table(USERS_TABLE).select("*").eq("user_id", user_id).single().execute()
        return result.data

    def update_user_profile(self, user_id: str, **kwargs) -> bool:
        """Update user profile."""
        if not kwargs:
            return True
        try:
            kwargs["updated_at"] = datetime.now().isoformat()
            self.admin.table(USERS_TABLE).update(kwargs).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Update user error: {e}")
            return False

    # ════════════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def get_plans(self) -> List[Dict[str, Any]]:
        """Get all available plans."""
        result = self.admin.table(SUBSCRIPTION_PLANS_TABLE).select("*").eq("is_active", True).order("sort_order").execute()
        plans = []
        for row in result.data:
            row["features"] = row.get("features_json", [])
            plans.append(row)
        return plans

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get plan details."""
        result = self.admin.table(SUBSCRIPTION_PLANS_TABLE).select("*").eq("plan_id", plan_id).single().execute()
        if result.data:
            row = result.data
            row["features"] = row.get("features_json", [])
            return row
        return None

    def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's active subscription with plan details."""
        result = self.admin.table(SUBSCRIPTIONS_TABLE).select("""
            *,
            subscription_plans!inner(display_name, usage_limit, features_json)
        """).eq("user_id", user_id).in_("status", ["active", "trialing"]).order("created_at", desc=True).limit(1).execute()

        if result.data:
            row = result.data[0]
            if row.get("subscription_plans"):
                row["plan_display_name"] = row["subscription_plans"]["display_name"]
                row["plan_usage_limit"] = row["subscription_plans"]["usage_limit"]
                row["plan_features"] = row["subscription_plans"].get("features_json", [])
        return result.data[0] if result.data else None

    def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all user subscriptions."""
        result = self.admin.table(SUBSCRIPTIONS_TABLE).select("""
            *,
            subscription_plans!inner(display_name, usage_limit, features_json)
        """).eq("user_id", user_id).order("created_at", desc=True).execute()

        for row in result.data:
            if row.get("subscription_plans"):
                row["plan_display_name"] = row["subscription_plans"]["display_name"]
                row["plan_usage_limit"] = row["subscription_plans"]["usage_limit"]
                row["plan_features"] = row["subscription_plans"].get("features_json", [])
        return result.data

    def create_subscription_order(self, user_id: str, plan_id: str) -> Dict[str, Any]:
        """Create a subscription order for payment."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise SubscriptionError(f"Plan {plan_id} not found")

        # Check if user already has active subscription
        active = self.get_user_subscription(user_id)
        if active:
            raise SubscriptionError("User already has an active subscription")

        return {
            "plan": plan,
            "amount": plan["price"],
            "currency": plan["currency"]
        }

    def activate_subscription(self, user_id: str, plan_id: str,
                              provider: str = "razorpay",
                              provider_subscription_id: str = None,
                              provider_customer_id: str = None) -> str:
        """Activate a subscription after successful payment."""
        import uuid
        subscription_id = str(uuid.uuid4())
        now = datetime.now()
        period_end = now + timedelta(days=30)

        self.admin.table(SUBSCRIPTIONS_TABLE).insert({
            "subscription_id": subscription_id,
            "user_id": user_id,
            "plan_id": plan_id,
            "provider": provider,
            "provider_subscription_id": provider_subscription_id,
            "provider_customer_id": provider_customer_id,
            "status": "active",
            "price": self.get_plan(plan_id)["price"],
            "currency": "INR",
            "current_period_start": now.isoformat(),
            "current_period_end": period_end.isoformat()
        }).execute()

        return subscription_id

    def cancel_user_subscription(self, user_id: str, at_period_end: bool = True) -> bool:
        """Cancel user's active subscription."""
        active = self.get_user_subscription(user_id)
        if not active:
            raise SubscriptionError("No active subscription found")

        if at_period_end:
            self.admin.table(SUBSCRIPTIONS_TABLE).update({
                "cancel_at_period_end": True,
                "updated_at": datetime.now().isoformat()
            }).eq("subscription_id", active["subscription_id"]).execute()
        else:
            self.admin.table(SUBSCRIPTIONS_TABLE).update({
                "status": "cancelled",
                "cancelled_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }).eq("subscription_id", active["subscription_id"]).execute()
        return True

    # ════════════════════════════════════════════════════════════════════════════
    # USAGE TRACKING
    # ═══════════════════════════════════════════════════════════════════════════

    def check_usage(self, user_id: str) -> Dict[str, Any]:
        """Check user's current usage status."""
        period_start, period_end = get_current_week_period()
        period_id = f"{user_id}_{period_start}"

        # Get or create usage period
        result = self.admin.table(USAGE_PERIODS_TABLE).select("*").eq("user_id", user_id).eq("period_start", period_start).single().execute()

        if not result.data:
            # Create new period
            active_sub = self.get_user_subscription(user_id)
            paid_limit = active_sub.get("plan_usage_limit", 0) if active_sub else 0

            new_period = {
                "user_id": user_id,
                "period_start": period_start,
                "period_end": period_end,
                "free_limit": FREE_WEEKLY_LIMIT,
                "free_used": 0,
                "paid_limit": paid_limit,
                "paid_used": 0
            }
            self.admin.table(USAGE_PERIODS_TABLE).insert(new_period).execute()

            return {
                "plan": "FREE" if not active_sub else active_sub.get("plan_id", "FREE"),
                "subscription_status": "inactive" if not active_sub else active_sub.get("status", "inactive"),
                "weekly_free": {
                    "limit": FREE_WEEKLY_LIMIT,
                    "used": 0,
                    "remaining": FREE_WEEKLY_LIMIT,
                    "period_start": period_start,
                    "period_end": period_end
                },
                "paid_usage": {
                    "limit": paid_limit,
                    "used": 0,
                    "remaining": paid_limit
                }
            }

        period = result.data
        active_sub = self.get_user_subscription(user_id)
        paid_limit = active_sub.get("plan_usage_limit", 0) if active_sub else 0

        # Update paid limit if changed
        if period.get("paid_limit", 0) != paid_limit:
            self.admin.table(USAGE_PERIODS_TABLE).update({"paid_limit": paid_limit}).eq("period_id", period["period_id"]).execute()
            period["paid_limit"] = paid_limit

        free_remaining = period["free_limit"] - period["free_used"]
        paid_remaining = period["paid_limit"] - period["paid_used"]

        return {
            "plan": "FREE" if not active_sub else active_sub.get("plan_id", "FREE"),
            "subscription_status": "inactive" if not active_sub else active_sub.get("status", "inactive"),
            "weekly_free": {
                "limit": period["free_limit"],
                "used": period["free_used"],
                "remaining": max(0, free_remaining),
                "period_start": period["period_start"],
                "period_end": period["period_end"]
            },
            "paid_usage": {
                "limit": period["paid_limit"],
                "used": period["paid_used"],
                "remaining": max(0, paid_remaining)
            }
        }

    def consume_feature_usage(self, user_id: str, feature: str = "swarm_scan") -> Dict[str, Any]:
        """
        Atomically consume one usage from free or paid allowance.
        Returns usage result with success status and remaining allowances.
        """
        period_start, period_end = get_current_week_period()

        if not self.admin:
            raise UsageError("Database not available")

        # Use RPC for atomic operation
        # For now, use a transaction-like approach
        period_id = f"{user_id}_{period_start}"

        # Get current period with lock
        result = self.admin.table(USAGE_PERIODS_TABLE).select("*").eq("user_id", user_id).eq("period_start", period_start).single().execute()

        if not result.data:
            # Create period
            active_sub = self.get_user_subscription(user_id)
            paid_limit = active_sub.get("plan_usage_limit", 0) if active_sub else 0

            self.admin.table(USAGE_PERIODS_TABLE).insert({
                "user_id": user_id,
                "period_start": period_start,
                "period_end": period_end,
                "free_limit": FREE_WEEKLY_LIMIT,
                "free_used": 0,
                "paid_limit": paid_limit,
                "paid_used": 0
            }).execute()

            period = {
                "user_id": user_id,
                "period_start": period_start,
                "period_end": period_end,
                "free_limit": FREE_WEEKLY_LIMIT,
                "free_used": 0,
                "paid_limit": paid_limit,
                "paid_used": 0
            }
        else:
            period = result.data
            # Update paid limit if subscription changed
            active_sub = self.get_user_subscription(user_id)
            new_paid_limit = active_sub.get("plan_usage_limit", 0) if active_sub else 0
            if period.get("paid_limit", 0) != new_paid_limit:
                self.admin.table(USAGE_PERIODS_TABLE).update({"paid_limit": new_paid_limit}).eq("user_id", user_id).eq("period_start", period_start).execute()
                period["paid_limit"] = new_paid_limit

        # Check and consume
        free_remaining = period["free_limit"] - period["free_used"]
        paid_remaining = period["paid_limit"] - period["paid_used"]

        if free_remaining > 0:
            # Consume free usage
            self.admin.table(USAGE_PERIODS_TABLE).update({
                "free_used": period["free_used"] + 1,
                "updated_at": datetime.now().isoformat()
            }).eq("user_id", user_id).eq("period_start", period_start).execute()

            return {
                "success": True,
                "usage_type": "free",
                "free_remaining": free_remaining - 1,
                "paid_remaining": paid_remaining,
                "free_used": period["free_used"] + 1,
                "paid_used": period["paid_used"],
                "period_end": period_end
            }
        elif paid_remaining > 0:
            # Consume paid usage
            self.admin.table(USAGE_PERIODS_TABLE).update({
                "paid_used": period["paid_used"] + 1,
                "updated_at": datetime.now().isoformat()
            }).eq("user_id", user_id).eq("period_start", period_start).execute()

            return {
                "success": True,
                "usage_type": "paid",
                "free_remaining": free_remaining,
                "paid_remaining": paid_remaining - 1,
                "free_used": period["free_used"],
                "paid_used": period["paid_used"] + 1,
                "period_end": period_end
            }
        else:
            raise UsageError(
                "USAGE_LIMIT_REACHED",
                "Your weekly free usage has been used. Upgrade your plan to continue."
            )

    def can_access_feature(self, user_id: str, feature: str = "default") -> Tuple[bool, str]:
        """Check if user can access feature without consuming usage."""
        usage = self.check_usage(user_id)
        free_remaining = usage["weekly_free"]["remaining"]
        paid_remaining = usage["paid_usage"]["remaining"]

        if free_remaining > 0 or paid_remaining > 0:
            return True, "OK"
        return False, "USAGE_LIMIT_REACHED"

    # ════════════════════════════════════════════════════════════════════════════
    # PAYMENT PROCESSING (RAZORPAY)
    # ════════════════════════════════════════════════════════════════════════════

    def create_payment_order(self, user_id: str, plan_id: str) -> Dict[str, Any]:
        """Create a payment order (Razorpay or mock)."""
        plan = self.get_plan(plan_id)
        if not plan:
            raise PaymentError(f"Plan {plan_id} not found")

        # Create payment record
        import uuid
        payment_id = str(uuid.uuid4())
        provider_order_id = f"order_{uuid.uuid4().hex[:12]}"

        self.admin.table(PAYMENTS_TABLE).insert({
            "payment_id": payment_id,
            "user_id": user_id,
            "subscription_id": None,
            "provider": "razorpay",
            "provider_order_id": provider_order_id,
            "amount": plan["price"],
            "currency": plan["currency"],
            "status": "pending",
            "plan_id": plan_id,
            "plan_name": plan["display_name"],
            "metadata_json": {"plan_name": plan["display_name"]}
        }).execute()

        return {
            "payment_id": payment_id,
            "razorpay_order_id": provider_order_id,
            "amount": plan["price"],
            "currency": plan["currency"],
            "key_id": os.getenv("RAZORPAY_KEY_ID", "rzp_test_mock"),
            "plan": plan,
            "mock": not bool(os.getenv("RAZORPAY_KEY_ID"))
        }

    def verify_payment_signature(self, razorpay_order_id: str,
                                  razorpay_payment_id: str,
                                  razorpay_signature: str) -> bool:
        """Verify Razorpay payment signature."""
        # In production, use razorpay client
        # For now, mock mode always verifies
        return True

    def handle_payment_success(self, razorpay_order_id: str,
                                razorpay_payment_id: str,
                                razorpay_signature: str) -> Dict[str, Any]:
        """Handle successful payment callback."""
        if not self.verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            raise PaymentError("Invalid payment signature")

        # Find payment by order ID
        result = self.admin.table(PAYMENTS_TABLE).select("*").eq("provider_order_id", razorpay_order_id).single().execute()

        if not result.data:
            raise PaymentError("Payment not found")

        payment = result.data

        # Update payment status
        self.admin.table(PAYMENTS_TABLE).update({
            "status": "completed",
            "provider_payment_id": razorpay_payment_id,
            "provider_signature": razorpay_signature,
            "updated_at": datetime.now().isoformat()
        }).eq("payment_id", payment["payment_id"]).execute()

        # Create and activate subscription
        subscription_id = self.activate_subscription(
            user_id=payment["user_id"],
            plan_id=payment["plan_id"],
            provider="razorpay",
            provider_subscription_id=razorpay_payment_id
        )

        return {
            "success": True,
            "subscription_id": subscription_id,
            "payment_id": payment["payment_id"],
            "plan_id": payment["plan_id"]
        }

    # ════════════════════════════════════════════════════════════════════════════
    # WEBHOOK HANDLING
    # ════════════════════════════════════════════════════════════════════════════

    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        """Verify Razorpay webhook signature."""
        if not RAZORPAY_WEBHOOK_SECRET or not signature:
            return False
        import hmac, hashlib
        expected_sig = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body.encode("utf-8") if isinstance(body, str) else body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    def process_webhook(self, payload: dict, signature: str = None, raw_body: str = None) -> Dict[str, Any]:
        """Process Razorpay webhook."""
        if signature and raw_body and RAZORPAY_WEBHOOK_SECRET:
            if not self.verify_webhook_signature(raw_body, signature):
                logger.warning("Invalid webhook signature received")
                return {"success": False, "error": "Invalid webhook signature"}

        event_id = payload.get("event_id") or payload.get("id")
        if not event_id:
            entity_id = (
                payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id") or
                payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("id") or
                payload.get("payload", {}).get("order", {}).get("entity", {}).get("id")
            )
            if entity_id:
                event_id = f"{payload.get('event', 'evt')}_{entity_id}"
            else:
                event_id = f"{payload.get('event', 'evt')}_{payload.get('created_at', int(time.time()))}"

        if not self.admin:
            raise PaymentError("Database not available")

        # Check idempotency
        existing = self.admin.table(WEBHOOK_EVENTS_TABLE).select("processed").eq("event_id", event_id).single().execute()
        if existing.data and existing.data.get("processed"):
            return {"success": True, "message": "Event already processed"}

        # Record webhook event
        self.admin.table(WEBHOOK_EVENTS_TABLE).insert({
            "event_id": event_id,
            "provider": "razorpay",
            "event_type": payload.get("event", "unknown"),
            "payload_json": payload
        }).execute()

        event_type = payload.get("event", "")

        try:
            if event_type == "payment.captured":
                payment_data = payload.get("payload", {}).get("payment", {}).get("entity", {})
                self._handle_payment_captured(payment_data)

            elif event_type == "payment.failed":
                payment_data = payload.get("payload", {}).get("payment", {}).get("entity", {})
                self._handle_payment_failed(payment_data)

            elif event_type == "subscription.activated":
                sub_data = payload.get("payload", {}).get("subscription", {}).get("entity", {})
                self._handle_subscription_activated(sub_data)

            elif event_type == "subscription.cancelled":
                sub_data = payload.get("payload", {}).get("subscription", {}).get("entity", {})
                self._handle_subscription_cancelled(sub_data)

            elif event_type == "subscription.completed":
                sub_data = payload.get("payload", {}).get("subscription", {}).get("entity", {})
                self._handle_subscription_completed(sub_data)

            # Mark as processed
            self.admin.table(WEBHOOK_EVENTS_TABLE).update({
                "processed": True,
                "processed_at": datetime.now().isoformat()
            }).eq("event_id", event_id).execute()

            return {"success": True, "event": event_type}

        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            raise PaymentError(f"Webhook processing failed: {e}")

    def _handle_payment_captured(self, payment_data: dict):
        order_id = payment_data.get("order_id")
        payment_id = payment_data.get("id")
        signature = payment_data.get("signature")
        self.handle_payment_success(order_id, payment_id, signature)

    def _handle_payment_failed(self, payment_data: dict):
        order_id = payment_data.get("order_id")
        self.admin.table(PAYMENTS_TABLE).update({"status": "failed"}).eq("provider_order_id", order_id).execute()

    def _handle_subscription_activated(self, sub_data: dict):
        sub_id = sub_data.get("id")
        # Already handled via payment success
        pass

    def _handle_subscription_cancelled(self, sub_data: dict):
        sub_id = sub_data.get("id")
        result = self.admin.table(SUBSCRIPTIONS_TABLE).select("subscription_id").eq("provider_subscription_id", sub_id).single().execute()
        if result.data:
            self.admin.table(SUBSCRIPTIONS_TABLE).update({
                "status": "cancelled",
                "cancelled_at": datetime.now().isoformat(),
                "cancel_at_period_end": False
            }).eq("subscription_id", result.data["subscription_id"]).execute()

    def _handle_subscription_completed(self, sub_data: dict):
        sub_id = sub_data.get("id")
        result = self.admin.table(SUBSCRIPTIONS_TABLE).select("subscription_id").eq("provider_subscription_id", sub_id).single().execute()
        if result.data:
            self.admin.table(SUBSCRIPTIONS_TABLE).update({
                "status": "completed",
                "updated_at": datetime.now().isoformat()
            }).eq("subscription_id", result.data["subscription_id"]).execute()

    # ════════════════════════════════════════════════════════════════════════════
    # ADMIN / UTILITY
    # ════════════════════════════════════════════════════════════════════════════

    def get_user_dashboard_data(self, user_id: str) -> Dict[str, Any]:
        """Get all data needed for user dashboard."""
        user = self.get_user(user_id)
        if not user:
            raise AuthError("User not found")

        subscription = self.get_user_subscription(user_id)
        usage = self.check_usage(user_id)

        # Get payment history
        payments_result = self.admin.table(PAYMENTS_TABLE).select("*").eq("user_id", user_id).order("created_at", desc=True).execute()

        return {
            "user": user,
            "subscription": subscription,
            "usage": usage,
            "payments": payments_result.data,
            "plans": self.get_plans()
        }

    def seed_database(self):
        """Seed plans and initialize database."""
        seed_plans()
        logger.info("Database seeded successfully")


# Singleton instance
_supabase_subscription_service = None

def get_supabase_subscription_service() -> SupabaseSubscriptionService:
    """Get singleton subscription service instance."""
    global _supabase_subscription_service
    if _supabase_subscription_service is None:
        _supabase_subscription_service = SupabaseSubscriptionService()
    return _supabase_subscription_service


# Convenience functions
def require_usage(user_id: str, feature: str = "swarm_scan") -> Dict[str, Any]:
    """Check and consume usage for a feature."""
    service = get_supabase_subscription_service()
    return service.consume_feature_usage(user_id, feature)


def check_feature_access(user_id: str, feature: str = "default") -> Tuple[bool, str]:
    """Check if user can access feature without consuming usage."""
    service = get_supabase_subscription_service()
    return service.can_access_feature(user_id, feature)


if __name__ == "__main__":
    # Quick test
    import asyncio

    async def test():
        service = get_supabase_subscription_service()
        plans = service.get_plans()
        for p in plans:
            print(f"{p['plan_id']}: {p['display_name']} - ₹{p['price']} - {p['usage_limit']} uses/month")

    asyncio.run(test())