import urllib.parse

import aiohttp
from bs4 import BeautifulSoup

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Image, Node, Nodes, Plain

from ..utils.image_extractor import resolve_image_bytes


def parse_saucenao_html(
    html_text: str, limit: int, bot_id: str, bot_name: str
) -> tuple[bool, MessageChain, str]:
    """Parse SauceNAO HTML web response into message nodes and summary text.

    Args:
        html_text: Raw HTML string returned by SauceNAO.
        limit: Max results.
        bot_id: Uploader ID.
        bot_name: Uploader name.

    Returns:
        Tuple of (is_success, MessageChain, summary_string).
    """
    soup = BeautifulSoup(html_text, "html.parser")
    results = []

    for res in soup.find_all("div", class_="result"):
        if res.get("id") == "result-hidden-notification":
            continue
        sim_elem = res.find("div", class_="resultsimilarityinfo")
        if not sim_elem:
            continue
        sim_str = sim_elem.get_text(strip=True)

        img_url = ""
        img_elem = res.find("div", class_="resultimage")
        if img_elem:
            img_tag = img_elem.find("img")
            if img_tag:
                raw_url = (
                    img_tag.get("src")
                    or img_tag.get("data-src")
                    or img_tag.get("data-src2")
                    or ""
                )
                if raw_url:
                    img_url = urllib.parse.urljoin("https://saucenao.com/", raw_url)

        title_elem = res.find("div", class_="resulttitle")
        title = title_elem.get_text(strip=True) if title_elem else "未知作品"

        content_cols = res.find_all("div", class_="resultcontentcolumn")
        details = []
        source_links = []
        for col in content_cols:
            text = col.get_text(" ", strip=True)
            if text:
                details.append(text)
            for a in col.find_all("a"):
                href = a.get("href", "")
                if (
                    href
                    and href.startswith("http")
                    and "saucenao.com/info.php" not in href
                ):
                    label = a.get_text(strip=True)
                    source_links.append(f"{label}: {href}")

        results.append(
            {
                "similarity": sim_str,
                "title": title,
                "img_url": img_url,
                "details": details,
                "links": source_links,
            }
        )

    if not results:
        return (
            False,
            MessageChain([Plain("🧐 没有识别到相关插画来源信息的喵")]),
            "No illustration search results found.",
        )

    target_results = results[:limit]
    nodes = []
    uploader_uin = bot_id or "10000"
    uploader_name = bot_name or "AstrBot"

    header_node = Node(
        uin=uploader_uin,
        name=uploader_name,
        content=[
            Plain(f"🎨 SauceNAO 插画来源结果\n共匹配到 {len(target_results)} 个出处：")
        ],
    )
    nodes.append(header_node)

    summary_items = []

    for idx, item in enumerate(target_results, 1):
        lines = [f"【结果 #{idx}】"]
        if item["title"]:
            lines.append(f"作品: {item['title']}")
        lines.append(f"相似度: {item['similarity']}")

        if item["details"]:
            lines.append("信息: " + " | ".join(item["details"]))

        if item["links"]:
            lines.append("链接: " + " ; ".join(item["links"][:3]))

        node_content = [Plain("\n".join(lines))]
        if item["img_url"] and item["img_url"].startswith(("http://", "https://")):
            node_content.append(Image.fromURL(item["img_url"]))

        nodes.append(
            Node(
                uin=uploader_uin,
                name=f"插画来源 #{idx} | {item['similarity']}",
                content=node_content,
            )
        )

        summary_items.append(
            f"#{idx} 作品: {item['title']}, 相似度: {item['similarity']}, 信息: {' '.join(item['details'])}"
        )

    summary_str = "SauceNAO 搜插画成功：\n" + "\n".join(summary_items)
    return True, MessageChain([Nodes(nodes)]), summary_str


