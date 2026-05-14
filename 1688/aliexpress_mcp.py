#!/usr/bin/env python3
"""
1688 MCP Server for OpenCode
============================
基于逆向工程的 1688.com 选品 MCP 工具。

安装方式:
  1. pip install -r requirements.txt
  2. 添加至 opencode/toolbox.jsonc:
     "aliexpress1688": {
       "type": "local",
       "command": ["python3", "/path/to/aliexpress_mcp.py"],
       "description": "1688 选品助手 (搜索/详情/以图搜图)"
     }
  3. 首次使用需设置 COOKIE 环境变量:
     export ALI1688_COOKIE='_m_h5_tk=xxx...'

协议实现: JSON-RPC over stdio (MCP)
"""

import json
import sys
import os
import logging
import traceback
from typing import Any

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("1688-mcp")

# 抑制 requests 日志
logging.getLogger("urllib3").setLevel(logging.WARNING)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from core import MTOPSession
from client import Alibaba1688Client


def get_client() -> Alibaba1688Client:
    cookie = os.environ.get("ALI1688_COOKIE", "")
    s = MTOPSession()
    if cookie:
        s.set_cookie(cookie)
    elif not s.login():
        raise RuntimeError(
            "需要 1688 cookie。设置环境变量 ALI1688_COOKIE "
            "或在浏览器 F12 → Network 复制 cookie 字符串"
        )
    return Alibaba1688Client(s)


# ------------------------------------------------------------------
# MCP Tools
# ------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_products",
        "description": "关键词搜索 1688 商品，返回标题/价格/offerId",
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
        "description": "获取商品详情 (标题/重量/SKU价格/图片)",
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
        "description": "以图搜图：上传本地图片或远程 URL 搜索相似商品",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_source": {
                    "oneOf": [
                        {"type": "string", "format": "uri", "description": "图片 URL"},
                        {"type": "string", "description": "本地图片路径"},
                    ]
                },
                "page_size": {"type": "integer", "default": 20},
            },
            "required": ["image_source"],
        },
    },
    {
        "name": "recommend_for_ozon",
        "description": "智能选品：搜索适合 Ozon 平台的家居日用商品 (自动过滤重量<500g)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "品类关键词，如 夏季、厨房、收纳",
                    "default": "家居日用",
                },
                "max_weight": {"type": "integer", "default": 500, "description": "最大重量(g)"},
                "count": {"type": "integer", "default": 10, "description": "返回数量"},
            },
        },
    },
    {
        "name": "get_search_config",
        "description": "获取搜索筛选项 (类目/排序/包邮/一件代发等)",
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
    resp = c.search_by_text(
        keywords=args["keywords"],
        page=args.get("page", 1),
        page_size=args.get("page_size", 20),
    )
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
                "price": info.get("price"),
                "title": info.get("title", ""),
                "seller_id": info.get("sellerId"),
            })
    return {"total": len(results), "products": results[: args.get("page_size", 20)]}


def handle_get_product_detail(args: dict) -> dict:
    c = get_client()
    detail = c.get_offer_detail(args["offer_id"])
    offer = detail["offerDetail"]
    dm = detail["dataModel"]
    ppi = dm.get("productPackInfo", {}).get("fields", {}).get("pieceWeightScale", {}).get("pieceWeightScaleInfo", [])
    weights = [p.get("weight", 0) for p in ppi if p.get("weight", 0) > 0]
    skus = dm.get("mainPrice", {}).get("fields", {}).get("finalPriceModel", {}).get("tradeWithoutPromotion", {}).get("skuMapOriginal", [])
    prices = [{"spec": s["specAttrs"], "price": s["price"], "stock": s["canBookCount"]} for s in skus]
    images = [i.get("fullPathImageURI", "") for i in offer.get("imageList", [])[:5]]
    return {
        "offer_id": offer.get("offerId"),
        "title": offer.get("subject"),
        "status": offer.get("status"),
        "min_weight_g": min(weights) if weights else None,
        "skus": prices,
        "images": images,
        "category": offer.get("leafCategoryName"),
        "offer_link": f"https://detail.1688.com/offer/{offer.get('offerId')}.html",
    }


