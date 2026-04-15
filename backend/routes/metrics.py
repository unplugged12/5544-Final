"""Metrics endpoints — admin-gated operational data for the chat feature.

GET /api/metrics/chat
  Returns daily turn counts + refusal counts aggregated from interaction_history.
  Admin-gated via Authorization: Bearer <CHAT_ADMIN_TOKEN> header.

Token counts are NOT available from interaction_history (that table predates
the PR 7 structured log). A future PR with a log shipper integration can
populate per-turn token data from the structured JSON logs emitted by
chat_service. The endpoint documents this gap in its response body.

Security:
  - secrets.compare_digest is used for token comparison (timing-safe).
  - If CHAT_ADMIN_TOKEN equals the sentinel default, the endpoint returns 503
    rather than silently operating with a known-weak token. This "fail loud"
    behavior ensures misconfigured deployments are caught immediately.
"""

import secrets
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Header, HTTPException, status

from config import settings
from services.chat_service import _CANNED_REFUSAL

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

_ADMIN_TOKEN_SENTINEL = "REPLACE_ME_WITH_ADMIN_TOKEN"


def _verify_admin_token(authorization: str | None) -> None:
    """Validate the Bearer token in the Authorization header.

    Raises:
        HTTPException 503: Admin token is still the sentinel default — server
            is misconfigured and must not serve admin data.
        HTTPException 401: Token is missing or does not match.
    """
    if settings.CHAT_ADMIN_TOKEN == _ADMIN_TOKEN_SENTINEL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoint not configured — set CHAT_ADMIN_TOKEN in the environment.",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token required.",
        )

    provided_token = authorization[len("Bearer "):]
    if not secrets.compare_digest(provided_token, settings.CHAT_ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token.",
        )


@router.get("/chat")
async def chat_metrics(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Return daily chat turn counts and refusal counts (admin-gated).

    Aggregates from interaction_history WHERE task_type='chat', grouped by
    DATE(created_at). Token totals are not available from this table — see
    the structured JSON logs emitted by chat_service for per-turn token data.

    Response shape:
    {
        "days": [
            {
                "date": "2026-04-15",
                "turns": 42,
                "refusals": 3,
                "input_tokens": null,   // not available from audit table
                "output_tokens": null   // not available from audit table
            },
            ...
        ],
        "totals": {
            "turns": 42,
            "refusals": 3,
            "input_tokens": null,
            "output_tokens": null
        },
        "note": "token totals require log shipper integration (future PR)"
    }
    """
    _verify_admin_token(authorization)

    # Query interaction_history grouped by date.
    # Refusals are approximated as rows where output_text equals the canned
    # refusal phrase — a best-effort heuristic until a log shipper is in place.
    try:
        async with aiosqlite.connect(settings.SQLITE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    DATE(created_at) AS day,
                    COUNT(*) AS turns,
                    SUM(CASE WHEN output_text = ? THEN 1 ELSE 0 END) AS refusals
                FROM interaction_history
                WHERE task_type = 'chat'
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at) DESC
                """,
                (_CANNED_REFUSAL,),
            )
            rows = await cursor.fetchall()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DB query failed: {exc}",
        ) from exc

    days = [
        {
            "date": row["day"],
            "turns": row["turns"],
            "refusals": row["refusals"],
            "input_tokens": None,   # TODO: tokens require log shipper integration
            "output_tokens": None,  # TODO: tokens require log shipper integration
        }
        for row in rows
    ]

    total_turns = sum(d["turns"] for d in days)
    total_refusals = sum(d["refusals"] for d in days)

    return {
        "days": days,
        "totals": {
            "turns": total_turns,
            "refusals": total_refusals,
            "input_tokens": None,
            "output_tokens": None,
        },
        "note": "token totals require log shipper integration (future PR)",
    }
