from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, computed_field


class PostBase(BaseModel):
    title: Optional[str] = None
    caption: str
    hashtags: List[str] = Field(default_factory=list)
    scheduled_at: Optional[datetime] = None


class PostCreate(PostBase):
    campaign_id: Optional[str] = None
    platforms: List[str] = Field(default_factory=lambda: ["instagram"])
    media_url: Optional[str] = None
    status: Optional[str] = "draft"


class PostUpdate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    status: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class PostApprove(BaseModel):
    edited_caption: Optional[str] = None
    edited_hashtags: Optional[List[str]] = None
    schedule_now: Optional[bool] = False
    custom_scheduled_at: Optional[datetime] = None


class PostReject(BaseModel):
    feedback: str = Field(..., description="Reason for rejection to guide AI agent revision")


class PostReschedule(BaseModel):
    scheduled_at: datetime


class MediaAssetOut(BaseModel):
    id: str
    url: str
    aspect_ratio: Optional[str] = None
    alt_text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostTargetOut(BaseModel):
    id: str
    platform: str
    status: str
    published_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostOut(PostBase):
    id: str
    workspace_id: str
    campaign_id: str
    status: str
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_by: str
    agent_run_id: Optional[str] = None
    rejection_feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    media_assets: List[MediaAssetOut] = Field(default_factory=list)
    targets: List[PostTargetOut] = Field(default_factory=list)

    @computed_field
    @property
    def media_url(self) -> Optional[str]:
        if self.media_assets and len(self.media_assets) > 0:
            return self.media_assets[0].url
        return None

    model_config = ConfigDict(from_attributes=True)
