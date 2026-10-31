# Backend Specification

## 1. Architecture Overview

```
┌───────────────────────────────┐
│   Browser (Next.js client)    │
└──────────────┬────────────────┘
               │ HTTPS (REST + SSE)
┌──────────────▼────────────────┐        ┌──────────────────────┐
│  Next.js (App Router / BFF)   │◄──────►│  PostgreSQL          │
│  - Auth, API routes           │ Drizzle│  (InsForge / managed)│
│  - Inngest functions          │        └──────────────────────┘
└───────┬───────────────┬───────┘
        │ internal HTTPS │ events
        │ (signed JWT)   ▼
        │        ┌───────────────┐
        │        │   Inngest     │  background jobs, cron, retries
        │        └───────┬───────┘
        ▼                ▼
┌───────────────────────────────┐   ┌────────────────────┐
│  Python Agent Service         │──►│ LangSmith (traces) │
│  FastAPI + LangGraph          │   └────────────────────┘
│  Gemini via langchain-google  │
│  Postgres checkpointer        │
└───┬────────┬────────┬─────────┘
    │        │        │
    ▼        ▼        ▼
  E2B     ImageKit   Blotato
 (browse) (images)   (publish + analytics)
```

**Principles**
- Next.js owns users, UI, CRUD, and orchestration of background jobs.
- The Python service owns all LLM and agent logic. It never talks to the browser directly except through Next.js (streaming proxied).
- All long-running work goes through Inngest. HTTP requests never block on agent runs longer than a few seconds.
- Postgres is the single source of truth. LangGraph checkpoints are stored in the same cluster (separate schema).

## 2. Repository Layout (monorepo)

```
/
├── apps/
│   ├── web/                      # Next.js
│   │   ├── app/                  # routes, API handlers
│   │   ├── lib/db/               # Drizzle schema + client
│   │   ├── lib/integrations/     # blotato.ts, imagekit.ts, agent-client.ts
│   │   ├── inngest/              # job functions
│   │   └── drizzle/              # migrations
│   └── agents/                   # Python service
│       ├── app/
│       │   ├── main.py           # FastAPI entry
│       │   ├── api/              # routers: runs, health
│       │   ├── graph/            # LangGraph definition
│       │   │   ├── state.py
│       │   │   ├── supervisor.py
│       │   │   ├── nodes/        # researcher.py creator.py scheduler.py analytics.py
│       │   │   └── builder.py
│       │   ├── tools/            # blotato.py imagekit.py e2b_browser.py db.py
│       │   ├── prompts/
│       │   ├── core/             # config, auth, logging, llm factory
│       │   └── evals/            # LangSmith datasets and evaluators
│       ├── tests/
│       └── pyproject.toml
├── .github/workflows/            # CI + CodeRabbit config
└── docs/                         # PRD.md BACKEND.md UI.md LOGIC.md SECURITY.md
```

## 3. Database Schema (PostgreSQL + Drizzle)

All tenant-owned tables carry `workspace_id` for isolation.

### Core tables

| Table | Key columns |
|---|---|
| `users` | id, email, name, avatar_url, created_at |
| `workspaces` | id, name, owner_id, plan, created_at |
| `workspace_members` | workspace_id, user_id, role (`owner`/`admin`/`editor`/`viewer`) |
| `campaigns` | id, workspace_id, name, goal, brand_voice (jsonb), audience, timezone, approval_mode (`manual`/`auto`), status, created_at |
| `social_accounts` | id, workspace_id, campaign_id, platform, blotato_account_id, display_name, status, connected_at |
| `posts` | id, campaign_id, workspace_id, title, caption, hashtags (text[]), status, scheduled_at, published_at, created_by (`user`/`agent`), agent_run_id, rejection_feedback |
| `post_targets` | id, post_id, social_account_id, platform, blotato_post_id, status, error, published_url |
| `media_assets` | id, workspace_id, post_id, imagekit_file_id, url, width, height, transformations (jsonb), alt_text |
| `agent_runs` | id, workspace_id, campaign_id, thread_id, user_message, status, plan (jsonb), langsmith_run_id, tokens_in, tokens_out, cost_usd, started_at, finished_at |
| `agent_tasks` | id, run_id, agent (`master`/`researcher`/`creator`/`scheduler`/`analytics`), description, status, input, output (jsonb), error, started_at, finished_at |
| `agent_messages` | id, workspace_id, campaign_id, agent, thread_id, role, content, metadata, created_at |
| `research_briefs` | id, campaign_id, run_id, topics (jsonb), sources (jsonb), created_at |
| `analytics_snapshots` | id, campaign_id, social_account_id, post_id (nullable), date, metrics (jsonb) |
| `analytics_insights` | id, campaign_id, run_id, summary, recommendations (jsonb), period_start, period_end |
| `notifications` | id, user_id, type, payload, read_at, created_at |
| `usage_ledger` | id, workspace_id, kind (`llm`/`sandbox`/`image`), quantity, cost_usd, run_id, created_at |
| `audit_logs` | id, workspace_id, actor_type (`user`/`agent`/`system`), actor_id, action, entity, entity_id, diff, ip, created_at |

