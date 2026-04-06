# GitHub Issue Pack - Esports Community Mod + FAQ Copilot

Use the issues below to create repository issues in roughly this order. They are sequenced to reduce rework and keep the team aligned around a single architecture.

---

## Issue 1 - Scaffold the repository structure for the POC
**Suggested labels:** setup, architecture, repo
**Priority:** High
**Depends on:** None

### Goal
Create the initial project structure so all contributors and coding agents work from the same layout.

### Scope
Create the base folders and placeholder files for:
- `frontend/`
- `backend/`
- `bot/`
- `data/`
- `docs/`

Within `backend/`, include placeholders for:
- `routes/`
- `services/`
- `providers/`
- `prompts/`
- `repositories/`
- `models/`

### Deliverables
- Initial folder layout committed to the repo
- Minimal `README` updates if needed
- Placeholder files or keep files that make the structure obvious

### Acceptance Criteria
- The repo clearly separates frontend, backend, bot, data, and docs
- A new contributor can understand where code belongs without asking
- The structure supports Docker Compose and local development

---

## Issue 2 - Add local development workflow with Docker Compose and environment config
**Suggested labels:** setup, infra, docker
**Priority:** High
**Depends on:** Issue 1

### Goal
Make the app easy to run locally on teammate machines with a single, documented workflow.

### Scope
- Add `docker-compose.yml`
- Add `.env.example`
- Define environment variables for OpenAI, Anthropic, Discord bot token, DB settings, demo mode defaults, and app URLs
- Add startup instructions to the repo

### Deliverables
- Working Docker Compose file
- Example env file with comments
- Run instructions in `README.md`

### Acceptance Criteria
- A teammate can clone the repo, copy `.env.example`, and start the stack locally
- Frontend, backend, and any supporting services have a clear startup path
- Environment variable names are consistent across code and docs

---

## Issue 3 - Scaffold the FastAPI backend application
**Suggested labels:** backend, api, setup
**Priority:** High
**Depends on:** Issue 1, Issue 2

### Goal
Create the backend foundation that will later host all application workflows.

### Scope
- Initialize FastAPI app
- Add health endpoint
- Add route modules for FAQ, announcements, moderation, settings, and history
- Add basic config loading
- Add structured error response shape

### Deliverables
- Running FastAPI app
- Route registration pattern
- Health check endpoint
- Base response and error conventions

### Acceptance Criteria
- Backend starts cleanly in Docker and local dev
- Route organization is clear and extensible
- Health endpoint can be used to verify the service is running

---

## Issue 4 - Scaffold the React dashboard shell as a one-page moderator console
**Suggested labels:** frontend, ui, setup
**Priority:** High
**Depends on:** Issue 1, Issue 2

### Goal
Create the one-page frontend shell with tabs or cards for the main workflows.

### Scope
Add the top-level UI structure for:
- Knowledge Base
- Ask FAQ
- Summarize Announcement
- Moderator Draft
- Review Queue
- Moderation History
- Demo mode indicator

### Deliverables
- Running React + Vite app
- One-page layout with navigation tabs or cards
- Placeholder panels for each workflow

### Acceptance Criteria
- The dashboard loads and is presentation-friendly
- The six main workflow areas are visible
- The app structure supports iterative feature wiring without redesign

---

## Issue 5 - Scaffold the Discord bot service and register core slash commands
**Suggested labels:** bot, discord, setup
**Priority:** High
**Depends on:** Issue 1, Issue 2

### Goal
Establish the Discord bot foundation early so command design is not an afterthought.

### Scope
- Initialize `discord.py` bot service
- Register slash commands:
  - `/askfaq`
  - `/summarize`
  - `/moddraft`
  - `/toggle-demomode`
- Add config for guild/server targeting in development

### Deliverables
- Bot project skeleton
- Successful bot login and command registration
- Placeholder command handlers

### Acceptance Criteria
- Bot connects successfully in the sandbox server
- Slash commands appear in the test server
- Command handlers can later be wired to the backend without major rework

---

## Issue 6 - Design and implement the SQLite schema for sources, messages, moderation events, history, and settings
**Suggested labels:** backend, database, persistence
**Priority:** High
**Depends on:** Issue 3

