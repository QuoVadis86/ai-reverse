import httpx, re, os, sys, time

HOST = "spiderdemo.cn"
CT = "CSS1_challenge"
TOTAL = 100
COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)
W = 15


def solve_number(html):
    css = {}
    for m in re.finditer(r'--([\w-]+):\s*calc\(', html):
        name = m.group(1)
        start = m.end()
        depth, pos = 1, start
        while depth > 0 and pos < len(html):
            if html[pos] == '(':
                depth += 1
            elif html[pos] == ')':
                depth -= 1
            pos += 1
        expr = html[start:pos - 1].replace('px', '').strip()
        try:
            if 'min(' in expr:
                parts = [eval(p.strip()) for p in expr[4:-1].split(',')]
                css[name] = min(parts)
            elif 'max(' in expr:
                parts = [eval(p.strip()) for p in expr[4:-1].split(',')]
                css[name] = max(parts)
            elif '-1 * var' in expr:
                inner = re.search(r'--([\w-]+)', expr)
                css[name] = -css.get(inner.group(1), 0) if inner else 0
            else:
                css[name] = eval(expr)
        except Exception:
            pass

    clean = re.sub(r'<style>.*?</style>', '', html)
    entries = []
    i = nat = 0
    while i < len(clean):
        if clean[i] == '<' and clean[i:i + 6] == '<span ':
            end = clean.index('</span>', i)
            inner = clean[clean.index('>', i) + 1:end]
            tag = clean[i:clean.index('>', i) + 1]
            offset_px = 0
            lm = re.search(r'left:\s*var\(--([\w-]+)\)', tag)
            rm = re.search(r'right:\s*var\(--([\w-]+)\)', tag)
            if lm:
                offset_px = css.get(lm.group(1), 0)
            elif rm:
                offset_px = -css.get(rm.group(1), 0)
            entries.append((inner, nat, nat * W + offset_px))
            nat += 1
            i = end + 7
        elif clean[i] == '<':
            i = clean.index('>', i) + 1
        else:
            if clean[i].isdigit():
                entries.append((clean[i], nat, nat * W))
                nat += 1
            i += 1

    entries.sort(key=lambda x: (x[2], x[1]))
    return int(''.join(d for d, _, _ in entries))


def main():
    if not COOKIE:
        print("Usage: export SPIDERDEMO_COOKIE=sessionid=xxx")
        sys.exit(1)

    cookie_str = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    headers = {"Cookie": cookie_str, "User-Agent": "Mozilla/5.0"}

    with httpx.Client() as client:
        r = client.get(
            f"https://{HOST}/css_anti/api/challenge/init/?challenge_type={CT}",
            headers=headers
        )
        nums = list(r.json()["page_data"])

        for pg in range(2, TOTAL + 1):
            r = client.get(
                f"https://{HOST}/css_anti/api/CSS1_challenge/page/{pg}/?challenge_type={CT}",
                headers=headers
            )
            for item in r.json()["page_data"]:
                nums.append(solve_number(item["display_html"]))
            if pg % 25 == 0:
                print(f"  Page {pg}: {len(nums)} numbers")
            time.sleep(0.05)

        total = sum(nums)
        print(f"Total sum: {total}")

        r = client.post(
            f"https://{HOST}/css_anti/api/challenge/submit/",
            json={"challenge_type": CT, "answer": total},
            headers={"Content-Type": "application/json", "Cookie": cookie_str}
        )
        print(f"Result: {r.json()}")


if __name__ == "__main__":
    main()
