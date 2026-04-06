# Kanban Board - Esports Community Mod + FAQ Copilot

Use this page as the working project board until a native GitHub Project is created manually.

## Columns
- Backlog
- Next Up
- In Progress
- Blocked
- Review / Test
- Done

## Backlog

### Planning
- [ ] Finalize environment variables for OpenAI, Anthropic, Discord bot, and app config
- [ ] Define the seeded Call of Duty server name, channels, and moderator personas
- [ ] Define the response schema for citations, severity, and recommended actions
- [ ] Finalize moderation categories and severity scale

### Data
- [ ] Create 15-20 server rules
- [ ] Create 25-35 FAQs
- [ ] Create 10-15 announcements
- [ ] Create 8-12 moderator notes
- [ ] Create 20 clean user question examples
- [ ] Create 20 rule-breaking or toxic message examples
- [ ] Create 10 ambiguous edge cases

### Backend
- [ ] Add models for knowledge items, messages, moderation events, and history
- [ ] Add route for FAQ answering
- [ ] Add route for announcement summarization
- [ ] Add route for moderator drafting
- [ ] Add route for moderation analysis
- [ ] Add route to approve or reject suggested actions
- [ ] Add route to toggle demo mode

### Retrieval
- [ ] Create ingestion script for rules, FAQs, announcements, and mod notes
- [ ] Store source records in SQLite
- [ ] Chunk and embed source content in Chroma
- [ ] Return relevant source chunks with metadata
- [ ] Standardize citation format for dashboard and bot responses

### Discord Bot
- [ ] Register slash commands
- [ ] Implement /askfaq
- [ ] Implement /summarize
- [ ] Implement /moddraft
- [ ] Implement passive message monitoring in a sandbox channel
- [ ] Implement admin-only demo mode toggle
- [ ] Implement delete action for demo-mode auto-remove
- [ ] Implement audit logging back to the backend

### Frontend
- [ ] Build one-page dashboard shell with tabs or cards
- [ ] Build knowledge base tab
- [ ] Build FAQ tab
- [ ] Build announcement summary tab
- [ ] Build mod assistant tab
- [ ] Build moderation queue tab
- [ ] Build moderation history tab
- [ ] Add demo mode indicator and toggle
- [ ] Display citations and matched rules

### QA and Demo
- [ ] Build a live demo script
- [ ] Record a backup demo video
- [ ] Capture screenshots for the report
- [ ] Test fallback from OpenAI to Anthropic
- [ ] Dry-run the full demo on the presentation machine

## Next Up

### Sprint 1 - Foundation
- [ ] Scaffold frontend, backend, bot, data, and docs folders
- [ ] Add Docker Compose
- [ ] Create .env.example
- [ ] Scaffold FastAPI app
- [ ] Scaffold React dashboard
- [ ] Scaffold discord.py bot
- [ ] Add provider abstraction layer

### Sprint 2 - Core POC
- [ ] Implement seeded data ingestion
- [ ] Implement retrieval-backed FAQ answering
- [ ] Implement announcement summarization
- [ ] Implement moderation analysis route
- [ ] Wire dashboard to backend APIs
- [ ] Wire bot commands to backend APIs

## In Progress
- [ ] None yet

## Blocked
- [ ] None yet

## Review / Test
- [ ] None yet

## Done
- [x] Finalized project concept and scope
- [x] Selected Call of Duty theme for seeded server
- [x] Chose Discord-first architecture with one-page dashboard
- [x] Decided on passive moderation in a sandbox channel
- [x] Defined dual moderation behavior for demo mode and approval mode
- [x] Locked core stack: React, FastAPI, discord.py, SQLite, Chroma, Docker Compose

## Suggested Ownership
- Teammate A: backend, orchestration, prompts, moderation logic
- Teammate B: frontend dashboard and citations display
- Teammate C: Discord bot, passive monitoring, delete action, audit flow
- Teammate D: seeded data, QA cases, screenshots, demo script

## Definition of Done
A task is done when the code exists in the repo, runs locally, is tested with seeded data, matches scope, and is understandable to another teammate.