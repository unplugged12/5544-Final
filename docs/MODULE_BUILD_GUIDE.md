# Module Build Guide - Esports Community Mod + FAQ Copilot

This guide explains what each module is responsible for, how the modules interact, what each one should expose, and what good output looks like. It is written so a teammate or coding agent can pick up a module and build it with minimal guesswork.

## Product Goal
Build a Discord-first moderation and FAQ copilot for a seeded Call of Duty community. The system should answer repetitive questions from approved server content, summarize announcements, draft moderator responses, and detect rule violations or toxic messages. The web dashboard acts as the moderator control plane and review surface.

## Global Design Rules
- Keep the product scoped to one fictional but realistic Call of Duty community.
- Prefer deterministic flows over clever but unstable ones.
- Every grounded answer should include citations.
- Every moderation result should include the likely rule match, explanation, severity, and suggested action.
- Demo mode may auto-delete content in the sandbox server.
- Standard mode must require moderator approval before deletion.
- The app should run locally through Docker Compose.

---

## Module 1 - Frontend Dashboard

### Purpose
Provide a one-page moderator dashboard with tabs or cards for knowledge sources, FAQ testing, announcement summarization, moderator drafting, moderation review, and history.

### Primary User
Moderator or project presenter.

### Key Responsibilities
- Show knowledge base records by source type: rules, FAQs, announcements, mod notes.
- Let the user test FAQ queries against approved sources.
- Let the user paste announcements for summarization.
- Let the user paste a situation or message for a moderator response draft.
- Show flagged moderation events in a review queue.
- Show moderation history and audit log entries.
- Show demo mode state.
- Show citations and matched rules clearly.

### Inputs
- API responses from backend routes.
- Seeded knowledge source metadata.
- Moderation history records.

### Outputs
- Visual interface for moderation review.
- Clean display of answer text, citations, severity, and suggested actions.
- Approval and rejection actions sent to backend.

### Suggested UI Sections
1. Knowledge Base
2. Ask FAQ
3. Summarize Announcement
4. Moderator Draft
5. Review Queue
6. Moderation History

### Suggested Components
- Source list or accordion
- Prompt input box
- Response panel
- Citation badges
- Rule match chip
- Severity badge
- Approve button
- Reject button
- Demo mode toggle
- Audit log table

### Acceptance Criteria
- A moderator can move through all core workflows from one page.
- Citations are visible and readable.
- Review queue items can be approved or rejected.
- History displays previous moderation actions.
- The UI is clear enough for a live demo without narration explaining every field.

---

## Module 2 - Backend API and Orchestration Layer

### Purpose
Act as the central application brain. The backend receives requests from the dashboard and Discord bot, performs retrieval and prompt orchestration, calls the model provider, normalizes outputs, stores results, and returns structured responses.

### Key Responsibilities
- Expose API routes for each workflow.
- Route inputs to the right service.
- Pull relevant source chunks from the retrieval layer.
- Assemble task-specific prompts.
- Call the configured LLM provider.
- Normalize provider responses to a common schema.
- Log interactions and moderation outcomes.

### Suggested Routes
- POST /api/faq/ask
- POST /api/announcements/summarize
- POST /api/moderation/draft
- POST /api/moderation/analyze
- POST /api/moderation/approve
- POST /api/moderation/reject
- POST /api/settings/demo-mode
- GET /api/history
- GET /api/sources

### Core Services
- provider_service
- retrieval_service
- faq_service
- summary_service
- mod_draft_service
- moderation_service
- audit_service

### Common Response Shape
A response should be predictable and typed. At minimum include:
- task_type
- output_text
- citations
- confidence or certainty note
- matched_rule if applicable
- severity if applicable
- suggested_action if applicable
- raw_source_ids for traceability

### Acceptance Criteria
- The same route contracts work for both the dashboard and Discord bot.
- Provider changes do not require rewriting route logic.
- Every moderation action and major interaction is logged.
- Structured errors are returned instead of silent failures.

---

## Module 3 - LLM Provider Adapter Layer

### Purpose
Make model choice swappable. The app should use OpenAI as primary, Anthropic as fallback, and optionally support a future Ollama adapter without changing the rest of the app.

### Key Responsibilities
- Expose a common interface for generation tasks.
- Accept normalized prompt inputs from the backend.
- Return normalized text outputs and metadata.
- Handle provider-specific errors and retries.

### Suggested Interface
Functions should cover:
- answer_grounded_question
- summarize_announcement
- draft_moderator_response
- analyze_moderation_case

### Behavior Rules
- Do not let provider-specific response formats leak into route handlers.
- Return a uniform structure for all providers.
- Log which provider was used for the request.
- Support a config-driven primary and fallback provider.

### Acceptance Criteria
- Backend services call one abstraction, not raw provider SDKs everywhere.
- A failed OpenAI call can cleanly fall back to Anthropic.
- A teammate can add Ollama later with minimal changes.

---

## Module 4 - Knowledge Base and Retrieval Layer

### Purpose
Store and retrieve approved source material used to ground answers and moderation decisions.

### Source Types
- Rules
- FAQs
- Announcements
- Moderator notes

### Key Responsibilities
- Load seeded Call of Duty server data from local files.
- Store structured metadata in SQLite.
- Chunk source text into retrieval-friendly pieces.
- Embed chunks and store them in Chroma.
- Return top relevant chunks with source metadata.
- Preserve enough metadata to produce citations in the UI and bot responses.

### Minimum Metadata Per Source Item
- source_id
- source_type
- title
- content
- tags
- created_at
- citation_label

