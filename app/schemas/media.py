from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ImageKitAuthResponse(BaseModel):
    token: str
    expire: int
    signature: str
    publicKey: str
    urlEndpoint: str


class ImageTransformRequest(BaseModel):
    image_url: str = Field(..., description="Base ImageKit or external image URL")
    aspect_ratio: Optional[str] = Field("1:1", description="1:1, 4:5, 16:9, 9:16, 1.91:1")
    width: Optional[int] = None
    height: Optional[int] = None
    rotate: Optional[int] = None
    overlay_text: Optional[str] = None
    brightness: Optional[int] = None
    contrast: Optional[int] = None
    blur: Optional[int] = None
    filter_name: Optional[str] = None  # 'grayscale', 'sepia', 'sharpen'
    post_id: Optional[str] = None


class AiImageEditRequest(BaseModel):
    image_url: str = Field(..., description="Base image URL to edit")
    prompt: str = Field(..., description="Natural language edit request e.g. 'Crop for Instagram portrait and make brighter with title Launch Day'")
    post_id: Optional[str] = None


class MediaAssetResponse(BaseModel):
    id: str
    workspace_id: str
    post_id: Optional[str] = None
    url: str
    aspect_ratio: Optional[str] = None
    transformations: Dict[str, Any] = Field(default_factory=dict)
    alt_text: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
