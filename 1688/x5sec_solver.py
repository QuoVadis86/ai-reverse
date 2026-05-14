import hashlib, json, logging, os, re, sys, time as time_module
import random, base64, io
from typing import Optional

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from core import MTOPSession

logger = logging.getLogger("x5sec_solver")

SLIDER_W = 320
BTN_W = 48
MAX_SLIDE = SLIDER_W - BTN_W
OFFSET = 24


def trigger_x5sec(session, api, ver, data):
    resp = session.request(api, ver, data)
    if resp.success:
        return {"status": "ok", "data": resp.data}
    ret = " ".join(resp.ret)
    if "FAIL_SYS_USER_VALIDATE" not in ret:
        raise RuntimeError(f"Unexpected: {ret}")
    u = resp.raw.get("data", {}).get("url")
    if not u:
        raise RuntimeError("No punish URL")
    return {"status": "x5sec", "punish_url": u}


def get_fireye_tokens(punish_url, timeout=10):
    import requests as req
    r = req.get(punish_url, timeout=15)
    m = re.search(r'window\._config_\s*=\s*(\{[^;]+\});', r.text, re.DOTALL)
    if not m:
        raise RuntimeError("No _config_ in punish page")
    cfg = json.loads(m.group(1))

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 500, "height": 700})
        page = ctx.new_page()
        page.goto(punish_url, wait_until="networkidle", timeout=30000)
        fy = None
        for _ in range(timeout * 2):
            fy = page.evaluate("""() => {
                const f = window.FYModule;
                return f && typeof f.getFYToken === 'function'
                    ? {ua: f.getFYToken(), umid: f.getUidToken()} : null;
            }""")
            if fy:
                break
            time_module.sleep(0.5)
        cks = {c["name"]: c["value"] for c in ctx.cookies()}
        page.close()
        b.close()
    if not fy:
        raise RuntimeError("Fireye not ready")
    return {**fy, "cfg": cfg, "cookies": cks}


def get_challenge(session, base_url, token, appkey, secdata, ua):
    params = {"token": token, "appKey": appkey, "ua": ua,
              "x5secdata": secdata, "language": "cn",
              "_rand": f"r{int(time_module.time()*1000)}",
              "v": str(int(time_module.time() * 1000))}
    resp = session.http.get(f"{base_url}/newslidecaptcha", params=params, timeout=15)
    d = resp.json()
    if not d.get("success"):
        raise RuntimeError(f"newslidecaptcha: {d}")
    return d["data"]


def find_position(bg_arr, piece_arr):
    hb, wb = bg_arr.shape[:2]
    hp, wp = piece_arr.shape[:2]
    alpha = piece_arr[:, :, 3].astype(float)

    try:
        import cv2
        bg_gray = np.mean(bg_arr, axis=2).astype(np.uint8)
        piece_gray = np.mean(piece_arr[:, :, :3], axis=2).astype(np.uint8)
        mask = (alpha > 10).astype(np.uint8) * 255
        best_corr, best_x = -999, 0
        for y0 in range(0, hb - hp + 1, 10):
            res = cv2.matchTemplate(bg_gray[y0:y0+hp], piece_gray,
                                     cv2.TM_CCOEFF_NORMED, mask=mask)
            _, mv, _, ml = cv2.minMaxLoc(res)
            if mv > best_corr:
                best_corr, best_x = mv, ml[0]
    except ImportError:
        best_x = 0
        best_score = -99999
        for y0 in range(0, hb - hp + 1, 20):
            for x0 in range(0, wb - wp + 1):
                strip = bg_arr[y0:y0+hp, x0:x0+wp, :3].astype(float)
                a3 = alpha[:, :, np.newaxis] / 255.0
                score = -np.mean(np.abs((strip - piece_arr[:,:,:3].astype(float)) * a3))
                if score > best_score:
                    best_score, best_x = score, x0
    return max(0.1, min(0.92, (best_x + OFFSET) / SLIDER_W))


