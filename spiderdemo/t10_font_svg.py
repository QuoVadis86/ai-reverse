import httpx, re, io, os, sys, time
from PIL import Image, ImageOps
import cairosvg
from collections import defaultdict

HOST = "spiderdemo.cn"
CT = "font_svg_challenge"
TOTAL = 100
COOKIE = os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv) > 1 else None)

"""
T10-SVG字体反爬 - 分析笔记
=========================
API 返回 40 个 SVG <path> 元素（无 page_data），每 4 个组成一个 4 位数，
共 10 个数。每个 path 渲染一个数字，使用自定义 OCR 抗性字体。

尝试过的方案:
  1. pytesseract 直接 OCR → 全部识别为同一数字（字体抗 OCR）
  2. 像素聚类 → 特征不够区分（字体设计近似）
  3. 坐标特征分析 → 精度不够

可能解法:
  A. 用 fontTools 提取 T8 字体轮廓，与 SVG path 坐标做匹配
  B. 训练 CNN 分类器（每页可自生成 40 个 labeled 样本）
  C. Playwright 渲染 Canvas 后读像素
"""


def render_full_svg(svg_content, scale=4.0):
    return cairosvg.svg2png(bytestring=svg_content.encode(), scale=scale)


def extract_transform_positions(svg_content):
    transforms = re.findall(r'translate\(([^,]+),\s*([^)]+)\)\s*scale\(([^)]+)\)', svg_content)
    return [(float(t[0]), float(t[1]), float(t[2])) for t in transforms]


def main():
    if not COOKIE:
        print("Usage: export SPIDERDEMO_COOKIE=sessionid=xxx")
        sys.exit(1)

    cookie_str = COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
    headers = {"Cookie": cookie_str, "User-Agent": "Mozilla/5.0"}

    with httpx.Client() as client:
        client.headers.update(headers)

        r = client.get(f"https://{HOST}/font_anti/api/{CT}/page/1/?challenge_type={CT}")
        svg = r.json()['svg_content']

        png_data = render_full_svg(svg, scale=5.0)
        img = Image.open(io.BytesIO(png_data)).convert('L')
        inv = ImageOps.invert(img)

        transforms = extract_transform_positions(svg)
        scale_factor = 5.0

        results = []
        for i, (x, y, sc) in enumerate(transforms):
            px = int(x * scale_factor)
            left = max(0, px - 3)
            right = min(inv.width, px + int(13 * scale_factor))
            crop = inv.crop((left, 0, right, inv.height))
            crop.save(f"/tmp/t10_digit_{i}.png")

        print(f"Extracted {len(transforms)} digit images to /tmp/t10_digit_*.png")
        print("Need digit classifier to recognize the custom SVG font")


if __name__ == "__main__":
    main()
