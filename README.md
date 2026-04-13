# Esports Community Mod + FAQ Copilot

Discord-first, locally hosted proof of concept for a Call of Duty community moderation and FAQ assistant.

## Project Summary
This project demonstrates how an LLM application can improve moderation and support workflows for a large esports Discord server. The app combines a Discord bot with a one-page moderator dashboard. It answers repetitive fan questions, summarizes announcements, drafts moderator responses, and detects rule-breaking or toxic content.

## Core Workflows
1. FAQ Copilot
2. Announcement Summarizer
3. Moderator Response Drafting
4. Toxicity / Rule Violation Detection

## Demo Modes
- **Demo Mode ON**: the system may auto-delete violating content in the sandbox server.
- **Demo Mode OFF**: the system recommends an action and requires moderator approval.

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

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/unplugged12/5544-Final.git
cd 5544-Final
cp .env.example .env
# Edit .env — fill in OPENAI_API_KEY, ANTHROPIC_API_KEY, DISCORD_TOKEN, DISCORD_GUILD_ID, SANDBOX_CHANNEL_ID

# 2. Seed the knowledge base (one-time)
cd data && pip install -r requirements.txt && python ingest.py && cd ..

# 3. Start all services
docker compose up --build

# 4. Open the dashboard
# http://localhost:5173
```

**Without Docker** (local dev):
```bash
# Terminal 1 — Backend
cd backend && pip install -r requirements.txt
SQLITE_PATH=../data/copilot.db CHROMA_PERSIST_DIR=../data/chroma uvicorn main:app --port 8000

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
