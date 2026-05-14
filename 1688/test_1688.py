import sys, os, traceback
sys.path.insert(0, os.path.dirname(__file__))

from client import Alibaba1688Client

OFFER_ID = 849246166605

c = Alibaba1688Client()
if not c.session.login():
    print("failed to get token")
    sys.exit(1)

print(f"token: {c.session._token[:16]}...\n")

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ok {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        failed += 1

test("get_offer_detail", lambda: (
    r := c.get_offer_detail(OFFER_ID),
    r["offerDetail"]["subject"],
    r["dataModel"],
))

test("get_offer_detail_from_html", lambda: (
    r := c.get_offer_detail_from_html(OFFER_ID),
    r.get("offerDetail") or r.get("productTitle"),
))

test("get_offer_recommendations", lambda: (
    r := c.get_offer_recommendations(OFFER_ID), r.success,
))

test("get_offer_logistics", lambda: (
    r := c.get_offer_logistics(OFFER_ID, 2215935988385), r.success,
))

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

test("get_ratings", lambda: (
    r := c.get_ratings(OFFER_ID, 1, 3), r.success,
))

test("get_dsr_ratings", lambda: (
    r := c.get_dsr_ratings(OFFER_ID), r.success,
))

test("get_freight_info", lambda: (
    r := c.get_freight_info(OFFER_ID), r.success,
))

test("get_fulfillment_solution", lambda: (
    r := c.get_fulfillment_solution(OFFER_ID), r.success,
))

test("get_search_config", lambda: (
    r := c.get_search_config("手机"), r.success, r.data["data"]["filterData"],
))

test("search_by_text", lambda: (
    r := c.search_by_text("手机壳", 1, 5), r.success,
))

IMG = "https://cbu01.alicdn.com/img/ibank/O1CN01jhWptz1LjwDnxJdcK_!!2359971336-0-cib.jpg"

test("search_similar_by_image", lambda: (
    r := c.search_similar_by_image(IMG, page_size=5),
    r.success,
    r.data["data"]["OFFER"]["found"] > 0,
))

test("search_by_image(URL)", lambda: (
    r := c.search_by_image(IMG, page_size=5), r.success,
))

local = os.path.expanduser("~/Desktop/test_search_img.jpg")
if os.path.exists(local):
    test("search_by_image(local)", lambda: (
        r := c.search_by_image(local, page_size=5), r.success,
    ))

print(f"\n{'='*40}")
print(f"{passed}/{passed+failed} passed", "🎉" if failed == 0 else f" ❌ {failed}")
