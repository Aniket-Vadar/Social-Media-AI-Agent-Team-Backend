import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class PostizClient:
    """
    Client for Postiz Social Media Gateway API.
    Interacts with self-hosted Postiz instances (e.g. deployed on Render / Docker).
    Handles Instagram, LinkedIn, X (Twitter), TikTok, Facebook, and YouTube.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.POSTIZ_API_KEY
        # Normalize base URL (strip trailing slashes)
        raw_url = base_url or settings.POSTIZ_BASE_URL or "https://my-postiz.onrender.com"
        self.base_url = raw_url.rstrip("/")
        # Headers for Postiz API authentication
        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "x-api-key": self.api_key or "",
            "Content-Type": "application/json"
        }

    @property
    def is_configured(self) -> bool:
        """Returns True if the user has provided a Postiz API key."""
        return bool(self.api_key and self.api_key.strip())

    async def list_connected_accounts(self) -> List[Dict[str, Any]]:
        """
        Lists all social channels connected to Postiz (Instagram, LinkedIn, X, TikTok, etc.).
        """
        if not self.is_configured:
            logger.info("PostizClient: No POSTIZ_API_KEY set. Returning standard mock connections.")
            return [
                {
                    "id": "postiz-ig-tubeguruji",
                    "platform": "instagram",
                    "display_name": "Tubeguruji Instagram",
                    "handle": "@tubeguruji",
                    "status": "connected",
                    "provider": "postiz",
                    "avatar_url": None
                },
                {
                    "id": "postiz-li-tubeguruji",
                    "platform": "linkedin",
                    "display_name": "Tubeguruji Agency",
                    "handle": "tubeguruji",
                    "status": "connected",
                    "provider": "postiz",
                    "avatar_url": None
                }
            ]

        url = f"{self.base_url}/public/v1/integrations"
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=self.headers, timeout=10.0)
                res.raise_for_status()
                data = res.json()
                accounts = []
                for item in (data if isinstance(data, list) else data.get("integrations", [])):
                    accounts.append({
                        "id": item.get("id"),
                        "platform": item.get("providerIdentifier", "instagram").lower(),
                        "display_name": item.get("name", item.get("identifier", "Connected Account")),
                        "handle": item.get("identifier", ""),
                        "avatar_url": item.get("picture"),
                        "status": "connected",
                        "provider": "postiz"
                    })
                return accounts
        except Exception as e:
            logger.error(f"Error fetching integrations from Postiz ({url}): {e}")
            raise

    async def schedule_post(
        self,
        integration_id: str,
        caption: str,
        media_urls: List[str],
        scheduled_at: datetime,
        idempotency_key: Optional[str] = None,
        platform: str = "instagram"
    ) -> Dict[str, Any]:
        """
        Schedules a post through Postiz to Instagram, LinkedIn, X, etc.
        """
        if not self.is_configured:
            logger.info(f"PostizClient (Mock Mode): Scheduled post for {scheduled_at} via Postiz.")
            return {
                "postiz_post_id": f"postiz_post_{int(datetime.utcnow().timestamp())}",
                "status": "scheduled",
                "scheduled_at": scheduled_at.isoformat(),
                "platform": platform,
                "provider": "postiz",
                "idempotency_key": idempotency_key
            }

        url = f"{self.base_url}/public/v1/posts"
        media_list = [{"url": m} for m in media_urls if m]

        payload = {
            "type": "schedule",
            "date": scheduled_at.isoformat(),
            "posts": [
                {
                    "integration": {
                        "id": integration_id
                    },
                    "value": [
                        {
                            "content": caption,
                            "media": media_list
                        }
                    ]
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=self.headers, timeout=15.0)
                res.raise_for_status()
                result = res.json()
                return {
                    "postiz_post_id": str(result.get("id", f"postiz_{int(datetime.utcnow().timestamp())}")),
                    "status": "scheduled",
                    "scheduled_at": scheduled_at.isoformat(),
                    "platform": platform,
                    "provider": "postiz",
                    "raw_response": result
                }
        except Exception as e:
            logger.error(f"Error scheduling post to Postiz ({url}): {e}")
            raise

    async def publish_now(
        self,
        integration_id: str,
        caption: str,
        media_urls: List[str],
        platform: str = "instagram"
    ) -> Dict[str, Any]:
        """
        Immediately dispatches a post through Postiz to the target channel.
        """
        if not self.is_configured:
            logger.info("PostizClient (Mock Mode): Immediate publish triggered.")
            return {
                "postiz_post_id": f"postiz_post_{int(datetime.utcnow().timestamp())}",
                "status": "publishing",
                "published_at": datetime.utcnow().isoformat(),
                "platform": platform,
                "provider": "postiz"
            }

        url = f"{self.base_url}/public/v1/posts"
        media_list = [{"url": m} for m in media_urls if m]

        payload = {
            "type": "now",
            "date": datetime.utcnow().isoformat(),
            "posts": [
                {
                    "integration": {
                        "id": integration_id
                    },
                    "value": [
                        {
                            "content": caption,
                            "media": media_list
                        }
                    ]
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=self.headers, timeout=15.0)
                res.raise_for_status()
                result = res.json()
                return {
                    "postiz_post_id": str(result.get("id", f"postiz_{int(datetime.utcnow().timestamp())}")),
                    "status": "publishing",
                    "platform": platform,
                    "provider": "postiz",
                    "raw_response": result
                }
        except Exception as e:
            logger.error(f"Error publishing immediately to Postiz ({url}): {e}")
            raise


postiz_client = PostizClient()
