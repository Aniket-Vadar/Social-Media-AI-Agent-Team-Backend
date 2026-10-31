-- ==============================================================================
-- Socialix - Supabase (PostgreSQL) Production Schema
-- Designed for: Multi-Tenant AI Agent Social Media Office
-- Stack: PostgreSQL 15+ / Supabase with pgvector, JSONB & Row-Level Security (RLS)
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 2. ENUMS
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('owner', 'admin', 'editor', 'viewer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE approval_mode AS ENUM ('manual', 'auto');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE post_status AS ENUM ('draft', 'pending_approval', 'scheduled', 'publishing', 'published', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE creator_type AS ENUM ('user', 'agent');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE agent_type AS ENUM ('master', 'researcher', 'creator', 'scheduler', 'analytics');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE run_status AS ENUM ('running', 'waiting_approval', 'completed', 'failed', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE task_status AS ENUM ('pending', 'running', 'done', 'failed', 'skipped');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE social_platform AS ENUM ('instagram', 'facebook', 'x', 'linkedin', 'tiktok', 'youtube');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 3. CORE TABLES

-- Workspaces (Tenant isolation unit)
CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    owner_id UUID NOT NULL,
    plan VARCHAR(50) NOT NULL DEFAULT 'pro',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Workspace Members
CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role user_role NOT NULL DEFAULT 'editor',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id)
);

-- Campaigns
CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    goal TEXT,
    brand_voice JSONB NOT NULL DEFAULT '{"tone": "professional, engaging", "banned_words": [], "guidelines": ""}',
    audience TEXT,
    timezone VARCHAR(100) NOT NULL DEFAULT 'UTC',
    approval_mode approval_mode NOT NULL DEFAULT 'manual',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Connected Social Accounts (via Blotato)
CREATE TABLE IF NOT EXISTS social_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    platform social_platform NOT NULL,
    blotato_account_id VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    handle VARCHAR(255),
    avatar_url TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'connected',
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(workspace_id, platform, blotato_account_id)
);

-- Agent Runs (LangGraph Execution Tracks)
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    thread_id VARCHAR(255) NOT NULL,
    user_message TEXT NOT NULL,
    status run_status NOT NULL DEFAULT 'running',
    plan JSONB DEFAULT '[]'::jsonb,
    langsmith_run_id VARCHAR(255),
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0.000000,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- Agent Tasks (Execution sub-steps in Plan)
CREATE TABLE IF NOT EXISTS agent_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    agent agent_type NOT NULL,
    description TEXT NOT NULL,
    status task_status NOT NULL DEFAULT 'pending',
    input JSONB DEFAULT '{}'::jsonb,
    output JSONB DEFAULT '{}'::jsonb,
    error TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

-- Agent Messages (Chat History)
CREATE TABLE IF NOT EXISTS agent_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    thread_id VARCHAR(255) NOT NULL,
    agent agent_type,
    role VARCHAR(50) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Posts
CREATE TABLE IF NOT EXISTS posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    title VARCHAR(255),
    caption TEXT NOT NULL,
    hashtags TEXT[] DEFAULT '{}',
    status post_status NOT NULL DEFAULT 'draft',
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    created_by creator_type NOT NULL DEFAULT 'user',
    agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    rejection_feedback TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Post Targets (Multi-platform publishing targets per post)
CREATE TABLE IF NOT EXISTS post_targets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    social_account_id UUID NOT NULL REFERENCES social_accounts(id) ON DELETE CASCADE,
    platform social_platform NOT NULL,
    blotato_post_id VARCHAR(255),
    status post_status NOT NULL DEFAULT 'draft',
    error TEXT,
    published_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(post_id, social_account_id)
);

-- Media Assets (ImageKit integration)
CREATE TABLE IF NOT EXISTS media_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    imagekit_file_id VARCHAR(255),
    url TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    aspect_ratio VARCHAR(20),
    transformations JSONB DEFAULT '{}'::jsonb,
    alt_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Research Briefs (Researcher Agent output)
CREATE TABLE IF NOT EXISTS research_briefs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Analytics Snapshots
CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    social_account_id UUID REFERENCES social_accounts(id) ON DELETE SET NULL,
    post_id UUID REFERENCES posts(id) ON DELETE SET NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb, -- impressions, reach, engagement, likes, comments, shares
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Analytics AI Insights (Analytics Agent output)
CREATE TABLE IF NOT EXISTS analytics_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
    summary TEXT NOT NULL,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Semantic Vector Embeddings for Content Memory & Style Retrieval
CREATE TABLE IF NOT EXISTS post_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    content_vector vector(1536), -- 1536 for OpenAI / 768 for Gemini text-embedding-004
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    type VARCHAR(100) NOT NULL, -- 'approval_required', 'publish_success', 'publish_failed', 'task_completed'
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    actor_type VARCHAR(50) NOT NULL, -- 'user', 'agent', 'system'
    actor_id VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    entity VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    diff JSONB,
    ip VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. INDEXES FOR HIGH-THROUGHPUT QUERYING
CREATE INDEX IF NOT EXISTS idx_campaigns_workspace ON campaigns(workspace_id);
CREATE INDEX IF NOT EXISTS idx_posts_campaign_status ON posts(campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_at ON posts(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_post_targets_post ON post_targets(post_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_thread ON agent_runs(thread_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_thread ON agent_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_run ON agent_tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_date ON analytics_snapshots(campaign_id, date);

-- 5. ROW LEVEL SECURITY (RLS) POLICIES FOR SUPABASE
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE social_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Dynamic Tenant Isolation Policy Example:
-- In Supabase, auth.uid() links to current user.
-- App level requests set app.current_workspace_id.
CREATE POLICY workspace_isolation_campaigns ON campaigns
    USING (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid);

CREATE POLICY workspace_isolation_posts ON posts
    USING (workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid);
