"""Discord embed builders for backend API responses."""

from __future__ import annotations

from typing import Any

import discord

# ── severity -> colour mapping ────────────────────────────────────────

SEVERITY_COLORS: dict[str, discord.Color] = {
    "low": discord.Color.green(),
    "medium": discord.Color.yellow(),
    "high": discord.Color.orange(),
    "critical": discord.Color.red(),
}


def _truncate(text: str, limit: int) -> str:
    """Truncate *text* to *limit* chars, appending an ellipsis if needed."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "\u2026"


# ── TaskResponse embed ────────────────────────────────────────────────

def build_task_embed(
    title: str,
    data: dict[str, Any],
    color: discord.Color,
) -> discord.Embed:
    """Convert a TaskResponse dict into a rich Discord embed."""
    description = _truncate(data.get("output_text", ""), 4000)
    embed = discord.Embed(title=title, description=description, color=color)

    # Optional scalar fields
    if data.get("matched_rule"):
        embed.add_field(name="Matched Rule", value=data["matched_rule"], inline=True)
    if data.get("severity"):
        embed.add_field(name="Severity", value=data["severity"], inline=True)
    if data.get("suggested_action"):
        embed.add_field(
            name="Suggested Action", value=data["suggested_action"], inline=True
        )

    # Citations / sources
    citations: list[dict] = data.get("citations") or []
    if citations:
        lines: list[str] = []
        for cite in citations[:5]:
            label = cite.get("citation_label", "")
            snippet = cite.get("snippet", "")
            entry = _truncate(f"[{label}] {snippet}", 200)
            lines.append(entry)
        sources_text = _truncate("\n".join(lines), 1024)
        embed.add_field(name="Sources", value=sources_text, inline=False)

    # Footer
    confidence = data.get("confidence_note", "")
    if confidence:
        embed.set_footer(text=confidence)

    return embed


# ── ModerationEventResponse embed ────────────────────────────────────

def build_moderation_alert(
    data: dict[str, Any],
    message: discord.Message,
) -> discord.Embed:
    """Build an alert embed from a ModerationEventResponse and the source message."""
    violation = data.get("violation_type", "unknown")
    explanation = data.get("explanation", "")
    description = _truncate(f"**{violation}**\n{explanation}", 4000)

    severity = data.get("severity", "medium")
    color = SEVERITY_COLORS.get(severity, discord.Color.greyple())

    embed = discord.Embed(
        title="Moderation Alert",
        description=description,
        color=color,
    )

    embed.add_field(name="Author", value=str(message.author), inline=True)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    if severity:
        embed.add_field(name="Severity", value=severity, inline=True)
    if data.get("matched_rule"):
        embed.add_field(name="Matched Rule", value=data["matched_rule"], inline=False)
    if data.get("suggested_action"):
        embed.add_field(
            name="Action", value=data["suggested_action"], inline=True
        )

    return embed
