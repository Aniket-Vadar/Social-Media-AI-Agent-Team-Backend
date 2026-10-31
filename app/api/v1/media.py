import uuid
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_tenant_context, TenantContext
from app.models.models import MediaAsset, Post
from app.schemas.media import (
    ImageKitAuthResponse, ImageTransformRequest,
    AiImageEditRequest, MediaAssetResponse
)
from app.schemas.common import ApiResponse
from app.tools.imagekit import imagekit_helper

router = APIRouter(prefix="/media", tags=["Media & Image Editing"])


@router.post("/imagekit-auth", response_model=ApiResponse[ImageKitAuthResponse])
async def get_imagekit_auth():
    """
    Generate client-side upload authentication parameters for frontend ImageKit SDK.
    Enables direct, secure browser uploads with short-lived HMAC-SHA1 signatures.
    """
    auth_params = imagekit_helper.get_auth_parameters()
    return ApiResponse(data=ImageKitAuthResponse(**auth_params))


@router.post("/transform", response_model=ApiResponse[MediaAssetResponse])
async def transform_image(
    payload: ImageTransformRequest,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """
    Apply real-time ImageKit transformations (aspect ratio crop, overlay text, filters, resize).
    Saves transformation record to database.
    """
    transformed_url = imagekit_helper.transform_url(
        base_url=payload.image_url,
        aspect_ratio=payload.aspect_ratio or "1:1",
        width=payload.width,
        height=payload.height,
        rotate=payload.rotate,
        overlay_text=payload.overlay_text,
        brightness=payload.brightness,
        contrast=payload.contrast,
        blur=payload.blur,
        filter_name=payload.filter_name
    )

    media = MediaAsset(
        id=str(uuid.uuid4()),
        workspace_id=tenant.workspace_id,
        post_id=payload.post_id,
        url=transformed_url,
        aspect_ratio=payload.aspect_ratio,
        transformations=payload.model_dump(exclude_unset=True)
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)

    return ApiResponse(data=MediaAssetResponse.model_validate(media))


@router.post("/ai-edit", response_model=ApiResponse[MediaAssetResponse])
async def ai_edit_image(
    payload: AiImageEditRequest,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """
    'Ask Creator Agent' image editing (UI.md §6.6):
    Parses natural language image editing prompt into optimal visual transformations.
    e.g., 'Crop for Instagram 4:5 and enhance brightness with title Summer Launch'
    """
    prompt_lower = payload.prompt.lower()

    # Smart parsing of editing instructions
    aspect_ratio = "1:1"
    if "4:5" in prompt_lower or "portrait" in prompt_lower or "instagram portrait" in prompt_lower:
        aspect_ratio = "4:5"
    elif "16:9" in prompt_lower or "landscape" in prompt_lower or "twitter" in prompt_lower:
        aspect_ratio = "16:9"
    elif "9:16" in prompt_lower or "reel" in prompt_lower or "story" in prompt_lower or "tiktok" in prompt_lower:
        aspect_ratio = "9:16"

    brightness = 20 if "bright" in prompt_lower or "light" in prompt_lower else None
    contrast = 15 if "contrast" in prompt_lower or "pop" in prompt_lower or "vibrant" in prompt_lower else None
    filter_name = "grayscale" if "black and white" in prompt_lower or "grayscale" in prompt_lower else None

    # Extract overlay text if requested
    overlay_text = None
    if "title" in prompt_lower or "overlay" in prompt_lower or "text" in prompt_lower:
        # Heuristic title extraction
        parts = payload.prompt.split("title")
        if len(parts) > 1:
            overlay_text = parts[1].strip(" :\"'")
        else:
            overlay_text = payload.prompt[:30]

    transformed_url = imagekit_helper.transform_url(
        base_url=payload.image_url,
        aspect_ratio=aspect_ratio,
        overlay_text=overlay_text,
        brightness=brightness,
        contrast=contrast,
        filter_name=filter_name
    )

    media = MediaAsset(
        id=str(uuid.uuid4()),
        workspace_id=tenant.workspace_id,
        post_id=payload.post_id,
        url=transformed_url,
        aspect_ratio=aspect_ratio,
        transformations={
            "ai_prompt": payload.prompt,
            "derived_aspect_ratio": aspect_ratio,
            "brightness": brightness,
            "contrast": contrast,
            "overlay_text": overlay_text
        }
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)

    return ApiResponse(data=MediaAssetResponse.model_validate(media))


@router.get("/{media_id}", response_model=ApiResponse[MediaAssetResponse])
async def get_media_asset(
    media_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Retrieve media asset details and active transformation JSON."""
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.workspace_id == tenant.workspace_id
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return ApiResponse(data=MediaAssetResponse.model_validate(media))
