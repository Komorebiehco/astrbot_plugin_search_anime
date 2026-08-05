# astrbot_plugin_search_anime

基于 [trace.moe](https://trace.moe) 与 [SauceNAO](https://saucenao.com) 的 AstrBot 以图搜番与搜插画/搜图插件。支持标准 LLM 工具 (Function Calling) 自动调用及指令手动触发。

## 功能特性

- **以图搜图 LLM 工具 (`search_image`)**:
  - 统一大模型工具调用，避免冗余提示词注入。
  - 参数 `type`: `'anime'`（动画截图搜番剧及时间轴）或 `'illust'`（插画/画师出处搜索）。
  - 参数 `url`: 支持图片网络地址 (http/https)、本地文件路径或图片哈希值 (`media_id`)。
  - **Giftia 兼容模式开关 (`enable_giftia_mode`)**: 开启后将 `url` 描述自动简化为最极致干净的 `"Image hash."`；关闭时保留标准路径描述。
- **斜杠指令**:
  - 以图搜番: `/搜番` / `/sa` / `/search_anime`
  - 以图搜插画/搜图: `/搜插画` / `/搜图` / `/si` / `/search_illust`
- **灵活的输出模式**:
  - **直接发送卡片模式（默认）**: 大模型触发工具时，直接在会话窗口中发送合并转发富文本卡片，并返回完成提示结束工具循环。
  - **LLM 独占模式 (`enable_llm_only_mode`)**: 大模型触发工具时不直接发送卡片，仅将包含画面信息/画师出处的详细文本返回给大模型，由大模型自行思考并组织回复。

## 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `enable_llm_tool` | bool | `true` | 是否在 LLM 工具列表中暴露 `search_image`。关闭后大模型将无法发现或调用此工具。 |
| `enable_giftia_mode` | bool | `false` | Giftia 兼容模式开关。开启后 `url` 描述简化为 `"Image hash."`；关闭时（默认）描述为 `"Target image HTTP/HTTPS URL or local file path."`。 |
| `enable_llm_only_mode` | bool | `false` | 仅返回文本给大模型。`false` 时直接发送富文本卡片；`true` 时仅返回文本摘要给大模型思考回复。 |
| `default_limit` | int | `3` | 搜索结果最大返回条数（范围：`1` ~ `10`）。控制指令与工具调用的默认候选返回数量。 |
| `saucenao_api_key` | string | `""` | 可选。SauceNAO 官方 API Key。留空则自动降级使用网页 HTML 解析。 |

## 使用方法

### 1. 大模型对话模式 (LLM Tool)
直接在对话中发送图片/截图/地址并向机器人提问，大模型会自动触发 `search_image` 工具：
- *"帮我看看这个截图 https://example.com/demo.jpg 出自哪部动漫"* (`search_image(type="anime", url="...")`)
- *"帮我查查这个画师作品出处 https://example.com/art.jpg"* (`search_image(type="illust", url="...")`)

### 2. 指令模式
- **搜番**: `/搜番` 或 `/sa` 或 `/search_anime` (附带图片/URL/路径或引用带图消息)
- **搜插画/搜图**: `/搜插画` 或 `/搜图` 或 `/si` 或 `/search_illust` (附带图片/URL/路径或引用带图消息)
