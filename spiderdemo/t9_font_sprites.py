import httpx, re, base64, io, time, os, sys
from PIL import Image

HOST = "spiderdemo.cn"
CT = "font_sprites_challenge"
TOTAL = 100
COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)
W = 25


def build_reference(client):
    r = client.get(f"https://{HOST}/font_anti/api/{CT}/page/1/?challenge_type={CT}")
    data = r.json()
    sprite_b64 = data['sprite']
    css_code = data['css_code']
    page_data = data['page_data']

    r = client.get(f"https://{HOST}/font_anti/api/{CT}/init/?challenge_type={CT}")
    correct = r.json()['page_data']

    class_to_pos = {}
    for m in re.finditer(r'\.class(\d+)\s*\{background-position:\s*(-?\d+)px\s+0;?\}', css_code):
        class_to_pos[m.group(1)] = -int(m.group(2))

    class_to_digit = {}
    for html_str, expected in zip(page_data, correct):
        classes = re.findall(r'class(\d+)', html_str)
        for cls, digit in zip(classes, str(expected)):
            class_to_digit[cls] = digit

    sprite_img = Image.open(io.BytesIO(base64.b64decode(sprite_b64))).convert('L')
    positions = sorted(set(class_to_pos.values()))

    refs = {}
    for cls, px in class_to_pos.items():
        digit = class_to_digit[cls]
        char = sprite_img.crop((px, 2, px + W, 47))
        refs[digit] = list(char.getdata())

    return refs, positions


def decode_page(client, pg, refs, positions):
    r = client.get(f"https://{HOST}/font_anti/api/{CT}/page/{pg}/?challenge_type={CT}")
    data = r.json()

    sprite_img = Image.open(io.BytesIO(base64.b64decode(data['sprite']))).convert('L')

    class_to_pos = {}
    for m in re.finditer(r'\.class(\d+)\s*\{background-position:\s*(-?\d+)px\s+0;?\}', data['css_code']):
        class_to_pos[m.group(1)] = -int(m.group(2))

    pos_to_digit = {}
    for px in positions:
        char = sprite_img.crop((px, 2, px + W, 47))
        pixels = list(char.getdata())
        pos_to_digit[px] = min(refs, key=lambda d: sum(abs(a - b) for a, b in zip(pixels, refs[d])))

    mapping = {cls: pos_to_digit[px] for cls, px in class_to_pos.items()}

    nums = []
    for item_html in data['page_data']:
        classes = re.findall(r'class(\d+)', item_html)
        if classes:
            nums.append(int(''.join(mapping[c] for c in classes)))
        else:
            nums.append(int(''.join(re.findall(r'\d', item_html))))
    return nums


def main():
    if not COOKIE:
        print("Usage: export SPIDERDEMO_COOKIE=sessionid=xxx"); sys.exit(1)
    cookie_str = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    headers = {"Cookie": cookie_str, "User-Agent": "Mozilla/5.0"}

    with httpx.Client() as client:
        client.headers.update(headers)
        refs, positions = build_reference(client)

        r = client.get(f"https://{HOST}/font_anti/api/{CT}/init/?challenge_type={CT}")
        nums = list(r.json()['page_data'])

        for pg in range(2, TOTAL + 1):
            nums.extend(decode_page(client, pg, refs, positions))
            if pg % 25 == 0:
                print(f"  Page {pg}: {len(nums)} numbers")
            time.sleep(0.05)

        total = sum(nums)
        print(f"Total: {total}")

        r = client.post(f"https://{HOST}/font_anti/api/{CT}/submit/",
            json={"challenge_type": CT, "answer": total},
            headers={"Content-Type": "application/json"})
        print(r.json())


if __name__ == "__main__":
    main()
