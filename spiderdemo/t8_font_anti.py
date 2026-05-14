"""
T8-字体反爬 (Font Anti-Crawl)
---------------------------------------
挑战要点
  1. 每页数据使用自定义字体显示数字，字体中的字形被随机打乱
  2. 响应包含 b64Font (WOFF2)、page_data (混淆后的字符串数字)
  3. 需要解析字体中每个 cmap 位置对应的实际数字

解法:
  1. Init 获取正确数字 → 比对 Font API page 1 建立字形 → 数字映射
  2. 对后续每页: 解析字体中每个字形的坐标哈希
  3. 与参考映射匹配，还原真实数字

API 端点:
  Init:  GET /font_anti/api/challenge/init/?challenge_type=font_anti_challenge
  Page:  GET /font_anti/api/font_anti_challenge/page/{page}/?challenge_type=font_anti_challenge
  Submit: POST /font_anti/api/challenge/submit/

用法:
  export SPIDERDEMO_COOKIE="sessionid=xxxx"
  python spiderdemo/t8_font_anti.py
"""

import base64
import hashlib
import os
import sys
import time
from fontTools.ttLib import TTFont
import httpx
import io

HOST = "spiderdemo.cn"
CHALLENGE_TYPE = "font_anti_challenge"
TOTAL_PAGES = 100
COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)

GLYPH_NAMES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']


def _glyph_hash(glyf, name):
    g = glyf[name]
    coords = list(g.coordinates) if hasattr(g, 'coordinates') and g.coordinates else []
    flags = list(g.flags) if hasattr(g, 'flags') else []
    data = b''
    for x, y in coords[:100]:
        data += x.to_bytes(4, 'big', signed=True) + y.to_bytes(4, 'big', signed=True)
    for f in flags[:100]:
        data += bytes([f])
    return hashlib.md5(data).hexdigest()


def build_headers(cookie):
    return {
        "Host": HOST,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "*/*",
        "Referer": f"https://{HOST}/font_anti/font_anti_challenge/",
        "Cookie": cookie,
    }


def main():
    if not COOKIE:
        print("export SPIDERDEMO_COOKIE=\"sessionid=xxx\"")
        sys.exit(1)
    cookie = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    base = f"https://{HOST}"

    with httpx.Client() as client:
        bh = build_headers(cookie)

        # 1) Init: get correct page 1 numbers
        r = client.get(f"{base}/font_anti/api/challenge/init/?challenge_type={CHALLENGE_TYPE}", headers=bh)
        correct_p1 = r.json()['page_data']

        # 2) Get font-obfuscated page 1
        r = client.get(f"{base}/font_anti/api/font_anti_challenge/page/1/?challenge_type={CHALLENGE_TYPE}", headers=bh)
        ref = r.json()
        ref_display = ref['page_data']

        # Build reference mapping: cmap_digit → actual_digit
        ref_mapping = {}
        for actual_str, display_str in zip([str(n) for n in correct_p1], ref_display):
            for a, d in zip(actual_str, display_str):
                if d not in ref_mapping:
                    ref_mapping[d] = a

        # Build shape → actual_digit lookup from reference font
        ref_font = TTFont(io.BytesIO(base64.b64decode(ref['b64Font'])))
        ref_glyf = ref_font['glyf']
        shape_to_actual = {}
        for cmap_d in range(10):
            h = _glyph_hash(ref_glyf, GLYPH_NAMES[cmap_d])
            shape_to_actual[h] = ref_mapping[str(cmap_d)]
        ref_font.close()

        def decode_page(page_nums, font_b64):
            font = TTFont(io.BytesIO(base64.b64decode(font_b64)))
            glyf = font['glyf']
            mapping = {}
            for cmap_d in range(10):
                h = _glyph_hash(glyf, GLYPH_NAMES[cmap_d])
                mapping[str(cmap_d)] = shape_to_actual.get(h, str(cmap_d))
            decoded = [int(''.join(mapping.get(c, c) for c in s)) for s in page_nums]
            font.close()
            return decoded

        # 3) Collect all pages
        nums = list(correct_p1)
        for i in range(2, TOTAL_PAGES + 1):
            r = client.get(
                f"{base}/font_anti/api/font_anti_challenge/page/{i}/?challenge_type={CHALLENGE_TYPE}",
                headers=bh,
            )
            data = r.json()
            decoded = decode_page(data['page_data'], data['b64Font'])
            nums.extend(decoded)
            if i % 20 == 0:
                print(f"  {i}/{TOTAL_PAGES} ({len(nums)})")
            time.sleep(0.05)

        total = sum(nums)
        print(f"Total: {total}")

        # 4) Submit
        r = client.post(
            f"{base}/font_anti/api/challenge/submit/",
            json={"challenge_type": CHALLENGE_TYPE, "answer": total},
            headers={"Content-Type": "application/json", "Cookie": cookie},
        )
        result = r.json()
        if result.get("is_correct"):
            print(f"Answer correct! ({result['submitted_answer']})")
        else:
            print(f"Wrong: {result}")


if __name__ == "__main__":
    main()
