import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Integer, Numeric, Boolean,
    ARRAY, JSON, Enum as SQLEnum
)
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UTCDateTime(TypeDecorator):
    """
    Ensures datetime values are always timezone-aware UTC timestamps
    compatible with PostgreSQL TIMESTAMPTZ and asyncpg.
    Seamlessly handles timezone-aware datetimes, offset-naive datetimes, and ISO string inputs.
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, str):
            try:
                from dateutil.parser import parse
                value = parse(value)
            except Exception:
                value = datetime.fromisoformat(value)
        if hasattr(value, "tzinfo"):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and getattr(value, "tzinfo", None) is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class GUID(TypeDecorator):
    """
    Platform-independent GUID / UUID type.
    Uses PostgreSQL's native UUID(as_uuid=False), otherwise uses CHAR(36).
    Deterministically converts non-UUID strings to standard RFC 4122 UUIDs so
    legacy strings never cause 'operator does not exist: uuid = character varying'.
    """
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        try:
            return str(uuid.UUID(str(value)))
        except (ValueError, AttributeError):
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


# Official PostgreSQL enum wrappers matching schema.sql
approval_mode_enum = SQLEnum("manual", "auto", name="approval_mode", create_type=False)
post_status_enum = SQLEnum("draft", "pending_approval", "scheduled", "publishing", "published", "failed", name="post_status", create_type=False)
creator_type_enum = SQLEnum("user", "agent", name="creator_type", create_type=False)
social_platform_enum = SQLEnum("instagram", "facebook", "x", "linkedin", "tiktok", "youtube", name="social_platform", create_type=False)
run_status_enum = SQLEnum("running", "waiting_approval", "completed", "failed", "cancelled", name="run_status", create_type=False)
agent_type_enum = SQLEnum("master", "researcher", "creator", "scheduler", "analytics", name="agent_type", create_type=False)
task_status_enum = SQLEnum("pending", "running", "done", "failed", "skipped", name="task_status", create_type=False)


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    owner_id = Column(GUID, nullable=False, default=lambda: str(uuid.uuid4()))

    plan = Column(String(50), default="pro", nullable=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    campaigns = relationship("Campaign", back_populates="workspace", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="workspace", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    avatar_url = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    goal = Column(Text, nullable=True)
    brand_voice = Column(JSON, default=dict, nullable=False)
    audience = Column(Text, nullable=True)
    timezone = Column(String(100), default="UTC", nullable=False)
    approval_mode = Column(approval_mode_enum, default="manual", nullable=False)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    workspace = relationship("Workspace", back_populates="campaigns")
    posts = relationship("Post", back_populates="campaign", cascade="all, delete-orphan")
    social_accounts = relationship("SocialAccount", back_populates="campaign")
    agent_runs = relationship("AgentRun", back_populates="campaign", cascade="all, delete-orphan")


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(GUID, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    platform = Column(social_platform_enum, nullable=False)
    blotato_account_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)

    handle = Column(String(255), nullable=True)
    avatar_url = Column(Text, nullable=True)
    status = Column(String(50), default="connected", nullable=False)
    connected_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    campaign = relationship("Campaign", back_populates="social_accounts")
    targets = relationship("PostTarget", back_populates="social_account")


class Post(Base):
    __tablename__ = "posts"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(GUID, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    caption = Column(Text, nullable=False)
    hashtags = Column(ARRAY(Text).with_variant(JSON, "sqlite"), default=list, nullable=False)
    status = Column(post_status_enum, default="draft", nullable=False)
    scheduled_at = Column(UTCDateTime, nullable=True)
    published_at = Column(UTCDateTime, nullable=True)
    created_by = Column(creator_type_enum, default="user", nullable=False)
    agent_run_id = Column(GUID, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    rejection_feedback = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    workspace = relationship("Workspace", back_populates="posts")
    campaign = relationship("Campaign", back_populates="posts")
    targets = relationship("PostTarget", back_populates="post", cascade="all, delete-orphan", lazy="selectin")
    media_assets = relationship("MediaAsset", back_populates="post", cascade="all, delete-orphan", lazy="selectin")


class PostTarget(Base):
    __tablename__ = "post_targets"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = Column(GUID, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    social_account_id = Column(GUID, ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False)
    platform = Column(social_platform_enum, nullable=False)
    blotato_post_id = Column(String(255), nullable=True)
    status = Column(post_status_enum, default="draft", nullable=False)
    error = Column(Text, nullable=True)
    published_url = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    post = relationship("Post", back_populates="targets")
    social_account = relationship("SocialAccount", back_populates="targets")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(GUID, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    imagekit_file_id = Column(String(255), nullable=True)
    url = Column(Text, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    aspect_ratio = Column(String(20), nullable=True)  # '1:1', '4:5', '9:16', '16:9'
    transformations = Column(JSON, default=dict, nullable=False)
    alt_text = Column(Text, nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    post = relationship("Post", back_populates="media_assets")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(GUID, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(String(255), nullable=False, index=True)
    user_message = Column(Text, nullable=False)
    status = Column(run_status_enum, default="running", nullable=False)
    plan = Column(JSON, default=list, nullable=False)
    langsmith_run_id = Column(String(255), nullable=True)
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    cost_usd = Column(Numeric(10, 6), default=0.0)
    started_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at = Column(UTCDateTime, nullable=True)

    campaign = relationship("Campaign", back_populates="agent_runs")
    tasks = relationship("AgentTask", back_populates="run", cascade="all, delete-orphan", lazy="selectin")


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(GUID, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    agent = Column(agent_type_enum, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(task_status_enum, default="pending", nullable=False)
    input = Column(JSON, default=dict, nullable=False)
    output = Column(JSON, default=dict, nullable=False)
    error = Column(Text, nullable=True)
    started_at = Column(UTCDateTime, nullable=True)
    finished_at = Column(UTCDateTime, nullable=True)

    run = relationship("AgentRun", back_populates="tasks")


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(GUID, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(String(255), nullable=False, index=True)
    agent = Column(agent_type_enum, nullable=True)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict, nullable=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchBrief(Base):
    __tablename__ = "research_briefs"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(GUID, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(GUID, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    topics = Column(JSON, default=list, nullable=False)
    sources = Column(JSON, default=list, nullable=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(GUID, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    social_account_id = Column(GUID, ForeignKey("social_accounts.id", ondelete="SET NULL"), nullable=True)
    post_id = Column(GUID, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    date = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    metrics = Column(JSON, default=dict, nullable=False)  # impressions, reach, engagement, likes, comments, shares
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AnalyticsInsight(Base):
    __tablename__ = "analytics_insights"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(GUID, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(GUID, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    summary = Column(Text, nullable=False)
    recommendations = Column(JSON, default=list, nullable=False)
    period_start = Column(UTCDateTime, nullable=True)
    period_end = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id = Column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    read_at = Column(UTCDateTime, nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(GUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(GUID, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    actor_type = Column(String(50), nullable=False)
    actor_id = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    entity = Column(String(100), nullable=False)
    entity_id = Column(String(255), nullable=False)
    diff = Column(JSON, nullable=True)
    ip = Column(String(50), nullable=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False)



