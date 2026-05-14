"""
1688 MTOP SDK 测试脚本
=====================
验证所有 API 方法是否正常工作。

使用方式:
  python3 test_1688.py

首次使用需要从浏览器复制 cookie 填入下方 COOKIE_STR 变量。
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core import MTOPSession
from client import Alibaba1688Client

# ⚠️ 先填入从浏览器复制的 cookie
# 打开浏览器 F12 → Network → 任意请求 → Request Headers → cookie
# 复制整个 cookie 字符串到下面
COOKIE_STR = os.environ.get(
    "COOKIE",
    "",
)

OFFER_ID = 849246166605


def get_client():
    s = MTOPSession()
    if COOKIE_STR:
        s.set_cookie(COOKIE_STR)
    elif not s.login():
        print("❌ 需要 cookie")
        print("    export COOKIE='_m_h5_tk=xxx...; ...'")
        sys.exit(1)
    return Alibaba1688Client(s)


def test_offer_detail(c):
    print("\n=== get_offer_detail ===")
    r = c.get_offer_detail(OFFER_ID)
    offer = r["offerDetail"]
    dm = r["dataModel"]
    print(f"  标题: {offer['subject']}")
    print(f"  状态: {offer['status']}")
    print(f"  类目: {offer['leafCategoryName']}")
    mp = dm.get("mainPrice", {}).get("fields", {})
    skus = mp.get("finalPriceModel", {}).get("tradeWithoutPromotion", {}).get("skuMapOriginal", [])
    print(f"  SKU ({len(skus)}个):")
    for s in skus[:3]:
        print(f"    {s['specAttrs']}: ¥{s['price']} 库存={s['canBookCount']}")


def test_offer_recommendations(c):
    print("\n=== get_offer_recommendations ===")
    r = c.get_offer_recommendations(OFFER_ID)
    result = r.data.get("result", {})
    major = result.get("majorRecommendOfferInfos", [])
    print(f"  推荐商品: {len(major)} 个")
    for o in major[:3]:
        print(f"    {o['title'][:30]}... ¥{o['price']}")


def test_shop_card(c):
    print("\n=== get_shop_card ===")
    r = c.get_shop_card(
        offer_id=OFFER_ID,
        seller_user_id=2215935988385,
        seller_member_id="b2b-221593598838573ca7",
    )
    model = r.data.get("model", {})
    print(f"  店铺: {model.get('shopName')}")
    for d in model.get("shopData", []):
        print(f"    {d['dataKey']}: {d['dataValue']}")


def test_ratings(c):
    print("\n=== get_ratings ===")
    r = c.get_ratings(OFFER_ID, page=1, page_size=3)
    d = r.data
    if d and isinstance(d, dict):
        print(f"  返回 keys: {list(d.keys())}")


def test_search_config(c):
    print("\n=== get_search_config ===")
    r = c.get_search_config("手机")
    if not r.success:
        print(f"  ❌ {r.ret}")
        return
    d = r.data
    fd = d.get("data", {}).get("filterData", {})
    left = fd.get("filtbarLeft", [])
    bottom = fd.get("filtbarBottom", [])
    print(f"  排序方式: {[x['label'] for x in left[:4]]}")
    print(f"  快捷筛选: {[x['label'] for x in bottom[:6]]}")


def test_search_by_text(c):
    print("\n=== search_by_text ===")
    r = c.search_by_text("手机壳", page=1, page_size=5)
    if not r.success:
        print(f"  ❌ {r.ret}")
        return
    d = r.data
    print(f"  响应结构 keys: {list(d.keys())}")


def test_upload_image(c):
    print("\n=== upload_image ===")
    # 用本地测试图片
    test_img = os.path.expanduser("~/Desktop/test_search_img.jpg")
    if not os.path.exists(test_img):
        print(f"  ⏭️ 跳过: 没有测试图片 ({test_img})")
        return
    image_id = c.upload_image(test_img)
    print(f"  imageId: {image_id}")
    return image_id


def test_search_by_image_id(c, image_id):
    print(f"\n=== search_by_image_id ===")
    r = c.search_by_image_id(image_id)
    if not r.success:
        print(f"  ❌ {r.ret}")
        return
    d = r.data
    print(f"  响应 keys: {list(d.keys())}")


def main():
    c = get_client()
    print(f"✅ SDK 就绪 (token: {c.session._token[:12]}...)")

    test_offer_detail(c)
    test_offer_recommendations(c)
    test_shop_card(c)
    test_ratings(c)
    test_search_config(c)
    test_search_by_text(c)

    image_id = test_upload_image(c)
    if image_id:
        test_search_by_image_id(c, image_id)

    print("\n✅ 全部测试完成")


if __name__ == "__main__":
    main()
