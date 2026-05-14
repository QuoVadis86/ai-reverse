"""
T1-请求头检测 (Header Check Challenge)

服务端校验逻辑
----------------
服务端（istio-envoy）在校验 HTTP 请求头的发送顺序。
Chrome 原生 fetch() 发送的请求头有固定的顺序：

  host → connection → sec-ch-ua → sec-ch-ua-mobile → sec-ch-ua-platform
  → user-agent → accept → referer → accept-encoding → accept-language → cookie

如果请求头的发送顺序不匹配，返回 400 "检测到爬虫模式，访问被拒绝"。

为什么 requests 不行
--------------------
Python `requests` 底层使用 `urllib3`，它会在发送前对标准头（User-Agent、
Accept、Accept-Encoding 等）做重排（提前），打乱了 Chrome 原生顺序。

为什么 httpx / http.client 可以
--------------------------------
`httpx` 和 `http.client` 严格按照用户插入的顺序发送请求头，
不会自动重排，因此能通过服务端的顺序校验。

本脚本提供两种实现：
  - http.client（标准库，零依赖）
  - httpx（三方库，更简洁）

用法:
  export SPIDERDEMO_COOKIE="sessionid=xxxx"
  python spiderdemo/t1_header_check.py
"""

import json
import os
import sys
import time

HOST = "spiderdemo.cn"
CHALLENGE_TYPE = "header_check"
TOTAL_PAGES = 100

COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)

# ============================================================
# Chrome 原生请求头顺序 —— 服务端严格按此顺序校验
#
# 实测 requests(urllib3) 会重排为:
#   User-Agent → Accept-Encoding → Accept → Connection → Host → ...  → ❌ 400
# httpx/http.client 保留插入顺序:
#   host → connection → sec-ch-ua → ... → cookie                     → ✅ 200
# ============================================================
CHROME_HEADER_ORDER = [
    ("Host", HOST),
    ("Connection", "keep-alive"),
    ("sec-ch-ua", '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"macOS"'),
    ("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/148.0.0.0 Safari/537.36"),
    ("Accept", "*/*"),
    ("Referer", "https://spiderdemo.cn/sec1/header_check/"),
    ("Accept-Encoding", "gzip, deflate, br"),
    ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
    ("Cookie", None),  # 由调用方填入
]


def build_headers(cookie, method="GET"):
    """生成严格按 Chrome 顺序的请求头列表，method=POST 时替换 Accept → Content-Type"""
    cookie_val = cookie if cookie.startswith("sessionid=") else f"sessionid={cookie}"
    result = []
    for k, v in CHROME_HEADER_ORDER:
        if k == "Cookie":
            result.append((k, cookie_val))
        elif k == "Accept" and method == "POST":
            result.append(("Content-Type", "application/json"))
        else:
            result.append((k, v))
    if method == "POST":
        result.append(("Content-Length", "0"))  # 稍后更新
    return result


# ============================================================
# 方式 A: http.client（标准库，零依赖）
# ============================================================

def request_httpclient(method, path, cookie, body=None):
    import http.client
    headers = build_headers(cookie, method)
    body_bytes = None
    if method == "POST":
        body_bytes = json.dumps(body).encode()
        # 更新 Content-Length
        headers = [(k, "0") if k == "Content-Length" else (k, v) for k, v in headers]
        headers = [(k, str(len(body_bytes))) if k == "Content-Length" else (k, v) for k, v in headers]
    conn = http.client.HTTPSConnection(HOST)
    conn.request(method, path, body=body_bytes, headers=dict(headers))
    resp = conn.getresponse()
    data = resp.read().decode()
    conn.close()
    return resp.status, json.loads(data)


# ============================================================
# 方式 B: httpx（保留头顺序，用法更简洁）
# ============================================================

def request_httpx(method, path, cookie, body=None):
    import httpx
    headers_list = build_headers(cookie, method)
    headers_dict = dict(headers_list)
    if method == "POST":
        body_bytes = json.dumps(body).encode()
        headers_dict["Content-Length"] = str(len(body_bytes))
    with httpx.Client() as client:
        resp = client.request(method, f"https://{HOST}{path}",
                              headers=headers_dict,
                              content=json.dumps(body) if method == "POST" else None)
        return resp.status_code, resp.json()


# 默认使用 http.client，可切换
REQUEST_IMPL = os.environ.get("HTTP_LIB", "httpclient")  # 或 "httpx"
_request = request_httpclient if REQUEST_IMPL == "httpclient" else request_httpx


def main():
    if not COOKIE:
        print("❌ 请提供 cookie:")
        print("   export SPIDERDEMO_COOKIE=\"sessionid=xxx\"")
        print("   或: python t1_header_check.py \"sessionid=xxx\"")
        print("\n   HTTP 库切换: export HTTP_LIB=httpx  (默认 httpclient)")
        sys.exit(1)

    impl_name = "http.client" if REQUEST_IMPL == "httpclient" else "httpx"
    print(f"🔧 使用 {impl_name} (请求头发送顺序保持 Chrome 原生顺序)")

    # 1. 初始化挑战
    print("\n📡 初始化挑战...")
    status, data = _request("GET", f"/sec1/api/challenge/init/?challenge_type={CHALLENGE_TYPE}", COOKIE)
    if status != 200 or not data.get("success"):
        print(f"❌ 初始化失败: {data.get('error', data)}")
        sys.exit(1)
    print(f"   {data.get('message', '')}")

    # 2. 采集全部 100 页
    print(f"\n📊 采集 {TOTAL_PAGES} 页数据...")
    all_numbers = list(data.get("page_data", []))

    for i in range(2, TOTAL_PAGES + 1):
        status, data = _request(
            "GET",
            f"/sec1/api/challenge/page/{i}/?challenge_type={CHALLENGE_TYPE}",
            COOKIE,
        )
        if status != 200 or not data.get("success"):
            print(f"❌ 第 {i} 页失败 ({status}): {data.get('error', data)}")
            sys.exit(1)
        all_numbers.extend(data["page_data"])
        if i % 20 == 0:
            print(f"   ✅ {i}/{TOTAL_PAGES} 页 ({len(all_numbers)} 个数字)")
        time.sleep(0.05)

    total = sum(all_numbers)
    print(f"   ✅ {TOTAL_PAGES}/{TOTAL_PAGES} 页 ({len(all_numbers)} 个数字)")
    print(f"\n📝 总和: {total:,}")

    # 3. 提交答案
    print("\n📤 提交答案...")
    status, result = _request("POST", "/sec1/api/challenge/submit/", COOKIE, {
        "challenge_type": CHALLENGE_TYPE,
        "answer": total,
    })
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
