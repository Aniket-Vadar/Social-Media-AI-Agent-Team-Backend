from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

AgentName = Literal["master", "researcher", "creator", "scheduler", "analytics"]
TaskStatus = Literal["pending", "running", "done", "failed", "skipped"]
AgentRunStatus = Literal["running", "waiting_approval", "completed", "failed", "cancelled"]


class PlanStepSchema(BaseModel):
    id: str
    agent: AgentName
    instruction: str
    depends_on: List[str] = Field(default_factory=list)
    status: TaskStatus = "pending"
    result_ref: Optional[str] = None


class AgentRunCreate(BaseModel):
    message: str = Field(..., description="User prompt or instruction to Master Agent")
    campaign_id: Optional[str] = None
    thread_id: Optional[str] = None


class AgentTaskOut(BaseModel):
    id: str
    agent: str
    description: str
    status: str
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AgentRunOut(BaseModel):
    id: str
    workspace_id: str
    campaign_id: str
    thread_id: str
    user_message: str
    status: str
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    langsmith_run_id: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    started_at: datetime
    finished_at: Optional[datetime] = None
    tasks: List[AgentTaskOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RejectedItem(BaseModel):
    id: str
    feedback: str


class ResumeRunRequest(BaseModel):
    approved_post_ids: List[str] = Field(default_factory=list)
    rejected_posts: List[RejectedItem] = Field(default_factory=list)
    edited_posts: List[Dict[str, Any]] = Field(default_factory=list)


class AgentOfficeStatus(BaseModel):
    id: str
    name: str
    role: str
    status: Literal["idle", "thinking", "working", "waiting_approval", "error", "done"]
    current_task: Optional[str] = None
    avatar: str
    color: str


class AgentMessageOut(BaseModel):
    id: str
    thread_id: str
    agent: Optional[str] = None
    role: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
