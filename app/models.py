from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func, UniqueConstraint, ForeignKey
from .db import db


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        # Ensure we never create duplicate OAuth identities
        UniqueConstraint("oauth_provider", "oauth_sub", name="uq_user_oauth_identity"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    email_verified_at = db.Column(DateTime(timezone=True), nullable=True)
    is_active = db.Column(Boolean, default=True, nullable=False)
    is_admin = db.Column(Boolean, default=False, nullable=False)
    oauth_provider = db.Column(db.String(20), nullable=True, index=True)
    oauth_sub = db.Column(db.String(255), nullable=True, index=True)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    updated_at = db.Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True, nullable=False)
    deleted_at = db.Column(DateTime(timezone=True), nullable=True, index=True)
    last_login_at = db.Column(DateTime(timezone=True), nullable=True)
    last_seen_at = db.Column(DateTime(timezone=True), nullable=True)
    plan = db.Column(db.String(50), default="free", nullable=False)
    plan_started_at = db.Column(DateTime(timezone=True), nullable=True)
    plan_renews_at = db.Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = db.Column(Boolean, default=False, nullable=False)
    quota_claude_monthly = db.Column(Integer, default=3, nullable=False)
    quota_gpt_monthly = db.Column(Integer, default=2, nullable=False)
    quota_claude_used = db.Column(Integer, default=0, nullable=False)
    quota_gpt_used = db.Column(Integer, default=0, nullable=False)
    stripe_customer_id = db.Column(db.String(100), nullable=True, unique=True, index=True)
    default_language = db.Column(db.String(10), nullable=True)
    marketing_opt_in = db.Column(Boolean, default=False, nullable=False)
    privacy_accepted_at = db.Column(DateTime(timezone=True), nullable=True)
    password_reset_nonce = db.Column(db.String(64), nullable=True)
    password_reset_sent_at = db.Column(DateTime(timezone=True), nullable=True)

    generations = db.relationship("Generation", back_populates="user")
    sessions = db.relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Article(db.Model):
    __tablename__ = "articles"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    source = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(2000), unique=True, index=True, nullable=False)
    title = db.Column(db.String(1000), nullable=False)
    summary = db.Column(Text, nullable=False)
    topics = db.Column(JSON, nullable=False)
    image_url = db.Column(db.String(2000), nullable=True)
    published_at = db.Column(DateTime(timezone=True), nullable=True)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    updated_at = db.Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True, nullable=False)
    deleted_at = db.Column(DateTime(timezone=True), nullable=True, index=True)

    generations = db.relationship("Generation", back_populates="article")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), unique=True, index=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, index=True, nullable=False)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ArticleCategory(db.Model):
    __tablename__ = "article_categories"
    __table_args__ = (UniqueConstraint("article_id", "category_id", name="uq_article_category"),)

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    article_id = db.Column(db.String(36), ForeignKey("articles.id"), index=True, nullable=False)
    category_id = db.Column(db.String(36), ForeignKey("categories.id"), index=True, nullable=False)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserNewsPreference(db.Model):
    __tablename__ = "user_news_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_news_pref_user"),)

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), ForeignKey("users.id"), index=True, nullable=False)
    categories = db.Column(JSON, default=dict, nullable=False)
    show_only_my_categories = db.Column(Boolean, default=False, nullable=False)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Generation(db.Model):
    __tablename__ = "generations"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), ForeignKey("users.id"), index=True, nullable=False)
    article_id = db.Column(db.String(36), ForeignKey("articles.id"), index=True, nullable=True)
    model = db.Column(db.String(100), nullable=False)
    prompt = db.Column(Text, nullable=False)
    draft_text = db.Column(Text, nullable=False)
    persona = db.Column(db.String(50), nullable=True)
    tone = db.Column(db.String(50), nullable=True)
    tokens_used = db.Column(Integer, nullable=True)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    updated_at = db.Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True, nullable=False)
    deleted_at = db.Column(DateTime(timezone=True), nullable=True, index=True)

    user = db.relationship("User", back_populates="generations")
    article = db.relationship("Article", back_populates="generations")


class Session(db.Model):
    __tablename__ = "sessions"
    __table_args__ = (
        # Speed up lookups of recent sessions per user
        db.Index("ix_sessions_user_created", "user_id", "created_at"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    user_agent = db.Column(db.String(400), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    last_seen_at = db.Column(DateTime(timezone=True), nullable=True, index=True)
    revoked_at = db.Column(DateTime(timezone=True), nullable=True)
    expires_at = db.Column(DateTime(timezone=True), nullable=True)

    # ORM relationship
    user = db.relationship("User", back_populates="sessions")


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), ForeignKey("users.id"), index=True, nullable=True)
    provider = db.Column(db.String(20), default="stripe", nullable=False)
    status = db.Column(db.String(30), nullable=False)
    stripe_subscription_id = db.Column(db.String(100), nullable=True, index=True)
    stripe_price_id = db.Column(db.String(100), nullable=True)
    current_period_start = db.Column(DateTime(timezone=True), nullable=True)
    current_period_end = db.Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = db.Column(Boolean, default=False, nullable=False)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PaymentAttempt(db.Model):
    __tablename__ = "payment_attempts"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), ForeignKey("users.id"), index=True, nullable=True)
    provider = db.Column(db.String(20), default="stripe", nullable=False)
    stripe_payment_intent_id = db.Column(db.String(100), nullable=True, index=True)
    amount_cents = db.Column(Integer, nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(30), nullable=False)
    error_code = db.Column(db.String(100), nullable=True)
    error_message = db.Column(db.String(400), nullable=True)
    extra = db.Column(JSON, default=dict, nullable=False)
    created_at = db.Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

