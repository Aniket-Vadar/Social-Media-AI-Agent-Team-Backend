from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, Request, Header, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.models import Post, PostTarget, AuditLog
from app.schemas.common import ApiResponse
from app.tools.blotato import blotato_client
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/blotato")
async def handle_blotato_webhook(
    request: Request,
    x_blotato_signature: str = Header(None, alias="X-Blotato-Signature"),
    db: AsyncSession = Depends(get_db)
):
    """
    Handles Blotato asynchronous publishing and analytics webhooks:
    - Reconciles post publish status to 'published' or 'failed'
    - Updates post target with final Instagram URL
    - Records immutable audit log entry
    """
    body = await request.body()

    if not blotato_client.verify_webhook_signature(body, x_blotato_signature or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Blotato webhook signature"
        )

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = data.get("type", "post.status_update")
    payload = data.get("data", {})
    blotato_post_id = payload.get("blotato_post_id")
    new_status = payload.get("status", "published")  # 'published', 'failed'
    published_url = payload.get("published_url")

    logger.info(f"Received Blotato webhook [{event_type}] for post {blotato_post_id}: {new_status}")

    # Reconcile post target in DB
    if blotato_post_id:
        target_res = await db.execute(
            select(PostTarget).where(PostTarget.blotato_post_id == blotato_post_id)
        )
        target = target_res.scalar_one_or_none()
        if target:
            target.status = new_status
            target.published_url = published_url
            # Also update parent post
            post_res = await db.execute(select(Post).where(Post.id == target.post_id))
            post = post_res.scalar_one_or_none()
            if post:
                post.status = new_status
                if new_status == "published":
                    post.published_at = datetime.utcnow()

            # Record audit log
            audit = AuditLog(
                workspace_id=target.social_account.workspace_id if target.social_account else "default",
                actor_type="system",
                actor_id="blotato_webhook",
                action="post_published" if new_status == "published" else "post_publish_failed",
                entity="post",
                entity_id=target.post_id,
                diff=payload
            )
            db.add(audit)
            await db.commit()

    return {"status": "success", "event": event_type, "reconciled": True}
