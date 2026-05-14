import httpx, os, sys

HOST = "spiderdemo.cn"
CT = "jsvmp_challenge"
TOTAL = 100
COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)

"""
T6-JSVMP挑战 - 分析笔记
====================
161KB 重度混淆 JS，使用 JSVMP (JavaScript Virtual Machine Protection):
  - Unicode 变量名 (ㅇﾟ, ᐤﾟ, ㅇꄲ 等)
  - 控制流平坦化
  - Protobuf 鉴权通信 (ChallengePageRequest/Response)
  - Browser Fingerprint 检测
  - CSS Anti-Crawler Decryptor

API 模式:
  Init:  GET /authentication/api/jsvmp_challenge/init/?challenge_type=jsvmp_challenge
  Page:  POST /authentication/api/jsvmp_challenge/page/{n}/?challenge_type=jsvmp_challenge
         Content-Type: application/x-protobuf
  Submit: POST /authentication/api/jsvmp_challenge/submit/

Init 返回 page_data (正确答案)，但 page 请求需要 protobuf 编码
"""


def main():
    if not COOKIE:
        print("Usage: export SPIDERDEMO_COOKIE=sessionid=xxx")
        sys.exit(1)

    cookie_str = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    headers = {"Cookie": cookie_str, "User-Agent": "Mozilla/5.0"}

    with httpx.Client() as client:
        client.headers.update(headers)

        r = client.get(f"https://{HOST}/authentication/api/{CT}/init/?challenge_type={CT}")
        print(f"Init: {r.json().get('message', '')}")
        print(f"page_data: {r.json().get('page_data', 'N/A')}")

        print(f"\nT6 requires protobuf request encoding")
        print(f"See analysis notes in this file header")


if __name__ == "__main__":
    main()