### Goal
Create the persistence layer that supports retrieval traceability, moderation history, and demo mode state.

### Scope
Model the following entities:
- Knowledge items
- Messages
- Moderation events
- Interaction history
- App settings

### Deliverables
- Schema definitions and migrations or initialization logic
- Repository or data access layer pattern
- Seed-safe initialization behavior

### Acceptance Criteria
- Structured records can be created and retrieved for each entity
- Demo mode state can be persisted
- Moderation events can be linked back to messages and outputs

---

## Issue 7 - Implement the provider abstraction layer for OpenAI primary and Anthropic fallback
**Suggested labels:** backend, llm, architecture
**Priority:** High
**Depends on:** Issue 3

### Goal
Keep model-provider choice isolated so the rest of the app calls one clean interface.

### Scope
Create a provider abstraction with methods for:
- grounded FAQ answering
- announcement summarization
- moderator response drafting
- moderation analysis

Add:
- OpenAI provider implementation
- Anthropic provider implementation
- fallback strategy when primary fails

### Deliverables
- Provider interface and normalized response contract
- Config-driven primary/fallback selection
- Logging of provider used per request

### Acceptance Criteria
- Backend services do not call raw provider SDKs directly
- A failed primary call can fall back cleanly when configured
- Output shape is normalized across providers

---

## Issue 8 - Create the seeded Call of Duty community dataset
**Suggested labels:** data, content, seed
**Priority:** High
**Depends on:** Issue 1

### Goal
Build the realistic source content that will make the POC feel like a real esports moderation environment.

### Scope
Create local seed files for:
- 15-20 server rules
- 25-35 FAQs
- 10-15 announcements
- 8-12 moderator notes
- 20 clean example user questions
- 20 toxic or rule-breaking messages
- 10 ambiguous moderation edge cases

### Deliverables
- Seed files stored in `data/`
- Consistent naming and metadata conventions
- Content aligned to a fictional but realistic Call of Duty community

### Acceptance Criteria
- The dataset is internally consistent
- Rules referenced by moderation exist in the seed content
- FAQ and announcement content are rich enough to support meaningful retrieval

---

## Issue 9 - Build knowledge ingestion and Chroma retrieval for approved source content
**Suggested labels:** backend, retrieval, data
**Priority:** High
**Depends on:** Issue 6, Issue 8

### Goal
Enable retrieval-augmented grounding from approved server sources.

### Scope
- Load seed files into SQLite
- Chunk source content
- Embed chunks into Chroma
- Preserve metadata for citations
- Support retrieval by source type and task type

### Deliverables
- Ingestion script or startup job
- Retrieval service that returns top relevant chunks with metadata
- Citation-ready source labels

### Acceptance Criteria
- Seed data can be ingested without manual cleanup
- Queries can retrieve relevant chunks from rules, FAQs, announcements, and mod notes
- Retrieval responses include enough metadata to produce citations

---

## Issue 10 - Implement the retrieval-backed FAQ workflow
**Suggested labels:** backend, llm, faq
**Priority:** High
**Depends on:** Issue 7, Issue 9

### Goal
Allow users to ask community questions and receive grounded answers using only approved sources.

### Scope
- Create FAQ service
- Retrieve relevant chunks from rules, FAQs, and announcements
- Apply a grounded-answer prompt
- Return answer text with citations and a confidence note
- Add route: `POST /api/faq/ask`

### Deliverables
- FAQ route and service
- Prompt template for grounded answering
- Structured response with citations

### Acceptance Criteria
- The system answers common server questions using only approved content
- If the answer is not supported by sources, the system says so clearly
- Citations are included in the response payload

---

## Issue 11 - Implement the announcement summarization workflow
**Suggested labels:** backend, llm, summarization
**Priority:** Medium
**Depends on:** Issue 7

### Goal
Let moderators summarize long announcements into concise member-friendly output.

### Scope
- Create summary service
- Prompt for concise fan-facing summarization
- Preserve times, dates, deadlines, and policy changes
- Add route: `POST /api/announcements/summarize`

### Deliverables
- Summary route and service
- Prompt template for announcement summarization
- Structured response contract

