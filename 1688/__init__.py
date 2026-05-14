"""
1688 MTOP API SDK
=================
基于逆向工程分析的 1688.com MTOP 网关签名算法封装。

核心能力：
  - MTOP 签名算法 (MD5)
  - Session/Cookie 管理
  - Token 自动获取与刷新
  - 1688 业务 API 封装

使用方式：
  from h5api_sdk import Alibaba1688Client

  client = Alibaba1688Client()
  client.login()  # 首次需获取 token

  # 获取商品详情
  detail = client.get_offer_detail(849246166605)
  print(detail["productTitle"]["fields"]["title"])
"""

from .core import MTOPSession, MTOPAuthError, MTOPError
from .client import Alibaba1688Client

__all__ = ["MTOPSession", "Alibaba1688Client", "MTOPAuthError", "MTOPError"]
