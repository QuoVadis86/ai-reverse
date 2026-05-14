"""
MTOP 协议核心实现
=================
基于 lib-mtop.js 逆向分析 (v2.7.4):
  - 签名算法: MD5(token & "&" & timestamp & "&" & appKey & "&" & data)
  - Token 来源: _m_h5_tk cookie (服务端 Set-Cookie)
  - 网关: https://h5api.m.1688.com/h5/{api}/{version}/
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

logger = logging.getLogger("mtop_sdk")


class MTOPError(Exception):
    """MTOP API 调用错误"""

class MTOPAuthError(MTOPError):
    """认证/Token 相关错误"""


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
        ret_str = " ".join(ret)
        return cls(
            api=raw.get("api", ""),
            version=raw.get("v", ""),
            data=raw.get("data"),
            raw=raw,
            ret=ret,
            trace_id=raw.get("traceId", ""),
            success="SUCCESS" in ret_str,
        )


class MTOPSession:
    """MTOP API 会话

    - 管理 _m_h5_tk token
    - 实现 MTOP 签名算法
    - 自动处理 token 过期刷新
    """

    BASE_URL = "https://h5api.m.1688.com/h5"
    APP_KEY = "12574478"
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://detail.1688.com",
        "Referer": "https://detail.1688.com/",
    }

    def __init__(self, cookie_str: Optional[str] = None):
        self.http = requests.Session()
        self.http.headers.update(self.DEFAULT_HEADERS)

        self._token: Optional[str] = None
        self._cookie_str = cookie_str

        if cookie_str:
            # 从已有 cookie 中提取 token
            self._token = self._extract_token(cookie_str)

    # ------------------------------------------------------------------
    # Token 管理
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_token(cookie_str: str) -> Optional[str]:
        m = _M_H5_TK_RE.search(cookie_str)
        if not m:
            return None
        raw = m.group(1)
        return raw.split("_")[0]

    def _token_from_session(self) -> Optional[str]:
        for cookie in self.http.cookies:
            if cookie.name == "_m_h5_tk":
                return cookie.value.split("_")[0]
        return None

    def login(self) -> bool:
        """访问 1688.com 首页获取 _m_h5_tk cookie (服务端 Set-Cookie)"""
        logger.info("正在访问 1688.com 获取 token ...")
        resp = self.http.get(
            "https://www.1688.com/",
            headers={
                "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=15,
        )
        token = self._token_from_session()
        if token:
            self._token = token
            logger.info("token 获取成功")
            return True

        # 部分场景下 Set-Cookie 在 302 跳转中，再试一次
        for resp in resp.history:
            set_cookie = resp.headers.get("Set-Cookie", "")
            t = self._extract_token(set_cookie)
            if t:
                self._token = t
                # 同步到 session
                self.http.cookies.set("_m_h5_tk", set_cookie.split(";")[0].split("=", 1)[1])
                logger.info("token 获取成功 (from redirect)")
                return True

        logger.warning("token 获取失败，需手动提供 cookie")
        return False

    def set_cookie(self, cookie_str: str):
        """手动设置 cookie (从浏览器复制)"""
        self._cookie_str = cookie_str
        self._token = self._extract_token(cookie_str)
        if self._token:
            # 解析并设置所有 cookie
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    name, value = part.split("=", 1)
                    self.http.cookies.set(name.strip(), value.strip())

    @property
    def has_token(self) -> bool:
        return self._token is not None

    # ------------------------------------------------------------------
    # 签名 & 请求
    # ------------------------------------------------------------------

    def _sign(self, token: str, timestamp: str, data_str: str) -> str:
        raw = f"{token}&{timestamp}&{self.APP_KEY}&{data_str}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def request(
        self,
        api: str,
        version: str = "1.0",
        data: Optional[dict] = None,
        method: str = "POST",
        extra_params: Optional[dict] = None,
    ) -> MTOPResponse:
        """发送 MTOP API 请求

        Args:
            api: MTOP API 名称, 如 "mtop.1688.mmga.offerdetail.service"
            version: API 版本号
            data: 请求数据 (dict, 会自动 JSON 序列化)
            method: "POST" 或 "GET"
            extra_params: 额外的 URL query 参数
        """
        if not self._token:
            raise MTOPAuthError("缺少 token, 请先调用 login() 或 set_cookie()")

        timestamp = str(int(time.time() * 1000))
        data_str = json.dumps(data, separators=(",", ":")) if data else "{}"
        sign = self._sign(self._token, timestamp, data_str)

        params = {
            "jsv": "2.7.4",
            "appKey": self.APP_KEY,
            "t": timestamp,
            "sign": sign,
            "api": api,
            "v": version,
            "type": "originaljson",
            "dataType": "jsonp",
            "timeout": "20000",
            "_bx-login": "new",
        }
        if extra_params:
            params.update(extra_params)

        url = f"{self.BASE_URL}/{api.lower()}/{version.lower()}/"

        logger.debug("请求 %s | data=%s", api, data_str[:200])

        if method == "POST":
            body = {"data": data_str}
            resp = self.http.post(url, params=params, data=body, timeout=30)
        else:
            params["data"] = data_str
            resp = self.http.get(url, params=params, timeout=30)

        result = resp.json()
        mtop_resp = MTOPResponse.from_json(result)

        # 检查 token 错误 → 自动重试一次
        if not mtop_resp.success:
            ret_text = " ".join(mtop_resp.ret)
            if any(kw in ret_text for kw in ("TOKEN_EMPTY", "TOKEN_EXOIRED", "ILLEGAL_ACCESS")):
                logger.warning("token 过期, 尝试刷新 ...")
                if self.login():
                    return self.request(api, version, data, method, extra_params)
                raise MTOPAuthError(f"token 刷新失败: {ret_text}")

        return mtop_resp
