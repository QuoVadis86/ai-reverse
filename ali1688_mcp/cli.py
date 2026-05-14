#!/usr/bin/env python3
"""
1688 MCP 选品助手 — 搜索/详情/以图搜图/Ozon推荐

一行命令启动（无需 cd、无需手动复制 cookie）：
  uvx --from git+https://github.com/QuoVadis86/ai-reverse ali1688-mcp

配置到 OpenCode toolbox.jsonc：
  "ali1688": {
    "type": "local",
    "command": ["uvx", "--from", "git+https://github.com/QuoVadis86/ai-reverse", "ali1688-mcp"],
    "description": "1688 选品助手 (搜索/以图搜图/Ozon推荐)"
  }
"""

import json
import os
import sys
import logging
import traceback

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger("ali1688-mcp")

# ── 路径处理：确保能找到 SDK ──
_HERE = os.path.dirname(os.path.abspath(__file__))
_SDK = os.path.join(_HERE, "sdk")
_PROJECT = os.path.dirname(_HERE)
if os.path.isdir(_SDK):
    sys.path.insert(0, _SDK)
else:
    _SDK = os.path.join(_PROJECT, "1688")
    if os.path.isdir(_SDK):
        sys.path.insert(0, _SDK)

# ── Cookie 持久化 ──
_CONFIG_DIR = os.path.expanduser("~/.config/ali1688-mcp")
_COOKIE_FILE = os.path.join(_CONFIG_DIR, "cookie.txt")


def load_cookie() -> str:
    if os.path.exists(_COOKIE_FILE):
        with open(_COOKIE_FILE) as f:
            return f.read().strip()
    return ""


def save_cookie(cookie: str):
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(_COOKIE_FILE, "w") as f:
        f.write(cookie)
    os.chmod(_COOKIE_FILE, 0o600)


# ── 延迟导入（让 MCP 协议先就绪，再加载 SDK） ──
_client = None


def get_client():
    global _client
    if _client is not None:
        return _client

    from core import MTOPSession
    from client import Alibaba1688Client

    s = MTOPSession()

    cookie = os.environ.get("ALI1688_COOKIE", "")
    if cookie:
        s.set_cookie(cookie)
        save_cookie(cookie)
    else:
        cached = load_cookie()
        if cached:
            s.set_cookie(cached)

    if not s.has_token:
        raise RuntimeError(
            "需要 1688 cookie 才能使用。\n"
            "  首次使用运行:\n"
            "    export ALI1688_COOKIE='这里粘贴cookie'\n"
            "    ali1688-mcp\n"
            "  Cookie 获取: 浏览器打开 1688.com → F12 → Network →\n"
            "    任意请求头 → 复制 cookie 完整值\n"
            "  Cookie 会自动缓存到 ~/.config/ali1688-mcp/cookie.txt\n"
            "  之后无需再设置环境变量"
        )

    _client = Alibaba1688Client(s)
    return _client


# ── MCP Tools ──

TOOLS = [
    {
        "name": "search_products",
        "description": "关键词搜索 1688 商品",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "string", "description": "搜索关键词"},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 20},
            },
            "required": ["keywords"],
        },
    },
    {
        "name": "get_product_detail",
        "description": "获取商品详情 (标题/重量/SKU/图片/链接)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "offer_id": {"type": "integer", "description": "商品 offerId"},
            },
            "required": ["offer_id"],
        },
    },
    {
        "name": "search_by_image",
        "description": "以图搜图：上传 URL 或本地图片搜相似商品",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_source": {"type": "string", "description": "图片 URL 或本地路径"},
                "page_size": {"type": "integer", "default": 20},
            },
            "required": ["image_source"],
        },
    },
    {
        "name": "recommend_for_ozon",
        "description": "智能选品：搜索适合 Ozon 的轻量家居商品 (自动过滤重量)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "default": "家居日用", "description": "品类"},
                "max_weight": {"type": "integer", "default": 500, "description": "最大重量(g)"},
                "count": {"type": "integer", "default": 10, "description": "返回数量"},
            },
        },
    },
    {
        "name": "get_search_config",
        "description": "获取搜索筛选项",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["keywords"],
        },
    },
]


def handle_search_products(args: dict) -> dict:
    c = get_client()
    resp = c.search_by_text(args["keywords"], args.get("page", 1), args.get("page_size", 20))
    if not resp.success:
        return {"error": resp.ret}
    items = resp.data.get("data", {}).get("OFFER", {}).get("items", [])
    results = []
    for item in items:
        expo = item.get("trackInfo", {}).get("expoArgs", {}).get("ext_expo_data", "")
        info = {}
        for part in expo.split("^"):
            if "@" in part:
                k, v = part.split("@", 1)
                info[k] = v
        if info.get("sub_object_type") == "normal":
            results.append({
                "offer_id": info.get("object_id"),
                "title": info.get("title", ""),
                "price": info.get("price"),
                "link": f"https://detail.1688.com/offer/{info.get('object_id')}.html",
            })
    return {"total": len(results), "products": results[:args.get("page_size", 20)]}


def handle_get_product_detail(args: dict) -> dict:
    c = get_client()
    detail = c.get_offer_detail(args["offer_id"])
    offer = detail["offerDetail"]
    dm = detail["dataModel"]
    ppi = dm.get("productPackInfo", {}).get("fields", {}).get("pieceWeightScale", {}).get("pieceWeightScaleInfo", [])
    weights = [p.get("weight", 0) for p in ppi if p.get("weight", 0) > 0]
    skus = dm.get("mainPrice", {}).get("fields", {}).get("finalPriceModel", {}).get("tradeWithoutPromotion", {}).get("skuMapOriginal", [])
    return {
        "offer_id": offer.get("offerId"),
        "title": offer.get("subject"),
        "status": offer.get("status"),
        "min_weight_g": min(weights) if weights else None,
        "skus": [{"spec": s["specAttrs"], "price": s["price"], "stock": s["canBookCount"]} for s in skus],
        "images": [i.get("fullPathImageURI", "") for i in offer.get("imageList", [])[:5]],
        "category": offer.get("leafCategoryName"),
        "link": f"https://detail.1688.com/offer/{offer.get('offerId')}.html",
    }


