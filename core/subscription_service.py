"""
core/subscription_service.py — Subscription, Authentication, Usage & Payment Service.
Central business logic for the SaaS monetization system.
"""
import os
import sys
import hashlib
import secrets
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Project root import
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import (
    PLAN_CONFIG, FREE_WEEKLY_LIMIT, TIMEZONE, FREE_WEEK_START_DAY,
    RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET
)
from core.database import (
    get_connection, create_user, get_user_by_email, get_user_by_id, update_user,
    get_subscription_plans, get_plan_by_id, get_active_subscription, get_user_subscriptions,
    create_subscription, get_subscription_by_id, update_subscription, cancel_subscription,
    get_or_create_usage_period, consume_usage, get_usage_status,
    create_payment, get_payment_by_id, update_payment, get_payments_by_user,
    record_webhook_event, mark_webhook_processed, is_webhook_processed
)

try:
    import razorpay
    RAZORPAY_AVAILABLE = True
except ImportError:
    RAZORPAY_AVAILABLE = False

logger = logging.getLogger("aprs.subscription")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(name)s %(levelname)s — %(message)s")


class AuthError(Exception):
    """Authentication error."""
    pass


class SubscriptionError(Exception):
    """Subscription error."""
    pass


class UsageError(Exception):
    """Usage limit error."""
    pass


class PaymentError(Exception):
    """Payment error."""
    pass


