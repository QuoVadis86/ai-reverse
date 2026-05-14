"""
T3-protobuf加密 (Protobuf Challenge)
---------------------------------------
挑战要点
  1. 请求头顺序检测（同 T1），POST Content-Type: application/x-protobuf
  2. Protobuf 消息 4 个字段:
     - field 1: page (varint)
     - field 2: ROT3(challenge_type) (string)
     - field 3: timestamp (varint)
     - field 4: md_sign.OooO(timestamp_str) (32-char hex)
  3. 签名算法: 3 轮魔改 MD5
     - Round 1: F(x,y,z) = (~x&z)|(y&x), shifts 3,7,11,19
     - Round 2: G(x,y,z) = (x&y)|(x&z)|(y&z), +0x5A827999, shifts 3,5,9,13
     - Round 3: H(x,y,z) = x^y^z, +0x6ED9EBA1, shifts 3,9,11,15
     - 初始值: A=0x67452301 B=0xEFCDAB89 C=0x98BADCFE D=0x10325476
     - 填充: 标准 MD5/SHA1 padding (0x80 + 0x00 + 64-bit length)
     - 输入: timestamp.toString() 的字符串，字符按 int 值处理

用法:
  export SPIDERDEMO_COOKIE="sessionid=xxxx"
  python spiderdemo/t3_protobuf_challenge.py
"""

import os
import sys
import time

import httpx

HOST = "spiderdemo.cn"
CHALLENGE_TYPE = "protobuf_challenge"
TOTAL_PAGES = 100

COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)


# ============================================================
# 魔改 MD5 签名 (md_sign.OooO 的 Python 实现)
# ============================================================

def _rot(x, n):
    """32-bit 循环左移 (逻辑移位)"""
    return ((x << n) | ((x & 0xFFFFFFFF) >> (32 - n))) & 0xFFFFFFFF


def _round1(a, b, c, d, k, s):
    return _rot((a + ((~b & d) | (c & b)) + k) & 0xFFFFFFFF, s)


def _round2(a, b, c, d, k, s):
    return _rot((a + ((b & c) | (b & d) | (c & d)) + k + 0x5A827999) & 0xFFFFFFFF, s)


def _round3(a, b, c, d, k, s):
    return _rot((a + (b ^ c ^ d) + k + 0x6ED9EBA1) & 0xFFFFFFFF, s)


