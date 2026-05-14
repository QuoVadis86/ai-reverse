"""
1688 业务 API 封装
==================
基于 MTOP Core SDK 的各业务接口。

API 列表:
  - 商品详情 (mtop.1688.laputa.miniod) — 一次调用获取全量数据
  - 物流/配送信息 (mmga offerLogisticsService)
  - 推荐商品 (mmga offerRecommendService)
  - 店铺卡片 (moga.pc.shopcard)
  - 评价/DSR 数据 (trade.service.MtopRateService)
  - 运费查询 (freightInfoService)
  - 履约方案 (carriageCenter)
"""

import json
import logging
from typing import Any, Optional

try:
    from .core import MTOPSession, MTOPResponse
except ImportError:
    from core import MTOPSession, MTOPResponse

logger = logging.getLogger("mtop_client")


class Alibaba1688Client:
    """1688 MTOP API 业务客户端"""

    def __init__(self, session: Optional[MTOPSession] = None):
        self.session = session or MTOPSession()

    # ==============================================================
    # 商品详情 (miniod API — 推荐方式)
    # ==============================================================

    def get_offer_detail(self, offer_id: int) -> dict:
        """获取商品详情全量数据 (MTOP API, 无需解析 HTML)

        调用 mtop.1688.laputa.miniod，返回结构化商品数据。

        返回 dict 包含:
          offerDetail (model.offerModel.offerDetail):
            - subject: 标题
            - status: 状态 (PUBLISHED)
            - imageList / mainImageList: 图片列表
            - skuProps: SKU 规格属性
            - featureAttributes: 商品属性 (品牌/产地/货号等)
            - offerSystemAttributes: 系统时间 (创建/修改/过期)
            - wirelessVideo: 视频信息
            - offerSign: 商品标识 (是否含SKU/预售/分销等)
            - topCategoryId / leafCategoryId / leafCategoryName: 类目

          dataModel (model.dataModel = 同 SSR window.context):
            - productTitle: 标题、店铺、评价统计
            - mainPrice: 价格区间、SKU 级价格库存
            - gallery: 商品主图、视频
            - skuSelection: SKU 选择器
            - productPackInfo: 件重尺信息
            - shippingServices: 买家保障/配送
            - productEvaluation: 评价标签
            - promotionBanner / discountCoupon: 促销/优惠券
            - description: 详情页 URL
        """
        data = {
            "sk": "",
            "offerId": offer_id,
            "parametersMap": json.dumps({"fromPC": True}),
        }
        resp = self.session.request("mtop.1688.laputa.miniod", data=data)
        model = resp.data["model"]
        return {
            "offerDetail": model["offerModel"]["offerDetail"],
            "dataModel": model.get("dataModel", {}),
            "endpoint": model.get("endpoint"),
            "hierarchy": model.get("hierarchy"),
        }

    def get_offer_detail_from_html(self, offer_id: int) -> dict:
        """【备用】从 HTML 解析商品详情 (SSR window.context)

        当 miniod API 不可用时回退到 HTML 解析。
        """
        import re

        url = f"https://detail.1688.com/offer/{offer_id}.html"
        headers = {
            "User-Agent": self.session.DEFAULT_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = self.session.http.get(url, headers=headers, timeout=15)
        m = re.search(
            r"window\.context\s*=\s*(\{.+?\});\s*</script>",
            resp.text,
            re.DOTALL,
        )
        if not m:
            raise ValueError("无法从 HTML 提取 context 数据")
        context = json.loads(m.group(1))
        return context["result"]["data"]

    # ==============================================================
    # 商品物流/配送信息
    # ==============================================================

    def get_offer_logistics(
        self,
        offer_id: int,
        seller_id: int,
        to_address_code: str = "440300",
        from_address_id: str = "",
        protection_infos: Optional[list] = None,
        buyer_protection: Optional[list] = None,
        delivery_time: int = 0,
    ) -> MTOPResponse:
        """获取商品物流/配送时效信息

        API: mtop.1688.mmga.offerdetail.service
        Service: offerLogisticsService

        Args:
            offer_id: 商品 ID
            seller_id: 卖家用户 ID
            to_address_code: 收货地址编码 (默认 440300=深圳)
            from_address_id: 发货地址 ID
            protection_infos: 保障服务信息列表
            buyer_protection: 买家保障模型
            delivery_time: 配送时间
        """
        data = {
            "mmgaRequest": {
                "serviceName": "offerLogisticsService",
                "invokeSource": "pc",
                "channelType": "dsc",
                "offerDeliveryTime": delivery_time,
                "offerId": offer_id,
                "toAddressCode": to_address_code,
                "fromAddressId": from_address_id,
                "sellerId": seller_id,
                "protectionInfos": json.dumps(protection_infos or []),
                "buyerProtectionModel": json.dumps(buyer_protection or []),
            }
        }
        return self.session.request("mtop.1688.mmga.offerdetail.service", data=data)

    # ==============================================================
    # 推荐商品
    # ==============================================================

    def get_offer_recommendations(self, offer_id: int) -> MTOPResponse:
        """获取商品详情页的推荐商品列表

        API: mtop.1688.mmga.offerdetail.service
        Service: offerRecommendService

        返回包含:
          - majorRecommendOfferInfos: 主要推荐
          - relationRecommendOfferInfos: 相关推荐
          - shopSimilarRecommendOfferInfos: 店铺相似推荐
        """
        data = {
            "mmgaRequest": {
                "serviceName": "offerRecommendService",
                "offerId": offer_id,
            }
        }
        return self.session.request("mtop.1688.mmga.offerdetail.service", data=data)

    # ==============================================================
    # 店铺卡片
    # ==============================================================

    def get_shop_card(
        self,
        offer_id: int,
        seller_user_id: int,
        seller_member_id: str,
        top_category_id: int = 15,
    ) -> MTOPResponse:
        """获取店铺卡片信息 (名称、评分、粉丝数)

        API: mtop.1688.moga.pc.shopcard

        Args:
            offer_id: 商品 ID
            seller_user_id: 卖家用户 ID
            seller_member_id: 卖家 memberId
            top_category_id: 顶级类目 ID
        """
        data = {
            "offerId": offer_id,
            "userId": 0,
            "offerMemberTags": [],
            "sellerUserId": seller_user_id,
            "sellerMemberId": seller_member_id,
            "topCategoryId": top_category_id,
        }
        return self.session.request("mtop.1688.moga.pc.shopcard", data=data)

    # ==============================================================
    # 店铺异步模块 (店铺头、认证等)
    # ==============================================================

    def get_shop_header(self, member_id: str) -> MTOPResponse:
        """获取店铺头部信息

        API: mtop.alibaba.alisite.cbu.server.moduleasyncservice
        Component: wp_pc_common_header
        """
        data = {
            "componentKey": "wp_pc_common_header",
            "params": json.dumps({"memberId": member_id}),
        }
        return self.session.request(
            "mtop.alibaba.alisite.cbu.server.moduleasyncservice",
            data=data,
        )

    def get_shop_certification(self, member_id: str) -> MTOPResponse:
        """获取店铺认证信息

        API: mtop.alibaba.alisite.cbu.server.moduleasyncservice
        Component: wp_pc_certification
        """
        data = {
            "componentKey": "wp_pc_certification",
            "params": json.dumps({"memberId": member_id}),
        }
        return self.session.request(
            "mtop.alibaba.alisite.cbu.server.moduleasyncservice",
            data=data,
        )

    # ==============================================================
    # 评价数据
    # ==============================================================

    def get_ratings(self, offer_id: int, page: int = 1, page_size: int = 20) -> MTOPResponse:
        """获取商品评价列表

        API: mtop.1688.trade.service.MtopRateService.queryItemRatedListV2
        """
        data = {
            "offerId": str(offer_id),
            "beginPage": page,
            "pageSize": page_size,
            "auctionStarType": "all",
        }
        return self.session.request(
            "mtop.1688.trade.service.MtopRateService.queryItemRatedListV2",
            version="1.0",
            data=data,
        )

    def get_dsr_ratings(self, offer_id: int) -> MTOPResponse:
        """获取商品 DSR 评分数据 (描述、物流、服务)

        API: mtop.1688.trade.service.MtopRateService.queryDsrRateDataV2
        """
        data = {"offerId": str(offer_id)}
        return self.session.request(
            "mtop.1688.trade.service.MtopRateService.queryDsrRateDataV2",
            version="1.0",
            data=data,
        )

    # ==============================================================
    # 运费 & 配送
    # ==============================================================

    def get_freight_info(
        self,
        offer_id: int,
        to_address_code: str = "440300",
        scene: str = "dsc",
        amount: int = 1,
    ) -> MTOPResponse:
        """获取商品运费信息

        API: mtop.1688.freightinfoservice.getfreightinfowithscene
        """
        data = {
            "offerId": offer_id,
            "toAddrCode": to_address_code,
            "scene": scene,
            "amount": amount,
            "needOD": "true",
        }
        return self.session.request(
            "mtop.1688.freightInfoService.getFreightInfoWithScene",
            data=data,
        )

    def get_fulfillment_solution(
        self,
        offer_id: int,
        amount: int = 1,
        address_code: str = "440300",
    ) -> MTOPResponse:
        """获取履约配送方案

        API: mtop.alibaba.carriagecenter.fulfillmentsolution.query4offer
        """
        data = {
            "offerId": offer_id,
            "amount": amount,
            "addressCode": address_code,
        }
        return self.session.request(
            "mtop.alibaba.carriagecenter.fulfillmentsolution.query4offer",
            data=data,
        )

    # ==============================================================
    # 店铺关注状态
    # ==============================================================

    def check_shop_relation(self, shop_login_id: str) -> MTOPResponse:
        """检查店铺关注状态

        API: mtop.1688.mmga.offerdetail.service
        Service: shopRelationFnService
        """
        data = {
            "mmgaRequest": {
                "serviceName": "shopRelationFnService",
                "shopLoginId": shop_login_id,
            }
        }
        return self.session.request("mtop.1688.mmga.offerdetail.service", data=data)

    # ==============================================================
    # 用户信息
    # ==============================================================

    def get_user_simple(self) -> MTOPResponse:
        """获取当前用户基本信息

        API: mtop.user.getUserSimple
        """
        return self.session.request(
            "mtop.user.getUserSimple",
            version="1.0",
            data={},
            method="GET",
        )
