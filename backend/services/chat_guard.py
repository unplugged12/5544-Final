"""Chat guardrail utilities: sanitize_input, scrub_output, and marker detectors.

Pure-Python regex/string work only. No LLM calls, no provider imports.

Functions:
    sanitize_input  — clean untrusted user text before it reaches the LLM.
    scrub_output    — scrub model reply before it reaches the Discord channel.
    contains_prompt_injection_markers — detect injection attempt signals (for telemetry).
    contains_risky_output_markers     — detect output patterns that warrant a second-pass
                                        moderation classifier call.
"""

import re
import unicodedata


# ---------------------------------------------------------------------------
# Compiled regex constants (module-level for performance)
# ---------------------------------------------------------------------------

# Discord role mention: <@&123456>
_RE_ROLE_MENTION = re.compile(r"<@&\d+>")

# Discord user mentions: <@!123456> and <@123456>
_RE_USER_MENTION = re.compile(r"<@!?\d+>")

# Markdown hyperlink title: [title](url) — keep url, drop title
_RE_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")

# Raw URLs
_RE_RAW_URL = re.compile(r"https?://\S+")

# Control characters (ASCII < 0x20) except \n (0x0A) and \t (0x09)
_RE_CTRL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

# Zero-width / invisible Unicode chars
_RE_ZERO_WIDTH = re.compile(r"[\u200B\u200C\u200D\uFEFF]")

# Collapse horizontal whitespace runs (spaces/tabs) to single space,
# but do NOT collapse newlines (preserve paragraph structure).
_RE_HSPACE_RUN = re.compile(r"[^\S\n]+")

# --- scrub_output patterns ---

# OpenAI-style secret key (sk- prefix, 16+ chars)
_RE_OAI_SECRET = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")

# Anthropic-style secret key (sk-ant- prefix, 16+ chars after the prefix)
# Must come BEFORE the generic sk- pattern in application order.
_RE_ANT_SECRET = re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")

# Long hex tokens (>= 20 consecutive hex chars) — word-boundary anchored
_RE_HEX_TOKEN = re.compile(r"\b[a-fA-F0-9]{20,}\b")

# Bearer tokens
_RE_BEARER = re.compile(r"Bearer [A-Za-z0-9._\-]{16,}")

# Discord bot token shape: base64url{24}.base64url{6}.base64url{27+}
_RE_DISCORD_TOKEN = re.compile(
    r"[A-Za-z0-9_\-]{24}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}"
)

# --- contains_risky_output_markers patterns ---

# SSN pattern
_RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Credit-card 16-digit run (no separators — conservative; hyphen/space-separated
# patterns are too noisy and skipped per spec)
_RE_CC = re.compile(r"\b\d{16}\b")

# Minimal, conservative slur list — only obviously-prohibited terms.
# Kept short intentionally: over-flagging triggers a cheap second-pass call,
# not a hard block, so erring toward inclusion is acceptable.
_SLUR_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bn[i\*][g\*]{2}[e\*]?r\b", re.IGNORECASE),
    re.compile(r"\bf[a\*][g\*]{2}[o\*]?t\b", re.IGNORECASE),
    re.compile(r"\bc[u\*]nt\b", re.IGNORECASE),
    re.compile(r"\bk[i\*]k[e\*]\b", re.IGNORECASE),
    re.compile(r"\bsp[i\*]c\b", re.IGNORECASE),
]

# Threat phrases (checked as plain substrings for speed)
_THREAT_PHRASES: frozenset[str] = frozenset(
    ["i'll kill", "go die", "kys", "unalive"]
)

# PII keywords that should not appear in LLM output
_PII_OUTPUT_PHRASES: frozenset[str] = frozenset(
    ["my password", "my address is", "my phone is"]
)


# ---------------------------------------------------------------------------
# sanitize_input
# ---------------------------------------------------------------------------


def sanitize_input(text: str) -> str:
    """Sanitize untrusted user text before forwarding to the LLM.

    Operations (in order):
    1. Truncate to settings.CHAT_INPUT_MAX_CHARS.
    2. Strip @everyone / @here literals.
    3. Strip Discord role mentions (<@&...>).
    4. Strip Discord user mentions (<@!...> and <@...>).
    5. Replace markdown link titles with bare URL: [title](url) → url.
    6. Replace raw URLs with [link redacted].
    7. Strip control characters (ASCII < 0x20 except \\n and \\t).
    8. Strip zero-width Unicode characters.
    9. Collapse horizontal whitespace runs to single space (newlines preserved).

    Args:
        text: Raw user-supplied message content.

    Returns:
        Cleaned string safe to embed in an LLM user turn.
    """
    from config import settings  # lazy import — avoids circular imports & enables monkeypatching

    # 1. Truncate
    text = text[: settings.CHAT_INPUT_MAX_CHARS]

    # 2. Strip @everyone / @here
    text = text.replace("@everyone", "").replace("@here", "")

    # 3. Strip role mentions
    text = _RE_ROLE_MENTION.sub("", text)

    # 4. Strip user mentions (both <@!id> and <@id>)
    text = _RE_USER_MENTION.sub("", text)

    # 5. Replace markdown link with bare URL ([title](url) → url)
    text = _RE_MD_LINK.sub(r"\2", text)

    # 6. Replace raw URLs
    text = _RE_RAW_URL.sub("[link redacted]", text)

    # 7. Strip control chars (except \n \t)
    text = _RE_CTRL.sub("", text)

    # 8. Strip zero-width chars
    text = _RE_ZERO_WIDTH.sub("", text)

    # 9. Collapse horizontal whitespace runs (preserve newlines)
    text = _RE_HSPACE_RUN.sub(" ", text)

    return text.strip()


