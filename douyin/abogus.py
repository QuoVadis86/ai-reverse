"""
抖音 a_bogus 签名算法纯 Python 实现
基于浏览器断点调试 + 开源参考验证

算法: URL params + method + UA + 时间戳 + 随机数
   → 双 SM3 → 50位数组 + 浏览器指纹 + XOR → RC4("y") → 自定义Base64(s4)
"""

import random
import time
from urllib.parse import urlencode, quote, urlparse
from gmssl import sm3, func

S4_ALPHABET = "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe"


def _sm3(data: bytes) -> bytes:
    h = sm3.sm3_hash(func.bytes_to_list(data))
    return bytes.fromhex(h)


def double_sm3(data_str: str) -> list[int]:
    h1 = _sm3((data_str + "cus").encode("utf-8"))
    h2 = _sm3(h1)
    return list(h2)


def char_codes(s: str) -> list[int]:
    return [ord(c) for c in s]


def random_4bytes(r=None, b=170, c=85, d=0, e=0, f=0, g=0) -> list[int]:
    a = r if r is not None else random.random() * 10000
    v1, v2 = int(a) & 255, int(a) >> 8
    return [v1 & b | d, v1 & c | e, v2 & b | f, v2 & c | g]


def random_prefix(r1=None, r2=None, r3=None) -> str:
    return "".join(chr(x) for x in (
        random_4bytes(r1, 170, 85, 1, 2, 5, 85 & 170)
        + random_4bytes(r2, 170, 85, 1, 0, 0, 0)
        + random_4bytes(r3, 170, 85, 1, 0, 5, 0)
    ))


def build_50byte(params_hash: list, method_hash: list, ua_code: list,
                 browser_len: int, start_ms: int = None, end_ms: int = None) -> list[int]:
    now = int(time.time() * 1000)
    st = start_ms or now
    et = end_ms or (st + random.randint(4, 8))

    def b(v, shift): return (v >> (shift * 8)) & 255

    return [
        44, b(et, 3), 0, 0, 0, 0,
        24, params_hash[21], ua_code[23], b(et, 2),
        0, 0, 0, 1,
        0, 239, params_hash[22], ua_code[24], b(et, 1), b(et, 0),
        0, 0, 0, 0,
        0, 0,
        0, 14,
        b(st, 3), b(st, 2), b(st, 1), b(st, 0),
        0, method_hash[21], method_hash[22], 3, browser_len, 1, browser_len, 0, 0, 0,
    ]


def rc4(data: str, key: str = "y") -> str:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + ord(key[i % len(key)])) & 255
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = []
    for ch in data:
        i = (i + 1) & 255
        j = (j + s[i]) & 255
        s[i], s[j] = s[j], s[i]
        out.append(chr(s[(s[i] + s[j]) & 255] ^ ord(ch)))
    return "".join(out)


def b64_encode(data: str) -> str:
    raw = data.encode("latin-1")
    r = []
    for i in range(0, len(raw), 3):
        n = (raw[i] << 16) | (raw[i + 1] << 8) | raw[i + 2] if i + 2 < len(raw) else (
            (raw[i] << 16) | (raw[i + 1] << 8) if i + 1 < len(raw) else raw[i] << 16
        )
        for shift, mask in [(18, 0xFC0000), (12, 0x03F000), (6, 0x0FC0), (0, 0x3F)]:
            if shift == 6 and i + 1 >= len(raw): break
            if shift == 0 and i + 2 >= len(raw): break
            r.append(S4_ALPHABET[(n & mask) >> shift])
    r.append("=" * ((4 - len(r) % 4) % 4))
    return "".join(r)


class ABogus:
    def __init__(self, user_agent: str = None, platform: str = "MacIntel"):
        ua = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36")
        self.ua_code = double_sm3(ua)
        win = "1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|" + platform
        self.browser_code = char_codes(win)
        self.browser_len = len(win)

    def generate(self, query: str, method: str = "GET",
                 start_ms: int = None, end_ms: int = None,
                 r1=None, r2=None, r3=None) -> str:
        params_hash = double_sm3(query)
        method_hash = double_sm3(method)

        arr50 = build_50byte(params_hash, method_hash, self.ua_code,
                             self.browser_len, start_ms, end_ms)

        xor_check = 0
        for b in arr50:
            xor_check ^= b

        rc4_in = "".join(chr(b) for b in arr50 + self.browser_code + [xor_check])
        rc4_out = rc4(rc4_in)

        return b64_encode(random_prefix(r1, r2, r3) + rc4_out)


def get_a_bogus(url: str, user_agent: str = None) -> str:
    """从完整 URL 提取 query string 后生成 a_bogus"""
    query = urlparse(url).query
    if not query:
        raise ValueError("URL 必须包含 query string")
    return ABogus(user_agent=user_agent).generate(query)


def get_a_bogus_from_params(params: dict, user_agent: str = None) -> str:
    """按 key 排序后编码为 query string 再生成 a_bogus"""
    query = urlencode(sorted(params.items(), key=lambda x: x[0]))
    return ABogus(user_agent=user_agent).generate(query)


if __name__ == "__main__":
    UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/148.0.0.0 Safari/537.36")

    params = {
        "device_platform": "webapp", "aid": "6383",
        "channel": "channel_pc_web", "source": "6",
        "update_version_code": "170400",
        "version_code": "170400", "version_name": "17.4.0",
        "cookie_enabled": "true",
        "screen_width": "2560", "screen_height": "1440",
        "browser_language": "zh-CN", "browser_platform": "MacIntel",
        "browser_name": "Chrome", "browser_version": "148.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink", "engine_version": "148.0.0.0",
        "os_name": "Mac OS", "os_version": "10.15.7",
        "device_memory": "16", "platform": "PC",
        "downlink": "1.45", "effective_type": "4g",
        "round_trip_time": "50", "webid": "7639712448747947561",
        "cpu_core_num": "10",
    }

    a_bogus = get_a_bogus_from_params(params, UA)
    print(f"a_bogus: {a_bogus}")
    print(f"encoded: {quote(a_bogus, safe='')}")
    print(f"length:  {len(a_bogus)}")