def md_sign_ooo(input_str):
    """
    md_sign.OooO 的 Python 实现
    输入: 字符串 (timestamp.toString())
    输出: 32 字符 hex string
    """
    # padMessage: 将字符串的每个字符按 int 值处理
    chars = [int(c) for c in input_str]
    bits = len(chars) * 8
    padded = chars + [0x80]
    while ((len(padded) * 8) + 64) % 512 != 0:
        padded.append(0)
    # JS >>> 对 ≥32 的移位会取模 32，i*8 = 32 → >>> 32 ≡ >>> 0
    # Python >> 没有这个行为，需手动模拟
    for i in range(8):
        shift = (i * 8) % 32  # JS 的 >>> 只取低 5 位
        padded.append((bits >> shift) & 0xFF)

    A, B, C, D = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476

    for block in range(len(padded) // 64):
        M = [0] * 16
        for i in range(16):
            offset = block * 64 + i * 4
            M[i] = (padded[offset] & 0xFF) | ((padded[offset + 1] & 0xFF) << 8) | \
                   ((padded[offset + 2] & 0xFF) << 16) | ((padded[offset + 3] & 0xFF) << 24)

        AA, BB, CC, DD = A, B, C, D

        # Round 1 (shifts: 3,7,11,19)
        AA = _round1(AA, BB, CC, DD, M[0],  3); DD = _round1(DD, AA, BB, CC, M[1],  7)
        CC = _round1(CC, DD, AA, BB, M[2], 11); BB = _round1(BB, CC, DD, AA, M[3], 19)
        AA = _round1(AA, BB, CC, DD, M[4],  3); DD = _round1(DD, AA, BB, CC, M[5],  7)
        CC = _round1(CC, DD, AA, BB, M[6], 11); BB = _round1(BB, CC, DD, AA, M[7], 19)
        AA = _round1(AA, BB, CC, DD, M[8],  3); DD = _round1(DD, AA, BB, CC, M[9],  7)
        CC = _round1(CC, DD, AA, BB, M[10], 11); BB = _round1(BB, CC, DD, AA, M[11], 19)
        AA = _round1(AA, BB, CC, DD, M[12], 3); DD = _round1(DD, AA, BB, CC, M[13], 7)
        CC = _round1(CC, DD, AA, BB, M[14], 11); BB = _round1(BB, CC, DD, AA, M[15], 19)

        # Round 2 (shifts: 3,5,9,13)
        AA = _round2(AA, BB, CC, DD, M[0],  3); DD = _round2(DD, AA, BB, CC, M[4],  5)
        CC = _round2(CC, DD, AA, BB, M[8],  9); BB = _round2(BB, CC, DD, AA, M[12], 13)
        AA = _round2(AA, BB, CC, DD, M[1],  3); DD = _round2(DD, AA, BB, CC, M[5],  5)
        CC = _round2(CC, DD, AA, BB, M[9],  9); BB = _round2(BB, CC, DD, AA, M[13], 13)
        AA = _round2(AA, BB, CC, DD, M[2],  3); DD = _round2(DD, AA, BB, CC, M[6],  5)
        CC = _round2(CC, DD, AA, BB, M[10], 9); BB = _round2(BB, CC, DD, AA, M[14], 13)
        AA = _round2(AA, BB, CC, DD, M[3],  3); DD = _round2(DD, AA, BB, CC, M[7],  5)
        CC = _round2(CC, DD, AA, BB, M[11], 9); BB = _round2(BB, CC, DD, AA, M[15], 13)

        # Round 3 (shifts: 3,9,11,15)
        AA = _round3(AA, BB, CC, DD, M[0],  3); DD = _round3(DD, AA, BB, CC, M[8],  9)
        CC = _round3(CC, DD, AA, BB, M[4], 11); BB = _round3(BB, CC, DD, AA, M[12], 15)
        AA = _round3(AA, BB, CC, DD, M[2],  3); DD = _round3(DD, AA, BB, CC, M[10], 9)
        CC = _round3(CC, DD, AA, BB, M[6], 11); BB = _round3(BB, CC, DD, AA, M[14], 15)
        AA = _round3(AA, BB, CC, DD, M[1],  3); DD = _round3(DD, AA, BB, CC, M[9],  9)
        CC = _round3(CC, DD, AA, BB, M[5], 11); BB = _round3(BB, CC, DD, AA, M[13], 15)
        AA = _round3(AA, BB, CC, DD, M[3],  3); DD = _round3(DD, AA, BB, CC, M[11], 9)
        CC = _round3(CC, DD, AA, BB, M[7], 11); BB = _round3(BB, CC, DD, AA, M[15], 15)

        A = (A + AA) & 0xFFFFFFFF
        B = (B + BB) & 0xFFFFFFFF
        C = (C + CC) & 0xFFFFFFFF
        D = (D + DD) & 0xFFFFFFFF

    result = [
        A & 0xFF, (A >> 8) & 0xFF, (A >> 16) & 0xFF, (A >> 24) & 0xFF,
        B & 0xFF, (B >> 8) & 0xFF, (B >> 16) & 0xFF, (B >> 24) & 0xFF,
        C & 0xFF, (C >> 8) & 0xFF, (C >> 16) & 0xFF, (C >> 24) & 0xFF,
        D & 0xFF, (D >> 8) & 0xFF, (D >> 16) & 0xFF, (D >> 24) & 0xFF,
    ]

    return "".join(f"{b:02x}" for b in result)


def _varint(value):
    buf = []
    while value > 0x7F:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value & 0x7F)
    return bytes(buf)


def _parse_varint(data, offset):
    value = 0
    shift = 0
    while True:
        byte = data[offset]
        value |= (byte & 0x7F) << shift
        shift += 7
        offset += 1
        if not (byte & 0x80):
            break
    return value, offset


