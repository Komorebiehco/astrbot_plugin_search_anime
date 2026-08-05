import aiohttp

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Image, Node, Nodes, Plain

from ..utils.image_extractor import resolve_image_bytes


def _time_convert(t: float | int) -> str:
    """Convert seconds into a minutes and seconds string representation.

    Args:
        t: Time in seconds.

    Returns:
        Formatted string (e.g. '1分30秒').
    """
    m, s = divmod(t, 60)
    return f"{int(m)}分{int(s)}秒"


async def search_anime_trace_moe(
    image_url: str | None = None,
    image_bytes: bytes | None = None,
    limit: int = 3,
    bot_id: str = "",
    bot_name: str = "AstrBot",
) -> tuple[bool, MessageChain, str]:
    """Query trace.moe API to search anime scene info from an image.

    Args:
        image_url: Image URL or file path.
        image_bytes: Raw image bytes.
        limit: Maximum results count.
        bot_id: Sender ID for forward nodes.
        bot_name: Sender name for forward nodes.

    Returns:
        Tuple of (is_success, MessageChain, summary_string).
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        data = None
        async with aiohttp.ClientSession(headers=headers) as session:
            image_bytes = await resolve_image_bytes(session, image_url, image_bytes)

            api_url = "https://api.trace.moe/search"
            params = {"anilistInfo": "", "cutBorders": ""}

            if image_bytes:
                post_headers = {"Content-Type": "image/jpeg", **headers}
                async with session.post(
                    api_url,
                    params=params,
                    data=image_bytes,
                    headers=post_headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        err_detail = (
                            err_text[:100] if err_text else f"HTTP {resp.status}"
                        )
                        return (
                            False,
                            MessageChain(
                                [
                                    Plain(
                                        f"搜番请求失败 (HTTP {resp.status}): {err_detail}"
                                    )
                                ]
                            ),
                            f"trace.moe API error (HTTP {resp.status}): {err_detail}",
                        )
                    data = await resp.json()
            elif image_url:
                params["url"] = image_url
                async with session.get(
                    api_url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        err_detail = (
                            err_text[:100] if err_text else f"HTTP {resp.status}"
                        )
                        return (
                            False,
                            MessageChain(
                                [
                                    Plain(
                                        f"搜番请求失败 (HTTP {resp.status}): {err_detail}"
                                    )
                                ]
                            ),
                            f"trace.moe API error (HTTP {resp.status}): {err_detail}",
                        )
                    data = await resp.json()
            else:
                return (
                    False,
                    MessageChain([Plain("未提供或未成功获取到有效的图片数据喵。")]),
                    "No image provided or retrieved.",
                )

        if data and data.get("result") and len(data["result"]) > 0:
            raw_results = data["result"]
            max_count = max(1, min(int(limit or 3), 10))
            target_results = raw_results[:max_count]

            nodes = []
            uploader_uin = bot_id or "10000"
            uploader_name = bot_name or "AstrBot"

            header_node = Node(
                uin=uploader_uin,
                name=uploader_name,
                content=[
                    Plain(
                        f"🔍 以图搜番结果 (trace.moe)\n"
                        f"共包含 {len(target_results)} 个候选结果："
                    )
                ],
            )
            nodes.append(header_node)

            summary_items = []

            for idx, top_result in enumerate(target_results, 1):
                from_str = _time_convert(top_result.get("from", 0))
                to_str = _time_convert(top_result.get("to", 0))
                similarity = float(top_result.get("similarity", 0))

                warn = ""
                if similarity < 0.8:
                    warn = "⚠️ 相似度较低，可能非相同画面/剧集\n"

                anilist = top_result.get("anilist") or {}
                title_dict = anilist.get("title") or {}
                title = (
                    title_dict.get("native")
                    or title_dict.get("chinese")
                    or title_dict.get("romaji")
                    or title_dict.get("english")
                    or "未知番剧"
                )
                episode = top_result.get("episode") or "未知"
                shot_image_url = top_result.get("image", "")

                sim_percent = f"{similarity * 100:.1f}%"

                node_text = (
                    f"【结果 #{idx}】\n"
                    f"{warn}"
                    f"番名: {title}\n"
                    f"相似度: {sim_percent}\n"
                    f"剧集: 第{episode}集\n"
                    f"时间: {from_str} - {to_str}\n"
                    f"精准截图:"
                )

                node_content = [Plain(node_text)]
                if shot_image_url:
                    node_content.append(Image.fromURL(shot_image_url))

                nodes.append(
                    Node(
                        uin=uploader_uin,
                        name=f"结果 #{idx} | {title[:20]}",
                        content=node_content,
                    )
                )

                summary_items.append(
                    f"#{idx} 番名: {title}, 剧集: 第{episode}集, 相似度: {sim_percent}, 时间点: {from_str}-{to_str}"
                )

            summary_str = "以图搜番识别成功：\n" + "\n".join(summary_items)
            return True, MessageChain([Nodes(nodes)]), summary_str
        else:
            return (
                False,
                MessageChain([Plain("🧐 没有识别到相关番剧信息的喵")]),
                "No matching anime found for the image.",
            )
    except Exception as e:
        logger.error(
            f"[search_anime] Exception during anime search: {e}", exc_info=True
        )
        return (
            False,
            MessageChain([Plain(f"搜番时发生错误: {e}")]),
            f"Error performing anime search: {e}",
        )
