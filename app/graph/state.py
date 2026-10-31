from typing import Annotated, Literal, TypedDict, Optional, List, Dict, Any
from langgraph.graph.message import add_messages

AgentName = Literal["master", "researcher", "creator", "scheduler", "analytics"]


class PlanStep(TypedDict):
    id: str
    agent: AgentName
    instruction: str
    depends_on: List[str]
    status: Literal["pending", "running", "done", "failed", "skipped"]
    result_ref: Optional[str]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    workspace_id: str
    campaign_id: str
    user_id: str
    campaign_ctx: Dict[str, Any]      # brand_voice, audience, platforms, approval_mode, timezone
    plan: List[PlanStep]
    artifacts: Dict[str, Any]         # research briefs, draft posts, scheduled targets, insights
    next: Optional[str]               # routing target
    pending_approval: Optional[Dict[str, Any]]  # human in the loop interrupt state
    step_count: int
    errors: List[Dict[str, Any]]
    budget: Dict[str, Any]            # tokens, max steps
