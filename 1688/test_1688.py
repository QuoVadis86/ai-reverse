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
    """taklid=39ee372737ff41b1acbdacb829233566; _csrf_token=1778721947150; xlly_s=1; cookie2=2a0b0d544d767ed774b9c44a7a695cab; t=38daa81cd4de8f685ddfb40971278036; _tb_token_=5e3e3e5e3deee; __cn_logon__=false; leftMenuLastMode=COLLAPSE; leftMenuModeTip=shown; plugin_home_downLoad_cookie=%E4%B8%8B%E8%BD%BD%E6%8F%92%E4%BB%B6; keywordsHistory=%E6%8B%8D%E7%AB%8B%E5%BE%97%E7%9B%B8%E7%BA%B8; mtop_partitioned_detect=1; _m_h5_tk=87ee993f2da00bd7f0cc46fe74c8364c_1778737255614; _m_h5_tk_enc=f91bf2bf4b450fb2a158c22210cc94cd; cna=TGyEIu1QN1YCAXQeZBZydOd7; isg=BG5utf4biFw2b__AtuwF16N5v8IwbzJp1hkthZg32nEsew7VAP-CeRT4M--XoyqB; tfstk=gzhjjzMTNchzjiLvXi8PRhTtpyF6YURUMNat-VCVWSFY51gnfqPZW-BRyrqrgou4Mc6sADaaD1E9w8U38rBTWP3RwuiA_-oZ1Yfs-Vc2o580iqVg6H-eTAgmo5qdvY5244LTS5ax4VJklqVg63-eTBumomNBWW0T6UN85yrT6RnOyUaT7iBOMc3JPu4GDGBYXQU8-PUT65ntyUag2lFTHc3JPPq8XUoOVPJbWqTGvKQgasb4ku1O6bavmk3bVz4oNrwbv8E56ZG7l-ZKkXUSsWzspXwmv3W4DvMZAyo2wsiIkmMLpjIJV50rdcaIMeBQfm0-g8hv794usxHLMftCDqwIwjPmFH1UvY0t183DA94rB2lqCm-l6okIy0wEag5UwjijM8Nd40CUAo81Cawh6zZePU6GIIyC8gzWMtruHz4vTUT5VO2YrzakPU6GI-Uul88WPiSF.; _user_vitals_session_data_={"user_line_track":true,"ul_session_id":"ju166g2rddn","last_page_id":"detail.1688.com%2F33gcy2njkko"}""",
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
    # test_search_config(c)
    test_search_by_text(c)

    image_id = test_upload_image(c)
    if image_id:
        test_search_by_image_id(c, image_id)

    print("\n✅ 全部测试完成")


if __name__ == "__main__":
    main()
