from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.core.security import get_tenant_context, TenantContext
from app.models.models import AgentMessage, AgentRun
from app.schemas.agent import AgentOfficeStatus, AgentMessageOut
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/agents", tags=["Agents"])

# Agent Roster defined in PRD.md & UI.md
ROSTER: List[AgentOfficeStatus] = [
    AgentOfficeStatus(
        id="master",
        name="Master Agent",
        role="Planner & Coordinator",
        status="idle",
        current_task="Ready to orchestrate campaign workflows",
        avatar="🪄",
        color="#6D5EF5"
    ),
    AgentOfficeStatus(
        id="researcher",
        name="Research Agent",
        role="Trend & Competitor Analyst",
        status="working",
        current_task="Scanning tech trends & competitor viral hooks",
        avatar="🔍",
        color="#0EA5E9"
    ),
    AgentOfficeStatus(
        id="creator",
        name="Creator Agent",
        role="Copywriter & Visual Designer",
        status="working",
        current_task="Crafting 1:1 image transformations & captions",
        avatar="🎨",
        color="#F59E0B"
    ),
    AgentOfficeStatus(
        id="scheduler",
        name="Scheduler Agent",
        role="Distribution & Best-Time Planner",
        status="idle",
        current_task="Standby for post approval batch",
        avatar="📅",
        color="#10B981"
    ),
    AgentOfficeStatus(
        id="analytics",
        name="Analytics Agent",
        role="Growth & Performance Analyst",
        status="idle",
        current_task="Monitoring weekly impressions & conversion lift",
        avatar="📊",
        color="#EC4899"
    )
]


@router.get("", response_model=ApiResponse[List[AgentOfficeStatus]])
async def get_agent_roster(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Retrieve all agents in the office with live visual states."""
    return ApiResponse(data=ROSTER)


@router.get("/{agent_id}", response_model=ApiResponse[AgentOfficeStatus])
async def get_agent_details(
    agent_id: str,
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Retrieve details and state for an individual agent (used by the side drawer)."""
    agent = next((a for a in ROSTER if a.id == agent_id.lower()), None)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=agent)


@router.get("/threads/{thread_id}/messages", response_model=ApiResponse[List[AgentMessageOut]])
async def get_thread_messages(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Fetch conversation and execution logs for a chat thread."""
    result = await db.execute(
        select(AgentMessage)
        .where(
            AgentMessage.thread_id == thread_id,
            AgentMessage.workspace_id == tenant.workspace_id
        )
        .order_by(AgentMessage.created_at)
    )
    messages = result.scalars().all()
    return ApiResponse(data=[
        AgentMessageOut(
            id=m.id,
            thread_id=m.thread_id,
            agent=m.agent,
            role=m.role,
            content=m.content,
            metadata=m.metadata_ or {},
            created_at=m.created_at
        )
        for m in messages
    ])