def handle_search_by_image(args: dict) -> dict:
    c = get_client()
    resp = c.search_by_image(args["image_source"], page_size=args.get("page_size", 20))
    if not resp.success:
        return {"error": resp.ret}
    offer = resp.data.get("data", {}).get("OFFER", {})
    items = offer.get("items", [])
    results = []
    for item in items[:args.get("page_size", 20)]:
        expo = item.get("trackInfo", {}).get("expoData", "")
        info = {}
        for part in expo.split("^"):
            if "@" in part:
                k, v = part.split("@", 1)
                info[k] = v
        sp = info.get("sp_expo_data", "")
        pic_url = ""
        if "pic_url:" in sp:
            pic_url = sp.split("pic_url:")[1].split(";")[0]
        results.append({"offer_id": info.get("object_id"), "price": info.get("price"), "pic_url": pic_url, "type": info.get("sub_object_type")})
    return {"found": offer.get("found", 0), "products": results}


def handle_recommend_for_ozon(args: dict) -> dict:
    c = get_client()
    category = args.get("category", "家居日用")
    max_weight = args.get("max_weight", 500)
    count = args.get("count", 10)
    queries = [f"{category} {kw}" for kw in ["收纳 轻量", "厨房 小工具", "夏季 便携", "桌面 置物", "挂钩"]]

    candidates = []
    seen = set()
    for q in queries:
        try:
            resp = c.search_by_text(q, page=1, page_size=15)
            if not resp.success:
                continue
            for item in resp.data.get("data", {}).get("OFFER", {}).get("items", []):
                ex = item.get("trackInfo", {}).get("expoArgs", {}).get("ext_expo_data", "")
                info = {}
                for p in ex.split("^"):
                    if "@" in p:
                        k, v = p.split("@", 1)
                        info[k] = v
                oid = info.get("object_id")
                if oid and oid not in seen and info.get("sub_object_type") == "normal":
                    seen.add(oid)
                    candidates.append({"offer_id": int(oid), "title": info.get("title", ""), "price": info.get("price")})
        except Exception:
            continue

    products = []
    for p in candidates:
        try:
            detail = c.get_offer_detail(p["offer_id"])
            dm = detail.get("dataModel", {})
            ppi = dm.get("productPackInfo", {}).get("fields", {}).get("pieceWeightScale", {}).get("pieceWeightScaleInfo", [])
            weights = [w.get("weight", 0) for w in ppi if w.get("weight", 0) > 0]
            w = min(weights) if weights else None
            if w is None or w > max_weight:
                continue
            offer = detail.get("offerDetail", {})
            skus = dm.get("mainPrice", {}).get("fields", {}).get("finalPriceModel", {}).get("tradeWithoutPromotion", {}).get("skuMapOriginal", [])
            products.append({
                "offer_id": p["offer_id"],
                "title": p["title"],
                "weight_g": w,
                "price": min((float(s["price"]) for s in skus), default=0),
                "link": f"https://detail.1688.com/offer/{p['offer_id']}.html",
            })
        except Exception:
            continue

    products.sort(key=lambda x: x["weight_g"])
    return {"products": products[:count], "total_found": len(products)}


def handle_get_search_config(args: dict) -> dict:
    c = get_client()
    resp = c.get_search_config(args["keywords"])
    if not resp.success:
        return {"error": resp.ret}
    fd = resp.data.get("data", {}).get("filterData", {})
    return {
        "filters": [x.get("label") for x in fd.get("filtbarBottom", [])],
        "sort_options": [x.get("label") for x in fd.get("filtbarLeft", [])],
    }


HANDLERS = {
    "search_products": handle_search_products,
    "get_product_detail": handle_get_product_detail,
    "search_by_image": handle_search_by_image,
    "recommend_for_ozon": handle_recommend_for_ozon,
    "get_search_config": handle_get_search_config,
}


# ── MCP 协议 (JSON-RPC over stdio) ──

def send_json(obj: dict):
    msg = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(f"Content-Length: {len(msg)}\r\n\r\n{msg}")
    sys.stdout.flush()


def main():
    stdin = sys.stdin.buffer
    while True:
        try:
            line = b""
            while b"\n" not in line:
                c = stdin.read(1)
                if not c:
                    return
                line += c
            line = line.decode()
        except (EOFError, KeyboardInterrupt):
            break
        if not line or line == "\n":
            continue
        if not line.startswith("Content-Length:"):
            continue
        length = int(line.split(":")[1].strip())
        while True:
            cl = stdin.readline().decode()
            if cl in ("\r\n", "\n", ""):
                break
        body = stdin.read(length).decode()
        try:
            msg = json.loads(body)
        except json.JSONDecodeError:
            continue

        msg_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        if method == "initialize":
            send_json({
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "ali1688-mcp", "version": "1.0.0"},
                },
            })
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send_json({"id": msg_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            h = HANDLERS.get(tool_name)
            if not h:
                send_json({"id": msg_id, "error": {"code": -32601, "message": f"unknown tool: {tool_name}"}})
                continue
            try:
                result = h(params.get("arguments", {}))
                send_json({"id": msg_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}})
            except Exception as e:
                send_json({"id": msg_id, "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"}})
        elif method == "ping":
            send_json({"id": msg_id, "result": {}})


if __name__ == "__main__":
    main()
