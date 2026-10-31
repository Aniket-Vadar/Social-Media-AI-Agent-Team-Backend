# Product Requirements Document (PRD)

**Product:** AI Social Media Agent Office (working name)
**Version:** 1.0 (MVP)
**Status:** Draft

---

## 1. Overview

An AI-powered social media management SaaS where a team of autonomous AI agents researches trends, creates content, schedules posts, and analyzes performance across multiple social platforms. Users interact with a **Master Agent** (a "project manager") in natural language. The Master Agent delegates work to specialized agents: **Researcher, Creator, Scheduler, Analytics**.

The UI presents this as a virtual **"Agent Office"** where users can see agents working, chat with them, and review their output.

## 2. Problem Statement

Small teams, creators, and agencies spend hours each week on ideation, design, copywriting, scheduling, and reporting across platforms. Existing schedulers automate *publishing* but not *thinking*. Users need a system that can take a goal ("Create and schedule two Instagram posts about X") and execute it end to end, with human control where it matters.

## 3. Goals and Non-Goals

### Goals
- G1: Turn a one-line natural language goal into scheduled posts with minimal user effort.
- G2: Provide transparent agent activity (who is doing what, and why).
- G3: Support multi-campaign, multi-platform management in one workspace.
- G4: Give users approval control before anything is published.
- G5: Surface actionable analytics, not just raw numbers.

### Non-Goals (MVP)
- Paid ad management and ad spend optimization.
- Native mobile apps (responsive web only).
- Community management (DM and comment replies).
- Video generation (images and text only in MVP).
- White-label or agency reseller features.

## 4. Target Users

| Persona | Description | Key Need |
|---|---|---|
| Solo Creator | Individual with 1-3 accounts | Save time, stay consistent |
| Startup Marketer | Small team, many channels | Research-backed content at speed |
| Agency Manager | Multiple client campaigns | Campaign separation, reporting |

## 5. Agent Roster

| Agent | Responsibility | Key Tools |
|---|---|---|
| **Master Agent** | Parses request, plans, delegates, aggregates, reports to user | Planner, router, all sub-agents |
| **Researcher** | Finds trending topics, competitor and niche insights | E2B desktop sandbox (browser), web search |
| **Creator** | Writes captions and hashtags, generates and edits images | Gemini (text and image), ImageKit |
| **Scheduler** | Picks optimal times, schedules and publishes posts | Blotato API |
| **Analytics** | Pulls performance data, produces insights and recommendations | Blotato analytics API |

## 6. Functional Requirements

### FR-1: Authentication and Workspace
- Users sign up and log in (email and OAuth).
- Each user has a workspace containing one or more **Campaigns**.
- *Acceptance:* A new user can create a workspace and first campaign in under 2 minutes.

