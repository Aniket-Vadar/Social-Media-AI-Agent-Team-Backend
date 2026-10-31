from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.posts import router as posts_router
from app.api.v1.agents import router as agents_router
from app.api.v1.runs import router as runs_router
from app.api.v1.social_accounts import router as social_accounts_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.media import router as media_router
from app.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(campaigns_router)
api_router.include_router(posts_router)
api_router.include_router(agents_router)
api_router.include_router(runs_router)
api_router.include_router(social_accounts_router)
api_router.include_router(calendar_router)
api_router.include_router(analytics_router)
api_router.include_router(media_router)
api_router.include_router(webhooks_router)
