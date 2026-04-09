# Agent Build Prompts — Esports Community Mod + FAQ Copilot

These are detailed, self-contained prompts designed to be fed to a coding agent (Claude, Codex, etc.) to build each component in one shot. Each prompt includes the full interface contracts, file manifests, build ordering, and explicit warnings so the agent can execute without guesswork.

## Execution Order

```
PROMPT 1: Data Seed Pack (first — everything else depends on this data)
     |
     v
PROMPT 2: Backend API (second — consumes seed data, exposes API)
     |
     v
PROMPT 3: Frontend Dashboard  }  (third — both consume the backend API,
PROMPT 4: Discord Bot          }   can run in parallel with each other)
```

After all 4 components are built, create the root-level `docker-compose.yml` and `.env.example` to wire them together (instructions at the end of this document).

---

## Prompt 1 — Data Seed Pack

### Copy everything below this line into the agent prompt:

---

You are building the **Data Seed Pack** for an esports Discord moderation copilot. This component provides all the seeded content for a fictional Call of Duty competitive community Discord server called **CDL Ranked Discord**.

### Tech Stack

- Python 3.11+
- JSON files for seed data
- `chromadb` (PersistentClient) for vector storage
- `sentence-transformers` for embeddings (model: `all-MiniLM-L6-v2`)
- `sqlite3` (stdlib) for structured storage

### File Manifest

Create every file listed below. No other files are needed.

```
data/
├── seed/
│   ├── rules.json
│   ├── faqs.json
│   ├── announcements.json
│   ├── mod_notes.json
│   ├── test_questions.json
│   ├── test_toxic_messages.json
│   └── test_edge_cases.json
├── ingest.py
└── requirements.txt
```

### Build Order

Create files in this exact order:

1. `rules.json` — everything else references rule IDs
2. `faqs.json` — references rule IDs and tournament names from announcements
3. `announcements.json` — standalone, uses consistent channel names
4. `mod_notes.json` — references rule numbers and procedures
5. `test_questions.json` — must reference FAQ topics that actually exist
6. `test_toxic_messages.json` — must map to specific rule IDs from rules.json
7. `test_edge_cases.json` — deliberately ambiguous, references real rules
8. `requirements.txt`
9. `ingest.py` — last, because it parses all JSON files above

### Shared Constants

Use these consistently across ALL files:

**Server name:** CDL Ranked Discord
**Game title:** Call of Duty: Black Ops 7 (BO7)
**Current season:** Season 2 (Spring 2026)
**Major tournament:** Spring Major Qualifier (April 19, 2026)
**Weekly event:** Wednesday Night Wagers (8pm ET)
**Casual event:** Friday Pub Stomp Night

**source_id format:** `{type}_{three_digit_index}` — e.g., `rule_001`, `faq_012`, `ann_003`, `mod_005`
This format is critical — the backend, frontend, and Discord bot all use these IDs for citations. Do not deviate.

**Channel names** (use these exact names with `#` prefix in content):
`#general`, `#competitive`, `#ranked-lfg`, `#tournament-info`, `#tournament-signup`, `#tournament-rules`, `#match-results`, `#dispute-resolution`, `#announcements`, `#rules`, `#verify`, `#rank-verify`, `#content-share`, `#memes`, `#clan-recruitment`, `#bot-commands`, `#mod-discussion`, `#mod-log`, `#appeals`, `#report-cheaters`, `#international`, `#leaks-spoilers`, `#mod-applications`, `#streaming`, `#sandbox`

**Date format:** ISO 8601 strings (`"2026-04-01"`)

### JSON Schemas

#### rules.json

```json
{
  "rules": [
    {
      "source_id": "rule_001",
      "rule_number": 1,
      "title": "No Harassment or Bullying",
      "description": "Do not target, harass, threaten, or bully any member. This includes persistent unwanted messages, dogpiling, and intimidation. Competitive trash talk must stay about gameplay, never about a person's identity or personal life.",
      "category": "conduct",
      "severity_default": "high",
      "tags": ["harassment", "bullying", "conduct"],
      "citation_label": "Rule 1: No Harassment or Bullying"
    }
  ]
}
```

Create **18 rules** covering these categories:

| # | Title | Category | Severity | Key Details |
|---|-------|----------|----------|-------------|
| 1 | No Harassment or Bullying | conduct | high | Personal attacks, dogpiling, intimidation; gameplay trash talk OK |
| 2 | No Hate Speech or Slurs | conduct | critical | Zero tolerance; text, voice, nicknames, profile images |
| 3 | No Spam or Flooding | content | low | Repeated messages, copypasta, emoji spam, rapid-fire posting |
| 4 | No Unauthorized Self-Promotion | content | low | No Twitch/YouTube outside #content-share; no DM promotion |
| 5 | No Spoilers for Unreleased Content | content | medium | Leaked gameplay, datamined info requires spoiler tags in #leaks-spoilers |
| 6 | Stay On Topic | server | low | Use channels for designated purpose |
| 7 | No Impersonation | conduct | high | Staff, pro players, content creators, other members |
| 8 | No Account Trading or Selling | content | high | No selling/buying/trading accounts, boosting, unlock services |
| 9 | No Cheating Discussion or Promotion | competitive | critical | No sharing, promoting, or discussing cheats/exploits |
| 10 | Respect Staff Decisions | conduct | medium | No arguing mod decisions publicly; use #appeals |
| 11 | No NSFW Content | content | high | No pornography, gore, explicit content anywhere |
| 12 | Voice Chat Conduct | voice | medium | No mic spamming, soundboards, screaming; same rules as text |
| 13 | Tournament Conduct | competitive | high | No match-fixing, intentional disconnects, unsportsmanlike behavior |
| 14 | Clan Recruitment Rules | server | low | #clan-recruitment only; max 1 post per clan per 48 hours |
| 15 | English in Main Channels | server | low | Main channels English-only; other languages in #international |
| 16 | No Doxxing or Sharing Personal Info | conduct | critical | Never share another person's real name, address, photo |
| 17 | Follow Discord TOS | server | medium | All Discord Terms of Service apply; minimum age 13 |
| 18 | One Account Per Person | server | medium | No alt accounts; all accounts banned if detected |

Write realistic, complete description text for each rule (2-4 sentences). Do NOT use placeholder text.

#### faqs.json

```json
{
  "faqs": [
    {
      "source_id": "faq_001",
      "question": "When is the next tournament?",
      "answer": "Our next tournament is the Spring Major Qualifier on April 19, 2026. Registration closes April 16. Check #tournament-info for bracket details and sign-up links.",
      "category": "tournaments",
      "tags": ["tournament", "schedule", "registration"],
      "citation_label": "FAQ: Tournament Schedule"
    }
  ]
}
```

Create **30 FAQs** across these categories:
- **tournaments** (8-10): next tournament, sign-up, format (4v4 HP/SnD/Control), entry fee, prize pool ($500 credit), roster lock, substitutes, scheduling, bracket location, Wednesday Night Wagers
- **competitive** (6-8): banned weapons/GAs, controller vs MnK, rank requirements (Gold III minimum), ladder system, map rotation, reporting cheaters, Gentleman's Agreements
- **roles** (5-6): Verified role, Competitor role, moderator applications, role list, nickname changes, clip sharing
- **technical** (3-4): server region (NA East primary), hardware requirements, Discord overlay, posting permissions
- **streaming** (2-3): tournament stream link (Twitch.tv/CDLRankedDiscord), POV streaming rules (2-min delay), Streamer role

