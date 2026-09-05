## [v1.0.2] - 2026-09-05

### Bug Fixes
- Direct rich-card results now terminate the local LLM tool loop after delivery, preventing repeated `search_image` calls and max-step stalls.

## [v1.0.1] - 2026-08-20

### Bug Fixes
- 统一大模型工具调用，避免冗余提示词注入
