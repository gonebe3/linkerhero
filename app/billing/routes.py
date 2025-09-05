from __future__ import annotations

import os
from flask import current_app, jsonify, request, render_template, session as flask_session
from dotenv import dotenv_values
from . import bp
from ..db import db_session
from ..models import User, PaymentAttempt
from ..utils import next_month
from ..limiter import limiter
from flask_limiter.util import get_remote_address

def _clean_value(v: str | None) -> str | None:
    if not v:
        return None
    s = v.strip()
    # Strip BOM if present
    if s and s[0] == "\ufeff":
        s = s.lstrip("\ufeff")
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    return s or None


def _get_env(name: str) -> str | None:
    # Try Flask config, process env, then parse .env file explicitly
    val = _clean_value(current_app.config.get(name)) or _clean_value(os.getenv(name))
    if val:
        return val
    try:
        root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
        env_path = os.path.join(root, ".env")
        parsed = dotenv_values(env_path) if os.path.exists(env_path) else {}
        return _clean_value(parsed.get(name))
    except Exception:
        return None


@bp.get("/config")
def get_config():
    # Expose publishable key to frontend
    pk = _get_env("STRIPE_PUBLISHABLE_KEY")
    return jsonify({"publishableKey": pk})


@bp.post("/create-payment-intent")
@limiter.limit("10 per minute", key_func=lambda: (flask_session.get("user_id") or get_remote_address()))
def create_payment_intent():
    import stripe

    sk = _get_env("STRIPE_SECRET_KEY")
    if not sk:
        return jsonify({"error": "Stripe not configured"}), 500
    stripe.api_key = sk

    data = request.get_json(force=True, silent=True) or {}
    # Expect amount_cents and currency
    amount_cents = int(data.get("amount_cents") or 0)
    currency = (data.get("currency") or "usd").lower()
    if amount_cents <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    # Create a PaymentIntent in test mode (based on secret key)
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        automatic_payment_methods={"enabled": True},
        metadata={"app": "LinkerHero"},
    )
    return jsonify({"clientSecret": intent.client_secret})


@bp.post("/success")
@limiter.limit("10 per minute", key_func=lambda: (flask_session.get("user_id") or get_remote_address()))
def payment_success():
    import stripe

    sk = _get_env("STRIPE_SECRET_KEY")
    if not sk:
        return jsonify({"success": False, "message": "Stripe not configured"}), 500
    stripe.api_key = sk

    data = request.get_json(force=True, silent=True) or {}
    pi_id = data.get("payment_intent_id")
    if not pi_id:
        return jsonify({"success": False, "message": "payment_intent_id required"}), 400
    try:
        pi = stripe.PaymentIntent.retrieve(pi_id)
    except Exception:
        return jsonify({"success": False, "message": "Could not retrieve PaymentIntent"}), 400

    if pi.get("status") != "succeeded":
        return jsonify({"success": False, "message": "Payment not succeeded"}), 400

    # Record attempt and upgrade plan
    uid = flask_session.get("user_id")
    with db_session() as s:
        user = s.get(User, uid) if uid else None
        pa = PaymentAttempt(
            user_id=(user.id if user else None),
            provider="stripe",
            stripe_payment_intent_id=pi_id,
            amount_cents=pi.get("amount"),
            currency=pi.get("currency"),
            status=pi.get("status"),
            error_code=None,
            error_message=None,
            extra={"payment_method": pi.get("payment_method")},
        )
        s.add(pa)
        if user:
            # Upgrade plan and reset quotas for Personal
            user.plan = "personal"
            user.quota_claude_monthly = 30
            user.quota_gpt_monthly = 50
            user.quota_claude_used = 0
            user.quota_gpt_used = 0
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            user.plan_started_at = now
            user.plan_renews_at = next_month(now)
    return jsonify({"success": True})


@bp.post("/cancel")
def cancel_subscription():
    # Simple cancellation for PaymentIntent-based Personal plan
    uid = flask_session.get("user_id")
    if not uid:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    with db_session() as s:
        user = s.get(User, uid)
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        # Soft-cancel: keep access until end of current period
        user.cancel_at_period_end = True
    from flask import render_template
    return render_template("billing_cancelled.html")


@bp.get("/cancel")
def cancel_subscription_page():
    # Render a confirmation page with a POST form
    if not flask_session.get("user_id"):
        return render_template("auth_login_spaceship.html", sent=False)
    return render_template("billing_cancel.html")


@bp.get("/success")
def payment_success_page():
    # Optional: simple success page if needed
    if not flask_session.get("user_id"):
        return render_template("auth_login_spaceship.html", sent=False)
    return render_template("billing_success.html")


@bp.post("/resume")
def resume_subscription():
    # Clear cancel-at-period-end so plan renews as usual on next renewal date
    uid = flask_session.get("user_id")
    if not uid:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    with db_session() as s:
        user = s.get(User, uid)
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        user.cancel_at_period_end = False
    from flask import redirect, url_for
    return redirect(url_for("main.dashboard"))


