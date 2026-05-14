# ai-reverse / 1688

1688.com MTOP API 逆向分析与 Python SDK。

基于对 `lib-mtop.js` (v2.7.4) 的逆向分析，完整还原了 MTOP 网关的签名算法与请求流程。

## 目录结构

```
ai-reverse/
├── 1688/                    # 1688 MTOP SDK
│   ├── __init__.py          # 包入口
│   ├── core.py              # MTOP 核心 (签名/会话/请求)
│   └── client.py            # 业务 API 封装 (13个方法)
├── requirements.txt
└── README.md
```

## SDK 使用

```python
from sdk import Alibaba1688Client  # 见下方导入说明

client = Alibaba1688Client()

# 首次使用：从浏览器复制 cookie 注入
client.session.set_cookie("_m_h5_tk=xxx...; _m_h5_tk_enc=xxx...")

# 获取商品全量数据
detail = client.get_offer_detail(849246166605)
print(detail["offerDetail"]["subject"])  # 标题

# 获取 SKU 价格
from core import MTOPSession
mp = detail["dataModel"]["mainPrice"]["fields"]
for sku in mp["finalPriceModel"]["tradeWithoutPromotion"]["skuMapOriginal"]:
    print(f'{sku["specAttrs"]}: ¥{sku["price"]}')
```

## 导入方式

```python
# 方式 1: 作为包导入
import sys
sys.path.insert(0, "~/Desktop/ai-reverse")
import importlib
spec = importlib.util.spec_from_file_location("sdk", "1688/__init__.py")
sdk = importlib.util.module_from_spec(spec)
sys.modules["sdk"] = spec.loader.exec_module(sdk)
from sdk import Alibaba1688Client

# 方式 2: 直接 import (从 1688/ 目录下运行)
from client import Alibaba1688Client
```

## API 列表

| 方法 | 说明 |
|---|---|
| `get_offer_detail(offer_id)` | 商品详情 (miniod API, 全量数据) |
| `get_offer_detail_from_html(offer_id)` | 商品详情 (HTML 解析, 备用) |
| `get_offer_recommendations(offer_id)` | 推荐商品 |
| `get_offer_logistics(offer_id, ...)` | 物流配送时效 |
| `get_shop_card(offer_id, ...)` | 店铺卡片 |
| `get_shop_header(member_id)` | 店铺头部 |
| `get_shop_certification(member_id)` | 店铺认证 |
| `get_ratings(offer_id)` | 评价列表 |
| `get_dsr_ratings(offer_id)` | DSR 评分 |
| `get_freight_info(offer_id)` | 运费信息 |
| `get_fulfillment_solution(offer_id)` | 履约方案 |
| `check_shop_relation(shop_login_id)` | 店铺关注状态 |
| `get_user_simple()` | 用户信息 |

## MTOP 签名算法

```python
sign = MD5(token + "&" + timestamp + "&" + appKey + "&" + data)
# token: _m_h5_tk cookie 中 _ 左边的部分
# timestamp: 当前时间毫秒数
# appKey: 12574478
# data: JSON.stringify(requestPayload)
```
