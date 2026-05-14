import json, logging, os, re, sys, time
import hashlib, base64, io

sys.path.insert(0, os.path.dirname(__file__))
from core import MTOPSession

logger = logging.getLogger("x5sec_solver")

SLIDER_W = 320
BTN_W = 48
MAX_SLIDE = SLIDER_W - BTN_W
OFFSET = 24


def solve(api="mtop.1688.laputa.miniod", ver="1.0", data=None):
    if data is None:
        data = {"sk": "", "offerId": 849246166605,
                "parametersMap": '{"fromPC":true}'}

    session = MTOPSession()
    if not session.login():
        raise RuntimeError("login failed")
    print(f"token: {session._token[:16]}...")

    r = session.request(api, ver, data)
    if r.success:
        return {"success": True, "data": r.data}
    ret = " ".join(r.ret)
    if "FAIL_SYS_USER_VALIDATE" not in ret:
        raise RuntimeError(f"Unexpected: {ret}")
    punish_url = r.raw.get("data", {}).get("url")
    if not punish_url:
        raise RuntimeError("No punish URL")
    print(f"punish: ...{punish_url[-60:]}")

    from playwright.sync_api import sync_playwright
    bx_x5sec = None
    cookie_jar = {}

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=False)
        ctx = b.new_context(viewport={"width": 500, "height": 700})
        page = ctx.new_page()

        def on_response(resp):
            nonlocal bx_x5sec
            if "newslidevalidate" in resp.url:
                bx = resp.headers.get("bx-x5sec", "")
                if bx:
                    bx_x5sec = bx

        page.on("response", on_response)
        page.goto(punish_url, wait_until="networkidle", timeout=30000)

        for _ in range(40):
            ok = page.evaluate(
                "() => !!(document.getElementById('scratch-captcha-btn') && window.FYModule)"
            )
            if ok:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Captcha not ready")

        print("Browser opened. Captcha loaded. Drag will start in 5 seconds...")
        time.sleep(5)

        print("Dragging slider...")
        page.evaluate("""async () => {
            const btn = document.getElementById('scratch-captcha-btn');
            const slider = document.querySelector('.scratch-captcha-slider');
            const br = btn.getBoundingClientRect();
            const sr = slider.getBoundingClientRect();
            const sx = br.x + br.width/2, sy = br.y + br.height/2;
            const ex = sr.x + sr.width - 10, ey = sy;

            btn.dispatchEvent(new PointerEvent('pointerdown', {
                bubbles: true, clientX: sx, clientY: sy
            }));
            await new Promise(r => setTimeout(r, 300 + Math.random()*200));

            const steps = 15 + Math.floor(Math.random() * 8);
            for (let i = 1; i <= steps; i++) {
                const t = i / steps;
                const x = sx + (ex - sx) * t;
                const y = sy + (Math.random()-0.5) * 4;
                document.dispatchEvent(new PointerEvent('pointermove', {
                    bubbles: true, clientX: x, clientY: y
                }));
                await new Promise(r => setTimeout(r, 100 + Math.random()*80));
            }
            await new Promise(r => setTimeout(r, 200));
            document.dispatchEvent(new PointerEvent('pointerup', {
                bubbles: true, clientX: ex, clientY: ey
            }));
        }""")

        print("Waiting for captcha response...")
        time.sleep(5)

        for c in ctx.cookies():
            cookie_jar[c["name"]] = c["value"]
        page.close()
        b.close()

    if not bx_x5sec:
        raise RuntimeError("No bx-x5sec received (slider position rejected)")

    session.http.cookies.set("x5sec", bx_x5sec,
                              domain="h5api.m.1688.com", path="/")
    for n in ("_m_h5_tk", "_m_h5_tk_enc", "isg"):
        if n in cookie_jar:
            session.http.cookies.set(n, cookie_jar[n],
                                      domain=".1688.com", path="/")

    m_h5 = cookie_jar.get("_m_h5_tk", "")
    if m_h5:
        session._token = m_h5.split("_")[0]

    retry = session.request(api, ver, data)
    print(f"retry: {retry.ret}")
    return {"success": retry.success, "data": retry.data, "x5sec": bx_x5sec, "cookies": cookie_jar}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    res = solve()
    print(f"\n{'='*40}")
    print(f"success: {res.get('success')}")
