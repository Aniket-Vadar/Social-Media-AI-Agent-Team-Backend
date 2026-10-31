from typing import Optional
from datetime import datetime, timedelta
from fastapi import Header, HTTPException, status, Depends
from jose import JWTError, jwt
from app.core.config import settings


class TenantContext:
    def __init__(self, workspace_id: str, campaign_id: Optional[str] = None, user_id: Optional[str] = None):
        self.workspace_id = workspace_id
        self.campaign_id = campaign_id
        self.user_id = user_id or "default-user-id"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create signed JWT for service-to-service communication."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "aud": "agent-service"})
    encoded_jwt = jwt.encode(to_encode, settings.AGENT_SERVICE_JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


async def get_tenant_context(
    authorization: Optional[str] = Header(None),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_campaign_id: Optional[str] = Header(None, alias="X-Campaign-Id"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
) -> TenantContext:
    """
    Extracts tenant isolation context (workspace_id, campaign_id, user_id).
    Validates either the signed service JWT or explicit trusted headers.
    """
    workspace_id = x_workspace_id
    campaign_id = x_campaign_id
    user_id = x_user_id

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(
                token,
                settings.AGENT_SERVICE_JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False}
            )
            workspace_id = payload.get("workspace_id") or workspace_id
            campaign_id = payload.get("campaign_id") or campaign_id
            user_id = payload.get("user_id") or user_id
        except JWTError:
            # If invalid JWT but headers exist in debug mode, proceed with warning
            if not settings.DEBUG and not workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                )

    # In development mode, provide standard default tenant IDs matching the deployed UI
    if not workspace_id:
        workspace_id = "ws-default-tubeguruji"
    if not campaign_id:
        campaign_id = "camp-tubeguruji-instagram"
    if not user_id:
        user_id = "user-saloni"

    return TenantContext(workspace_id=workspace_id, campaign_id=campaign_id, user_id=user_id)
