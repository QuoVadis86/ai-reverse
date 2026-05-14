"""
MTOP protocol implementation.

Reverse engineered from lib-mtop.js (v2.7.4):
  sign = MD5(token + "&" + ts + "&" + appKey + "&" + data)
  gateway: https://h5api.m.1688.com/h5/{api}/{version}/
"""

import hashlib, json, logging, re, time
from dataclasses import dataclass
from typing import Any, Optional

import requests

logger = logging.getLogger("mtop")

_M_H5_TK_RE = re.compile(r"_m_h5_tk=([^;]+)")


@dataclass
class MTOPResponse:
    api: str
    version: str
    data: Any
    raw: dict
    ret: list[str]
    trace_id: str
    success: bool

    @classmethod
    def from_json(cls, raw: dict) -> "MTOPResponse":
        ret = raw.get("ret", [])
        if isinstance(ret, str):
            ret = [ret]
        ok = "SUCCESS" in " ".join(ret)
        return cls(
            api=raw.get("api", ""),
            version=raw.get("v", ""),
            data=raw.get("data"),
            raw=raw, ret=ret,
            trace_id=raw.get("traceId", ""),
            success=ok,
        )


class MTOPSession:

    BASE_URL = "https://h5api.m.1688.com/h5"
    APP_KEY = "12574478"
    UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/148.0.0.0 Safari/537.36")

    def __init__(self):
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": self.UA,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://detail.1688.com",
            "Referer": "https://detail.1688.com/",
        })
        self._token = None

    # ── token ──

    def login(self) -> bool:
        """Get _m_h5_tk from server. No cookie needed.

        Call any MTOP API with token="undefined" in the sign.
        Server returns Set-Cookie with a real token.
        """
        ts = str(int(time.time() * 1000))
        raw = f"undefined&{ts}&{self.APP_KEY}&{{}}"
        sign = hashlib.md5(raw.encode()).hexdigest()

        try:
            r = self.http.post(
                f"{self.BASE_URL}/mtop.1688.moga.pc.shopcard/1.0/",
                params={"jsv":"2.7.4","appKey":self.APP_KEY,"t":ts,"sign":sign,
                        "api":"mtop.1688.moga.pc.shopcard","v":"1.0",
                        "type":"originaljson","dataType":"jsonp","timeout":"20000"},
                data={"data":"{}"},
                timeout=15,
            )
        except Exception:
            return False

        for c in r.cookies:
            if c.name == "_m_h5_tk":
                self._token = c.value.split("_")[0]
                return True

        m = _M_H5_TK_RE.search(r.headers.get("Set-Cookie", ""))
        if m:
            self._token = m.group(1).split("_")[0]
            return True

        return False

    def set_cookie(self, s: str):
        """Manually set cookie from browser."""
        m = _M_H5_TK_RE.search(s)
        if m:
            self._token = m.group(1).split("_")[0]
            for part in s.split(";"):
                p = part.strip()
                if "=" in p:
                    k, v = p.split("=", 1)
                    self.http.cookies.set(k.strip(), v.strip())

    def _update_token(self):
        for c in self.http.cookies:
            if c.name == "_m_h5_tk":
                self._token = c.value.split("_")[0]
                return

    @property
    def has_token(self):
        return self._token is not None

    # ── sign & request ──

    def _sign(self, token: str, ts: str, data: str) -> str:
        return hashlib.md5(f"{token}&{ts}&{self.APP_KEY}&{data}".encode()).hexdigest()

    def request(
        self,
        api: str,
        version: str = "1.0",
        data: Optional[dict] = None,
        method: str = "POST",
        extra_params: Optional[dict] = None,
        max_retries: int = 3,
    ) -> MTOPResponse:
        if not self._token:
            raise MTOPAuthError("no token, call login() first")

        ts = str(int(time.time() * 1000))
        ds = json.dumps(data, separators=(",", ":")) if data else "{}"
        sign = self._sign(self._token, ts, ds)

        params = {
            "jsv":"2.7.4","appKey":self.APP_KEY,"t":ts,"sign":sign,
            "api":api,"v":version,
            "type":"originaljson","dataType":"jsonp","timeout":"20000","_bx-login":"new",
        }
        if extra_params:
            params.update(extra_params)

        url = f"{self.BASE_URL}/{api.lower()}/{version.lower()}/"

        if method == "POST":
            resp = self.http.post(url, params=params, data={"data": ds}, timeout=30)
        else:
            params["data"] = ds
            resp = self.http.get(url, params=params, timeout=30)

        self._update_token()

        mtop_resp = MTOPResponse.from_json(resp.json())
        if mtop_resp.success:
            return mtop_resp

        ret = " ".join(mtop_resp.ret)
        if any(k in ret for k in ("TOKEN_EMPTY", "TOKEN_EXOIRED", "ILLEGAL_ACCESS")):
            if max_retries > 0:
                logger.warning("token expired, retrying (%s left)", max_retries)
                if self.login():
                    return self.request(api, version, data, method, extra_params, max_retries - 1)
            raise MTOPAuthError(f"token refresh failed: {ret}")

        return mtop_resp


class MTOPError(Exception):
    pass

class MTOPAuthError(MTOPError):
    pass
