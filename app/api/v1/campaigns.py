import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_tenant_context, TenantContext
from app.models.models import Campaign, Workspace
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignOut
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.get("", response_model=ApiResponse[List[CampaignOut]])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """List all campaigns in current workspace."""
    result = await db.execute(
        select(Campaign).where(Campaign.workspace_id == tenant.workspace_id)
    )
    campaigns = result.scalars().all()

    # If no campaign exists yet in db, provide the default campaign from the deployed UI
    if not campaigns:
        ws_res = await db.execute(select(Workspace).where(Workspace.id == tenant.workspace_id))
        if not ws_res.scalar_one_or_none():
            ws = Workspace(
                id=tenant.workspace_id,
                name="Tubeguruji Workspace",
                owner_id=tenant.user_id
            )
            db.add(ws)
            await db.flush()

        default_camp = Campaign(
            id="camp-tubeguruji-instagram",
            workspace_id=tenant.workspace_id,
            name="Tubeguruji Instagram",
            goal="Researching trends, creating engaging content and scheduling posts to grow your brand.",
            brand_voice={"tone": "professional, engaging", "banned_words": [], "guidelines": ""},
            audience="Tech Enthusiasts, Content Creators, Founders",
            timezone="UTC",
            approval_mode="manual",
            status="active"
        )
        db.add(default_camp)
        await db.commit()
        await db.refresh(default_camp)
        campaigns = [default_camp]

    return ApiResponse(data=[CampaignOut.model_validate(c) for c in campaigns])



@router.post("", response_model=ApiResponse[CampaignOut], status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Create a new campaign scoped to the tenant's workspace."""
    campaign = Campaign(
        id=str(uuid.uuid4()),
        workspace_id=tenant.workspace_id,
        name=payload.name,
        goal=payload.goal,
        brand_voice=payload.brand_voice.dict(),
        audience=payload.audience,
        timezone=payload.timezone,
        approval_mode=payload.approval_mode,
        status="active"
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return ApiResponse(data=CampaignOut.model_validate(campaign))


@router.get("/{campaign_id}", response_model=ApiResponse[CampaignOut])
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Retrieve details for a specific campaign."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == tenant.workspace_id
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return ApiResponse(data=CampaignOut.model_validate(campaign))


@router.patch("/{campaign_id}", response_model=ApiResponse[CampaignOut])
async def update_campaign(
    campaign_id: str,
    payload: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Update campaign settings (brand voice, goal, approval mode, etc.)."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == tenant.workspace_id
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if payload.name is not None:
        campaign.name = payload.name
    if payload.goal is not None:
        campaign.goal = payload.goal
    if payload.brand_voice is not None:
        campaign.brand_voice = payload.brand_voice.dict()
    if payload.audience is not None:
        campaign.audience = payload.audience
    if payload.timezone is not None:
        campaign.timezone = payload.timezone
    if payload.approval_mode is not None:
        campaign.approval_mode = payload.approval_mode
    if payload.status is not None:
        campaign.status = payload.status

    campaign.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(campaign)
    return ApiResponse(data=CampaignOut.model_validate(campaign))


@router.delete("/{campaign_id}", response_model=ApiResponse[dict])
async def delete_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Archive or delete a campaign."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == tenant.workspace_id
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await db.delete(campaign)
    await db.commit()
    return ApiResponse(data={"message": f"Campaign {campaign_id} deleted successfully"})