Each answer must be 2-5 sentences, conversational, and reference channel names or dates from announcements where applicable.

#### announcements.json

```json
{
  "announcements": [
    {
      "source_id": "ann_001",
      "title": "Spring Major Qualifier — Registration Open",
      "content": "Registration is now open for the CDL Ranked Discord Spring Major Qualifier! Date: April 19, 2026. Format: 4v4 Hardpoint/S&D/Control. Entry: Free. Prize pool: $500 credit. Teams must register in #tournament-signup by April 16. All players must be verified members with at least 7 days server tenure. Full rules in #tournament-rules.",
      "date": "2026-04-01",
      "category": "tournament",
      "tags": ["tournament", "spring-major", "registration"],
      "citation_label": "Announcement: Spring Major Qualifier (Apr 1)"
    }
  ]
}
```

Create **12 announcements** with dates in March-April 2026:
1. Spring Major Qualifier registration (Apr 1, tournament)
2. BO7 Season 2 patch notes impact on GAs (Mar 28, patch)
3. Roster change deadline reminder (Apr 5, roster)
4. Server maintenance April 12 (Apr 8, maintenance)
5. New map "Checkpoint" added to rotation (Mar 20, patch)
6. Rule update: clan recruitment cooldown changed to 48h (Mar 15, rule-update)
7. Wednesday Night Wagers Season 2 schedule (Mar 10, tournament)
8. Community Movie Night cancelled/rescheduled (Apr 6, community)
9. Stream schedule update for April (Apr 1, streaming)
10. Prize pool increase from $300 to $500 (Apr 3, tournament)
11. Seasonal rank reset coming April 25 (Apr 7, patch)
12. New moderator applications open (Mar 25, community)

Each announcement should be 3-8 sentences with specific dates, times, and channel references.

#### mod_notes.json

```json
{
  "mod_notes": [
    {
      "source_id": "mod_001",
      "title": "Repeat Offender Escalation",
      "content": "When a user has 2+ warnings within 30 days, escalate to a 24-hour timeout on the next offense. If the user has 3+ timeouts in 90 days, bring to #mod-discussion for potential ban vote. Always check /modlog before issuing punishment to see prior history.",
      "context": "escalation",
      "tags": ["escalation", "repeat-offender", "timeout", "ban"],
      "citation_label": "Mod Note: Repeat Offender Escalation"
    }
  ]
}
```

Create **10 mod notes** across these contexts:
1. Repeat offender escalation (escalation)
2. Timeout vs ban guidelines (procedure)
3. Appeal process (appeal)
4. Common false positives in toxicity detection (false-positive)
5. Handling tournament disputes (dispute)
6. When to involve senior mods (escalation)
7. Post-match toxicity protocol — 15-min cool-down window (procedure)
8. Raid response procedure (procedure)
9. Handling cheating accusations (dispute)
10. Cultural context for competitive trash talk (false-positive) — "you're free" / "no shot" / "bot" = standard banter, not harassment; "kys" / personal attacks = always violation

Each note should be 2-5 sentences of internal moderator guidance.

#### test_questions.json

```json
{
  "test_questions": [
    {
      "question_id": "tq_001",
      "question": "hey when does the next tourney start?",
      "expected_source_type": "faq",
      "expected_topic": "tournament-schedule",
      "difficulty": "easy"
    }
  ]
}
```

Create **20 test questions** written in casual Discord style (lowercase, slang, abbreviations). Distribution: 8 easy (direct match), 8 medium (paraphrased), 4 hard (requires synthesis from multiple sources). Every question must be answerable from the seed data.

#### test_toxic_messages.json

```json
{
  "test_toxic_messages": [
    {
      "message_id": "tx_001",
      "content": "you're literal garbage uninstall the game and never come back nobody wants you here",
      "expected_violation_type": "harassment",
      "expected_severity": "high",
      "expected_rule_match": "rule_001",
      "explanation": "Targets a specific person with demeaning language and exclusion. Crosses from trash talk into personal attack."
    }
  ]
}
```

Create **20 toxic messages** distributed across violation types:
- harassment (3-4, map to rule_001)
- hate_speech (2-3, map to rule_002) — use `[slur]` placeholders, NEVER actual slurs
- spam (2-3, map to rule_003) — repeated text, all-caps flooding
- self_promo (2, map to rule_004) — Twitch/YouTube plugs in wrong channel
- spoiler (1-2, map to rule_005)
- account_trading (1-2, map to rule_008) — selling accounts/boosting
- cheating_promo (1-2, map to rule_009) — discussing cheat tools
- tournament_misconduct (1-2, map to rule_013) — match-fixing, rage quitting

Every `expected_rule_match` MUST reference a valid `source_id` from rules.json. Severity distribution: 3-4 critical, 6-8 high, 4-5 medium, 3-4 low.

#### test_edge_cases.json

```json
{
  "test_edge_cases": [
    {
      "case_id": "ec_001",
      "content": "dude you are ACTUALLY the worst player I have ever seen in ranked lmaooo",
      "ambiguity_reason": "Could be friendly banter between teammates or targeted harassment depending on context and relationship",
      "possible_violations": ["harassment", "no_violation"],
      "expected_action": "flag_for_review"
    }
  ]
}
```

Create **10 edge cases** — each must have genuine ambiguity where a reasonable moderator could argue either way:
1. Competitive trash talk — borderline personal attack vs standard banter
2. Sarcasm misread as toxic — frustrated venting vs passive-aggressive
3. Legitimate frustration vs harassment — complaining about a specific player
4. Quoting someone else's violation — contains slur but is reporting, not committing
5. Asking about a rule, not violating it — "is account selling banned here?"
6. Cultural communication style — intense FPS banter that reads as harassment outside context
7. Copypasta/meme — single long joke post vs spam
8. Self-promotion in context — sharing a clip in #general vs #content-share
9. Rage quit announcement — negativity about game/devs vs toxicity toward community
10. Joking about cheating — bragging about good aim vs implying actual cheats

### requirements.txt

```
chromadb>=1.0.0
sentence-transformers>=2.2.0
```

### ingest.py Specification

The ingestion script reads all 4 knowledge JSON files, stores structured records in SQLite, chunks text, embeds into Chroma.

**Database path:** `data/copilot.db` (sibling to the `seed/` folder)
**Chroma persist path:** `data/chroma/`
**Chroma collection name:** `knowledge_base`
**Embedding function:** `SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")` from `chromadb.utils.embedding_functions`

**SQLite schema (create this table):**

```sql
CREATE TABLE IF NOT EXISTS knowledge_items (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL CHECK(source_type IN ('rule','faq','announcement','mod_note')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    citation_label TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Ingestion flow:**
1. Connect to SQLite, create table if not exists
2. Initialize Chroma `PersistentClient(path="data/chroma")`
3. Delete collection `"knowledge_base"` if exists, then create fresh (idempotency)
4. Pass `SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")` to the collection
5. Clear SQLite `knowledge_items` table (`DELETE FROM knowledge_items`)
6. For each JSON file (rules, faqs, announcements, mod_notes):
   - Read and parse JSON
   - For each item: insert into SQLite (`source_id`, `source_type`, `title`, `content`, `category`, `tags` as JSON string, `citation_label`)
   - Map source_type: rules.json → `"rule"`, faqs.json → `"faq"`, announcements.json → `"announcement"`, mod_notes.json → `"mod_note"`
   - For rules: chunk text = `"Rule {rule_number}: {title}\n{description}"`
   - For FAQs: chunk text = `"Q: {question}\nA: {answer}"`
   - For announcements: chunk text = `"{title}\n{content}"` — if content > 500 chars, split at sentence boundaries into ~400 char chunks with 50 char overlap
   - For mod notes: chunk text = `"{title}\n{content}"`