class SubscriptionService:
    """
    Main service for handling authentication, subscriptions, usage, and payments.
    """
    
    def __init__(self):
        self.razorpay_client = None
        if RAZORPAY_AVAILABLE and RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
            self.razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            logger.info("Razorpay client initialized")
        else:
            logger.warning("Razorpay not configured - payments will be mocked")
    
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
    
    def register(self, email: str, password: str, full_name: str = None) -> Dict[str, Any]:
        """Register a new user."""
        email = email.strip().lower()
        
        # Check if user exists
        existing = get_user_by_email(email)
        if existing:
            raise AuthError("Email already registered")
        
        # Create user
        password_hash = self.hash_password(password)
        user_id = create_user(email=email, password_hash=password_hash, full_name=full_name)
        
        if not user_id:
            raise AuthError("Registration failed")
        
        return {
            "success": True,
            "user_id": user_id,
            "email": email,
            "full_name": full_name
        }
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user."""
        email = email.strip().lower()
        user = get_user_by_email(email)
        
        if not user:
            raise AuthError("Invalid credentials")
        
        if not user.get("password_hash"):
            raise AuthError("Account uses OAuth login")
        
        if not self.verify_password(password, user["password_hash"]):
            raise AuthError("Invalid credentials")
        
        # Create session token
        session_token = secrets.token_urlsafe(32)
        
        return {
            "success": True,
            "user_id": user["user_id"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "session_token": session_token
        }
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        return get_user_by_id(user_id)
    
    # ════════════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_plans(self) -> List[Dict[str, Any]]:
        """Get all available plans."""
        return get_subscription_plans()
    
    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get plan details."""
        return get_plan_by_id(plan_id)
    
    def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's active subscription with plan details."""
        return get_active_subscription(user_id)
    
    def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all user subscriptions."""
        return get_user_subscriptions(user_id)
    
    def create_subscription_order(self, user_id: str, plan_id: str) -> Dict[str, Any]:
        """Create a subscription order for payment."""
        plan = get_plan_by_id(plan_id)
        if not plan:
            raise SubscriptionError(f"Plan {plan_id} not found")
        
        # Check if user already has active subscription
        active = get_active_subscription(user_id)
        if active:
            raise SubscriptionError("User already has an active subscription")
        
        # Create subscription record
        subscription_id = create_subscription(user_id, plan_id)
        
        return {
            "subscription_id": subscription_id,
            "plan": plan,
            "amount": plan["price"],
            "currency": plan["currency"]
        }
    
    def activate_subscription(self, subscription_id: str, 
                              provider_subscription_id: str = None,
                              provider_customer_id: str = None) -> bool:
        """Activate a subscription after successful payment."""
        import datetime
        now = datetime.datetime.now()
        period_end = now + datetime.timedelta(days=30)
        
        return update_subscription(subscription_id, 
            status="active",
            provider_subscription_id=provider_subscription_id,
            provider_customer_id=provider_customer_id,
            current_period_start=now.isoformat(),
            current_period_end=period_end.isoformat()
        )
    
    def cancel_user_subscription(self, user_id: str, at_period_end: bool = True) -> bool:
        """Cancel user's active subscription."""
        active = get_active_subscription(user_id)
        if not active:
            raise SubscriptionError("No active subscription found")
        
        return cancel_subscription(active["subscription_id"], at_period_end)
    
    # ════════════════════════════════════════════════════════════════════════════
    # USAGE TRACKING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def check_usage(self, user_id: str) -> Dict[str, Any]:
        """Check user's current usage status."""
        return get_usage_status(user_id)
    
    def consume_feature_usage(self, user_id: str, feature: str = "swarm_scan") -> Dict[str, Any]:
        """
        Consume one usage for a feature.
        Returns usage result with success status and remaining allowances.
        """
        # Check if user can access feature
        usage_status = get_usage_status(user_id)
        
        free_remaining = usage_status["weekly_free"]["remaining"]
        paid_remaining = usage_status["paid_usage"]["remaining"]
        
        if free_remaining <= 0 and paid_remaining <= 0:
            raise UsageError("USAGE_LIMIT_REACHED", 
                "Your weekly free usage has been used. Upgrade your plan to continue.")
        
        # Consume usage atomically
        result = consume_usage(user_id, feature)
        
        if not result["success"]:
            raise UsageError(result.get("error", "USAGE_ERROR"), 
                           result.get("message", "Usage limit reached"))
        
        return result
    
    def can_access_feature(self, user_id: str, feature: str = "default") -> Tuple[bool, str]:
        """Check if user can access a feature."""
        usage_status = get_usage_status(user_id)
        free_remaining = usage_status["weekly_free"]["remaining"]
        paid_remaining = usage_status["paid_usage"]["remaining"]
        
        if free_remaining > 0 or paid_remaining > 0:
            return True, "OK"
        
        return False, "USAGE_LIMIT_REACHED"
    
    # ════════════════════════════════════════════════════════════════════════════
    # PAYMENT PROCESSING (RAZORPAY)
    # ════════════════════════════════════════════════════════════════════════════
    
    def create_payment_order(self, user_id: str, plan_id: str, 
                             receipt: str = None) -> Dict[str, Any]:
        """Create a Razorpay order for subscription payment."""
        plan = get_plan_by_id(plan_id)
        if not plan:
            raise PaymentError(f"Plan {plan_id} not found")
        
        # Create payment record
        payment_id = create_payment(
            user_id=user_id,
            plan_id=plan_id,
            provider="razorpay",
            amount=plan["price"],
            currency=plan["currency"],
            metadata={"plan_name": plan["display_name"]}
        )
        
        if self.razorpay_client:
            try:
                order_data = {
                    "amount": plan["price"] * 100,  # Razorpay expects paise
                    "currency": plan["currency"],
                    "receipt": receipt or f"sub_{payment_id[:8]}",
                    "notes": {
                        "payment_id": payment_id,
                        "user_id": user_id,
                        "plan_id": plan_id
                    }
                }
                razorpay_order = self.razorpay_client.order.create(order_data)
                
                # Update payment with Razorpay order ID
                update_payment(payment_id, provider_order_id=razorpay_order["id"])
                
                return {
                    "payment_id": payment_id,
                    "razorpay_order_id": razorpay_order["id"],
                    "amount": razorpay_order["amount"],
                    "currency": razorpay_order["currency"],
                    "key_id": RAZORPAY_KEY_ID,
                    "plan": plan
                }
            except Exception as e:
                logger.error(f"Razorpay order creation failed: {e}")
                raise PaymentError(f"Failed to create payment order: {e}")
        else:
            # Mock mode for development
            mock_order_id = f"order_mock_{secrets.token_hex(8)}"
            update_payment(payment_id, provider_order_id=mock_order_id)
            
            return {
                "payment_id": payment_id,
                "razorpay_order_id": mock_order_id,
                "amount": plan["price"] * 100,
                "currency": plan["currency"],
                "key_id": RAZORPAY_KEY_ID or "rzp_test_mock",
                "plan": plan,
                "mock": True
            }
    
    def verify_payment_signature(self, razorpay_order_id: str, 
                                  razorpay_payment_id: str, 
                                  razorpay_signature: str) -> bool:
        """Verify Razorpay payment signature."""
        if not self.razorpay_client:
            # Mock mode - always verify
            return True
        
        try:
            params = {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            }
            self.razorpay_client.utility.verify_payment_signature(params)
            return True
        except Exception as e:
            logger.error(f"Payment signature verification failed: {e}")
            return False
    
    def handle_payment_success(self, razorpay_order_id: str, 
                                razorpay_payment_id: str,
                                razorpay_signature: str) -> Dict[str, Any]:
        """Handle successful payment callback."""
        # Verify signature
        if not self.verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            raise PaymentError("Invalid payment signature")
        
        # Find payment by order ID
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM payments WHERE provider_order_id = ?", (razorpay_order_id,))
        payment = cur.fetchone()
        conn.close()
        
        if not payment:
            raise PaymentError("Payment not found")
        
        payment = dict(payment)
        
        # Update payment status
        update_payment(payment["payment_id"],
            status="completed",
            provider_payment_id=razorpay_payment_id,
            provider_signature=razorpay_signature
        )
        
        # Create and activate subscription
        subscription_id = create_subscription(
            user_id=payment["user_id"],
            plan_id=payment["plan_id"],
            provider="razorpay",
            provider_subscription_id=razorpay_payment_id,
            provider_customer_id=payment.get("metadata_json", {}).get("customer_id") if payment.get("metadata_json") else None,
            price=payment["amount"],
            currency=payment["currency"]
        )
        
        # Activate subscription
        self.activate_subscription(subscription_id, 
            provider_subscription_id=razorpay_payment_id)
        
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
        import hmac
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
                event_id = f"{payload.get('event', 'evt')}_{payload.get('created_at', int(datetime.datetime.now().timestamp()))}"
        
        # Check idempotency
        if is_webhook_processed(event_id):
            return {"success": True, "message": "Event already processed"}
        
        # Record webhook event
        record_webhook_event(event_id, "razorpay", payload.get("event", "unknown"), payload)
        
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
            mark_webhook_processed(event_id)
            
            return {"success": True, "event": event_type}
        
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            raise PaymentError(f"Webhook processing failed: {e}")
    
    def _handle_payment_captured(self, payment_data: dict):
        """Handle payment.captured webhook."""
        order_id = payment_data.get("order_id")
        payment_id = payment_data.get("id")
        signature = payment_data.get("signature")
        
        # Find payment record
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM payments WHERE provider_order_id = ?", (order_id,))
        payment = cur.fetchone()
        conn.close()
        
        if payment:
            payment = dict(payment)
            self.handle_payment_success(order_id, payment_id, signature)
    
    def _handle_payment_failed(self, payment_data: dict):
        """Handle payment.failed webhook."""
        order_id = payment_data.get("order_id")
        update_payment(order_id, status="failed")
    
    def _handle_subscription_activated(self, sub_data: dict):
        """Handle subscription.activated webhook."""
        sub_id = sub_data.get("id")
        # Subscription already activated via payment success
        pass
    
    def _handle_subscription_cancelled(self, sub_data: dict):
        """Handle subscription.cancelled webhook."""
        sub_id = sub_data.get("id")
        # Find and cancel local subscription
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM subscriptions WHERE provider_subscription_id = ?", (sub_id,))
        local_sub = cur.fetchone()
        conn.close()
        
        if local_sub:
            cancel_subscription(local_sub["subscription_id"], at_period_end=False)
    
    def _handle_subscription_completed(self, sub_data: dict):
        """Handle subscription.completed webhook."""
        sub_id = sub_data.get("id")
        # Update local subscription status
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM subscriptions WHERE provider_subscription_id = ?", (sub_id,))
        local_sub = cur.fetchone()
        conn.close()
        
        if local_sub:
            update_subscription(local_sub["subscription_id"], status="completed")
    
    # ════════════════════════════════════════════════════════════════════════════
    # ADMIN / UTILITY
    # ════════════════════════════════════════════════════════════════════════════
    
    def get_user_dashboard_data(self, user_id: str) -> Dict[str, Any]:
        """Get all data needed for user dashboard."""
        user = get_user_by_id(user_id)
        if not user:
            raise AuthError("User not found")
        
        subscription = get_active_subscription(user_id)
        usage = get_usage_status(user_id)
        payments = get_payments_by_user(user_id)
        
        return {
            "user": user,
            "subscription": subscription,
            "usage": usage,
            "payments": payments,
            "plans": get_subscription_plans()
        }
    
    def reset_weekly_usage(self, user_id: str) -> bool:
        """Admin: Reset user's weekly usage (for testing/support)."""
        period_start, period_end = get_current_week_period()
        period_id = f"{user_id}_{period_start}"
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM usage_periods WHERE period_id = ?", (period_id,))
        conn.commit()
        conn.close()
        return True


# Singleton instance
_subscription_service = None

def get_subscription_service() -> SubscriptionService:
    """Get singleton subscription service instance."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service


# Convenience functions for common operations
def require_usage(user_id: str, feature: str = "default") -> Dict[str, Any]:
    """
    Check and consume usage for a feature.
    Raises UsageError if limit reached.
    Returns usage result on success.
    """
    service = get_subscription_service()
    return service.consume_feature_usage(user_id, feature)


def check_feature_access(user_id: str, feature: str = "default") -> Tuple[bool, str]:
    """Check if user can access feature without consuming usage."""
    service = get_subscription_service()
    return service.can_access_feature(user_id, feature)


if __name__ == "__main__":
    # Quick test
    service = get_subscription_service()
    plans = service.get_plans()
    for p in plans:
        print(f"{p['plan_id']}: {p['display_name']} - ₹{p['price']} - {p['usage_limit']} uses/month")
    print("Subscription service initialized successfully!")