### Acceptance Criteria
- Summaries are shorter and clearer than input text
- Critical event details are preserved accurately
- The output is readable enough to present directly in a demo

---

## Issue 12 - Implement the moderator response drafting workflow
**Suggested labels:** backend, llm, moderation
**Priority:** Medium
**Depends on:** Issue 7, Issue 9

### Goal
Help moderators draft calm, consistent responses tied to rules or mod policy when applicable.

### Scope
- Create moderator drafting service
- Allow optional retrieval from rules and mod notes
- Generate a response draft, referenced rule, and suggested action level
- Add route: `POST /api/moderation/draft`

### Deliverables
- Moderator drafting route and service
- Prompt template for moderator-safe messaging
- Response contract with cited rule when relevant

### Acceptance Criteria
- The draft tone is controlled and professional
- The output references relevant rules when applicable
- The response is usable with minimal editing

---

## Issue 13 - Build the moderation analysis engine with rule matching, severity, and action recommendation
**Suggested labels:** backend, llm, moderation, core
**Priority:** High
**Depends on:** Issue 7, Issue 9

### Goal
Analyze potentially problematic messages and return explainable moderation decisions.

### Scope
For a given message, return:
- likely violation type
- matched rule
- explanation
- severity
- suggested action
- citations

Support categories such as:
- spam
- harassment
- slur or hate speech
- toxic personal attack
- self-promo
- spoiler violation
- flooding or caps abuse
- no clear violation

Add route: `POST /api/moderation/analyze`

### Deliverables
- Moderation analysis service
- Prompt template for classification and explanation
- Structured moderation result contract

### Acceptance Criteria
- The moderation result is explainable, not just a label
- The engine can distinguish no-violation cases from obvious violations
- The output can drive either review-mode or demo-mode behavior

---

## Issue 14 - Add moderation approval, rejection, and demo mode behavior in the backend
**Suggested labels:** backend, moderation, workflow
**Priority:** High
**Depends on:** Issue 6, Issue 13

### Goal
Support the two operating modes of the product: autonomous demo mode and safer approval mode.

### Scope
- Persist demo mode state
- Add route to toggle demo mode
- Add route to approve suggested actions
- Add route to reject suggested actions
- Log who approved or rejected when applicable
- Mark whether an action was automatic or human-approved

### Deliverables
- Settings route for demo mode
- Approval and rejection routes
- Audit behavior for moderation decisions

### Acceptance Criteria
- Demo mode can be turned on and off reliably
- Standard mode stores review decisions cleanly
- Automatic and manual actions are distinguishable in history

---

## Issue 15 - Wire the dashboard to the backend and complete the Knowledge Base, FAQ, Summary, and Mod Draft tabs
**Suggested labels:** frontend, integration, ui
**Priority:** High
**Depends on:** Issue 4, Issue 10, Issue 11, Issue 12, Issue 14

### Goal
Turn the dashboard shell into a functioning moderator console for the first three workflows.

### Scope
- Connect API calls for FAQ, summary, and mod draft
- Display answer text, citations, matched rules, and severity where applicable
- Show knowledge items grouped by source type
- Show current demo mode state

### Deliverables
- Working UI for the first four tabs
- Error and loading states
- Citation display component

### Acceptance Criteria
- A moderator can test FAQ, summary, and mod draft from the dashboard
- Source categories are visible and separate
- Citations render clearly and consistently

---

## Issue 16 - Build the review queue and moderation history UI
**Suggested labels:** frontend, moderation, history
**Priority:** High
**Depends on:** Issue 4, Issue 6, Issue 13, Issue 14

### Goal
Provide a real moderator control surface for flagged content, approvals, and audit history.

### Scope
- Display pending moderation items in a review queue
- Allow approve/reject actions when demo mode is off
- Display moderation history with timestamps, matched rule, severity, and action taken
- Clearly indicate whether the action was automatic or approved by a moderator

### Deliverables
- Review queue UI
- Moderation history UI
- Approval/rejection controls

### Acceptance Criteria
- Pending moderation events are easy to review
- Approval and rejection actions succeed and update history
- History is understandable during a presentation without deep explanation

