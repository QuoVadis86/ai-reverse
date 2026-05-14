"""
T2-加解密 (Obfuscation Challenge)
-----------------------------------
挑战要点
  1. 请求头顺序检测（同 T1），httpx 保留插入顺序即可通过
  2. 每页数据需带 sign 签名访问
  3. sign 算法: md5(timestamp + page + salt)，salt 在混淆 JS 中

签名逆向
  hex_md5 在 /static/js/obfuscation/ob_challenge1.js 中定义（重度混淆）
  关键代码:
    function hex_md5(input) {
        input += '\\xa3\\xac\\xa1\\xa3\\x66\\x64\\x6a\\x66' +
                 '\\x2c\\x6a\\x6b\\x67\\x66\\x6b\\x6c';  // 追加 salt
        return hex(md5(string_to_array(input), input.length * 8));
    }
  salt 字节: \\xa3\\xac\\xa1\\xa3fdjf,jkgfkl
  注: 编码为 latin-1，非 utf-8

API 端点
  初始化: /ob/api/challenge/init/?challenge_type=ob_challenge1
  分页:   /ob/api/ob_challenge1/page/{page}/?challenge_type=...&sign={md5}&timestamp={ts}
  提交:   /ob/api/challenge/submit/

用法:
  export SPIDERDEMO_COOKIE="sessionid=xxxx"
  python spiderdemo/t2_ob_challenge1.py
"""

import hashlib
import json
import os
import sys
import time

import httpx

HOST = "spiderdemo.cn"
CHALLENGE_TYPE = "ob_challenge1"
TOTAL_PAGES = 100

COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)

# 从混淆代码提取的 salt，编码必须用 latin-1
SALT = bytes([
    0xa3, 0xac, 0xa1, 0xa3,
    0x66, 0x64, 0x6a, 0x66,
    0x2c, 0x6a, 0x6b, 0x67,
    0x66, 0x6b, 0x6c,
]).decode("latin-1")


def calc_sign(page):
    ts = str(int(time.time() * 1000))
    raw = ts + str(page) + SALT
    sign = hashlib.md5(raw.encode("latin-1")).hexdigest()
    return ts, sign


# Chrome 原生请求头顺序
def build_headers(cookie, method="GET"):
    h = [
        ("Host", HOST),
        ("Connection", "keep-alive"),
        ("sec-ch-ua", '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"'),
        ("sec-ch-ua-mobile", "?0"),
        ("sec-ch-ua-platform", '"macOS"'),
        ("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/148.0.0.0 Safari/537.36"),
        ("Accept", "*/*"),
        ("Referer", f"https://{HOST}/ob/ob_challenge1/"),
        ("Accept-Encoding", "gzip, deflate, br"),
        ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
        ("Cookie", cookie),
    ]
    if method == "POST":
        h = [("Content-Type", "application/json") if k == "Accept" else (k, v) for k, v in h]
    return dict(h)


def main():
    if not COOKIE:
        print("❌ export SPIDERDEMO_COOKIE=\"sessionid=xxx\"")
        sys.exit(1)

    cookie = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    base = f"https://{HOST}"

    with httpx.Client() as client:
        bh = build_headers(cookie)

        # 1. 初始化挑战
        print("📡 初始化...")
        r = client.get(f"{base}/ob/api/challenge/init/?challenge_type={CHALLENGE_TYPE}", headers=bh)
        data = r.json()
        if not data.get("success"):
            print(f"❌ {data.get('error', data)}")
            sys.exit(1)
        print(f"   {data.get('message', '')}")
        nums = list(data["page_data"])

        # 2. 采集 2~100 页（每页需要 sign 签名）
        print(f"\n📊 采集 {TOTAL_PAGES} 页...")
        for i in range(2, TOTAL_PAGES + 1):
            ts, sign = calc_sign(i)
            r = client.get(
                f"{base}/ob/api/ob_challenge1/page/{i}/"
                f"?challenge_type={CHALLENGE_TYPE}&sign={sign}&timestamp={ts}",
                headers=bh,
            )
            if r.status_code != 200:
                print(f"❌ 第 {i} 页失败: {r.text[:120]}")
                sys.exit(1)
            nums.extend(r.json()["page_data"])
            if i % 20 == 0:
                print(f"   ✅ {i}/{TOTAL_PAGES} ({len(nums)} 个数字)")
            time.sleep(0.05)

        total = sum(nums)
        print(f"   ✅ {TOTAL_PAGES}/{TOTAL_PAGES}")
        print(f"\n📝 总和: {total:,}")

        # 3. 提交答案
        print("\n📤 提交...")
        r = client.post(
            f"{base}/ob/api/challenge/submit/",
            json={"challenge_type": CHALLENGE_TYPE, "answer": total},
            headers=build_headers(cookie, "POST"),
        )
        result = r.json()
        if result.get("success"):
            if result.get("is_correct"):
                print(f"🎉 答案正确！({result['submitted_answer']})")
                print(f"   {result.get('message', '')}")
            else:
                print(f"❌ 答案错误: {result.get('message', '')}")
        else:
            print(f"❌ 提交失败: {result.get('error', '')}")


if __name__ == "__main__":
    main()