def gen_trace(per):
    x = per * SLIDER_W - OFFSET
    x = max(0, min(MAX_SLIDE, x))
    total_ms = int(random.uniform(200, 800) + random.uniform(500, 2500))
    pf = round((x + OFFSET + random.uniform(-2, 2)) / SLIDER_W, 3)
    return {"time": str(total_ms), "width": str(MAX_SLIDE), "per": f"{pf:.3f}"}


def submit(session, base_url, token, appkey, secdata, ua, umid, et, trace):
    params = {"token": token, "appKey": appkey, "ua": ua,
              "umidToken": umid, "encryptToken": et, "x5secdata": secdata,
              "time": trace["time"], "width": trace["width"],
              "per": trace["per"],
              "_rand": f"r{int(time_module.time()*1000)}",
              "v": str(int(time_module.time() * 1000))}
    resp = session.http.get(f"{base_url}/newslidevalidate", params=params, timeout=15)
    return {"code": resp.json().get("code"),
            "result_code": resp.json().get("result", {}).get("code"),
            "bx_x5sec": resp.headers.get("bx-x5sec", "")}


def solve(api="mtop.1688.laputa.miniod", ver="1.0", data=None):
    if data is None:
        data = {"sk": "", "offerId": 849246166605,
                "parametersMap": '{"fromPC":true}'}

    session = MTOPSession()
    if not session.login():
        raise RuntimeError("login failed")
    print(f"token: {session._token[:16]}...")

    result = trigger_x5sec(session, api, ver, data)
    if result["status"] == "ok":
        return {"success": True, "data": result["data"]}
    pu = result["punish_url"]
    print(f"punish: {pu[:80]}...")

    fb = get_fireye_tokens(pu)
    ua = fb["ua"]; umid = fb["umid"]; cfg = fb["cfg"]
    print(f"Fireye ua: {ua[:40]}...")

    fa = cfg["FORMACTIOIN"].rstrip("/")
    if fa.endswith("/verify"):
        fa = fa[:-7]
    base_url = f"https://h5api.m.1688.com{fa}"

    ch = get_challenge(session, base_url, cfg["NCTOKENSTR"],
                       cfg["NCAPPKEY"], cfg["SECDATA"], ua)
    et = ch["encryptToken"]
    print(f"encryptToken: {et[:40]}...")

    bg = np.array(Image.open(io.BytesIO(base64.b64decode(ch["imageData"].split(",")[1]))))
    piece = np.array(Image.open(io.BytesIO(base64.b64decode(ch["ques"].split(",")[1]))))

    per = find_position(bg, piece)
    print(f"found per={per:.4f}")

    candidates = [per]
    for d in [-0.03, -0.02, -0.01, 0.01, 0.02, 0.03]:
        p = per + d
        if 0.1 <= p <= 0.92 and p not in candidates:
            candidates.append(p)

    bx = ""
    for i, p in enumerate(candidates):
        t = gen_trace(p)
        r = submit(session, base_url, cfg["NCTOKENSTR"], cfg["NCAPPKEY"],
                   cfg["SECDATA"], ua, umid, et, t)
        ok = " ✓" if r["bx_x5sec"] else ""
        print(f"  [{i+1}/{len(candidates)}] per={t['per']} -> code={r['code']} rc={r['result_code']}{ok}")
        if r["bx_x5sec"]:
            bx = r["bx_x5sec"]
            break
        time_module.sleep(0.3)

    if not bx:
        raise RuntimeError("All per values rejected")

    session.http.cookies.set("x5sec", bx, domain="h5api.m.1688.com", path="/")
    for n, v in fb.get("cookies", {}).items():
        if n in ("_m_h5_tk", "_m_h5_tk_enc", "isg"):
            session.http.cookies.set(n, v, domain=".1688.com", path="/")

    retry = session.request(api, ver, data)
    print(f"retry: {'ok' if retry.success else 'fail'} {retry.ret}")
    return {"success": retry.success, "data": retry.data, "x5sec": bx}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    r = solve()
    print(f"\n{'='*40}\nsuccess: {r.get('success')}")
