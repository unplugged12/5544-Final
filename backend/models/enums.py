"""Enumeration types shared across the application."""

from enum import Enum


class SourceType(str, Enum):
    RULE = "rule"
    FAQ = "faq"
    ANNOUNCEMENT = "announcement"
    MOD_NOTE = "mod_note"


class TaskType(str, Enum):
    FAQ = "faq"
    SUMMARY = "summary"
    MOD_DRAFT = "mod_draft"
    MODERATION = "moderation"
    CHAT = "chat"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SuggestedAction(str, Enum):
    NO_ACTION = "no_action"
    WARN = "warn"
    REMOVE_MESSAGE = "remove_message"
    TIMEOUT_RECOMMENDATION = "timeout_or_mute_recommendation"
    ESCALATE = "escalate_to_human"


class ModerationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_ACTIONED = "auto_actioned"


class ViolationType(str, Enum):
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    TOXIC_ATTACK = "toxic_attack"
    SELF_PROMO = "self_promo"
    SPOILER = "spoiler"
    FLOODING = "flooding"
    NO_VIOLATION = "no_violation"


class EventSource(str, Enum):
    DISCORD = "discord"
    DASHBOARD = "dashboard"
