"""
T5-柳暗花明又一墙 (OB1 Challenge)
---------------------------------------
挑战要点
  1. 每页请求需带 signature 参数
  2. 签名 = base64(core_b64 + timestamp)
  3. core_b64 是浏览器指纹的编码（session 绑定，页码无关）
  4. 指纹含 canvas 渲染、浏览器属性等

解法:
  Node.js + node-canvas 运行原始 O0o0O0O0 代码生成签名
  或从一次有效会话中提取 core_b64 缓存复用

用法:
  export SPIDERDEMO_COOKIE="sessionid=xxxx"
  python spiderdemo/t5_ob1_challenge.py
"""

import base64
import os
import subprocess
import sys
import time

import httpx

HOST = "spiderdemo.cn"
CHALLENGE_TYPE = "ob1_challenge"
TOTAL_PAGES = 100
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)
CORE_B64 = os.environ.get("SPIDERDEMO_CORE")


def generate_signature():
    global CORE_B64
    ts = str(int(time.time() * 1000))

    if CORE_B64:
        return base64.b64encode((CORE_B64 + ts).encode("latin-1")).decode()

    # 尝试通过 Node.js 生成
    sign_script = os.path.join(SCRIPT_DIR, "t5_sign.js")
    if os.path.exists(sign_script):
        try:
            r = subprocess.run(["node", sign_script], capture_output=True,
                               text=True, timeout=10, cwd=SCRIPT_DIR)
            sig = r.stdout.strip()
            if len(sig) > 50:
                layer1 = base64.b64decode(sig).decode("latin-1")
                idx = layer1.find("==")
                if idx >= 0:
                    CORE_B64 = layer1[:idx + 2]
                    return base64.b64encode((CORE_B64 + ts).encode("latin-1")).decode()
        except Exception:
            pass

    return None


def build_headers(cookie):
    return {
        "Host": HOST,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://{HOST}/authentication/ob1_challenge/",
        "Cookie": cookie,
    }


def main():
    if not COOKIE:
        print("export SPIDERDEMO_COOKIE=\"sessionid=xxx\"")
        sys.exit(1)

    cookie = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    base = f"https://{HOST}"

    sig = generate_signature()
    if not sig:
        print("无法生成签名，请安装 canvas: cd spiderdemo && npm install canvas")
        print("或设置缓存指纹: export SPIDERDEMO_CORE=\"eDEn...Ww==\"")
        sys.exit(1)

    with httpx.Client() as client:
        bh = build_headers(cookie)
        r = client.get(f"{base}/authentication/api/ob1_challenge/init/?challenge_type={CHALLENGE_TYPE}", headers=bh)
        data = r.json()
        nums = list(data.get("page_data", []))

        for i in range(2, TOTAL_PAGES + 1):
            sig = generate_signature()
            r = client.get(f"{base}/authentication/api/ob1_challenge/page/{i}/?challenge_type={CHALLENGE_TYPE}&signature={sig}", headers=bh)
            if r.status_code != 200:
                print(f"Page {i}: {r.status_code}")
                break
            nums.extend(r.json()["page_data"])
            if i % 20 == 0:
                print(f"  {i}/{TOTAL_PAGES} ({len(nums)})")
            time.sleep(0.1)

        total = sum(nums)
        r = client.post(f"{base}/authentication/api/ob1_challenge/submit/",
            json={"challenge_type": CHALLENGE_TYPE, "answer": total},
            headers={"Content-Type": "application/json", "Cookie": cookie})
        result = r.json()
        if result.get("is_correct"):
            print(f"Answer correct! ({result['submitted_answer']})")


if __name__ == "__main__":
    main()