def handle_search_by_image(args: dict) -> dict:
    c = get_client()
    resp = c.search_by_image(args["image_source"], page_size=args.get("page_size", 20))
    if not resp.success:
        return {"error": resp.ret}
    offer = resp.data.get("data", {}).get("OFFER", {})
    items = offer.get("items", [])
    results = []
    for item in items[: args.get("page_size", 20)]:
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
        results.append({
            "offer_id": info.get("object_id"),
            "price": info.get("price"),
            "sub_type": info.get("sub_object_type"),
            "pic_url": pic_url,
        })
    return {
        "found": offer.get("found", 0),
        "products": results,
    }


def handle_recommend_for_ozon(args: dict) -> dict:
    c = get_client()
    category = args.get("category", "家居日用")
    max_weight = args.get("max_weight", 500)
    count = args.get("count", 10)

    queries = [
        f"{category} 收纳 轻量 家用",
        f"{category} 厨房 小工具",
        f"{category} 夏季 便携",
        f"{category} 桌面 置物架",
        f"{category} 挂钩 置物",
    ]

    candidates = []
    seen_ids = set()
    for q in queries:
        try:
            resp = c.search_by_text(q, page=1, page_size=15)
            if not resp.success:
                continue
            items = resp.data.get("data", {}).get("OFFER", {}).get("items", [])
            for item in items:
                expo = item.get("trackInfo", {}).get("expoArgs", {}).get("ext_expo_data", "")
                info = {}
                for part in expo.split("^"):
                    if "@" in part:
                        k, v = part.split("@", 1)
                        info[k] = v
                oid = info.get("object_id")
                if oid and oid not in seen_ids and info.get("sub_object_type") == "normal":
                    seen_ids.add(oid)
                    candidates.append({
                        "offer_id": int(oid),
                        "title": info.get("title", ""),
                        "price": info.get("price"),
                        "keyword": q,
                    })
        except Exception:
            continue

    products = []
    for p in candidates:
        try:
            detail = c.get_offer_detail(p["offer_id"])
            dm = detail.get("dataModel", {})
            ppi = dm.get("productPackInfo", {}).get("fields", {}).get("pieceWeightScale", {}).get("pieceWeightScaleInfo", [])
            weights = [pw.get("weight", 0) for pw in ppi if pw.get("weight", 0) > 0]
            weight = min(weights) if weights else None
            if weight is None or weight > max_weight:
                continue
            mp = dm.get("mainPrice", {}).get("fields", {})
            skus = mp.get("finalPriceModel", {}).get("tradeWithoutPromotion", {}).get("skuMapOriginal", [])
            min_price = min((float(s["price"]) for s in skus), default=0)
            offer = detail.get("offerDetail", {})
            images = [i.get("fullPathImageURI", "") for i in offer.get("imageList", [])[:1]]
            products.append({
                "offer_id": p["offer_id"],
                "title": p["title"],
                "weight_g": weight,
                "price": min_price,
                "image": images[0] if images else "",
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
    d = resp.data.get("data", {}).get("filterData", {})
    return {
        "filters": [x.get("label") for x in d.get("filtbarBottom", [])],
        "sort_options": [x.get("label") for x in d.get("filtbarLeft", [])],
    }


HANDLERS = {
    "search_products": handle_search_products,
    "get_product_detail": handle_get_product_detail,
    "search_by_image": handle_search_by_image,
    "recommend_for_ozon": handle_recommend_for_ozon,
    "get_search_config": handle_get_search_config,
}


# ------------------------------------------------------------------
# MCP Protocol (JSON-RPC over stdio)
# ------------------------------------------------------------------

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
        # read until blank line
        while True:
            cl = stdin.readline().decode()
            if cl == "\r\n" or cl == "\n" or not cl.strip():
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
                    "serverInfo": {"name": "aliexpress1688", "version": "1.0.0"},
                },
            })
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send_json({"id": msg_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            handler = HANDLERS.get(tool_name)
            if not handler:
                send_json({
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                })
                continue
            try:
                result = handler(arguments)
                send_json({
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]},
                })
            except Exception as e:
                send_json({
                    "id": msg_id,
                    "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"},
                })
        elif method == "ping":
            send_json({"id": msg_id, "result": {}})


if __name__ == "__main__":
    main()
