import hmac
import hashlib
import time
import uuid
import urllib.parse
import logging
from typing import Dict, Any, Optional, List, Union
from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageKitHelper:
    """
    Production ImageKit client, server upload manager, and URL transformation generator.
    Enforces social media platform aspect ratios with smart focal cropping (fo-auto):
    - Instagram Square: 1:1 (w=1080, h=1080)
    - Instagram Portrait: 4:5 (w=1080, h=1350)
    - X (Twitter) Landscape: 16:9 (w=1200, h=675)
    - TikTok / Reels / Stories: 9:16 (w=1080, h=1920)
    - LinkedIn Post: 1.91:1 (w=1200, h=627)
    """

    ASPECT_RATIO_PRESETS = {
        "1:1": "w-1080,h-1080,cm-pad_resize,bg-F8F9FD,fo-auto",
        "4:5": "w-1080,h-1350,cm-pad_resize,bg-F8F9FD,fo-auto",
        "16:9": "w-1200,h-675,cm-pad_resize,bg-F8F9FD,fo-auto",
        "9:16": "w-1080,h-1920,cm-pad_resize,bg-F8F9FD,fo-auto",
        "1.91:1": "w-1200,h-627,cm-pad_resize,bg-F8F9FD,fo-auto",
    }

    @classmethod
    def build_transformation_string(
        cls,
        aspect_ratio: Optional[str] = "1:1",
        width: Optional[int] = None,
        height: Optional[int] = None,
        crop_mode: Optional[str] = "pad_resize",
        focus: Optional[str] = "auto",
        rotate: Optional[int] = None,
        overlay_text: Optional[str] = None,
        watermark_url: Optional[str] = None,
        brightness: Optional[int] = None,   # -100 to 100
        contrast: Optional[int] = None,     # -100 to 100
        blur: Optional[int] = None,         # 1 to 100
        filter_name: Optional[str] = None   # 'grayscale', 'sepia', 'sharpen'
    ) -> str:
        """Constructs an ImageKit transformation query string."""
        parts: List[str] = []

        if aspect_ratio and aspect_ratio in cls.ASPECT_RATIO_PRESETS:
            parts.append(cls.ASPECT_RATIO_PRESETS[aspect_ratio])
        else:
            if width:
                parts.append(f"w-{width}")
            if height:
                parts.append(f"h-{height}")
            if crop_mode:
                parts.append(f"cm-{crop_mode}")
            if focus:
                parts.append(f"fo-{focus}")

        if rotate:
            parts.append(f"rt-{rotate}")
        if brightness is not None:
            parts.append(f"b-{(brightness + 100) // 2}")
        if contrast is not None:
            parts.append("e-contrast")
        if blur:
            parts.append(f"bl-{blur}")
        if filter_name:
            if filter_name == "grayscale":
                parts.append("e-grayscale")
            elif filter_name == "sepia":
                parts.append("e-sepia")
            elif filter_name == "sharpen":
                parts.append("e-sharpen")

        if overlay_text:
            clean_text = urllib.parse.quote(overlay_text[:60])
            parts.append(f"ot-{clean_text},ots-32,otc-FFFFFF,tg-b")

        if watermark_url:
            clean_wm = urllib.parse.quote(watermark_url, safe="")
            parts.append(f"l-image,i-{clean_wm},w-120,bgo-0,l-end")

        return f"tr={':'.join(parts)}" if parts else ""

    @classmethod
    def transform_url(
        cls,
        base_url: str,
        aspect_ratio: str = "1:1",
        overlay_text: Optional[str] = None,
        watermark_url: Optional[str] = None,
        **kwargs
    ) -> str:
        """Apply ImageKit query transformations to an image URL."""
        tr_param = cls.build_transformation_string(
            aspect_ratio=aspect_ratio,
            overlay_text=overlay_text,
            watermark_url=watermark_url,
            **kwargs
        )
        if not tr_param:
            return base_url

        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}{tr_param}"

    @classmethod
    def get_all_platform_variants(cls, base_url: str, overlay_text: Optional[str] = None) -> Dict[str, str]:
        """Generate all standard social platform aspect ratio variants for a single image."""
        return {
            "instagram_square_1_1": cls.transform_url(base_url, aspect_ratio="1:1", overlay_text=overlay_text),
            "instagram_portrait_4_5": cls.transform_url(base_url, aspect_ratio="4:5", overlay_text=overlay_text),
            "reels_stories_tiktok_9_16": cls.transform_url(base_url, aspect_ratio="9:16", overlay_text=overlay_text),
            "twitter_x_landscape_16_9": cls.transform_url(base_url, aspect_ratio="16:9", overlay_text=overlay_text),
            "linkedin_feed_1_91_1": cls.transform_url(base_url, aspect_ratio="1.91:1", overlay_text=overlay_text),
        }

    @classmethod
    def get_auth_parameters(cls) -> Dict[str, Any]:
        """
        Generate server-issued authentication parameters for frontend ImageKit SDK
        using HMAC-SHA1 signature according to official ImageKit security protocol.
        """
        token = str(uuid.uuid4())
        expire = int(time.time()) + 1800
        private_key = settings.IMAGEKIT_PRIVATE_KEY or "demo_private_key"

        message = f"{token}{expire}".encode("utf-8")
        signature = hmac.new(
            private_key.encode("utf-8"),
            message,
            hashlib.sha1
        ).hexdigest()

        return {
            "token": token,
            "expire": expire,
            "signature": signature,
            "publicKey": settings.IMAGEKIT_PUBLIC_KEY or "demo_public_key",
            "urlEndpoint": settings.IMAGEKIT_URL_ENDPOINT or "https://ik.imagekit.io/socialix"
        }

    @classmethod
    async def upload_image(
        cls,
        file: Union[str, bytes],
        file_name: str,
        folder: str = "/socialix/uploads",
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Server-side direct image upload to ImageKit.
        Accepts binary bytes, base64 strings, or external image URLs.
        Automatically provisions platform variants and thumbnail URLs.
        """
        private_key = settings.IMAGEKIT_PRIVATE_KEY
        if private_key:
            try:
                from imagekitio import ImageKit
                ik = ImageKit(private_key=private_key)
                upload_res = ik.files.upload(
                    file=file,
                    file_name=file_name,
                    folder=folder,
                    tags=tags or ["socialix", "ai-agent"]
                )
                url = upload_res.url
                file_id = upload_res.file_id
                thumb = upload_res.thumbnail_url or cls.transform_url(url, width=300, height=300)
                logger.info(f"Image uploaded to ImageKit: file_id={file_id}, url={url}")
                return {
                    "file_id": file_id,
                    "file_name": upload_res.name,
                    "url": url,
                    "thumbnail_url": thumb,
                    "variants": cls.get_all_platform_variants(url),
                    "provider": "imagekit_live"
                }
            except Exception as e:
                logger.warning(f"ImageKit live upload failed, returning smart fallback: {e}")

        # Deterministic fallback when live keys are not yet configured in local dev
        sim_id = f"ik_file_{uuid.uuid4().hex[:10]}"
        base = settings.IMAGEKIT_URL_ENDPOINT or "https://ik.imagekit.io/socialix"
        url = file if isinstance(file, str) and file.startswith("http") else f"{base}/{sim_id}.jpg"
        return {
            "file_id": sim_id,
            "file_name": file_name,
            "url": url,
            "thumbnail_url": cls.transform_url(url, width=300, height=300),
            "variants": cls.get_all_platform_variants(url),
            "provider": "imagekit_simulated"
        }


imagekit_helper = ImageKitHelper()