### Retrieval Behavior
- FAQ questions should search rules, FAQs, and announcements.
- Moderator drafting can also search mod notes.
- Moderation analysis should search rules first, then mod notes.
- Retrieval results should be ranked and trimmed before prompt assembly.

### Acceptance Criteria
- FAQ answers use approved content instead of pure free-form generation.
- Citation labels map back to real source records.
- Seeded content can be re-ingested without manual cleanup.

---

## Module 5 - Discord Bot Integration

### Purpose
Deliver the most visible user experience in the demo. The bot should allow direct interaction inside Discord and pass requests to the backend.

### Key Responsibilities
- Register slash commands.
- Send command inputs to backend routes.
- Display output in a clean Discord-friendly format.
- Passively monitor a designated sandbox channel for new messages.
- Send suspected violations to the moderation analysis route.
- In demo mode, auto-delete confirmed violating messages.
- In standard mode, submit flagged items for moderator review.
- Write moderation events to the audit log.

### Required Commands
- /askfaq
- /summarize
- /moddraft
- /toggle-demomode

### Passive Monitoring Rules
- Only monitor a designated sandbox or test channel.
- Ignore bot messages.
- Rate-limit or debounce repeated events if needed.
- Store enough message metadata for deletion and audit logging.

### Suggested Discord Output Fields
- Answer or summary text
- Matched rule
- Severity
- Suggested action
- Citation list

### Acceptance Criteria
- A moderator can demo all major workflows in Discord.
- A violating message can be auto-deleted in demo mode.
- The deletion appears in the dashboard history.
- Standard mode creates a pending review instead of deleting.

---

## Module 6 - Moderation Analysis and Action Engine

### Purpose
Evaluate a message, decide whether it likely violates community rules, and recommend or execute an action based on mode and severity.

### Key Responsibilities
- Classify suspected violation type.
- Map the message to a likely rule.
- Assign severity.
- Recommend action.
- Support auto-delete in demo mode.
- Support approval flow in standard mode.

### Suggested Violation Types
- Spam
- Harassment
- Hate speech or slur use
- Toxic personal attack
- Self-promo or advertising
- Spoiler violation
- Excessive flooding or caps
- No clear violation

### Suggested Severity Scale
- low
- medium
- high
- critical

### Suggested Action Scale
- no_action
- warn
- remove_message
- timeout_or_mute_recommendation
- escalate_to_human

### Output Contract
Every moderation analysis should return:
- violation_type
- severity
- matched_rule
- explanation
- suggested_action
- confidence_note
- citations

### Acceptance Criteria
- Moderation output is explainable, not just a label.
- The system can distinguish no violation from obvious violation.
- The same contract works for both passive monitoring and manual review.

---

## Module 7 - Data Seed and Evaluation Pack

### Purpose
Create realistic content so the app feels like a real Call of Duty Discord server and gives the team reliable demo cases.

### Required Datasets
- Rules set
- FAQs set
- Announcement set
- Moderator notes set
- Clean user question set
- Problematic message set
- Edge-case evaluation set

### Content Guidance
Rules should cover common community topics such as harassment, spoilers, self-promo, spam, off-topic posting, repetitive flooding, and respect for teammates and staff. FAQs should cover event times, tournament stream locations, participation rules, role selection, clip sharing, and support questions. Announcements should include event scheduling changes, tournament news, patch note summaries, and community reminders.

### Acceptance Criteria
- Data feels internally consistent.
- The same rules cited by moderation are present in the seeded rules source.
- Demo questions have enough source material to answer accurately.

---

## Module 8 - Persistence, Audit, and History

### Purpose
Make the project feel like a real moderation tool instead of a stateless chatbot.

### Key Responsibilities
- Store interaction history.
- Store moderation events.
- Store review decisions.
- Store whether a delete was automatic or approved.
- Provide records back to the dashboard.

### Minimum Entities
- knowledge_items
- messages
- moderation_events
- interaction_history
- app_settings

### Acceptance Criteria
- The dashboard can show a usable moderation history.
- Demo mode state is persisted.
- A deleted message event is visible after action is taken.

---

## Suggested Build Order
1. Scaffold project structure and Docker Compose.
2. Build backend routes and provider adapter stubs.
3. Seed and ingest Call of Duty knowledge sources.
4. Implement retrieval-backed FAQ answering.
5. Implement summarization and moderator drafting.
6. Implement moderation analysis contract.
7. Build the dashboard.
8. Wire the Discord bot.
9. Add passive monitoring and demo-mode delete action.
10. Add audit history and polish.

## Agent Build Prompts

For coding agents (Claude, Codex, etc.), see [`AGENT_BUILD_PROMPTS.md`](AGENT_BUILD_PROMPTS.md) which contains 4 detailed, self-contained prompts — one per component — designed for one-shot builds. Execution order:

```
1. Data Seed Pack  →  2. Backend API  →  3a. Frontend Dashboard (parallel)
                                         3b. Discord Bot (parallel)
```

## Suggested Folder Shape
- frontend
- backend
- bot
- data
- docs

Within backend:
- routes
- services
- providers
- prompts
- repositories
- models

## Demo-Ready Definition
The project is demo-ready when the team can show:
1. A user asks a Call of Duty server question and gets a grounded answer with citations.
2. A moderator pastes an announcement and gets a concise summary.
3. A moderator pastes a situation and gets a drafted response.
4. A toxic or rule-breaking message in the sandbox channel is analyzed and deleted in demo mode.
5. The dashboard shows the matched rule, reasoning, and history entry.
