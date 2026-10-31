import hmac
import hashlib
import time
import uuid
import urllib.parse
from typing import Dict, Any, Optional, List
from app.core.config import settings


class ImageKitHelper:
    """
    ImageKit client and URL transformation generator.
    Enforces platform aspect ratios and provides full editing capabilities:
    - Instagram: 1:1 (w=1080, h=1080) or 4:5 (w=1080, h=1350)
    - X (Twitter): 16:9 (w=1200, h=675)
    - LinkedIn: 1.91:1 (w=1200, h=627)
    - TikTok / Reels / Stories: 9:16 (w=1080, h=1920)
    """

    ASPECT_RATIO_PRESETS = {
        "1:1": "w-1080,h-1080,cm-pad_resize,bg-F8F9FD",
        "4:5": "w-1080,h-1350,cm-pad_resize,bg-F8F9FD",
        "16:9": "w-1200,h-675,cm-pad_resize,bg-F8F9FD",
        "9:16": "w-1080,h-1920,cm-pad_resize,bg-F8F9FD",
        "1.91:1": "w-1200,h-627,cm-pad_resize,bg-F8F9FD",
    }

    @classmethod
    def build_transformation_string(
        cls,
        aspect_ratio: Optional[str] = "1:1",
        width: Optional[int] = None,
        height: Optional[int] = None,
        crop_mode: Optional[str] = "pad_resize",
        rotate: Optional[int] = None,
        overlay_text: Optional[str] = None,
        brightness: Optional[int] = None,   # -100 to 100
        contrast: Optional[int] = None,       # -100 to 100
        blur: Optional[int] = None,           # 1 to 100
        filter_name: Optional[str] = None     # 'grayscale', 'sepia', 'sharpen'
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

        if rotate:
            parts.append(f"rt-{rotate}")
        if brightness is not None:
            parts.append(f"b-{(brightness + 100) // 2}")
        if contrast is not None:
            parts.append(f"e-contrast")
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

        return f"tr={':'.join(parts)}" if parts else ""

    @classmethod
    def transform_url(
        cls,
        base_url: str,
        aspect_ratio: str = "1:1",
        overlay_text: Optional[str] = None,
        **kwargs
    ) -> str:
        """Apply ImageKit query transformations to an image URL."""
        tr_param = cls.build_transformation_string(
            aspect_ratio=aspect_ratio,
            overlay_text=overlay_text,
            **kwargs
        )
        if not tr_param:
            return base_url

        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}{tr_param}"

    @classmethod
    def get_auth_parameters(cls) -> Dict[str, Any]:
        """
        Generate server-issued authentication parameters for frontend ImageKit SDK
        using HMAC-SHA1 signature according to official ImageKit security protocol.
        """
        token = str(uuid.uuid4())
        expire = int(time.time()) + 1800
        private_key = settings.IMAGEKIT_PRIVATE_KEY or "demo_private_key"

        # HMAC-SHA1 hash of token + expire timestamp using ImageKit private key
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


imagekit_helper = ImageKitHelper()
