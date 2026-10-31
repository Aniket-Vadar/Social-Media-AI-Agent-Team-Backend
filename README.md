---
title: Socialix AI Agent Office Backend
emoji: 🪄
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Socialix — AI Agent Social Media Office Backend

Production-ready backend architecture for the **Socialix AI Agent Social Media Office** SaaS.
Integrated with the deployed frontend at: [https://socialmedia-ashen-iota.vercel.app/](https://socialmedia-ashen-iota.vercel.app/)

---

## 1. Database Architecture: Supabase (PostgreSQL) vs. NoSQL

### Verdict: **PostgreSQL (Supabase) is Required**

**Supabase IS PostgreSQL**. It is an open-source, scalable database platform built natively on PostgreSQL. It is **not** a traditional NoSQL database.

### Why PostgreSQL (Supabase) is the Right Production Choice:

| Architectural Requirement | Pure NoSQL (e.g., MongoDB, DynamoDB) | PostgreSQL on Supabase (Our Solution) |
|---|---|---|
| **Multi-Tenant Isolation & Security** | Manual application-level filtering on every query (high IDOR leak risk). | **Native Row-Level Security (RLS)** enforced by the PostgreSQL engine per `workspace_id`. |
| **Relational Integrity** | Weak or manual; data corruption risk between Users, Campaigns, Posts, PostTargets, and Social Accounts. | **Strict Foreign Keys, ACID transactions, and Cascading Deletes**. |
| **Preventing Double-Publishing** | Difficult to guarantee across multiple workers. | **Unique Constraint Idempotency Keys** on `(post_id, social_account_id)`. |
| **Hybrid Document Storage** | Native. | **PostgreSQL `JSONB`** delivers full document flexibility for dynamic agent plans, brand voice rules, ImageKit transformations, and metrics with GIN indexing. |
| **AI Agent Vector Search & Memory** | Requires a separate vector database (e.g. Pinecone/Qdrant) at additional cost and complexity. | **Native `pgvector` Extension** included inside Supabase for content embeddings, semantic search, and style matching. |
| **LangGraph Checkpointing** | Third-party or memory-only checkpointer. | **`langgraph-checkpoint-postgres` (`AsyncPostgresSaver`)** provides enterprise-grade thread state, pause/resume, and human-in-the-loop approval. |

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────┐
│  Next.js Deployed UI                                   │
│  https://socialmedia-ashen-iota.vercel.app             │
└───────────────────────────┬────────────────────────────┘
                            │ REST + SSE Streaming
┌───────────────────────────▼────────────────────────────┐
│  FastAPI Backend (Python 3.12)                         │
│  - Multi-Tenant Security & Tenant Context Ingestion    │
│  - Async SQLAlchemy 2.0 ORM Engine                     │
│  - Real-Time Event Streaming (SSE)                     │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────────────┐   ┌───────────────────────┐
│  Supabase (PostgreSQL 15+)    │   │  LangGraph Supervisor │
│  - Core Tables with RLS       │   │  Multi-Agent Engine   │
│  - pgvector Content Search    │   │  (Google Gemini LLM)  │
│  - JSONB Flexible Documents   │   └───────────┬───────────┘
└───────────────────────────────┘               │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
              ┌───────────┐               ┌───────────┐               ┌───────────┐
              │Researcher │               │  Creator  │               │ Scheduler │
              │(Trends)   │               │(Copy+Img) │               │ (Blotato) │
              └───────────┘               └───────────┘               └───────────┘
```

---

## 3. Implemented API Routes (Aligned with UI)

### 📌 Campaigns (`/api/v1/campaigns`)
- `GET /api/v1/campaigns`: List all campaigns for active workspace.
- `POST /api/v1/campaigns`: Create campaign with goal, brand voice, audience, timezone, approval mode.
- `GET /api/v1/campaigns/{id}`: Retrieve single campaign.
- `PATCH /api/v1/campaigns/{id}`: Update campaign settings (brand voice, approval mode).
- `DELETE /api/v1/campaigns/{id}`: Archive/delete campaign.

### 📌 Posts & Approval Workflow (`/api/v1/posts`)
- `GET /api/v1/posts`: Filterable post list (status, platform, creator).
- `POST /api/v1/posts`: Manual post creation.
- `GET /api/v1/posts/{id}`: Post details.
- `POST /api/v1/posts/{id}/approve`: **Human-in-the-Loop Approval** (optionally with caption/hashtag edits).
- `POST /api/v1/posts/{id}/reject`: Reject with feedback to trigger AI revision loop.
- `POST /api/v1/posts/{id}/reschedule`: Drag-and-drop or modal reschedule.
- `DELETE /api/v1/posts/{id}`: Delete post.

### 📌 AI Agents & Office Canvas (`/api/v1/agents`)
- `GET /api/v1/agents`: Live statuses of all 5 agents (Master, Researcher, Creator, Scheduler, Analytics).
- `GET /api/v1/agents/{agent_id}`: Side drawer details and per-agent configuration.
- `GET /api/v1/agents/threads/{thread_id}/messages`: Chat history for Master Agent or sub-agents.

### 📌 LangGraph Execution & Real-Time Streaming (`/api/v1/runs`)
- `POST /api/v1/runs`: Launch multi-agent autonomous workflow.
- `GET /api/v1/runs/{id}/events`: **Server-Sent Events (SSE)** stream delivering live updates (<3s latency).
- `POST /api/v1/runs/{id}/resume`: Resume interrupted graph run after human approval.

### 📌 Calendar (`/api/v1/calendar`)
- `GET /api/v1/calendar/events`: Scheduled and published posts for Month/Week/List views.

### 📌 Analytics Dashboard (`/api/v1/analytics`)
- `GET /api/v1/analytics/dashboard`: KPI summary (posts, completion rate, impressions, engagement), 7-day timeseries data, and AI-generated strategic insights.

### 📌 Social Accounts (`/api/v1/social-accounts`)
- `GET /api/v1/social-accounts`: List connected accounts (Instagram, LinkedIn, X, TikTok, Facebook).
- `POST /api/v1/social-accounts`: Connect new social account via Blotato.
- `DELETE /api/v1/social-accounts/{id}`: Disconnect account.

---

## 4. Quickstart: Running Locally

### 1. Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Configure `.env`
Set your Supabase PostgreSQL connection string and Google API Key in `.env`:
```env
DATABASE_URL="postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres"
GOOGLE_API_KEY="AIzaSy..."
```

### 3. Run Supabase Database Migration
Open the Supabase Dashboard -> **SQL Editor**, paste the contents of:
[`app/db/schema.sql`](file:///b:/Social%20media%20-backend/app/db/schema.sql)
and click **Run**.

### 4. Run Integration Verification Test
```powershell
.\.venv\Scripts\python.exe test_runner.py
```

### 5. Launch FastAPI Server
```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger Documentation: **`http://localhost:8000/docs`**
ReDoc Documentation: **`http://localhost:8000/redoc`**