def _parse_protobuf_response(data):
    """解析 protobuf 响应，提取数字列表"""
    offset = 0
    numbers = []
    while offset < len(data):
        tag, offset = _parse_varint(data, offset)
        field_num = tag >> 3
        wire_type = tag & 0x7

        if field_num == 1 and wire_type == 2:  # Number sub-message
            length, offset = _parse_varint(data, offset)
            end = offset + length
            val = None
            while offset < end:
                subtag, offset = _parse_varint(data, offset)
                subfield = subtag >> 3
                subwire = subtag & 0x7
                if subfield == 2 and subwire == 0:  # value
                    val, offset = _parse_varint(data, offset)
                elif subfield == 1 and subwire == 0:  # index
                    _, offset = _parse_varint(data, offset)
                else:
                    break
            if val is not None:
                numbers.append(val)
        elif wire_type == 0:  # skip other varint fields
            _, offset = _parse_varint(data, offset)
        elif wire_type == 2:  # skip other string/bytes fields
            length, offset = _parse_varint(data, offset)
            offset += length
        else:
            break
    return numbers


def build_protobuf(page, enc_type, timestamp, signature):
    buf = b""
    buf += _varint((1 << 3) | 0) + _varint(page)
    enc = enc_type.encode()
    buf += _varint((2 << 3) | 2) + _varint(len(enc)) + enc
    buf += _varint((3 << 3) | 0) + _varint(timestamp)
    sig = signature.encode()
    buf += _varint((4 << 3) | 2) + _varint(len(sig)) + sig
    return buf


def rot3(text):
    return "".join(chr(ord(c) + 3) for c in text)


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
        ("Referer", f"https://{HOST}/authentication/protobuf_challenge/"),
        ("Accept-Encoding", "gzip, deflate, br"),
        ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
        ("Cookie", cookie),
    ]
    if method == "POST":
        h = [("Content-Type", "application/x-protobuf") if k == "Accept" else (k, v) for k, v in h]
    return dict(h)


def main():
    if not COOKIE:
        print("❌ export SPIDERDEMO_COOKIE=\"sessionid=xxx\"")
        sys.exit(1)

    cookie = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    base = f"https://{HOST}"
    enc_type = rot3(CHALLENGE_TYPE)

    with httpx.Client() as client:
        r = client.get(
            f"{base}/authentication/api/protobuf_challenge/init/"
            f"?challenge_type={CHALLENGE_TYPE}",
            headers=build_headers(cookie),
        )
        data = r.json()
        if not data.get("success"):
            print(f"❌ {data.get('error', data)}")
            sys.exit(1)
        print(f"   {data.get('message', '')}")
        nums = list(data.get("page_data", []))

        print(f"\n📊 采集 {TOTAL_PAGES} 页...")
        for i in range(2, TOTAL_PAGES + 1):
            ts = int(time.time() * 1000)
            sign = md_sign_ooo(str(ts))
            body = build_protobuf(i, enc_type, ts, sign)

            r = client.post(
                f"{base}/authentication/api/protobuf_challenge/page/{i}/",
                headers=build_headers(cookie, "POST"),
                content=body,
            )
            if r.status_code != 200:
                print(f"❌ 第 {i} 页: {r.status_code} {r.text[:120]}")
                sys.exit(1)
            # 响应是 protobuf 格式，需要解码
            nums.extend(_parse_protobuf_response(r.content))
            if i % 20 == 0:
                print(f"   ✅ {i}/{TOTAL_PAGES} ({len(nums)} 个数字)")
            time.sleep(0.05)

        total = sum(nums)
        print(f"   ✅ {TOTAL_PAGES}/{TOTAL_PAGES}")
        print(f"\n📝 总和: {total:,}")

        r = client.post(
            f"{base}/authentication/api/protobuf_challenge/submit/",
            json={"challenge_type": CHALLENGE_TYPE, "answer": total},
            headers=build_headers(cookie, "POST"),
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
