"""
摘要算法 (Hash Challenge) - 简单
----------------------------------------
使用 HMAC-SHA256 + MD5 + SHA256 + SHA3-256 四种签名
请求需要: X-Request-Token, X-Verify-Code, sign, code, t 参数

用法:
  export SPIDERDEMO_COOKIE="sessionid=xxxx"
  python spiderdemo/t_hash_challenge.py
"""
import hashlib, hmac, os, sys, time
import httpx

HOST = "spiderdemo.cn"; CT = "hash_challenge"; TOTAL = 100
COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)

def sig(page, ts):
    d = f"{page}_{CT}_{ts}"
    return (
        hmac.new(b"spiderdemo_hmac_secret_2025", d.encode(), hashlib.sha256).hexdigest(),
        hashlib.md5((d + "spiderdemo_md5_salt_2025").encode()).hexdigest(),
        hashlib.sha256((d + "spiderdemo_sha_salt_2025").encode()).hexdigest(),
        hashlib.sha3_256((d + "spiderdemo_sha_salt_2025").encode()).hexdigest(),
    )

def bh(cookie):
    return {"Host": HOST, "sec-ch-ua": '"Chromium";v="148"...',
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*", "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://{HOST}/authentication/{CT}/", "Cookie": cookie}

def main():
    if not COOKIE: print("export SPIDERDEMO_COOKIE=..."); sys.exit(1)
    ck = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    with httpx.Client() as cl:
        h = bh(ck); r = cl.get(f"https://{HOST}/authentication/api/{CT}/init/?challenge_type={CT}", headers=h)
        nums = list(r.json()['page_data'])
        for i in range(2, TOTAL+1):
            ts = str(int(time.time() * 1000))
            hm, md, sh, s3 = sig(i, ts)
            h["X-Request-Token"] = hm; h["X-Verify-Code"] = md
            r = cl.get(f"https://{HOST}/authentication/api/{CT}/page/{i}/?challenge_type={CT}&sign={sh}&code={s3}&t={ts}", headers=h)
            nums.extend(r.json()['page_data'])
            if i % 25 == 0: print(f"  {i}/{TOTAL} ({len(nums)})")
            time.sleep(0.05)
        total = sum(nums); print(f"Total: {total}")
        r = cl.post(f"https://{HOST}/authentication/api/{CT}/submit/", json={"challenge_type": CT, "answer": total},
                    headers={"Content-Type": "application/json", "Cookie": ck})
        print("OK" if r.json().get("is_correct") else f"FAIL: {r.json()}")

if __name__ == "__main__": main()
