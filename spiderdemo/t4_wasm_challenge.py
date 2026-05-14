"""
T4-WASM挑战 (WASM Challenge)
---------------------------------------
挑战要点
  1. 请求头顺序检测（同 T1）
  2. 每页请求需带 wasm_auth 签名，由 WASM 模块生成
  3. WASM 函数: encrypt_simple(verifyString, timestamp) -> 64-char hex
  4. verifyString = "wasm_challenge_page_{page}"
  5. timestamp = floor(get_timestamp() / 1000)

解法: wasmtime 加载 wasm_anti_bg.wasm 直接调用 encrypt_simple
      httpx 负责 API 请求

用法:
  export SPIDERDEMO_COOKIE="sessionid=xxxx"
  python spiderdemo/t4_wasm_challenge.py
"""

import ctypes
import os
import sys
import time

import httpx
import wasmtime

HOST = "spiderdemo.cn"
CHALLENGE_TYPE = "wasm_challenge"
TOTAL_PAGES = 100

COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)

_encrypt_simple = _memory = _malloc = _store = _mem_base = None


def _ensure_wasm():
    global _encrypt_simple, _memory, _malloc, _store, _mem_base
    if _encrypt_simple is not None:
        return

    wasm_path = os.path.join(os.path.dirname(__file__), "wasm_anti_bg.wasm")
    engine = wasmtime.Engine()
    module = wasmtime.Module(engine, open(wasm_path, "rb").read())
    linker = wasmtime.Linker(engine)
    store = wasmtime.Store(engine)

    def _read_str(caller, ptr, length):
        if length == 0:
            return ""
        b = ctypes.c_ubyte * length
        addr = ctypes.addressof(caller.get_export("memory").data_ptr(caller).contents)
        return bytes(b.from_address(addr + ptr)).decode("utf-8")

    linker.define_func("wbg", "__wbindgen_string_new",
        wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()],
                         [wasmtime.ValType.externref()]),
        lambda c, p, l: _read_str(c, p, l))
    linker.define_func("wbg", "__wbg_now_807e54c39636c349",
        wasmtime.FuncType([], [wasmtime.ValType.f64()]),
        lambda: time.time() * 1000)
    linker.define_func("wbg", "__wbg_new_8a6f238a6ece86ea",
        wasmtime.FuncType([], [wasmtime.ValType.externref()]), lambda: None)
    linker.define_func("wbg", "__wbg_stack_0ed75d68575b0f3c",
        wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.externref()], []),
        lambda c, f, e: None)
    linker.define_func("wbg", "__wbg_error_7534b8e9a36f1ab4",
        wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []),
        lambda c, f, v: None)
    linker.define_func("wbg", "__wbindgen_throw",
        wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []),
        lambda c, p, l: (_ for _ in ()).throw(RuntimeError(_read_str(c, p, l))))
    linker.define_func("wbg", "__wbindgen_init_externref_table",
        wasmtime.FuncType([], []), lambda: None)

    instance = linker.instantiate(store, module)
    try:
        instance.exports(store)["__wbindgen_start"](store)
    except RuntimeError:
        pass

    _encrypt_simple = instance.exports(store)["encrypt_simple"]
    _memory = instance.exports(store)["memory"]
    _malloc = instance.exports(store)["__wbindgen_malloc"]
    _store = store
    _mem_base = ctypes.addressof(_memory.data_ptr(store).contents)


def _write_str(s):
    b = s.encode()
    p = _malloc(_store, len(b), 1)
    for i, byte in enumerate(b):
        (ctypes.c_ubyte * 1).from_address(_mem_base + p + i)[0] = byte
    return p, len(b)


def compute_wasm_auth(page_num):
    _ensure_wasm()
    verify = f"{CHALLENGE_TYPE}_page_{page_num}"
    ts = str(int(time.time()))
    p1, l1 = _write_str(verify)
    p2, l2 = _write_str(ts)
    result = _encrypt_simple(_store, p1, l1, p2, l2)
    r_ptr, r_len = result[0], result[1]
    out = bytes((ctypes.c_ubyte * r_len).from_address(_mem_base + r_ptr))
    return ts, out.decode()


def build_headers(cookie, extra=None):
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
        ("Referer", f"https://{HOST}/sec1/wasm_challenge/"),
        ("Accept-Encoding", "gzip, deflate, br"),
        ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
        ("Cookie", cookie),
    ]
    if extra:
        h.extend(extra)
    return dict(h)


def main():
    if not COOKIE:
        print("❌ export SPIDERDEMO_COOKIE=\"sessionid=xxx\"")
        sys.exit(1)

    cookie = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    base = f"https://{HOST}"

    print("📡 初始化 WASM...")
    _ensure_wasm()

    with httpx.Client() as client:
        bh = build_headers(cookie)
        r = client.get(
            f"{base}/sec1/api/challenge/init/?challenge_type={CHALLENGE_TYPE}",
            headers=bh,
        )
        data = r.json()
        if not data.get("success"):
            print(f"❌ {data.get('error', data)}")
            sys.exit(1)
        print(f"   {data.get('message', '')}")
        nums = list(data.get("page_data", []))

        print(f"\n📊 采集 {TOTAL_PAGES} 页...")
        for i in range(2, TOTAL_PAGES + 1):
            ts, auth = compute_wasm_auth(i)
            bh = build_headers(cookie, [("X-WASM-Timestamp", ts), ("X-WASM-Page", str(i))])
            r = client.get(
                f"{base}/sec1/api/wasm_challenge/page/{i}/"
                f"?challenge_type={CHALLENGE_TYPE}&wasm_auth={auth}",
                headers=bh,
            )
            if r.status_code != 200:
                print(f"❌ 第 {i} 页: {r.status_code} {r.text[:120]}")
                sys.exit(1)
            nums.extend(r.json()["page_data"])
            if i % 20 == 0:
                print(f"   ✅ {i}/{TOTAL_PAGES} ({len(nums)} 个数字)")
            time.sleep(0.05)

        total = sum(nums)
        print(f"   ✅ {TOTAL_PAGES}/{TOTAL_PAGES}")
        print(f"\n📝 总和: {total:,}")

        r = client.post(
            f"{base}/sec1/api/challenge/submit/",
            json={"challenge_type": CHALLENGE_TYPE, "answer": total},
            headers=build_headers(cookie),
        )
        result = r.json()
        if result.get("success"):
            if result.get("is_correct"):
                print(f"🎉 答案正确！({result['submitted_answer']})")
            else:
                print(f"❌ 答案错误: {result.get('message', '')}")
        else:
            print(f"❌ 提交失败: {result.get('error', '')}")


if __name__ == "__main__":
    main()
