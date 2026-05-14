---
name: 1688-ozon
description: 1688 选品助手 — 搜索/详情/以图搜图/Ozon推荐
compatibility: opencode
---

# 1688 选品助手 MCP Tool

一行命令配置，无需 cd、无需克隆代码。

## 安装

### 1. 加到 toolbox.jsonc

编辑 `~/.config/opencode/toolbox.jsonc`：

```json
"ali1688": {
  "type": "local",
  "command": ["uvx", "--from", "git+https://github.com/QuoVadis86/ai-reverse", "ali1688-mcp"],
  "description": "1688 选品助手 (搜索/以图搜图/Ozon推荐)",
  "environment": {
    "ALI1688_COOKIE": "从浏览器 F12 复制的 cookie"
  }
}
```

### 2. 首次获取 Cookie

浏览器打开 1688.com → F12 → Network → 任意请求头 → 复制 cookie 完整值。

填入上面 `ALI1688_COOKIE` 环境变量。Cookie 会自动缓存，此后不需要再填。

## 使用

在 OpenCode 中直接让 AI 调用：

```
帮我搜"夏季手持风扇"
推荐适合 Ozon 的 10 款家居商品（<500g）
用这张图搜相似款: https://xxx.jpg
```

## 可用工具

| 工具 | 说明 |
|---|---|
| `search_products` | 关键词搜索商品 |
| `get_product_detail` | 获取商品详情 (重量/SKU/图片) |
| `search_by_image` | 以图搜图 |
| `recommend_for_ozon` | 智能选品 (自动过滤重量) |
| `get_search_config` | 搜索筛选项 |