### Drizzle example

```ts
export const posts = pgTable("posts", {
  id: uuid("id").primaryKey().defaultRandom(),
  workspaceId: uuid("workspace_id").notNull().references(() => workspaces.id),
  campaignId: uuid("campaign_id").notNull().references(() => campaigns.id),
  title: text("title"),
  caption: text("caption").notNull(),
  hashtags: text("hashtags").array().default([]),
  status: postStatus("status").notNull().default("draft"),
  scheduledAt: timestamp("scheduled_at", { withTimezone: true }),
  publishedAt: timestamp("published_at", { withTimezone: true }),
  createdBy: text("created_by").notNull().default("user"),
  agentRunId: uuid("agent_run_id").references(() => agentRuns.id),
}, (t) => ({
  byCampaignStatus: index("posts_campaign_status_idx").on(t.campaignId, t.status),
  byScheduled: index("posts_scheduled_idx").on(t.scheduledAt),
}));
```

### Indexes and constraints
- Index `(workspace_id, campaign_id)` on all campaign-scoped tables.
- Unique `(post_id, social_account_id)` on `post_targets`.
- Idempotency key on `post_targets` to prevent double publishing.
- Enable Row-Level Security (RLS) policies keyed on `workspace_id` (see `SECURITY.md`).

## 4. Next.js API (Backend-for-Frontend)

All endpoints require an authenticated session and workspace membership check.

| Method | Route | Purpose |
|---|---|---|
| GET/POST | `/api/campaigns` | List, create |
| GET/PATCH/DELETE | `/api/campaigns/:id` | Read, update, archive |
| GET/POST | `/api/social-accounts` | List, start connect flow |
| DELETE | `/api/social-accounts/:id` | Disconnect |
| GET/POST | `/api/posts` | List (filters), create manual post |
| GET/PATCH/DELETE | `/api/posts/:id` | Read, edit, delete |
| POST | `/api/posts/:id/approve` | Approve (optionally with edits) |
| POST | `/api/posts/:id/reject` | Reject with feedback, resumes agent |
| POST | `/api/posts/:id/reschedule` | Change time |
| POST | `/api/media/imagekit-auth` | ImageKit upload auth params |
| POST | `/api/media/:id/transform` | Apply ImageKit transformations |
| POST | `/api/agent/runs` | Start an agent run (returns `runId`) |
| GET | `/api/agent/runs/:id/stream` | SSE stream of agent events |
| POST | `/api/agent/runs/:id/resume` | Resume after human approval |
| GET | `/api/agent/agents` | Agent roster and live status |
| GET | `/api/agent/threads/:id/messages` | Chat history |
| GET | `/api/analytics/summary` | KPI cards (campaign, range) |
| GET | `/api/analytics/timeseries` | Chart data |
| GET | `/api/analytics/insights` | AI insights |
| GET | `/api/notifications` | List and mark read |
| POST | `/api/webhooks/blotato` | Publish status and analytics webhooks (signed) |
| POST | `/api/inngest` | Inngest handler |

**Conventions:** Zod validation on every input, consistent error shape `{ error: { code, message, details? } }`, cursor pagination, ISO-8601 UTC timestamps.

## 5. Python Agent Service (FastAPI)

Internal only. Authenticated with a short-lived signed service JWT from Next.js (includes `workspace_id`, `user_id`, `campaign_id`).

| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/runs` | Start graph run (`thread_id`, `message`, `campaign_id`) |
| GET | `/v1/runs/{id}/events` | Stream node and token events (SSE) |
| POST | `/v1/runs/{id}/resume` | Resume from interrupt with approval payload |
| POST | `/v1/runs/{id}/cancel` | Cancel a run |
| GET | `/v1/threads/{id}/state` | Inspect graph state |
| POST | `/v1/tasks/research` | Direct invocation of Researcher (used by cron jobs) |
| POST | `/v1/tasks/analytics` | Direct invocation of Analytics (scheduled reports) |
| GET | `/healthz` | Liveness and readiness |

### Core dependencies

```
fastapi, uvicorn, pydantic>=2
langgraph, langgraph-checkpoint-postgres
langchain, langchain-google-genai
langsmith
e2b-desktop
imagekitio
httpx, tenacity
psycopg[pool], sqlalchemy (read and write for agent-owned tables)
```

### LLM factory (`core/llm.py`)

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

def get_llm(role: str = "worker"):
    model = settings.GEMINI_PRO_MODEL if role == "planner" else settings.GEMINI_FLASH_MODEL
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=0.2 if role == "planner" else 0.7,
        max_retries=3,
        timeout=60,
    )
```

Model names are environment variables so they can be updated without code changes.

### Checkpointing and persistence
- `PostgresSaver` / `AsyncPostgresSaver` stores graph state per `thread_id`, enabling pause, resume, and human-in-the-loop.
- Domain data (posts, tasks, briefs) is written to app tables through a tool layer, not directly from LLM output.

### Observability
- `LANGSMITH_TRACING=true`, project per environment (`social-agents-dev|staging|prod`).
- Tag runs with `workspace_id`, `campaign_id`, `agent`, `run_id` metadata. Do not include raw PII or tokens in metadata.