7. Add all chunks to Chroma with:
   - `ids`: `["{source_id}_chunk_0", "{source_id}_chunk_1", ...]`
   - `documents`: `[chunk_text, ...]`
   - `metadatas`: `[{"source_id": "...", "source_type": "...", "title": "...", "citation_label": "...", "category": "...", "chunk_index": 0}, ...]`
8. Print summary: total items per type, total chunks in Chroma

**Validation (run after ingestion):**
- Load test_toxic_messages.json, verify every `expected_rule_match` exists in the SQLite knowledge_items table
- Print pass/fail count

**Run via:** `python data/ingest.py` from the project root

### Warnings

1. **Do NOT generate placeholder or lorem-ipsum content.** Every rule must read like a real esports server rule. Every FAQ answer must be substantive (2-5 sentences). Every announcement must have specific dates and details.
2. **Ensure referential integrity.** Every `expected_rule_match` in toxic messages must correspond to a valid `source_id` in rules.json. FAQ answers that mention tournament dates must match announcement dates.
3. **Use consistent channel names.** Only use channels from the shared constants list above.
4. **Do NOT use chromadb's default embedding function.** Explicitly instantiate `SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")` and pass it to `get_or_create_collection()`. The backend will use the same model — a mismatch causes silent retrieval failures.
5. **The ingest script must be idempotent.** Deleting and recreating the Chroma collection + clearing the SQLite table achieves this.
6. **For hate speech test messages, use `[slur]` placeholders.** Never include actual slurs, racial epithets, or genuinely harmful language.
7. **Tags must be lowercase strings.** Store as a JSON array string in SQLite (e.g., `'["harassment", "bullying"]'`).

### Validation Checklist

After building, verify:
- [ ] `python data/ingest.py` runs without errors
- [ ] SQLite `data/copilot.db` contains 70+ records in `knowledge_items` (18 rules + 30 FAQs + 12 announcements + 10 mod notes)
- [ ] Chroma collection `knowledge_base` has 70+ chunks
- [ ] Every `expected_rule_match` in test_toxic_messages.json has a matching `source_id` in rules.json
- [ ] All JSON files are valid JSON (no trailing commas, no comments)

---

## Prompt 2 — Backend API

### Copy everything below this line into the agent prompt:

---

You are building the **Backend API** for an esports Discord moderation copilot. This is a FastAPI application that serves as the orchestration layer — it receives requests from a React frontend and Discord bot, performs retrieval-augmented generation, calls LLM providers, normalizes outputs, stores results, and returns structured responses.

### Tech Stack

- Python 3.11
- FastAPI 0.115+
- uvicorn 0.34+
- pydantic 2.x + pydantic-settings 2.x
- aiosqlite 0.20+
- chromadb 1.x (PersistentClient, embedded — no server)
- openai 1.x (AsyncOpenAI)
- anthropic 0.40+ (AsyncAnthropic)
- sentence-transformers (model: `all-MiniLM-L6-v2`)

### File Manifest

Create every file listed below. No other files are needed.

```
backend/
├── main.py
├── config.py
├── database.py
├── Dockerfile
├── requirements.txt
├── .env.example
├── models/
│   ├── __init__.py
│   ├── enums.py
│   └── schemas.py
├── routes/
│   ├── __init__.py
│   ├── health.py
│   ├── faq.py
│   ├── announcements.py
│   ├── moderation.py
│   ├── settings.py
│   ├── history.py
│   └── sources.py
├── services/
│   ├── __init__.py
│   ├── provider_service.py
│   ├── retrieval_service.py
│   ├── faq_service.py
│   ├── summary_service.py
│   ├── mod_draft_service.py
│   ├── moderation_service.py
│   └── audit_service.py
├── providers/
│   ├── __init__.py
│   ├── base.py
│   ├── openai_provider.py
│   └── anthropic_provider.py
├── prompts/
│   ├── __init__.py
│   ├── faq_prompt.py
│   ├── summary_prompt.py
│   ├── mod_draft_prompt.py
│   └── moderation_prompt.py
└── repositories/
    ├── __init__.py
    ├── knowledge_repo.py
    ├── moderation_repo.py
    ├── history_repo.py
    └── settings_repo.py
```

### Build Order

Create files in this exact phase order. Within each phase, create files in the listed order.

**Phase 1 — Foundation (models + config):**
1. `models/enums.py`
2. `models/schemas.py`
3. `models/__init__.py`
4. `config.py`
5. `database.py`

**Phase 2 — Data layer (repositories):**
6. `repositories/knowledge_repo.py`
7. `repositories/settings_repo.py`
8. `repositories/moderation_repo.py`
9. `repositories/history_repo.py`
10. `repositories/__init__.py`

**Phase 3 — LLM layer (prompts + providers):**
11. `prompts/faq_prompt.py`
12. `prompts/summary_prompt.py`
13. `prompts/mod_draft_prompt.py`
14. `prompts/moderation_prompt.py`
15. `prompts/__init__.py`
16. `providers/base.py`
17. `providers/openai_provider.py`
18. `providers/anthropic_provider.py`
19. `providers/__init__.py`

**Phase 4 — Business logic (services):**
20. `services/provider_service.py`
21. `services/retrieval_service.py`
22. `services/audit_service.py`
23. `services/faq_service.py`
24. `services/summary_service.py`
25. `services/mod_draft_service.py`
26. `services/moderation_service.py`
27. `services/__init__.py`

**Phase 5 — HTTP layer (routes):**
28. `routes/health.py`
29. `routes/sources.py`
30. `routes/faq.py`
31. `routes/announcements.py`
32. `routes/moderation.py`
33. `routes/settings.py`
34. `routes/history.py`
35. `routes/__init__.py`

**Phase 6 — Wiring + deployment:**
36. `main.py`
37. `requirements.txt`
38. `.env.example`
39. `Dockerfile`

### Interface Contracts

#### Enums

```python
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
```

#### API Response Models

**TaskResponse** — returned by `/faq/ask`, `/announcements/summarize`, `/moderation/draft`:

```json
{
  "task_type": "faq|summary|mod_draft",
  "output_text": "The grounded answer text...",
  "citations": [
    {"source_id": "rule_003", "citation_label": "Rule 3: No Spam or Flooding", "snippet": "First 150 chars of source content..."}
  ],
  "confidence_note": "High confidence — directly supported by Rule 3",
  "matched_rule": "Rule 3: No Spam or Flooding",
  "severity": null,
  "suggested_action": null,
  "raw_source_ids": ["rule_003", "rule_006"]
}
```

**ModerationEventResponse** — returned by `/moderation/analyze`, `/moderation/approve/{id}`, `/moderation/reject/{id}`, items in `/history`:

