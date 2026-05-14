---
name: 1688-ozon
description: 1688 选品助手 — 搜索/详情/以图搜图/自动选品推荐，专为 Ozon/WB 跨境界定
compatibility: opencode
---

# 1688 选品助手 MCP Tool

基于逆向工程的 1688.com MTOP API 封装，提供选品所需的搜索、详情查询、以图搜图和智能推荐能力。

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/<你的用户名>/ai-reverse.git ~/ai-reverse
cd ~/ai-reverse/1688
pip install -r requirements.txt
```

### 2. 获取 Cookie

浏览器打开 1688.com，F12 → Network → 任意请求 → Request Headers → 复制 `cookie` 完整值。

### 3. 配置 MCP 工具

编辑 `~/.config/opencode/toolbox.jsonc`，添加：

```json
"aliexpress1688": {
  "type": "local",
  "command": ["python3", "/Users/<你的用户名>/ai-reverse/1688/aliexpress_mcp.py"],
  "description": "1688 选品助手 (搜索/详情/以图搜图/Ozon推荐)",
  "environment": {
    "ALI1688_COOKIE": "_m_h5_tk=xxx...; tfstk=xxx...; ..."
  }
}
```

### 4. 使用

在 OpenCode 中直接让 AI 调用：

```
帮我搜"夏季手持风扇"
推荐适合Ozon的10款家居商品（<500g）
用这张图片搜相似款: https://xxx.jpg
```

## 可用工具

| 工具 | 说明 |
|---|---|
| `search_products` | 关键词搜索商品 (返回 offerId/标题/价格) |
| `get_product_detail` | 获取商品详情 (标题/重量/SKU/图片) |
| `search_by_image` | 以图搜图 (支持 URL 或本地文件) |
| `recommend_for_ozon` | 智能选品 (自动搜索+过滤重量+排序) |
| `get_search_config` | 获取搜索筛选项 |

## 环境变量

- `ALI1688_COOKIE`: 1688.com 的 cookie 字符串（必填，否则会尝试自动获取但可能失败）