## 6. Background Jobs (Inngest)

| Function | Trigger | Description |
|---|---|---|
| `agent.run` | event `agent/run.requested` | Calls Python `/v1/runs`, relays events to DB and SSE, handles timeout and retry |
| `agent.resume` | event `agent/run.approved` | Resumes interrupted graph |
| `research.scheduled` | cron (daily per campaign) | Keeps trend briefs fresh |
| `post.publish` | event `post/publish.due` and step `sleepUntil(scheduledAt)` | Publishes via Blotato with idempotency key |
| `post.sync-status` | cron (every 5 min) and Blotato webhook | Reconciles post statuses |
| `analytics.sync` | cron (hourly or daily) | Pulls metrics into `analytics_snapshots` |
| `analytics.insights` | cron (weekly) | Triggers Analytics agent to write insights |
| `usage.rollup` | cron (hourly) | Aggregates usage and enforces quotas |

**Rules:** every function is idempotent, uses `step.run` for each side effect, has bounded retries with exponential backoff, and writes failures to `agent_tasks` / `notifications`.

## 7. Third-Party Integrations

### Blotato
- Wrapper module with typed client: `connectAccount`, `listAccounts`, `createPost`, `schedulePost`, `getPostStatus`, `getAnalytics`.
- Retries with backoff on 429 and 5xx. Map Blotato errors to internal error codes.
- Verify webhook signatures.

### ImageKit
- Client-side upload using server-issued auth params.
- Transformations expressed as URL params (`tr=w-1080,h-1080,fo-auto,...`). Persist the chosen transformation JSON in `media_assets.transformations`.
- Enforce allowed MIME types and size limits.

### E2B Desktop Sandbox
- Created per research task (ephemeral), destroyed at end or on timeout (max 10 min).
- Used by Researcher through a tool that supplies a constrained set of actions (open URL, read page text, screenshot).
- No credentials or user data ever placed in the sandbox.

## 8. Real-Time Updates

- Agent events (`run_started`, `node_started`, `token`, `task_updated`, `approval_required`, `run_completed`, `run_failed`) are emitted by Python via SSE, persisted by Inngest/Next.js, and relayed to the browser over SSE.
- Event envelope:

```json
{ "runId": "uuid", "seq": 42, "type": "task_updated",
  "agent": "creator", "payload": { "taskId": "uuid", "status": "running" },
  "ts": "2026-01-01T10:00:00Z" }
```
- Client reconnects with `Last-Event-ID` to replay missed events from DB.

## 9. Environment Variables

```
# Web
DATABASE_URL=
AUTH_SECRET=
INNGEST_EVENT_KEY= INNGEST_SIGNING_KEY=
AGENT_SERVICE_URL= AGENT_SERVICE_JWT_SECRET=
IMAGEKIT_PUBLIC_KEY= IMAGEKIT_PRIVATE_KEY= IMAGEKIT_URL_ENDPOINT=
BLOTATO_API_KEY= BLOTATO_WEBHOOK_SECRET=

# Agent service
GOOGLE_API_KEY=
GEMINI_PRO_MODEL= GEMINI_FLASH_MODEL=
LANGSMITH_API_KEY= LANGSMITH_TRACING=true LANGSMITH_PROJECT=
E2B_API_KEY=
DATABASE_URL=            # same cluster, restricted role
AGENT_SERVICE_JWT_SECRET=
MAX_GRAPH_STEPS=25 RUN_TIMEOUT_SECONDS=600
```

## 9b. Deployment

| Component | Target |
|---|---|
| Next.js | Vercel (or container) |
| Python agent service | Container (Cloud Run / Fly / Railway / ECS), min 1 instance, autoscale on CPU and concurrency |
| Postgres | Managed (InsForge or equivalent) with PITR backups |
| Inngest | Inngest Cloud |
| Environments | `dev`, `staging`, `prod` with separate keys and LangSmith projects |

## 10. Testing and CI/CD

- **Web:** Vitest (unit), Playwright (e2e).
- **Agents:** pytest; node-level tests with mocked LLM; **LangSmith evals** on datasets (plan quality, brand voice adherence, platform format compliance, tool-call correctness).
- **CI pipeline:** lint → typecheck → unit tests → migration dry run → build → evals (nightly) → deploy.
- **CodeRabbit:** automated PR review; enforce on every PR. Branch protection requires passing CI and one review.
- **Migrations:** Drizzle Kit, forward-only, reviewed in PR; never auto-apply to prod without approval.

## 11. Error Handling Standards

| Code | Meaning |
|---|---|
| `AUTH_REQUIRED` / `FORBIDDEN` | Auth failures |
| `VALIDATION_ERROR` | Bad input |
| `QUOTA_EXCEEDED` | Usage limits hit |
| `PLATFORM_ERROR` | Blotato or social platform failure |
| `AGENT_TIMEOUT` / `AGENT_FAILED` | Agent run issues |
| `INTEGRATION_UNAVAILABLE` | Upstream (E2B, ImageKit, Gemini) down |

Failures surface as notifications and are shown with a retry action.
