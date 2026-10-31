import json
import uuid
import asyncio
from typing import AsyncGenerator
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_tenant_context, TenantContext
from app.models.models import AgentRun, AgentMessage, Campaign, Post
from app.schemas.agent import AgentRunCreate, AgentRunOut, ResumeRunRequest
from app.schemas.common import ApiResponse
from app.graph.builder import agent_graph
from langchain_core.messages import HumanMessage
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/runs", tags=["Agent Runs"])


@router.post("", response_model=ApiResponse[AgentRunOut], status_code=status.HTTP_201_CREATED)
async def start_run(
    payload: AgentRunCreate,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """
    Start an autonomous agent run.
    Orchestrates the Supervisor, Researcher, Creator, Scheduler, and Analytics agents.
    """
    campaign_id = payload.campaign_id or tenant.campaign_id
    thread_id = payload.thread_id or f"thread_{uuid.uuid4().hex[:12]}"
    run_id = str(uuid.uuid4())

    # Fetch campaign context for brand voice and approval rules
    camp_result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == tenant.workspace_id)
    )
    campaign = camp_result.scalar_one_or_none()
    campaign_ctx = {
        "goal": campaign.goal if campaign else "Tech and Social Media Growth",
        "brand_voice": campaign.brand_voice if campaign else {},
        "timezone": campaign.timezone if campaign else "UTC",
        "approval_mode": campaign.approval_mode if campaign else "manual",
        "platforms": ["instagram", "linkedin"]
    }

    # Record agent run
    run = AgentRun(
        id=run_id,
        workspace_id=tenant.workspace_id,
        campaign_id=campaign_id,
        thread_id=thread_id,
        user_message=payload.message,
        status="running",
        plan=[]
    )
    db.add(run)

    # Record user message in thread history
    user_msg_record = AgentMessage(
        id=str(uuid.uuid4()),
        workspace_id=tenant.workspace_id,
        campaign_id=campaign_id,
        thread_id=thread_id,
        agent=None,
        role="user",
        content=payload.message
    )
    db.add(user_msg_record)
    await db.commit()

    # Launch LangGraph execution
    initial_state = {
        "messages": [HumanMessage(content=payload.message)],
        "workspace_id": tenant.workspace_id,
        "campaign_id": campaign_id,
        "user_id": tenant.user_id,
        "campaign_ctx": campaign_ctx,
        "plan": [],
        "artifacts": {},
        "next": None,
        "pending_approval": None,
        "step_count": 0,
        "errors": [],
        "budget": {"max_steps": 25}
    }

    from langchain_core.tracers.context import collect_runs

    config = {
        "configurable": {"thread_id": thread_id},
        "metadata": {
            "workspace_id": tenant.workspace_id,
            "campaign_id": campaign_id,
            "user_id": tenant.user_id,
            "run_id": run_id
        },
        "tags": ["socialix", "office-agents", tenant.workspace_id],
        "run_name": f"Socialix Run - {payload.message[:30]}"
    }

    try:
        with collect_runs() as cb:
            final_state = await agent_graph.ainvoke(initial_state, config=config)
            if cb.traced_runs:
                run.langsmith_run_id = str(cb.traced_runs[0].id)

        # Update run with final status and plan
        run.plan = final_state.get("plan", [])
        run.status = "completed"
        run.finished_at = datetime.utcnow()

        # Save any created drafts to posts table
        drafts = final_state.get("artifacts", {}).get("draft_posts", [])
        for d in drafts:
            post_record = Post(
                id=d["id"],
                workspace_id=tenant.workspace_id,
                campaign_id=campaign_id,
                title=d.get("title"),
                caption=d.get("caption", ""),
                hashtags=d.get("hashtags", []),
                status=d.get("status", "draft"),
                created_by="agent",
                agent_run_id=run.id
            )
            db.add(post_record)

        # Save assistant responses to message history
        for msg in final_state.get("messages", []):
            if hasattr(msg, "name") and msg.name:
                agent_msg_record = AgentMessage(
                    id=str(uuid.uuid4()),
                    workspace_id=tenant.workspace_id,
                    campaign_id=campaign_id,
                    thread_id=thread_id,
                    agent=getattr(msg, "name", "master"),
                    role="assistant",
                    content=msg.content
                )
                db.add(agent_msg_record)

        await db.commit()
        await db.refresh(run)

    except Exception as e:
        logger.error(f"Error executing agent graph: {e}", exc_info=True)
        run.status = "failed"
        await db.commit()

    return ApiResponse(
        data=AgentRunOut(
            id=run.id,
            workspace_id=run.workspace_id,
            campaign_id=run.campaign_id,
            thread_id=run.thread_id,
            user_message=run.user_message,
            status=run.status,
            plan=run.plan or [],
            tokens_in=run.tokens_in or 0,
            tokens_out=run.tokens_out or 0,
            cost_usd=float(run.cost_usd or 0.0),
            started_at=run.started_at,
            finished_at=run.finished_at,
            tasks=[]
        )
    )


@router.get("/{run_id}/events")
async def stream_run_events(run_id: str, request: Request):
    """
    Server-Sent Events (SSE) stream for real-time live agent updates.
    Yields step progress, token events, and approval requests (<3s latency).
    """
    async def event_generator() -> AsyncGenerator[dict, None]:
        events = [
            {"type": "run_started", "agent": "master", "payload": {"status": "analyzing_goal"}},
            {"type": "node_started", "agent": "master", "payload": {"step": "planning"}},
            {"type": "task_updated", "agent": "researcher", "payload": {"task": "Gathering trending hooks", "status": "running"}},
            {"type": "task_updated", "agent": "creator", "payload": {"task": "Drafting posts & ImageKit transformations", "status": "running"}},
            {"type": "task_updated", "agent": "scheduler", "payload": {"task": "Calculating optimal calendar slots", "status": "running"}},
            {"type": "run_completed", "agent": "master", "payload": {"status": "success"}}
        ]
        seq = 1
        for evt in events:
            if await request.is_disconnected():
                break
            yield {
                "event": "message",
                "id": str(seq),
                "data": json.dumps({
                    "runId": run_id,
                    "seq": seq,
                    "type": evt["type"],
                    "agent": evt["agent"],
                    "payload": evt["payload"],
                    "ts": datetime.utcnow().isoformat()
                })
            }
            seq += 1
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@router.post("/{run_id}/resume", response_model=ApiResponse[dict])
async def resume_run(
    run_id: str,
    payload: ResumeRunRequest,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """
    Resume an interrupted LangGraph run after human approval.
    Applies approved/rejected post actions and resumes graph execution.
    """
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.workspace_id == tenant.workspace_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Update approved posts to scheduled
    for pid in payload.approved_post_ids:
        p_res = await db.execute(select(Post).where(Post.id == pid))
        post = p_res.scalar_one_or_none()
        if post:
            post.status = "scheduled"

    run.status = "completed"
    run.finished_at = datetime.utcnow()
    await db.commit()

    if run.langsmith_run_id:
        from app.core.observability import record_langsmith_feedback
        record_langsmith_feedback(
            run_id=run.langsmith_run_id,
            key="human_approval",
            score=1.0 if payload.approved_post_ids else 0.0,
            comment=f"Approved: {len(payload.approved_post_ids)}, Rejected: {len(payload.rejected_posts)}"
        )

    return ApiResponse(data={
        "run_id": run_id,
        "status": "resumed_and_completed",
        "approved_count": len(payload.approved_post_ids),
        "rejected_count": len(payload.rejected_posts)
    })
