import base64
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Image, Node, Nodes, Reply
from astrbot.core.star.star_tools import StarTools
from astrbot.core.utils.media_utils import file_uri_to_path


_IMAGE_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
}


def _looks_like_media_id(value: str) -> bool:
    """Return whether a value can safely be used as a cached media id."""
    return bool(
        value
        and not any(char.isspace() for char in value)
        and not any(separator in value for separator in ("/", "\\", ":"))
        and Path(value).suffix.lower() not in _IMAGE_SUFFIXES
    )


def _image_target(component: Image) -> str | None:
    """Return the most reliable target exposed by an Image component.

    Args:
        component: Image message component.

    Returns:
        A local file target or remote URL, if present.
    """
    # Adapters commonly populate all three fields. Prefer a real local file
    # over a stale/placeholder URL so trace.moe can use upload mode.
    candidates = (
        getattr(component, "path", None),
        getattr(component, "file", None),
        getattr(component, "url", None),
        getattr(component, "media_id", None),
        getattr(component, "hash", None),
    )
    fallback: str | None = None
    for candidate in candidates:
        if candidate is None:
            continue
        value = str(candidate).strip()
        if not value or value.lower() in {"none", "null"}:
            continue
        if value.startswith("file:"):
            local_path = file_uri_to_path(value)
            if Path(local_path).is_file():
                return local_path
            continue
        if Path(value).is_file():
            return value
        if value.startswith(("http://", "https://", "base64://")):
            if not _is_placeholder_url(value):
                return value
            continue
        if _looks_like_media_id(value) and fallback is None:
            fallback = value
    return fallback


def _is_placeholder_url(value: str) -> bool:
    """Return whether a URL is a documentation placeholder, not an image."""
    try:
        hostname = (urlsplit(value).hostname or "").lower()
    except ValueError:
        return False
    return hostname in {"example.com", "www.example.com", "example.org", "example.net"}


async def extract_image_info(
    event: AstrMessageEvent, url_param: str = ""
) -> tuple[str | None, bytes | None]:
    """Extract image URL or raw image bytes from direct parameter or message event.

    Args:
        event: AstrMessageEvent object.
        url_param: Direct image URL, file path, or media_id passed in arguments.

    Returns:
        Tuple of (image_url, image_bytes).
    """
    # 1. Direct URL, existing local path, or media_id parameter.
    #
    # A tool call can contain a stale local path after the platform has
    # already cleaned its temporary attachment.  In that case keep looking
    # for the live Image component on the event instead of returning a path
    # that will force trace.moe's URL mode and fail with HTTP 400.
    if (
        url_param
        and url_param.strip()
        and url_param.strip().lower() not in ("none", "null")
    ):
        clean_url = url_param.strip()
        if clean_url.startswith(("http://", "https://", "base64://")):
            if _is_placeholder_url(clean_url):
                clean_url = ""
            else:
                return clean_url, None
        if clean_url.startswith("file:"):
            clean_path = file_uri_to_path(clean_url)
        else:
            clean_path = clean_url
        if clean_path and Path(clean_path).is_file():
            return clean_path, None
        if _looks_like_media_id(clean_url):
            return clean_url, None

    # 2. Extract from message_str text (e.g. /搜番 https://example.com/a.jpg)
    raw_str = getattr(event, "message_str", "") or ""
    words = raw_str.strip().split()
    for w in words:
        w_clean = w.strip()
        if w_clean.startswith(("http://", "https://", "file://", "base64://")):
            if _is_placeholder_url(w_clean):
                continue
            return w_clean, None

    # 3. Extract from the current message, including nested forwards/replies.
    messages = list(event.get_messages() or [])
    message_obj = getattr(event, "message_obj", None)
    if not messages and message_obj and hasattr(message_obj, "message"):
        messages.extend(message_obj.message or [])

    while messages:
        comp = messages.pop(0)
        if isinstance(comp, Image):
            img_target = _image_target(comp)
            if img_target:
                return img_target, None
        elif isinstance(comp, Reply):
            reply_chain = getattr(comp, "chain", None) or getattr(comp, "message", None)
            if reply_chain:
                messages.extend(reply_chain)
        elif isinstance(comp, Nodes):
            messages.extend(comp.nodes)
        elif isinstance(comp, Node):
            messages.extend(comp.content)

    return None, None


async def resolve_image_bytes(
    session: aiohttp.ClientSession,
    image_url: str | None,
    image_bytes: bytes | None,
) -> bytes | None:
    """Resolve raw image bytes from local file path, giftia media_cache, or HTTP URL if image_bytes is missing.

    Args:
        session: Active aiohttp ClientSession.
        image_url: URL, local path, or media_id hash of the image.
        image_bytes: Existing image bytes.

    Returns:
        Resolved image bytes or None.
    """
    if image_bytes:
        return image_bytes

    if not image_url:
        return None

    # Base64 decode check
    if image_url.startswith("base64://"):
        try:
            b64_str = image_url[9:]
            return base64.b64decode(b64_str)
        except Exception as e:
            logger.error(f"[search_anime] Failed to decode base64 image_url: {e}")
            return None

    clean_path = file_uri_to_path(image_url)

    # 1. Direct file path check
    local_p = Path(clean_path)
    if local_p.exists() and local_p.is_file():
        try:
            return local_p.read_bytes()
        except Exception as e:
            logger.error(
                f"[search_anime] Failed to read local image file {clean_path}: {e}"
            )
            return None

    # 2. Check Giftia / Plugin media_cache by media_id (hash)
    try:
        giftia_cache_file = (
            StarTools.get_data_dir("astrbot_plugin_giftia") / "media_cache" / clean_path
        )
        if giftia_cache_file.exists() and giftia_cache_file.is_file():
            return giftia_cache_file.read_bytes()

        self_cache_file = (
            StarTools.get_data_dir("astrbot_plugin_search_anime")
            / "media_cache"
            / clean_path
        )
        if self_cache_file.exists() and self_cache_file.is_file():
            return self_cache_file.read_bytes()
    except Exception as e:
        logger.warning(
            f"[search_anime] Failed to read media_cache for {clean_path}: {e}"
        )

    # 3. HTTP / HTTPS download
    if image_url.startswith(("http://", "https://")):
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
            async with session.get(
                image_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logger.warning(
                        f"[search_anime] Image download HTTP {resp.status} for URL {image_url}"
                    )
        except Exception as e:
            logger.warning(
                f"[search_anime] Failed to download image from URL {image_url}: {e}"
            )

    return None