def parse_saucenao_json(
    data: dict, limit: int, bot_id: str, bot_name: str
) -> tuple[bool, MessageChain, str]:
    """Parse SauceNAO JSON API response into message nodes and summary text.

    Args:
        data: Dict returned by SauceNAO JSON endpoint.
        limit: Max results.
        bot_id: Uploader ID.
        bot_name: Uploader name.

    Returns:
        Tuple of (is_success, MessageChain, summary_string).
    """
    results = data.get("results") or []
    if not results:
        return (
            False,
            MessageChain([Plain("🧐 没有识别到相关插画来源信息的喵")]),
            "No illustration search results found.",
        )

    target_results = results[:limit]
    nodes = []
    uploader_uin = bot_id or "10000"
    uploader_name = bot_name or "AstrBot"

    header_node = Node(
        uin=uploader_uin,
        name=uploader_name,
        content=[
            Plain(
                f"🎨 SauceNAO 插画来源结果 (API)\n"
                f"共匹配到 {len(target_results)} 个出处："
            )
        ],
    )
    nodes.append(header_node)

    summary_items = []

    for idx, item in enumerate(target_results, 1):
        header = item.get("header") or {}
        item_data = item.get("data") or {}

        similarity = header.get("similarity", "0")
        thumbnail = header.get("thumbnail", "")

        title = (
            item_data.get("title")
            or item_data.get("source")
            or item_data.get("material")
            or "未知作品"
        )
        author = (
            item_data.get("author_name")
            or item_data.get("member_name")
            or item_data.get("creator")
            or ""
        )
        pixiv_id = item_data.get("pixiv_id") or ""
        ext_urls = item_data.get("ext_urls") or []

        lines = [f"【结果 #{idx}】", f"作品/来源: {title}", f"相似度: {similarity}%"]
        if author:
            lines.append(f"作者/画师: {author}")
        if pixiv_id:
            lines.append(f"Pixiv ID: {pixiv_id}")
        if ext_urls:
            lines.append("链接: " + " ; ".join(ext_urls[:3]))

        node_content = [Plain("\n".join(lines))]
        if thumbnail:
            node_content.append(Image.fromURL(thumbnail))

        nodes.append(
            Node(
                uin=uploader_uin,
                name=f"插画来源 #{idx} | {similarity}%",
                content=node_content,
            )
        )

        summary_items.append(
            f"#{idx} 作品: {title}, 作者: {author}, 相似度: {similarity}%"
        )

    summary_str = "SauceNAO 搜插画成功：\n" + "\n".join(summary_items)
    return True, MessageChain([Nodes(nodes)]), summary_str


async def search_illust_saucenao(
    image_url: str | None = None,
    image_bytes: bytes | None = None,
    limit: int = 3,
    api_key: str = "",
    bot_id: str = "",
    bot_name: str = "AstrBot",
) -> tuple[bool, MessageChain, str]:
    """Query SauceNAO API/Web to search illustration source from an image.

    Args:
        image_url: Image URL or file path.
        image_bytes: Raw image bytes.
        limit: Maximum results count.
        api_key: Optional SauceNAO API key.
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
        async with aiohttp.ClientSession(headers=headers) as session:
            image_bytes = await resolve_image_bytes(session, image_url, image_bytes)

            form = aiohttp.FormData()
            if image_bytes:
                form.add_field(
                    "file",
                    image_bytes,
                    filename="search.jpg",
                    content_type="image/jpeg",
                )
            elif image_url and image_url.startswith(("http://", "https://")):
                form.add_field("url", image_url)
            else:
                return (
                    False,
                    MessageChain([Plain("未提供或未成功获取到有效的插画图片数据喵。")]),
                    "No image provided or retrieved.",
                )

            form.add_field("db", "999")
            max_count = max(1, min(int(limit or 3), 10))
            form.add_field("numres", str(max_count))
            if api_key:
                form.add_field("output_type", "2")
                form.add_field("api_key", api_key)

            async with session.post(
                "https://saucenao.com/search.php",
                data=form,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return (
                        False,
                        MessageChain(
                            [Plain(f"SauceNAO 请求失败 (HTTP {resp.status})")]
                        ),
                        f"SauceNAO API error (HTTP {resp.status})",
                    )

                if api_key:
                    res_json = await resp.json()
                    return parse_saucenao_json(res_json, max_count, bot_id, bot_name)
                else:
                    html_text = await resp.text()
                    return parse_saucenao_html(html_text, max_count, bot_id, bot_name)

    except Exception as e:
        logger.error(
            f"[search_anime] Exception during illustration search: {e}",
            exc_info=True,
        )
        return (
            False,
            MessageChain([Plain(f"SauceNAO 搜图发生错误: {e}")]),
            f"Error performing illustration search: {e}",
        )
