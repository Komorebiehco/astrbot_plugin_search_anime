import base64
from pathlib import Path

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Image, Node, Nodes, Reply
from astrbot.core.star.star_tools import StarTools


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
            return clean_url, None
        clean_path = clean_url[7:] if clean_url.startswith("file://") else clean_url
        if Path(clean_path).is_file():
            return clean_url, None
        if clean_url.isdigit():
            return clean_url, None

    # 2. Extract from message_str text (e.g. /搜番 https://example.com/a.jpg)
    raw_str = getattr(event, "message_str", "") or ""
    words = raw_str.strip().split()
    for w in words:
        w_clean = w.strip()
        if w_clean.startswith(("http://", "https://", "file://", "base64://")):
            return w_clean, None

    # 3. Extract from the current message, including nested forwards/replies.
    messages = list(event.get_messages() or [])
    message_obj = getattr(event, "message_obj", None)
    if message_obj and hasattr(message_obj, "message"):
        messages.extend(message_obj.message or [])

    while messages:
        comp = messages.pop(0)
        if isinstance(comp, Image):
            img_target = (
                getattr(comp, "url", None)
                or getattr(comp, "file", None)
                or getattr(comp, "path", None)
            )
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

    clean_path = image_url[7:] if image_url.startswith("file://") else image_url

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