@bp.get("/checkout")
def checkout_page():
    # Require login to attribute plan upgrade
    if not flask_session.get("user_id"):
        return render_template("auth_login_spaceship.html", sent=False)
    # Hard-code Personal plan price for now
    pk = _get_env("STRIPE_PUBLISHABLE_KEY")
    return render_template("checkout.html", amount_cents=899, currency="usd", stripe_pk=pk)



@bp.get("/portal")
def portal_redirect():
    # Prefer a direct configured Stripe Billing Portal URL if provided
    from flask import redirect, url_for

    direct_url = _get_env("STRIPE_PORTAL_DIRECT_URL")
    if direct_url:
        return redirect(direct_url)

    # Otherwise, create a customer portal session dynamically
    import stripe

    sk = _get_env("STRIPE_SECRET_KEY")
    if not sk:
        return render_template("billing_error.html", message="Stripe not configured."), 500
    stripe.api_key = sk

    uid = flask_session.get("user_id")
    if not uid:
        return render_template("auth_login_spaceship.html", sent=False)

    with db_session() as s:
        user = s.get(User, uid)
        if not user:
            return render_template("billing_error.html", message="User not found."), 404
        try:
            if not user.stripe_customer_id:
                # Create a Stripe customer for the user if missing
                cust = stripe.Customer.create(email=user.email or None, name=user.display_name or None)
                user.stripe_customer_id = cust.id
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=url_for("main.dashboard", _external=True),
            )
            return redirect(session.url)
        except Exception as e:
            return render_template("billing_error.html", message=f"Unable to open Stripe Portal: {e}"), 500


@bp.get("/subscribe")
def start_subscription_checkout():
    # Create a Stripe Checkout Session (subscription mode) for Personal plan
    from flask import redirect, url_for
    import stripe

    sk = _get_env("STRIPE_SECRET_KEY")
    price_id = _get_env("STRIPE_PRICE_ID_PERSONAL")
    if not sk or not price_id:
        missing = []
        if not sk:
            missing.append("STRIPE_SECRET_KEY")
        if not price_id:
            missing.append("STRIPE_PRICE_ID_PERSONAL")
        missing_text = ", ".join(missing)
        return render_template("billing_error.html", message=f"Stripe not configured. Missing: {missing_text}"), 500
    stripe.api_key = sk

    uid = flask_session.get("user_id")
    if not uid:
        return render_template("auth_login_spaceship.html", sent=False)

    with db_session() as s:
        user = s.get(User, uid)
        if not user:
            return render_template("billing_error.html", message="User not found."), 404
        try:
            if not user.stripe_customer_id:
                cust = stripe.Customer.create(email=user.email or None, name=user.display_name or None)
                user.stripe_customer_id = cust.id
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=user.stripe_customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                allow_promotion_codes=True,
                success_url=url_for("main.dashboard", _external=True) + "?sub=success&session_id={CHECKOUT_SESSION_ID}",
                cancel_url=url_for("pricing", _external=True) if current_app.view_functions.get("pricing") else url_for("main.dashboard", _external=True),
            )
            return redirect(session.url)
        except Exception as e:
            return render_template("billing_error.html", message=f"Unable to start checkout: {e}"), 500


@bp.post("/webhook")
def stripe_webhook():
    import stripe
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    sk = _get_env("STRIPE_SECRET_KEY")
    stripe.api_key = sk or ""
    webhook_secret = _get_env("STRIPE_WEBHOOK_SECRET")

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            # Fallback without signature verification (not recommended for production)
            event = stripe.Event.construct_from(request.get_json(force=True, silent=True) or {}, stripe.api_key)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    def _update_user_from_subscription(sub: dict):
        customer_id = sub.get("customer")
        status = sub.get("status")
        cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
        current_period_end = sub.get("current_period_end")
        from datetime import datetime, timezone
        with db_session() as s:
            user = s.query(User).filter(User.stripe_customer_id == customer_id).first()
            if not user:
                return
            if status in ("active", "trialing"):
                user.plan = "personal"
                user.quota_claude_monthly = 30
                user.quota_gpt_monthly = 50
                user.cancel_at_period_end = cancel_at_period_end
                if current_period_end:
                    user.plan_renews_at = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
            elif status in ("canceled", "incomplete_expired", "unpaid", "paused"):
                # Move back to free on terminal statuses
                user.plan = "free"
                user.cancel_at_period_end = False
                user.plan_renews_at = None

    try:
        etype = event["type"]
        data_object = event["data"]["object"]
        if etype == "checkout.session.completed":
            # Retrieve subscription to copy details
            sub_id = data_object.get("subscription")
            if sub_id:
                sub = stripe.Subscription.retrieve(sub_id)
                _update_user_from_subscription(sub)
        elif etype in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
            _update_user_from_subscription(data_object)
    except Exception as e:
        # Always 200 to avoid retries storm; log in real app
        return jsonify({"received": True, "warning": str(e)}), 200

    return jsonify({"received": True}), 200

