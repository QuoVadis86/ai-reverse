import httpx, base64, os, sys, time
import ddddocr

HOST = "spiderdemo.cn"
CT = "cap2_challenge"
TOTAL = 100
COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)
MAX_ATTEMPTS = 60

ocr = ddddocr.DdddOcr()


def solve_page(client, pg):
    for _ in range(MAX_ATTEMPTS):
        ts = int(time.time() * 1000)
        r = client.get(f"https://{HOST}/captcha/api/{CT}/captcha_image/?t={ts}")
        data = r.json()
        text = ocr.classification(base64.b64decode(data['T']))
        if text and len(text) >= 3:
            r = client.post(f"https://{HOST}/captcha/api/{CT}/page/",
                json={"captcha_input": text, "page_num": pg, "challenge_type": CT})
            resp = r.json()
            if 'page_data' in resp and resp['page_data']:
                return resp['page_data']
    return None


def main():
    if not COOKIE:
        print("Usage: export SPIDERDEMO_COOKIE=sessionid=xxx")
        sys.exit(1)
    cookie_str = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    headers = {"Cookie": cookie_str, "User-Agent": "Mozilla/5.0"}
    with httpx.Client() as client:
        client.headers.update(headers)
        r = client.get(f"https://{HOST}/captcha/api/{CT}/init/?challenge_type={CT}")
        nums = list(r.json()['page_data'])
        print(f"Page 1 init: {len(nums)} numbers")
        for pg in range(2, TOTAL + 1):
            data = solve_page(client, pg)
            if data:
                nums.extend(data)
            else:
                print(f"  Page {pg}: FAILED after {MAX_ATTEMPTS} attempts")
            if pg % 10 == 0:
                print(f"  Page {pg}: {len(nums)} numbers")
            time.sleep(0.3)
        total = sum(nums)
        print(f"Total: {len(nums)} numbers, sum={total}")
        r = client.post(f"https://{HOST}/captcha/api/{CT}/submit/",
            json={"challenge_type": CT, "answer": total},
            headers={"Content-Type": "application/json"})
        print(f"Result: {r.json()}")


if __name__ == "__main__":
    main()