### FR-2: Campaign Management
- Create, edit, archive campaigns (name, goal, brand voice, target audience, platforms).
- Campaign switcher in the global sidebar.
- *Acceptance:* All data (posts, agents' tasks, analytics) is scoped to the selected campaign.

### FR-3: Social Account Connection
- Connect accounts for supported platforms via Blotato (Instagram, Facebook, X, LinkedIn, TikTok, and others supported by Blotato).
- *Acceptance:* Connection status is visible; disconnection revokes access.

### FR-4: Agent Chat (Master Agent)
- Natural language chat with streaming responses.
- Master Agent shows a **plan** (steps) before executing multi-step tasks.
- Users can chat directly with an individual agent.
- *Acceptance:* "Create and schedule two Instagram posts about X" yields a visible plan, task progress, and two drafted or scheduled posts.

### FR-5: Agent Office (Overview)
- Visual office showing each agent, current status (idle, working, waiting for approval, error), and current task.
- Click an agent to open a side drawer with chat, history, and settings.
- *Acceptance:* Status updates in real time (< 3 s latency).

### FR-6: Research
- Researcher produces a trend brief: topics, sources, relevance score, suggested angles.
- Research runs as a background job; results are stored and reusable.

### FR-7: Content Creation
- Creator generates caption, hashtags, and image per post, matching the campaign's brand voice.
- Image editing dialog with ImageKit transformations (crop, resize, overlay text, background, filters).
- *Acceptance:* Each generated post has platform-appropriate format (length, aspect ratio, hashtags).

### FR-8: Post Management
- Post list with statuses: `draft`, `pending_approval`, `scheduled`, `publishing`, `published`, `failed`.
- Manual creation form (title, caption, hashtags, media, platforms, time) and AI-assisted creation.
- Edit, reschedule, delete, duplicate.

### FR-9: Approval Workflow (Human-in-the-Loop)
- Per campaign setting: **Auto-publish** or **Require approval** (default: require approval).
- Agent pauses at approval step; user approves, edits, or rejects with feedback; agent resumes.

### FR-10: Calendar
- Month, week, and list views of scheduled and published posts, with drag-and-drop rescheduling.

### FR-11: Analytics Dashboard
- Metrics: impressions/views, reach, engagement rate, likes, comments, shares, follower growth.
- Filters: campaign, platform, date range.
- AI-written insights (e.g., "Carousel posts outperform single images by 32%").
- Top and bottom performing posts.

### FR-12: Background Jobs and Notifications
- Long-running work (research, generation, publishing, analytics sync) runs in the background via Inngest.
- In-app notifications for approvals needed, failures, and completions. Optional email.

### FR-13: Observability for Agents
- Each agent run is traceable (LangSmith). Users see a simplified activity log; admins see full traces.

## 7. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | Chat first token < 2 s; page loads < 2 s (p75) |
| Reliability | Scheduled posts published within ±1 min of schedule; 99.5% job success with retries |
| Scalability | Stateless services; horizontal scaling of agent service |
| Security | See `SECURITY.md` |
| Cost control | Per-workspace LLM and sandbox usage caps, with alerts |
| Accessibility | WCAG 2.1 AA |
| Browser support | Latest 2 versions of Chrome, Safari, Firefox, Edge |

## 8. Tech Stack Summary

| Layer | Choice |
|---|---|
| Frontend / BFF | Next.js (App Router), TypeScript, Tailwind, shadcn/ui |
| Agent service | **Python, FastAPI, LangGraph, LangChain** |
| LLM | **Google Gemini** (Pro for planning and reasoning, Flash for fast workers) |
| LLM observability and evals | **LangSmith** |
| Database | PostgreSQL + Drizzle ORM |
| Backend platform | InsForge (referred to as "Inforge" in the tutorial; verify) |
| Background jobs | Inngest (referred to as "Ingest" in the tutorial; verify) |
| Browser sandbox | E2B Desktop |
| Image transformation | ImageKit |
| Social publishing and analytics | Blotato |
| Code review | CodeRabbit |
| Dev workflow | Claude Code (for building the product) |

> Note: Claude Code is used as a **development tool** to build the product. The **runtime agents** use Python + LangGraph + Gemini.

## 9. Success Metrics

- Activation: % of new users who schedule/approve their first AI-generated post within 24 h (target > 50%).
- Time to first post < 10 minutes.
- Approval acceptance rate of AI drafts without edits (target > 60%).
- Weekly active campaigns per user.
- Publish success rate > 99%.
- Agent task completion rate > 90%; avg cost per task tracked in LangSmith.

## 10. Milestones

| Phase | Scope |
|---|---|
| M0 | Project setup, auth, DB schema, CI + CodeRabbit |
| M1 | Campaigns, sidebar, overview shell, manual post CRUD, calendar |
| M2 | LangGraph agent service, Master Agent chat, Creator agent, ImageKit editor |
| M3 | Blotato connection, Scheduler agent, Inngest jobs, approval workflow |
| M4 | Researcher agent with E2B sandbox |
| M5 | Analytics agent and dashboard |
| M6 | Hardening: security review, evals, load test, beta launch |

## 11. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucination or off-brand content | Brand voice config, approval workflow, LangSmith evals |
| Prompt injection from browsed web content | Sandbox isolation, content sanitization, tool allowlists (see `SECURITY.md`) |
| Platform API changes or rate limits | Blotato abstraction layer, retries and backoff |
| Runaway LLM and sandbox cost | Quotas, step limits, timeouts |
| Accidental publishing | Approval default on, confirmation step, audit log |

## 12. Open Questions

1. Pricing model (per seat, per campaign, or usage-based credits)?
2. Which platforms are in the MVP vs. later?
3. Is image generation done by Gemini image models, or only ImageKit transformations of user-supplied assets?
4. Will multi-user team roles (admin, editor, viewer) be in the MVP?
5. Confirm exact vendor names (InsForge, Inngest) and Python SDK availability for each.