---

## Issue 17 - Wire Discord slash commands to backend workflows
**Suggested labels:** bot, integration, discord
**Priority:** High
**Depends on:** Issue 5, Issue 10, Issue 11, Issue 12, Issue 14

### Goal
Make the Discord bot usable for the visible, interactive part of the demo.

### Scope
Connect bot commands to backend routes:
- `/askfaq` -> FAQ workflow
- `/summarize` -> announcement summarization
- `/moddraft` -> moderator drafting
- `/toggle-demomode` -> settings workflow

### Deliverables
- Working slash command integrations
- Discord-friendly formatting for answers, summaries, citations, and mod drafts

### Acceptance Criteria
- Commands return usable output in Discord
- Errors are handled cleanly in Discord responses
- Demo mode can be toggled from an admin-only command

---

## Issue 18 - Implement passive monitoring of a sandbox channel and execute auto-delete in demo mode
**Suggested labels:** bot, moderation, automation, core
**Priority:** High
**Depends on:** Issue 5, Issue 13, Issue 14, Issue 17

### Goal
Deliver the signature “AI moderator” moment of the demo while keeping the scope safe and controlled.

### Scope
- Listen for new messages in a designated sandbox or test channel
- Ignore bot messages
- Send each candidate message to the moderation analysis route
- If demo mode is on and the action is remove_message, delete the message automatically
- If demo mode is off, create a pending review item instead
- Log all actions back to the backend

### Deliverables
- Passive monitoring handler
- Auto-delete flow in demo mode
- Pending review flow in standard mode

### Acceptance Criteria
- A seeded toxic or rule-breaking message can be auto-deleted in demo mode
- The same message produces a pending review in standard mode
- The delete or review action appears in moderation history

---

## Issue 19 - Add end-to-end audit logging and cross-surface history consistency
**Suggested labels:** backend, bot, frontend, audit
**Priority:** Medium
**Depends on:** Issue 16, Issue 18

### Goal
Ensure that bot actions, dashboard actions, and backend decisions tell one coherent story.

### Scope
- Verify all major actions create history records
- Ensure the dashboard history reflects bot-triggered moderation events
- Ensure approval/rejection decisions update history correctly
- Normalize timestamps and action labels

### Deliverables
- End-to-end audit validation
- Any required schema or UI updates for consistency

### Acceptance Criteria
- A moderator can trace what happened to a flagged message from analysis to final action
- Bot-driven actions and dashboard-driven actions look consistent in the history log
- The audit trail is reliable enough for screenshots and presentation

---

## Issue 20 - Build a demo script, screenshots, and test checklist for presentation readiness
**Suggested labels:** qa, demo, report
**Priority:** High
**Depends on:** Issue 15, Issue 16, Issue 17, Issue 18, Issue 19

### Goal
Reduce demo risk and prepare the materials needed for the report and presentation.

### Scope
- Create a step-by-step live demo script
- Record a backup demo video
- Capture screenshots for FAQ, summary, mod draft, moderation delete, and history views
- Build a presentation-day smoke test checklist
- Test primary provider and fallback behavior

### Deliverables
- Demo script document
- Backup video plan or recording
- Screenshot pack
- Smoke test checklist

### Acceptance Criteria
- The team can rehearse the demo from start to finish
- There is a backup path if live Discord or API behavior is flaky
- Report screenshots can be produced without scrambling at the last minute

---

## Optional Stretch Issues

### Stretch A - Add an Ollama provider adapter for future local-model support
**Suggested labels:** stretch, llm, local
**Priority:** Low
**Depends on:** Issue 7

### Stretch B - Add a message context menu action in Discord for manual moderation analysis
**Suggested labels:** stretch, bot, discord
**Priority:** Low
**Depends on:** Issue 17

### Stretch C - Add simple evaluation scoring for seeded moderation cases
**Suggested labels:** stretch, qa, evaluation
**Priority:** Low
**Depends on:** Issue 13, Issue 20

---

## Recommended creation order
1. Issues 1-7
2. Issues 8-9
3. Issues 10-14
4. Issues 15-18
5. Issues 19-20
6. Stretch issues only if the core demo is stable
