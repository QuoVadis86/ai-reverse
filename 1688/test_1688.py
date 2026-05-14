"""
1688 MTOP SDK 测试脚本
=====================
无需 cookie，自动通过 enctk 从服务端获取 token。
"""

import json, sys, os, traceback
sys.path.insert(0, os.path.dirname(__file__))

from core import MTOPSession
from client import Alibaba1688Client

OFFER_ID = 849246166605

def get_client():
    s = MTOPSession()
    if not s.login():
        print("❌ 无法获取 token")
        sys.exit(1)
    return Alibaba1688Client(s)

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1

c = get_client()
print(f"✅ SDK 就绪 (token: {c.session._token[:16]}...)\n")

# ── 商品详情 ──
test("get_offer_detail", lambda: (
    r := c.get_offer_detail(OFFER_ID),
    r["offerDetail"]["subject"],
    r["dataModel"],
))

test("get_offer_detail_from_html", lambda: (
    r := c.get_offer_detail_from_html(OFFER_ID),
    r.get("offerDetail") or r.get("productTitle"),
))

# ── 推荐/物流 ──
test("get_offer_recommendations", lambda: (
    r := c.get_offer_recommendations(OFFER_ID), r.success,
))

test("get_offer_logistics", lambda: (
    r := c.get_offer_logistics(OFFER_ID, 2215935988385), r.success,
))

# ── 店铺 ──
test("get_shop_card", lambda: (
    r := c.get_shop_card(OFFER_ID, 2215935988385, "b2b-221593598838573ca7"),
    r.data["model"]["shopName"],
))

test("get_shop_header", lambda: (
    r := c.get_shop_header("b2b-221593598838573ca7"), r.success,
))

test("get_shop_certification", lambda: (
    r := c.get_shop_certification("b2b-221593598838573ca7"), r.success,
))

test("check_shop_relation", lambda: (
    r := c.check_shop_relation("颂伊家装建材"), r.success,
))

# ── 评价 ──
test("get_ratings", lambda: (
    r := c.get_ratings(OFFER_ID, 1, 3), r.success,
))

test("get_dsr_ratings", lambda: (
    r := c.get_dsr_ratings(OFFER_ID), r.success,
))

# ── 运费 ──
test("get_freight_info", lambda: (
    r := c.get_freight_info(OFFER_ID), r.success,
))

test("get_fulfillment_solution", lambda: (
    r := c.get_fulfillment_solution(OFFER_ID), r.success,
))

# ── 搜索 ──
test("get_search_config", lambda: (
    r := c.get_search_config("手机"), r.success, r.data["data"]["filterData"],
))

test("search_by_text", lambda: (
    r := c.search_by_text("手机壳", 1, 5), r.success,
))

# ── 以图搜图 ──
IMG_URL = "https://cbu01.alicdn.com/img/ibank/O1CN01jhWptz1LjwDnxJdcK_!!2359971336-0-cib.jpg"

test("search_similar_by_image(URL)", lambda: (
    r := c.search_similar_by_image(IMG_URL, page_size=5),
    r.success,
    r.data["data"]["OFFER"]["found"] > 0,
))

test("search_by_image(URL)", lambda: (
    r := c.search_by_image(IMG_URL, page_size=5), r.success,
))

local = os.path.expanduser("~/Desktop/test_search_img.jpg")
if os.path.exists(local):
    test("upload_image(local)", lambda: (
        i := c.upload_image(local), print(f"      imageId: {i}"),
    ))
    test("search_by_image(local)", lambda: (
        r := c.search_by_image(local, page_size=5), r.success,
    ))

print(f"\n{'='*40}")
print(f"结果: {passed}/{passed+failed} 通过", "🎉" if failed == 0 else f" ❌ {failed}")