```json
{
  "event_id": "a1b2c3d4",
  "message_content": "the original flagged message",
  "violation_type": "harassment",
  "matched_rule": "Rule 1: No Harassment or Bullying",
  "explanation": "This message targets a specific user with demeaning language...",
  "severity": "high",
  "suggested_action": "remove_message",
  "status": "pending",
  "source": "discord",
  "created_at": "2026-04-09T12:00:00",
  "resolved_at": null,
  "resolved_by": null
}
```

#### Route Table

| Method | Path | Request Body | Response | Notes |
|--------|------|-------------|----------|-------|
| GET | `/api/health` | — | `{"status": "ok", "demo_mode": bool, "provider": str, "knowledge_count": int}` | |
| GET | `/api/sources` | query: `?source_type=rule` | `{"sources": [KnowledgeItem], "total": int}` | |
| POST | `/api/faq/ask` | `{"question": str}` | `TaskResponse` | Retrieves from rules, FAQs, announcements |
| POST | `/api/announcements/summarize` | `{"text": str}` | `TaskResponse` | No retrieval needed — text provided directly |
| POST | `/api/moderation/draft` | `{"situation": str}` | `TaskResponse` | Retrieves from rules and mod_notes |
| POST | `/api/moderation/analyze` | `{"message_content": str, "source": "discord"\|"dashboard"}` | `ModerationEventResponse` | Creates a moderation_event in SQLite |
| POST | `/api/moderation/approve/{event_id}` | `{}` | `ModerationEventResponse` | Sets status=approved, resolved_at=now |
| POST | `/api/moderation/reject/{event_id}` | `{}` | `ModerationEventResponse` | Sets status=rejected, resolved_at=now |
| GET | `/api/settings/demo-mode` | — | `{"demo_mode": bool}` | |
| POST | `/api/settings/demo-mode` | `{"enabled": bool}` | `{"demo_mode": bool}` | |
| GET | `/api/history` | query: `?limit=50&offset=0` | `{"events": [ModerationEventResponse], "total": int}` | Returns moderation_events ordered by created_at DESC |

#### SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS knowledge_items (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL CHECK(source_type IN ('rule','faq','announcement','mod_note')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    citation_label TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_knowledge_source_type ON knowledge_items(source_type);

