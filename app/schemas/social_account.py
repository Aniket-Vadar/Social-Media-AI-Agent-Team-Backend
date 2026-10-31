from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SocialAccountBase(BaseModel):
    platform: str
    display_name: str
    handle: Optional[str] = None
    avatar_url: Optional[str] = None


class SocialAccountCreate(SocialAccountBase):
    blotato_account_id: str
    campaign_id: Optional[str] = None


class SocialAccountOut(SocialAccountBase):
    id: str
    workspace_id: str
    campaign_id: Optional[str] = None
    blotato_account_id: str
    status: str
    connected_at: datetime

    model_config = ConfigDict(from_attributes=True)
