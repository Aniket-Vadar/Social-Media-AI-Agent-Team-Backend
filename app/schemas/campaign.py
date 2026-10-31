from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class BrandVoiceSchema(BaseModel):
    tone: str = "professional, engaging"
    banned_words: List[str] = Field(default_factory=list)
    guidelines: str = ""


class CampaignBase(BaseModel):
    name: str
    goal: Optional[str] = None
    brand_voice: BrandVoiceSchema = Field(default_factory=BrandVoiceSchema)
    audience: Optional[str] = None
    timezone: str = "UTC"
    approval_mode: str = "manual"  # 'manual' | 'auto'


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    brand_voice: Optional[BrandVoiceSchema] = None
    audience: Optional[str] = None
    timezone: Optional[str] = None
    approval_mode: Optional[str] = None
    status: Optional[str] = None


class CampaignOut(CampaignBase):
    id: str
    workspace_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