# ---------------------------------------------------------------------------
# scrub_output
# ---------------------------------------------------------------------------


def _parse_allowed_domains() -> frozenset[str]:
    """Parse CHAT_ALLOWED_URL_DOMAINS from settings into a frozenset of lowercase domains."""
    from config import settings  # lazy import

    raw = settings.CHAT_ALLOWED_URL_DOMAINS
    return frozenset(d.strip().lower() for d in raw.split(",") if d.strip())


def _url_is_allowed(url: str, allowed_domains: frozenset[str]) -> bool:
    """Return True if the URL's domain (or any parent domain) is in allowed_domains."""
    # Extract host from URL — simple split approach, no urllib needed.
    # url starts with http:// or https://
    try:
        after_scheme = url.split("://", 1)[1]
        host = after_scheme.split("/")[0].lower()
        # Strip port if present
        host = host.split(":")[0]
    except IndexError:
        return False

    # Exact match or subdomain match:
    # host == domain OR host ends with ".<domain>"
    for domain in allowed_domains:
        if host == domain or host.endswith("." + domain):
            return True
    return False


def scrub_output(text: str) -> str:
    """Scrub LLM reply text before sending to Discord.

    Operations (in order):
    1. Remove URLs whose domain is not in settings.CHAT_ALLOWED_URL_DOMAINS.
    2. Redact Discord bot tokens (most specific token shape first).
    3. Redact Anthropic secrets (sk-ant-...).
    4. Redact OpenAI-style secrets (sk-...).
    5. Redact long hex tokens (>= 20 chars).
    6. Redact Bearer tokens.

    Args:
        text: Raw model reply string.

    Returns:
        Scrubbed string safe to send to Discord.
    """
    allowed_domains = _parse_allowed_domains()

    # 1. URL domain filter — replace disallowed URLs with empty string
    def _filter_url(m: re.Match) -> str:
        url = m.group(0)
        return url if _url_is_allowed(url, allowed_domains) else ""

    text = _RE_RAW_URL.sub(_filter_url, text)

    # 2. Discord bot tokens (most specific first — before generic hex/base64 patterns)
    text = _RE_DISCORD_TOKEN.sub("[redacted-discord-token]", text)

    # 3. Anthropic secrets (before generic sk- pattern)
    text = _RE_ANT_SECRET.sub("[redacted-secret]", text)

    # 4. OpenAI-style secrets
    text = _RE_OAI_SECRET.sub("[redacted-secret]", text)

    # 5. Long hex tokens
    text = _RE_HEX_TOKEN.sub("[redacted-token]", text)

    # 6. Bearer tokens
    text = _RE_BEARER.sub("Bearer [redacted]", text)

    return text


# ---------------------------------------------------------------------------
# contains_prompt_injection_markers
# ---------------------------------------------------------------------------

# All marker phrases lowercased for O(1) substring scan via a single lowercased pass.
_INJECTION_PHRASES: frozenset[str] = frozenset(
    [
        # Instruction override
        "ignore previous",
        "ignore all previous",
        "ignore the above",
        "disregard previous",
        # System prompt probing
        "system prompt",
        "system message",
        "your instructions",
        "your rules",
        "your guidelines",
        "your playbook",
        # Identity coercion
        "you are now",
        "you're now",
        "act as",
        "pretend to be",
        "role-play as",
        "roleplay as",
        # Jailbreak modes
        "dan mode",
        "developer mode",
        "jailbroken",
        "jailbreak",
        # Exfiltration
        "reveal your",
        "show me your",
        "print your",
        "output your",
        # Delimiter spoofing
        "<<<",
        ">>>",
    ]
)


def contains_prompt_injection_markers(text: str) -> bool:
    """Return True if text contains known prompt-injection signal phrases.

    Used by chat_service (PR 4) for telemetry and rate-limit escalation.
    Does NOT cause a refusal by itself — the system prompt handles identity lock.

    Args:
        text: User-supplied message content (pre-sanitization is fine).

    Returns:
        True if any injection marker phrase is found (case-insensitive).
    """
    lower = text.lower()
    return any(phrase in lower for phrase in _INJECTION_PHRASES)


# ---------------------------------------------------------------------------
# contains_risky_output_markers
# ---------------------------------------------------------------------------


def contains_risky_output_markers(text: str) -> bool:
    """Return True if model output contains markers that warrant a second-pass moderation call.

    This is a lightweight pre-filter. ~10-15% hit rate expected.
    Erring toward MORE flagging is acceptable — a second-pass call is cheap
    compared to the cost of a slur or PII reaching users.

    Checks:
    - SSN pattern (\\d{3}-\\d{2}-\\d{4})
    - 16-digit run (potential credit card)
    - Minimal slur patterns (conservative list)
    - Threat phrases (kys, go die, etc.)
    - PII output phrases (my password, my address is, etc.)

    Args:
        text: Raw model reply string (before scrub_output).

    Returns:
        True if any risky marker is detected.
    """
    if _RE_SSN.search(text):
        return True

    if _RE_CC.search(text):
        return True

    lower = text.lower()

    for pattern in _SLUR_PATTERNS:
        if pattern.search(lower):
            return True

    for phrase in _THREAT_PHRASES:
        if phrase in lower:
            return True

    for phrase in _PII_OUTPUT_PHRASES:
        if phrase in lower:
            return True

    return False