CREATE TABLE IF NOT EXISTS moderation_events (
    event_id TEXT PRIMARY KEY,
    message_content TEXT NOT NULL,
    violation_type TEXT NOT NULL,
    matched_rule TEXT,
    explanation TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('low','medium','high','critical')),
    suggested_action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','auto_actioned')),
    source TEXT NOT NULL DEFAULT 'dashboard' CHECK(source IN ('discord','dashboard')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolved_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_mod_events_status ON moderation_events(status);
CREATE INDEX IF NOT EXISTS idx_mod_events_created ON moderation_events(created_at DESC);

CREATE TABLE IF NOT EXISTS interaction_history (
    interaction_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL CHECK(task_type IN ('faq','summary','mod_draft','moderation')),
    input_text TEXT NOT NULL,
    output_text TEXT NOT NULL,
    citations TEXT NOT NULL DEFAULT '[]',
    provider_used TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Seed `app_settings` with `INSERT OR IGNORE INTO app_settings VALUES ('demo_mode', 'true')` during DB init.

#### Environment Variables

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
PRIMARY_PROVIDER=openai
FALLBACK_PROVIDER=anthropic
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_MODEL=claude-sonnet-4-20250514
SQLITE_PATH=./data/copilot.db
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_COLLECTION=knowledge_base
EMBEDDING_MODEL=all-MiniLM-L6-v2
TOP_K_RESULTS=5
FRONTEND_URL=http://localhost:5173
LOG_LEVEL=INFO
```

### Per-File Specifications

#### config.py
Use `pydantic_settings.BaseSettings` with `env_file = ".env"`. Define all env vars above with their defaults.

#### database.py
- `init_db()`: async function that creates tables using aiosqlite, seeds app_settings demo_mode default
- `get_db()`: async context manager that returns aiosqlite connection with `row_factory = aiosqlite.Row` and `PRAGMA journal_mode=WAL`
- Use `async with aiosqlite.connect(path) as db:` pattern — new connection per call. Do NOT create a module-level connection.

#### providers/base.py
Abstract base class `BaseLLMProvider` with 4 abstract async methods:
- `generate_grounded_answer(query: str, context_chunks: list[dict], system_prompt: str) -> ProviderResponse`
- `generate_summary(text: str, system_prompt: str) -> ProviderResponse`
- `generate_mod_draft(situation: str, context_chunks: list[dict], system_prompt: str) -> ProviderResponse`
- `generate_moderation_analysis(message_content: str, rule_chunks: list[dict], system_prompt: str) -> ProviderResponse`

`ProviderResponse` dataclass: `text: str`, `provider_name: str`, `model: str`, `usage: dict`

#### providers/openai_provider.py
Use `AsyncOpenAI`. For each method: build messages list with system + user, call `chat.completions.create()`. For `generate_moderation_analysis`, add `response_format={"type": "json_object"}` to force JSON output. Format context chunks as `"[{citation_label}]: {content}"` blocks in the user message.

#### providers/anthropic_provider.py
Use `AsyncAnthropic`. For each method: call `messages.create()` with `system=` parameter (string, NOT in messages array). Access response via `resp.content[0].text`. Note: Anthropic has no `response_format` — the prompt must instruct JSON output.

#### services/provider_service.py
Instantiates both providers. `call(method_name: str, **kwargs) -> ProviderResponse` tries primary, catches exceptions, falls back to secondary. Uses `getattr(provider, method_name)`. Logs which provider was used.

#### services/retrieval_service.py
- Initialize Chroma `PersistentClient(path=settings.CHROMA_PERSIST_DIR)`
- Get collection `settings.CHROMA_COLLECTION` with `SentenceTransformerEmbeddingFunction(model_name=settings.EMBEDDING_MODEL)`
- `retrieve(query: str, source_types: list[str] | None, top_k: int) -> list[dict]`: calls `collection.query()`, returns list of `{"content", "source_id", "citation_label", "title", "source_type", "distance"}`
- If `source_types` provided, use `where={"source_type": {"$in": source_types}}`

#### services/faq_service.py, summary_service.py, mod_draft_service.py
Each service: retrieves context (if needed), calls `provider_service.call()` with the appropriate method name and prompt, parses the response into a `TaskResponse`, logs via `audit_service`.

#### services/moderation_service.py
This is the most complex service:
1. Retrieve rule chunks (`source_types=["rule", "mod_note"]`)
2. Call `provider_service.call("generate_moderation_analysis", ...)`
3. Parse JSON from `result.text` — **strip markdown fences first**: `text.strip().removeprefix("```json").removesuffix("```").strip()`
4. Extract: `violation_type`, `matched_rule`, `explanation`, `severity`, `suggested_action`, `confidence_note`
5. Wrap JSON parsing in try/except — if parsing fails, set `violation_type="no_violation"` with explanation "Analysis could not be parsed"
6. Check demo_mode via `settings_repo.get("demo_mode")`
7. If demo_mode AND suggested_action in (remove_message, timeout, escalate): set status to `auto_actioned`; else set to `pending`
8. Create moderation_event in SQLite via `moderation_repo`
9. Log via audit_service
10. Return `ModerationEventResponse`

#### Prompt Templates
Each file in `prompts/` exports a `get_system_prompt() -> str` function.

**faq_prompt.py**: Instruct the LLM to answer ONLY from provided context, cite sources using bracket labels, keep answers 2-4 sentences, include confidence note (High/Moderate/Low), and say "I don't have enough approved information" if context is insufficient.

**summary_prompt.py**: Instruct to summarize into 2-5 bullet points, ALWAYS preserve exact dates/times/deadlines/URLs, highlight action items and policy changes.

**mod_draft_prompt.py**: Instruct to draft professional calm response under 150 words, reference relevant rule with bracket label, suggest action level, never be hostile or sarcastic.

**moderation_prompt.py**: Instruct to return ONLY valid JSON with fields: `violation_type`, `matched_rule`, `explanation`, `severity`, `suggested_action`, `confidence_note`. Provide guidelines: hate speech = critical, personal attacks = high minimum, spam = medium, ambiguous = low with escalate. If no violation, use `no_violation` type with `no_action`.

#### main.py
- Create FastAPI app with lifespan context manager
- Lifespan startup: call `init_db()`, initialize retrieval service (this ensures Chroma collection is accessible)
- Add CORSMiddleware with `allow_origins=["*"]` BEFORE including routers
- Include all routers with appropriate prefixes: `/api` for health, `/api/faq` for faq, etc.

### requirements.txt

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
aiosqlite>=0.20.0
chromadb>=1.0.0
openai>=1.0.0
anthropic>=0.40.0
sentence-transformers>=2.2.0
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model at build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Warnings

1. **Use `aiosqlite`, not `sqlite3`.** FastAPI is async. Synchronous SQLite calls block the event loop. Every database call must use `async with aiosqlite.connect(path) as db:`.
2. **Do NOT use SQLAlchemy or any ORM.** Raw aiosqlite with parameterized queries. Keep it simple.
3. **CORS middleware must be added BEFORE routes** in main.py. Otherwise preflight requests from the frontend fail silently.
4. **Use `chromadb.PersistentClient(path=...)`, not `Client()` or `persist_directory=`.** The Chroma API changed between versions.
5. **The `/analyze` endpoint MUST both create a moderation_event in SQLite AND return the result.** It is not just an LLM call — it persists the event with status `pending` or `auto_actioned` based on demo_mode.
6. **Strip markdown fences from LLM output before JSON parsing.** LLMs frequently return ` ```json ... ``` ` around JSON. Always do: `text.strip().removeprefix("```json").removesuffix("```").strip()` before `json.loads()`.
7. **Use `uuid.uuid4().hex` for event_id and interaction_id generation.** Do not use auto-increment integers.
8. **The Chroma embedding model MUST be `all-MiniLM-L6-v2`.** The ingest.py script uses this same model. A mismatch causes silent retrieval failures — vectors will be in different spaces.
9. **Do NOT generate seed data in the backend.** The backend reads from SQLite and Chroma stores populated by `data/ingest.py`. The lifespan should only create tables, not populate them.
10. **Provider fallback must catch specific exceptions** (`openai.APIError`, `anthropic.APIError`), not bare `except:`. Log the fallback.
11. **New aiosqlite connection per request.** Do NOT create a module-level connection — it will corrupt under concurrent access.
12. **Do NOT install or use SQLAlchemy, Flask, Django, or any framework other than FastAPI.**

### Validation Checklist

After building, verify:
- [ ] `cd backend && pip install -r requirements.txt` succeeds
- [ ] `uvicorn main:app --host 0.0.0.0 --port 8000` starts without errors
- [ ] `GET /api/health` returns `{"status": "ok", ...}`
- [ ] `GET /api/sources` returns knowledge items (after running ingest.py)
- [ ] `POST /api/faq/ask {"question": "when is the next tournament?"}` returns a TaskResponse with citations
- [ ] `POST /api/moderation/analyze {"message_content": "you are trash uninstall", "source": "dashboard"}` creates a moderation_event and returns ModerationEventResponse
- [ ] `GET /api/history` returns the created moderation events
- [ ] All responses match the documented JSON shapes exactly

---

## Prompt 3 — Frontend Dashboard

### Copy everything below this line into the agent prompt:

---

You are building the **Frontend Dashboard** for an esports Discord moderation copilot. This is a React + Vite single-page application that serves as a moderator control surface with 6 main sections.

### Tech Stack

- React 18 + React DOM
- Vite 5
- Plain CSS (CSS custom properties for theming) — NO Tailwind, NO CSS frameworks
- Native `fetch` API — NO axios
- JavaScript `.jsx` files — NO TypeScript

### File Manifest

Create every file listed below. No other files are needed.

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── Dockerfile
├── .env.example
├── .dockerignore
├── src/
│   ├── main.jsx
│   ├── App.jsx
│   ├── App.css
│   ├── index.css
│   ├── api.js
│   ├── hooks/
│   │   └── useApi.js
│   └── components/
│       ├── shared/
│       │   ├── CitationBadge.jsx
│       │   ├── CitationBadge.css
│       │   ├── SeverityBadge.jsx
│       │   ├── SeverityBadge.css
│       │   ├── RuleMatchChip.jsx
│       │   ├── RuleMatchChip.css
│       │   ├── ResponsePanel.jsx
│       │   ├── ResponsePanel.css
│       │   ├── PromptInput.jsx
│       │   ├── PromptInput.css
│       │   ├── StatusIndicator.jsx
│       │   └── StatusIndicator.css
│       ├── Sidebar.jsx
│       ├── Sidebar.css
│       ├── KnowledgeBase.jsx
│       ├── KnowledgeBase.css
│       ├── AskFaq.jsx
│       ├── AskFaq.css
│       ├── SummarizeAnnouncement.jsx
│       ├── SummarizeAnnouncement.css
│       ├── ModeratorDraft.jsx
│       ├── ModeratorDraft.css
│       ├── ReviewQueue.jsx
│       ├── ReviewQueue.css
│       ├── ModerationHistory.jsx
│       └── ModerationHistory.css
```

### Build Order

Create files in this exact order:

**Phase 1 — Scaffold (get project runnable):**
1. `package.json`
2. `vite.config.js`
3. `index.html`
4. `src/main.jsx`
5. `src/index.css` (full dark theme styles)

**Phase 2 — API layer:**
6. `.env.example`
7. `src/api.js`
8. `src/hooks/useApi.js`

**Phase 3 — Shared components (build before tabs):**
9. `src/components/shared/CitationBadge.jsx` + `.css`
10. `src/components/shared/SeverityBadge.jsx` + `.css`
11. `src/components/shared/RuleMatchChip.jsx` + `.css`
12. `src/components/shared/ResponsePanel.jsx` + `.css`
13. `src/components/shared/PromptInput.jsx` + `.css`
14. `src/components/shared/StatusIndicator.jsx` + `.css`

**Phase 4 — Tab panels (simplest to most complex):**
15. `src/components/KnowledgeBase.jsx` + `.css`
16. `src/components/AskFaq.jsx` + `.css`
17. `src/components/SummarizeAnnouncement.jsx` + `.css`
18. `src/components/ModeratorDraft.jsx` + `.css`
19. `src/components/ReviewQueue.jsx` + `.css`
20. `src/components/ModerationHistory.jsx` + `.css`

**Phase 5 — Shell (imports all components, created last):**
21. `src/components/Sidebar.jsx` + `.css`
22. `src/App.jsx` + `src/App.css`

**Phase 6 — Docker:**
23. `.dockerignore`
24. `Dockerfile`

### Backend API Contract

The backend runs at `http://localhost:8000`. The API client uses the env var `VITE_API_URL` (defaults to empty string for Vite proxy in dev).

**CRITICAL:** `VITE_API_URL` is substituted at build time by Vite and runs in the user's browser. It CANNOT use Docker service names like `http://backend:8000`. Default to empty string `""` so requests go through the Vite dev proxy, or `http://localhost:8000` for direct access.

#### TaskResponse (from POST /api/faq/ask, /api/announcements/summarize, /api/moderation/draft)

```json
{
  "task_type": "faq",
  "output_text": "The answer text...",
  "citations": [
    {"source_id": "rule_003", "citation_label": "Rule 3: No Spam", "snippet": "Do not send repeated messages..."}
  ],
  "confidence_note": "High confidence",
  "matched_rule": "Rule 3: No Spam or Flooding",
  "severity": null,
  "suggested_action": null,
  "raw_source_ids": ["rule_003"]
}
```

#### ModerationEventResponse (from /api/moderation/analyze, /api/history items)

```json
{
  "event_id": "a1b2c3d4",
  "message_content": "the flagged message text",
  "violation_type": "harassment",
  "matched_rule": "Rule 1: No Harassment or Bullying",
  "explanation": "Explanation of the violation...",
  "severity": "high",
  "suggested_action": "remove_message",
  "status": "pending",
  "source": "discord",
  "created_at": "2026-04-09T12:00:00",
  "resolved_at": null,
  "resolved_by": null
}
```

#### Route Table

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| GET | `/api/health` | — | `{"status": "ok", "demo_mode": bool}` |
| GET | `/api/sources` | query: `?source_type=rule` (optional) | `{"sources": [...], "total": int}` |
| POST | `/api/faq/ask` | `{"question": str}` | TaskResponse |
| POST | `/api/announcements/summarize` | `{"text": str}` | TaskResponse |
| POST | `/api/moderation/draft` | `{"situation": str}` | TaskResponse |
| POST | `/api/moderation/analyze` | `{"message_content": str, "source": "dashboard"}` | ModerationEventResponse |
| POST | `/api/moderation/approve/{event_id}` | `{}` | ModerationEventResponse |
| POST | `/api/moderation/reject/{event_id}` | `{}` | ModerationEventResponse |
| GET | `/api/settings/demo-mode` | — | `{"demo_mode": bool}` |
| POST | `/api/settings/demo-mode` | `{"enabled": bool}` | `{"demo_mode": bool}` |
| GET | `/api/history` | query: `?limit=50&offset=0` | `{"events": [...], "total": int}` |

### Per-Component Specifications

#### package.json

```json
{
  "name": "esports-mod-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.4.0"
  }
}
```

No other dependencies. No axios, no Tailwind, no React Router, no state management libraries.

#### vite.config.js

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

#### src/api.js

Single API client module. `BASE_URL = import.meta.env.VITE_API_URL || ""`. Export named functions for each endpoint:
- `askFaq(question)` — POST `/api/faq/ask`
- `summarize(text)` — POST `/api/announcements/summarize`
- `draftResponse(situation)` — POST `/api/moderation/draft`
- `analyzeMessage(messageContent)` — POST `/api/moderation/analyze` with `source: "dashboard"`
- `approveEvent(eventId)` — POST `/api/moderation/approve/${eventId}`
- `rejectEvent(eventId)` — POST `/api/moderation/reject/${eventId}`
- `getDemoMode()` — GET `/api/settings/demo-mode`
- `setDemoMode(enabled)` — POST `/api/settings/demo-mode`
- `getHistory(limit, offset)` — GET `/api/history`
- `getSources(sourceType)` — GET `/api/sources`
- `healthCheck()` — GET `/api/health`

Each function uses native `fetch`, throws on non-ok response with status details.

#### src/hooks/useApi.js

Custom hook that wraps an API function with `data`, `loading`, `error` state and an `execute(...args)` callback. This eliminates boilerplate in every tab component.

```javascript
function useApi(apiFn) {
  // returns { data, loading, error, execute, reset }
}
```

#### Theme and Styling (index.css)

**Professional dark theme.** Define CSS custom properties on `:root`:

```css
--color-bg: #0f1117;
--color-bg-secondary: #1a1d27;
--color-bg-card: #1e2130;
--color-text: #e4e6eb;
--color-text-muted: #8b8fa3;
--color-border: #2d3148;
--color-primary: #6366f1;
--color-primary-hover: #818cf8;
--color-severity-low: #3b82f6;
--color-severity-medium: #eab308;
--color-severity-high: #f97316;
--color-severity-critical: #ef4444;
--color-approved: #22c55e;
--color-rejected: #ef4444;
--color-pending: #eab308;
--color-citation-bg: #312e81;
--color-citation-text: #c7d2fe;
```

Layout: CSS Grid with 220px sidebar + flexible content area + 56px header + 40px footer. Font: Inter from Google Fonts (add `<link>` in index.html).

#### Shared Components

**CitationBadge** — props: `label`, `snippet`. Renders small rounded badge with hover tooltip showing snippet.

**SeverityBadge** — props: `level` (low/medium/high/critical). Color-coded pill badge. Background: low=#3b82f6, medium=#eab308, high=#f97316, critical=#ef4444. Dark text for medium, white for others.

**RuleMatchChip** — props: `rule`. Renders outlined chip with `"§ "` prefix. Returns null if `rule` is null/undefined.

**ResponsePanel** — props: `response` (TaskResponse object). Renders card with: output_text (preserve whitespace), severity badge (if present), suggested_action (if present), matched_rule chip, citations section with CitationBadge for each citation, confidence note in muted italic.

**PromptInput** — props: `placeholder`, `buttonLabel`, `onSubmit`, `loading`, `rows` (default 3). Renders textarea + submit button. Button disabled when loading or input empty. Shows "Processing..." when loading.

**StatusIndicator** — props: `demoMode`, `onToggle`. Green pulsing dot + "DEMO MODE" when on, gray dot + "LIVE MODE" when off. Toggle switch/button.

#### Tab Components

**KnowledgeBase** — fetches `GET /api/sources` on mount. Filter bar (All, Rules, FAQs, Announcements, Mod Notes). Renders cards grouped by type showing title, type badge, content preview (150 chars), source_id.

**AskFaq** — PromptInput (placeholder: "Ask a question about server rules, policies, or FAQs...") → `askFaq()` → ResponsePanel.

**SummarizeAnnouncement** — PromptInput (placeholder: "Paste the announcement text here...", rows=6) → `summarize()` → ResponsePanel.

**ModeratorDraft** — PromptInput (placeholder: "Describe the moderation situation or paste the user's message...") → `draftResponse()` → ResponsePanel. Include a copy-to-clipboard button on the output.

**ReviewQueue** — Fetches history, filters for `status === "pending"`. Each card shows: message_content, SeverityBadge, RuleMatchChip, suggested_action, explanation. Approve (green) and Reject (red) buttons per event. After action, re-fetch the list. Also includes an "Analyze Message" section at top: PromptInput → `analyzeMessage()` → ResponsePanel showing the analysis result. Refresh button.

**ModerationHistory** — Fetches `GET /api/history`. Filter bar by status (All, Approved, Rejected, Pending, Auto-Actioned). Table/card list with: timestamp, message snippet (80 chars), SeverityBadge, status badge (color-coded), RuleMatchChip, resolved_by. Expandable rows for full details. Refresh button.

#### App.jsx

State: `activeTab` (default "knowledge"), `demoMode` (default false). On mount: fetch `GET /api/settings/demo-mode` to get current state. Header shows app title + StatusIndicator. Sidebar shows 6 tabs. Content area renders the active tab component. Footer: "Esports Mod Copilot — POC".

#### Dockerfile

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

Dev-mode container for the POC — avoids build-time env var complications.

### Warnings

1. **Do NOT install react-router, redux, zustand, tailwind, axios, or any CSS framework.** Plain React state + plain CSS + native fetch only.
2. **Do NOT use TypeScript.** All files are `.jsx` and `.js`.
3. **Every `fetch` call must handle errors with try/catch and show user-visible error state.** Do not write happy-path-only code.
4. **`VITE_API_URL` is baked at build time and runs in the BROWSER.** It cannot use Docker service names. Default to `""` (empty) for Vite proxy, or `http://localhost:8000` for direct.
5. **Use `import.meta.env.VITE_API_URL`, NOT `process.env`.** Vite uses `import.meta.env`.
6. **Demo mode toggle is in the APP HEADER, not a separate settings tab.** State lives in App.jsx.
7. **Use `useState` and `useEffect` only.** No useReducer, no useContext, no custom hook libraries.
8. **Dark background theme is required.** Use the CSS variables specified above. Do not build a light theme.
9. **Do NOT add TypeScript type annotations, PropTypes, or any type checking.**

### Validation Checklist

After building, verify:
- [ ] `cd frontend && npm install && npm run dev` starts without errors
- [ ] Dashboard loads at `http://localhost:5173` with dark theme
- [ ] All 6 tabs are visible in sidebar and switch correctly
- [ ] Knowledge Base tab loads and displays data (when backend is running)
- [ ] Ask FAQ tab accepts input and displays response with citations
- [ ] Review Queue shows pending items with approve/reject buttons
- [ ] Demo mode toggle works and persists state to backend

---

## Prompt 4 — Discord Bot

### Copy everything below this line into the agent prompt:

---

You are building the **Discord Bot** for an esports Discord moderation copilot. This is a discord.py 2.x bot with slash commands and passive message monitoring that calls a FastAPI backend for all AI processing.

### Tech Stack

- Python 3.11+
- discord.py 2.x (app_commands, NOT legacy prefix commands)
- aiohttp (for backend HTTP calls)
- python-dotenv

### File Manifest

Create every file listed below. No other files are needed.

```
bot/
├── main.py
├── bot.py
├── config.py
├── api_client.py
├── embeds.py
├── cogs/
│   ├── __init__.py
│   ├── faq.py
│   ├── summarize.py
│   ├── moddraft.py
│   ├── settings.py
│   └── monitor.py
├── Dockerfile
├── requirements.txt
└── .env.example
```

### Build Order

Create files in this exact order:

**Phase 1 — Config and client:**
1. `config.py`
2. `api_client.py`
3. `embeds.py`

**Phase 2 — Cogs (simplest to most complex):**
4. `cogs/__init__.py`
5. `cogs/faq.py`
6. `cogs/summarize.py`
7. `cogs/moddraft.py`
8. `cogs/settings.py`
9. `cogs/monitor.py` (most complex — build last)

**Phase 3 — Wiring:**
10. `bot.py`
11. `main.py`

**Phase 4 — Deployment:**
12. `requirements.txt`
13. `.env.example`
14. `Dockerfile`

### Backend API Contract

The backend is at `BACKEND_URL` (default: `http://localhost:8000`, in Docker: `http://backend:8000`). Unlike the frontend, the bot runs server-side and CAN use Docker service names.

#### TaskResponse (from POST /api/faq/ask, /api/announcements/summarize, /api/moderation/draft)

```json
{
  "task_type": "faq",
  "output_text": "The answer text...",
  "citations": [
    {"source_id": "rule_003", "citation_label": "Rule 3: No Spam", "snippet": "Do not send repeated messages..."}
  ],
  "confidence_note": "High confidence",
  "matched_rule": "Rule 3: No Spam or Flooding",
  "severity": null,
  "suggested_action": null,
  "raw_source_ids": ["rule_003"]
}
```

#### ModerationEventResponse (from POST /api/moderation/analyze)

```json
{
  "event_id": "a1b2c3d4",
  "message_content": "the flagged message text",
  "violation_type": "harassment",
  "matched_rule": "Rule 1: No Harassment or Bullying",
  "explanation": "Explanation of the violation...",
  "severity": "high",
  "suggested_action": "remove_message",
  "status": "pending",
  "source": "discord",
  "created_at": "2026-04-09T12:00:00",
  "resolved_at": null,
  "resolved_by": null
}
```

#### Route Table

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| POST | `/api/faq/ask` | `{"question": str}` | TaskResponse |
| POST | `/api/announcements/summarize` | `{"text": str}` | TaskResponse |
| POST | `/api/moderation/draft` | `{"situation": str}` | TaskResponse |
| POST | `/api/moderation/analyze` | `{"message_content": str, "source": "discord"}` | ModerationEventResponse |
| GET | `/api/settings/demo-mode` | — | `{"demo_mode": bool}` |
| POST | `/api/settings/demo-mode` | `{"enabled": bool}` | `{"demo_mode": bool}` |

### Environment Variables

```
DISCORD_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=123456789012345678
SANDBOX_CHANNEL_ID=123456789012345678
BACKEND_URL=http://localhost:8000
```

### Per-File Specifications

#### config.py

Dataclass `Config` with `discord_token: str`, `guild_id: int`, `sandbox_channel_id: int`, `backend_url: str`. Class method `from_env()` loads from environment using `python-dotenv`.

#### api_client.py

Async class `BackendClient` that takes an `aiohttp.ClientSession`. Methods:
- `ask_faq(question: str) -> dict` — POST `/api/faq/ask`
- `summarize(text: str) -> dict` — POST `/api/announcements/summarize`
- `mod_draft(situation: str) -> dict` — POST `/api/moderation/draft`
- `analyze(message_content: str, author: str, channel: str, message_id: str) -> dict` — POST `/api/moderation/analyze` with `source: "discord"`
- `get_demo_mode() -> bool` — GET `/api/settings/demo-mode`
- `set_demo_mode(enabled: bool) -> dict` — POST `/api/settings/demo-mode`

Internal `_post(path, payload)` and `_get(path)` helpers. Use `self.session.post(path, json=payload)` with `raise_for_status()`.

#### embeds.py

Helper functions to convert API responses into Discord embeds:

**`build_task_embed(title: str, data: dict, color: discord.Color) -> discord.Embed`:**
- Embed title = title parameter
- Embed description = `data["output_text"]` truncated to 4000 chars
- Footer = `data["confidence_note"]`
- Add field "Matched Rule" if `data["matched_rule"]` exists
- Add field "Severity" if `data["severity"]` exists
- Add field "Suggested Action" if `data["suggested_action"]` exists
- Add "Sources" field: join first 5 citations as `"[label] snippet"`, truncate each to 200 chars, total field to 1024 chars

**`build_moderation_alert(data: dict, message: discord.Message) -> discord.Embed`:**
- Title: "Moderation Alert"
- Description: violation_type + explanation
- Fields: Author (message.author), Channel (message.channel.mention), Severity, Matched Rule, Action
- Color from severity mapping

**Severity color mapping:**
```python
SEVERITY_COLORS = {
    "low": discord.Color.green(),
    "medium": discord.Color.yellow(),
    "high": discord.Color.orange(),
    "critical": discord.Color.red(),
}
```

#### Cog Pattern (all cogs follow this)

```python
import discord
from discord import app_commands
from discord.ext import commands

class XxxCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="commandname", description="...")
    @app_commands.describe(param="...")
    async def commandname(self, interaction: discord.Interaction, param: str):
        await interaction.response.defer()  # REQUIRED — backend calls take >3 seconds
        client = BackendClient(self.bot.http_session)
        data = await client.some_method(param)
        embed = build_task_embed("Title", data, discord.Color.blurple())
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(XxxCog(bot))
```

#### Slash Commands

**`/askfaq question:str`** — calls `ask_faq(question)`, sends embed with title "FAQ Answer", color blurple.

**`/summarize text:str`** — calls `summarize(text)`, sends embed with title "Announcement Summary", color blue.

**`/moddraft situation:str`** — calls `mod_draft(situation)`, sends embed with title "Moderator Draft", color green.

**`/toggle-demomode`** (no parameters) — admin-only via `@app_commands.checks.has_permissions(manage_messages=True)`. Calls `get_demo_mode()`, then `set_demo_mode(!current)`. Sends ephemeral embed confirming new state. Include error handler for MissingPermissions.

#### cogs/monitor.py — Passive Monitoring

This is the most complex cog. It listens for `on_message` events.

**Filters (in order):**
1. `if message.channel.id != self.bot.config.sandbox_channel_id: return` — only sandbox channel
2. `if message.author.bot: return` — ignore all bots (including self!)
3. `if not message.content or not message.content.strip(): return` — ignore empty/image-only
4. Per-user cooldown: 5 seconds between analyses per user. Use a dict `{user_id: last_timestamp}` with `time.monotonic()`.

**Flow after filters pass:**
1. Call `client.analyze(message_content, author, channel, message_id)`
2. If `suggested_action == "no_action"`: return (ignore)
3. Check demo mode via `client.get_demo_mode()`
4. **If demo_mode ON and action in (remove_message, timeout_or_mute_recommendation, escalate_to_human):**
   - Delete the message: `await message.delete()`
   - Send alert embed to the channel with "Message auto-deleted (demo mode)"
5. **If demo_mode OFF:**
   - Backend already created a pending review event
   - For high/critical severity only: send a subtle alert embed with "Pending moderator review"
6. **All errors in on_message must be caught and logged, never raised.** The bot must never crash from a monitoring failure.

Handle `discord.Forbidden` (missing permissions) and `discord.NotFound` (already deleted) on `message.delete()`.

#### bot.py

Subclass `commands.Bot`:
- `__init__`: set up intents (`default()` + `message_content = True`), store config
- `setup_hook`: create `aiohttp.ClientSession(base_url=config.backend_url, timeout=aiohttp.ClientTimeout(total=30))`, load all 5 cogs, sync command tree to guild
- `close`: close aiohttp session, call `super().close()`

Guild-specific sync for instant slash command registration:
```python
guild = discord.Object(id=self.config.guild_id)
self.tree.copy_global_to(guild=guild)
await self.tree.sync(guild=guild)
```

#### main.py

```python
import logging
from config import Config
from bot import ModBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

def main():
    config = Config.from_env()
    bot = ModBot(config)
    bot.run(config.discord_token, log_handler=None)

if __name__ == "__main__":
    main()
```

### requirements.txt

```
discord.py>=2.3.0
aiohttp>=3.9.0
python-dotenv>=1.0.0
```

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

No ports exposed — the bot only makes outbound connections.

### Warnings

1. **Use discord.py 2.x `app_commands`, NOT legacy `@bot.command()` prefix commands.** All commands must be slash commands using `@app_commands.command()` in cogs.
2. **Every slash command must call `await interaction.response.defer()` first.** Backend LLM calls take >3 seconds. Without deferring, the interaction token expires and the user sees "This interaction failed."
3. **Create the `aiohttp.ClientSession` ONCE in `setup_hook`, NOT per-request.** Store on `self.bot.http_session`. Creating a session per request leaks connections.
4. **The `on_message` listener MUST ignore bot messages** (`if message.author.bot: return`). Without this, the bot analyzes its own embeds in an infinite loop.
5. **Use `discord.Intents.default()` plus `intents.message_content = True`.** Do NOT use `Intents.all()`. The `message_content` intent must also be enabled in the Discord Developer Portal under Bot > Privileged Gateway Intents.
6. **Embed field values have a 1024-char limit. Embed description has a 4096-char limit. Total embed is 6000 chars.** Truncate all LLM outputs before putting them in embeds.
7. **Slash command names must be lowercase with hyphens, no spaces.** Valid: `askfaq`, `toggle-demomode`. Invalid: `toggleDemoMode`, `toggle demo mode`.
8. **The bot's `BACKEND_URL` in Docker should be `http://backend:8000`** (Docker service name). The bot runs server-side, not in a browser, so it CAN resolve Docker DNS.
9. **Do NOT add a healthcheck in the bot Dockerfile.** The bot has no HTTP server. Health is implicit from the process running.
10. **All errors in the `on_message` passive monitoring must be caught and logged, never re-raised.** The bot must not crash from backend failures, permission errors, or rate limits.

### Validation Checklist

After building, verify:
- [ ] Bot starts and connects to Discord without errors
- [ ] Slash commands appear in the test server after guild sync
- [ ] `/askfaq "when is the next tournament"` returns an embed with answer + citations
- [ ] `/summarize "long announcement text here"` returns a summary embed
- [ ] `/moddraft "user is spamming in general"` returns a draft response embed
- [ ] `/toggle-demomode` toggles and confirms the new state (admin-only)
- [ ] Posting a toxic message in the sandbox channel triggers moderation analysis
- [ ] In demo mode, violating messages are auto-deleted with an alert embed
- [ ] In standard mode, violations are flagged but NOT deleted
- [ ] Bot ignores its own messages and messages outside the sandbox channel

---

## Root-Level Docker Compose

After all 4 components are built, create these files at the project root:

### docker-compose.yml

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: copilot-backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - model-cache:/root/.cache
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: copilot-frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  bot:
    build:
      context: ./bot
      dockerfile: Dockerfile
    container_name: copilot-bot
    env_file:
      - .env
    environment:
      - BACKEND_URL=http://backend:8000
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

volumes:
  model-cache:
```

### .env.example (root level)

```bash
# LLM Provider Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
PRIMARY_PROVIDER=openai
FALLBACK_PROVIDER=anthropic
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Database
SQLITE_PATH=/app/data/copilot.db
CHROMA_PERSIST_DIR=/app/data/chroma
CHROMA_COLLECTION=knowledge_base
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Discord Bot
DISCORD_TOKEN=your-bot-token
DISCORD_GUILD_ID=123456789012345678
SANDBOX_CHANNEL_ID=123456789012345678

# App Settings
DEMO_MODE_DEFAULT=true
TOP_K_RESULTS=5
LOG_LEVEL=INFO
FRONTEND_URL=http://localhost:5173
```

### Startup Sequence

```bash
# 1. Copy and fill in .env
cp .env.example .env

# 2. Run seed ingestion (one-time)
cd data && pip install -r requirements.txt && python ingest.py && cd ..

# 3. Start the stack
docker compose up --build
```
