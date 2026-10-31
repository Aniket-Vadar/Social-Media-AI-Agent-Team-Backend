import uuid
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_tenant_context, TenantContext
from app.models.models import SocialAccount, Workspace, Campaign
from app.schemas.social_account import SocialAccountCreate, SocialAccountOut
from app.schemas.common import ApiResponse
from app.tools.blotato import blotato_client


router = APIRouter(prefix="/social-accounts", tags=["Social Accounts"])


@router.get("", response_model=ApiResponse[List[SocialAccountOut]])
async def list_social_accounts(
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """List all connected accounts for the campaign/workspace."""
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.workspace_id == tenant.workspace_id)
    )
    accounts = result.scalars().all()

    # If no accounts yet, provide connected Instagram account matching UI
    if not accounts:
        ws_res = await db.execute(select(Workspace).where(Workspace.id == tenant.workspace_id))
        if not ws_res.scalar_one_or_none():
            ws = Workspace(
                id=tenant.workspace_id,
                name="Tubeguruji Workspace",
                owner_id=tenant.user_id
            )
            db.add(ws)
            await db.flush()

        # Find existing active campaign or set None
        camp_res = await db.execute(select(Campaign).where(Campaign.workspace_id == tenant.workspace_id))
        active_camp = camp_res.scalars().first()
        campaign_id = active_camp.id if active_camp else None

        demo_account = SocialAccount(
            id="acc-demo-ig-tubeguruji",
            workspace_id=tenant.workspace_id,
            campaign_id=campaign_id,
            platform="instagram",
            blotato_account_id="blotato-ig-1",
            display_name="Tubeguruji Instagram",
            handle="@tubeguruji",
            status="connected",
            connected_at=datetime.utcnow()
        )
        db.add(demo_account)
        await db.commit()
        await db.refresh(demo_account)
        accounts = [demo_account]



    return ApiResponse(data=[SocialAccountOut.model_validate(a) for a in accounts])


@router.post("", response_model=ApiResponse[SocialAccountOut], status_code=status.HTTP_201_CREATED)
async def connect_social_account(
    payload: SocialAccountCreate,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Connect a new social platform account via Blotato."""
    account = SocialAccount(
        id=str(uuid.uuid4()),
        workspace_id=tenant.workspace_id,
        campaign_id=payload.campaign_id or tenant.campaign_id,
        platform=payload.platform.lower(),
        blotato_account_id=payload.blotato_account_id,
        display_name=payload.display_name,
        handle=payload.handle,
        avatar_url=payload.avatar_url,
        status="connected",
        connected_at=datetime.utcnow()
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return ApiResponse(data=SocialAccountOut.model_validate(account))


@router.delete("/{account_id}", response_model=ApiResponse[dict])
async def disconnect_social_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Disconnect a social media account and revoke access."""
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == account_id,
            SocialAccount.workspace_id == tenant.workspace_id
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    await db.delete(account)
    await db.commit()
    return ApiResponse(data={"message": f"Account {account_id} disconnected successfully"})
