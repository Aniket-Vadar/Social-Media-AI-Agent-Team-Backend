from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_tenant_context, TenantContext
from app.models.models import Post
from app.schemas.post import PostOut
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("/events", response_model=ApiResponse[List[PostOut]])
async def get_calendar_events(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Retrieve posts with scheduled or published timestamps for calendar rendering."""
    query = select(Post).where(
        Post.workspace_id == tenant.workspace_id,
        Post.status.in_(["scheduled", "publishing", "published"])
    )
    if tenant.campaign_id:
        query = query.where(Post.campaign_id == tenant.campaign_id)

    if start_date:
        query = query.where(Post.scheduled_at >= start_date)
    if end_date:
        query = query.where(Post.scheduled_at <= end_date)

    result = await db.execute(query)
    posts = result.scalars().all()
    return ApiResponse(data=[PostOut.model_validate(p) for p in posts])
