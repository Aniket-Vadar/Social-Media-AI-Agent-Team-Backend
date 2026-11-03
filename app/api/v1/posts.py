import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.security import get_tenant_context, TenantContext
from app.models.models import Post, PostTarget, MediaAsset, Workspace, Campaign
from app.schemas.post import PostCreate, PostUpdate, PostOut, PostApprove, PostReject, PostReschedule
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("", response_model=ApiResponse[List[PostOut]])
async def list_posts(
    status_filter: Optional[str] = Query(None, alias="status"),
    platform: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """List posts scoped to the tenant workspace and campaign with filters."""
    query = (
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.workspace_id == tenant.workspace_id)
    )
    if tenant.campaign_id:
        query = query.where(Post.campaign_id == tenant.campaign_id)
    if status_filter:
        query = query.where(Post.status == status_filter)

    query = query.order_by(desc(Post.created_at)).limit(limit)
    result = await db.execute(query)
    posts = result.scalars().all()

    return ApiResponse(data=[PostOut.model_validate(p) for p in posts])



@router.post("", response_model=ApiResponse[PostOut], status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreate,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Create a new post (manual or AI-assisted)."""
    campaign_id = payload.campaign_id or tenant.campaign_id
    if not campaign_id:
        campaign_id = "065743f9-f908-5392-9192-ac92ab7895a9"

    # Ensure workspace exists in DB to prevent foreign key errors (e.g. from frontend dummy IDs)
    ws = await db.get(Workspace, tenant.workspace_id)
    if not ws:
        first_ws = (await db.execute(select(Workspace).limit(1))).scalar_one_or_none()
        if first_ws:
            tenant.workspace_id = str(first_ws.id)
        else:
            new_ws = Workspace(
                id=tenant.workspace_id,
                name="Default Workspace",
                owner_id="00000000-0000-0000-0000-000000000001",
                plan="pro"
            )
            db.add(new_ws)
            await db.flush()

    # Ensure campaign exists in DB to prevent foreign key errors
    camp = await db.get(Campaign, campaign_id)
    if not camp:
        first_camp = (await db.execute(
            select(Campaign).where(Campaign.workspace_id == tenant.workspace_id).limit(1)
        )).scalar_one_or_none()
        if first_camp:
            campaign_id = str(first_camp.id)
        else:
            camp = Campaign(
                id=campaign_id,
                workspace_id=tenant.workspace_id,
                name="Default Campaign",
                goal="Autonomous AI Growth",
                brand_voice={"tone": "professional, engaging", "banned_words": []},
                approval_mode="manual",
                status="active"
            )
            db.add(camp)
            await db.flush()

    post = Post(
        id=str(uuid.uuid4()),
        workspace_id=tenant.workspace_id,
        campaign_id=campaign_id,
        title=payload.title,
        caption=payload.caption,
        hashtags=payload.hashtags,
        status=payload.status or "draft",
        scheduled_at=payload.scheduled_at,
        created_by="user"
    )
    db.add(post)

    if payload.media_url:
        media = MediaAsset(
            id=str(uuid.uuid4()),
            workspace_id=tenant.workspace_id,
            post_id=post.id,
            url=payload.media_url,
            aspect_ratio="1:1"
        )
        db.add(media)

    await db.commit()
    post_res = await db.execute(
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.id == post.id)
    )
    post = post_res.scalar_one()
    return ApiResponse(data=PostOut.model_validate(post))


@router.get("/{post_id}", response_model=ApiResponse[PostOut])
async def get_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Retrieve full details of a specific post."""
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.id == post_id, Post.workspace_id == tenant.workspace_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return ApiResponse(data=PostOut.model_validate(post))


from app.tools.blotato import blotato_client


@router.post("/{post_id}/approve", response_model=ApiResponse[PostOut])
async def approve_post(
    post_id: str,
    payload: PostApprove,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Approve post for scheduling/publishing with optional live edits."""
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.id == post_id, Post.workspace_id == tenant.workspace_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if payload.edited_caption:
        post.caption = payload.edited_caption
    if payload.edited_hashtags:
        post.hashtags = payload.edited_hashtags
    if payload.custom_scheduled_at:
        post.scheduled_at = payload.custom_scheduled_at

    media_url = post.media_assets[0].url if post.media_assets else "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe"

    if payload.schedule_now:
        blotato_res = await blotato_client.publish_now(
            account_id="blotato-ig-1",
            caption=f"{post.caption}\n\n{' '.join(post.hashtags or [])}",
            media_urls=[media_url],
            idempotency_key=f"pub_{post.id}"
        )
        post.status = "publishing"
    else:
        post.status = "scheduled"

    post.updated_at = datetime.utcnow()
    await db.commit()
    post_res = await db.execute(
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.id == post.id)
    )
    post = post_res.scalar_one()
    return ApiResponse(data=PostOut.model_validate(post))


@router.post("/{post_id}/reject", response_model=ApiResponse[PostOut])
async def reject_post(
    post_id: str,
    payload: PostReject,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Reject a draft post with feedback so the AI Creator can revise it."""
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.id == post_id, Post.workspace_id == tenant.workspace_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.status = "draft"
    post.rejection_feedback = payload.feedback
    post.updated_at = datetime.utcnow()
    await db.commit()
    post_res = await db.execute(
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.id == post.id)
    )
    post = post_res.scalar_one()
    return ApiResponse(data=PostOut.model_validate(post))


@router.post("/{post_id}/reschedule", response_model=ApiResponse[PostOut])
async def reschedule_post(
    post_id: str,
    payload: PostReschedule,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Update scheduled publishing timestamp."""
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.id == post_id, Post.workspace_id == tenant.workspace_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.scheduled_at = payload.scheduled_at
    post.updated_at = datetime.utcnow()
    await db.commit()
    post_res = await db.execute(
        select(Post)
        .options(selectinload(Post.media_assets), selectinload(Post.targets))
        .where(Post.id == post.id)
    )
    post = post_res.scalar_one()
    return ApiResponse(data=PostOut.model_validate(post))


@router.delete("/{post_id}", response_model=ApiResponse[dict])
async def delete_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Delete a post from the workspace."""
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.workspace_id == tenant.workspace_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    await db.delete(post)
    await db.commit()
    return ApiResponse(data={"message": f"Post {post_id} deleted successfully"})
