# Esports Community Mod + FAQ Copilot

Discord-first, locally hosted proof of concept for a Call of Duty community moderation and FAQ assistant.

## Project Summary
This project demonstrates how an LLM application can improve moderation and support workflows for a large esports Discord server. The app combines a Discord bot with a one-page moderator dashboard. It answers repetitive fan questions, summarizes announcements, drafts moderator responses, detects rule-breaking or toxic content, and now supports conversational @-mention chat in a sandboxed channel with full OWASP LLM guardrails.

## Core Workflows
1. FAQ Copilot
2. Announcement Summarizer
3. Moderator Response Drafting
4. Toxicity / Rule Violation Detection
5. Conversational @-mention chat (ModBot)

## Demo Modes
- **Demo Mode ON**: the system may auto-delete violating content in the sandbox server.
- **Demo Mode OFF**: the system recommends an action and requires moderator approval.

## Conversational Chat (ModBot @-mention)

Added in the ModBot Conversational Upgrade (PRs #27–#33). Lets server members have casual back-and-forth exchanges with ModBot in the designated sandbox channel.

### How it triggers
- Mention `@ModBot` in a message, or reply directly to a ModBot message.
- **Sandbox channel only** in v1, gated by `SANDBOX_CHANNEL_ID` in `.env`.
- Replies use a casual gamer tone, capped at ~1–3 sentences / 60 words.
- Short-term memory: 6 turns per (guild, channel, user) with a 15-minute sliding TTL.

### Guardrails (OWASP LLM Top 10 2025)

The feature was designed against OWASP LLM Top 10 2025 (LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM05 Excessive Agency, LLM07 Insecure Plugin Design, LLM10 Unbounded Consumption). See `backend/tests/test_chat_adversarial.py` for the 15-case mocked adversarial test suite that serves as the authoritative threat-model spec.

- **Input sanitization**: strips Discord mentions, markdown link titles, raw URLs, control chars, and zero-width chars; neutralizes delimiter sequences (`<<<` / `>>>` → guillemets).
- **Output scrubbing**: secret regex catches `sk-...`, `sk-ant-...`, 20+ hex strings, `Bearer <token>`, and Discord bot token patterns; URL allowlist defaults to `discord.com`.
- **ID validation**: Snowflake regex (`\d{1,20}`) applied to all Discord ID fields before use.
- **Rate limiting**: 6 triggers/user/min, 60 triggers/guild/min (sliding window).
- **Auto-timeout**: >5 injection-marker hits in 10 min triggers a 1-hour ban.
- **Mention scope**: every reply uses `discord.AllowedMentions(users=[author], everyone=False, roles=False)`.
- **Adversarial CI**: 15-case mocked test suite in `backend/tests/test_chat_adversarial.py`.

### Required env vars (chat feature)

These are **in addition to** the base vars from the Quick Start (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DISCORD_TOKEN`, `DISCORD_GUILD_ID`, `SANDBOX_CHANNEL_ID`) — the chat feature does not run without all of them. Three vars specific to chat **must** be set to real values before running (see `.env.example` for full comments):

| Variable | Purpose |
|---|---|
| `CHAT_LOG_HMAC_SECRET` | HMAC-SHA256 secret for pseudonymising user IDs in structured logs. Logs emit `user_id_hash=null` and a one-per-process error if left as the sentinel. |
| `CHAT_ADMIN_TOKEN` | Bearer token for `GET /api/metrics/chat`. Endpoint returns 503 if left as the sentinel. |
| `CHAT_ENABLED` | Kill switch (default `true`). Set `false` + restart to disable the feature at the env layer. |

Generate secrets:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Optional tuning knobs (all have sensible defaults): `CHAT_MODEL_MAX_TOKENS`, `CHAT_INPUT_MAX_CHARS`, `CHAT_HISTORY_MAX_TURNS`, `CHAT_HISTORY_TTL_MINUTES`, `CHAT_ALLOWED_URL_DOMAINS`, `CHAT_DAILY_TOKEN_BUDGET`, `CHAT_MAX_USER_PER_MIN`, `CHAT_MAX_GUILD_PER_MIN`.

### Operational controls

- **Admin slash command**: `/toggle-chat enabled:false` — admin-only; invalidates the 30-second settings cache immediately, no redeploy needed.
- **Metrics endpoint**: `GET /api/metrics/chat` with `Authorization: Bearer $CHAT_ADMIN_TOKEN` — returns daily turn counts and refusal counts.
- **3-layer kill switch**:
  1. Env var: set `CHAT_ENABLED=false` and restart (hard off at startup).
  2. DB flag: `/toggle-chat` or `POST /api/settings/chat-enabled` — takes effect within ~30 s via cache expiry.
  3. Cog removal: unload the `ChatCog` from the bot process entirely.
- **Drift warnings**: backend logs emit a warning when refusal rate exceeds 20% or average output length falls below 20 chars over a rolling 1-hour window (sampled every 50th turn).

### Cost estimate

| Scenario | Cost |
|---|---|
| Per turn (gpt-4o-mini) | ~$0.00024 |
| 100 DAU × 20 turns/day | ~$0.48/day |
| Configured budget ceiling | `CHAT_DAILY_TOKEN_BUDGET=200000` tokens (see note below) |

> **Note**: `CHAT_DAILY_TOKEN_BUDGET` is a documented ceiling, **not a runtime-enforced hard cap** — the chat request path does not currently block turns when the budget is exceeded. Treat the value as an upper-bound target and monitor real usage via `GET /api/metrics/chat`. Runtime enforcement is tracked in [#35](https://github.com/unplugged12/5544-Final/issues/35).

## Primary Stack
- React + Vite frontend
- FastAPI backend
- discord.py bot
- SQLite for structured storage
- Chroma for retrieval
- OpenAI primary provider
- Anthropic fallback provider
- Docker Compose for local deployment

## Repository Docs
- [`docs/KANBAN_BOARD.md`](docs/KANBAN_BOARD.md) - Kanban-style tracking board and delivery plan
- [`docs/MODULE_BUILD_GUIDE.md`](docs/MODULE_BUILD_GUIDE.md) - detailed module-by-module implementation guide for the team and coding agents
- [`docs/AGENT_BUILD_PROMPTS.md`](docs/AGENT_BUILD_PROMPTS.md) - self-contained, one-shot build prompts for coding agents (4 prompts covering Data Seed, Backend, Frontend, Discord Bot)
- [`backend/tests/test_chat_adversarial.py`](backend/tests/test_chat_adversarial.py) - 15-case OWASP-mapped adversarial test suite (authoritative threat-model reference)

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/unplugged12/5544-Final.git
cd 5544-Final
cp .env.example .env
# Edit .env — fill in OPENAI_API_KEY, ANTHROPIC_API_KEY, DISCORD_TOKEN, DISCORD_GUILD_ID, SANDBOX_CHANNEL_ID, CHAT_LOG_HMAC_SECRET, CHAT_ADMIN_TOKEN

# 2. Seed the knowledge base (one-time)
cd data && pip install -r requirements.txt && python ingest.py && cd ..

# 3. Start all services
docker compose up --build

# 4. Open the dashboard
# http://localhost:15173   (backend API at http://localhost:18000)
```

**Without Docker** (local dev):
```bash
# Terminal 1 — Backend
cd backend && pip install -r requirements.txt
SQLITE_PATH=../data/copilot.db CHROMA_PERSIST_DIR=../data/chroma uvicorn main:app --port 18000

# Terminal 2 — Frontend
cd frontend && npm install && npm run dev

# Terminal 3 — Bot (optional)
cd bot && pip install -r requirements.txt && python main.py
```

## Testing

```bash
# Data integrity tests (no dependencies needed)
pytest data/tests/ -v

# Backend tests (mocked LLM — no API keys required)
cd backend && pip install -r requirements.txt && pytest tests/ -v

# Frontend build check
cd frontend && npm run build
```

CI runs automatically on push/PR via `.github/workflows/ci.yml`.

## Seeded Community Theme
Call of Duty competitive Discord server with rules, FAQs, announcements, mod notes, and seeded moderation test cases.

## High-Level Success Criteria
- Discord bot responds to slash commands for FAQ, summaries, and mod drafting
- Passive monitoring analyzes new messages in a sandbox moderation channel
- Violations are explained with a matched rule and suggested action
- Citations appear in grounded answers
- Dashboard shows knowledge sources, review queue, and moderation history
- Conversational @-mention chat in the sandbox channel with full OWASP LLM guardrails and 3-layer kill switch
