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
        """从 HTML 解析商品详情 (SSR window.context)
        SSR 数据可能为空时自动回退到 miniod API。
        """
        import re

        url = f"https://detail.1688.com/offer/{offer_id}.html"
        headers = {
            "User-Agent": self.session.UA,
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = self.session.http.get(url, headers=headers, timeout=15)
        m = re.search(
            r"window\.context\s*=\s*(\{.+?\});",
            resp.text,
            re.DOTALL,
        )
        if m:
            context = json.loads(m.group(1))
            data = context.get("result", {}).get("data")
            if data:
                return data

        return self.get_offer_detail(offer_id)

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
        winport_url: str = "",
        top_category_id: int = 15,
    ) -> MTOPResponse:
        """获取店铺卡片信息 (名称、评分、粉丝数)

        API: mtop.1688.moga.pc.shopcard
        """
        base_url = winport_url or f"https://shop{seller_user_id}.1688.com"
        data = {
            "offerId": offer_id,
            "userId": 0,
            "offerMemberTags": [],
            "sellerUserId": seller_user_id,
            "sellerMemberId": seller_member_id,
            "topCategoryId": top_category_id,
            "winportUrl": base_url,
            "sellerWinportUrlMap": {
                "indexUrl": f"{base_url}/page/index.html",
                "contactinfoUrl": f"{base_url}/page/contactinfo.html",
                "creditdetailUrl": f"{base_url}/page/creditdetail.html",
                "offerlistUrl": f"{base_url}/page/index.html",
                "shopdynamicUrl": f"{base_url}/page/shopdynamic.html",
                "defaultUrl": base_url,
            },
            "sellerIdentity": "cht",
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
            "offerId": offer_id,
            "beginPage": page,
            "pageSize": page_size,
            "starLevel": "all",
        }
        return self.session.request(
            "mtop.1688.trade.service.MtopRateService.queryItemRatedListV2",
            version="1.0",
            data=data,
        )

    def get_dsr_ratings(self, offer_id: int, scene: str = "dsc") -> MTOPResponse:
        """获取商品 DSR 评分数据 (描述、物流、服务)

        API: mtop.1688.trade.service.MtopRateService.queryDsrRateDataV2
        """
        data = {"offerId": offer_id, "scene": scene}
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

    # ==============================================================
    # 搜索
    # ==============================================================

    def search_by_text(
        self,
        keywords: str,
        page: int = 1,
        page_size: int = 60,
        sort_type: str = "normal",
    ) -> MTOPResponse:
        """关键词搜索商品

        API: mtop.relationrecommend.WirelessRecommend.recommend (v2.0)
        Method: getOfferList / Scene: pcOfferSearch
        """
        params = {
            "method": "getOfferList",
            "beginPage": page,
            "pageSize": page_size,
            "keywords": keywords,
            "searchScene": "pcOfferSearch",
            "verticalProductFlag": "pcmarket",
            "charset": "GBK",
            "sortType": sort_type,
        }
        data = {"appId": 32517, "params": json.dumps(params, separators=(",", ":"))}
        return self.session.request(
            "mtop.relationrecommend.WirelessRecommend.recommend",
            version="2.0",
            data=data,
        )

    # ==============================================================
    # 搜索配置 / 筛选项
    # ==============================================================

    def get_search_config(self, keywords: str) -> MTOPResponse:
        """获取搜索配置和筛选项

        API: mtop.relationrecommend.WirelessRecommend.recommend (v2.0)
        Method: batchGetNavigationAndConfigData

        返回包含:
          - filterData: 筛选 (包邮/一件代发/新品等)
          - navigationData: 类目导航
          - pageConfigData: 页面配置
        """
        params = {
            "method": "batchGetNavigationAndConfigData",
            "keywords": keywords,
            "searchScene": "pcOfferSearch",
            "verticalProductFlag": "pcmarket",
            "charset": "GBK",
        }
        data = {"appId": 32517, "params": json.dumps(params, separators=(",", ":"))}
        return self.session.request(
            "mtop.relationrecommend.WirelessRecommend.recommend",
            version="2.0",
            data=data,
        )

    # ==============================================================
    # 以图搜图
    # ==============================================================

    def upload_image(self, image_source: str) -> str:
        """上传图片到以图搜图引擎，返回 imageId

        支持本地文件路径和远程 URL。

        Args:
            image_source: 图片路径 (本地文件) 或 URL (http/https)

        Returns:
            imageId: 图片ID，用于后续搜索
        """
        import base64

        raw = self._read_image(image_source)
        b64_str = base64.b64encode(raw).decode()

        params = {
            "method": "uploadBase64WithRequest",
            "beginPage": 1,
            "pageSize": 60,
            "searchScene": "pcImageSearch",
            "appName": "pctusou",
            "imageBase64": b64_str,
            "sortType": "normal",
        }
        data = {"appId": 32517, "params": json.dumps(params, separators=(",", ":"))}
        resp = self.session.request(
            "mtop.relationrecommend.WirelessRecommend.recommend",
            version="2.0",
            data=data,
        )
        return resp.data["data"]["imageId"]

    def _read_image(self, source: str) -> bytes:
        """从本地路径或 URL 读取图片数据"""
        import requests as req_lib

        if source.startswith(("http://", "https://")):
            r = req_lib.get(source, timeout=30)
            r.raise_for_status()
            return r.content
        with open(source, "rb") as f:
            return f.read()

    def search_by_image_id(
        self,
        image_id: str,
        page: int = 1,
        page_size: int = 60,
    ) -> MTOPResponse:
        """用已上传的 imageId 搜索以图搜图结果
        """
        params = {
            "method": "imageOfferSearchService",
            "beginPage": page,
            "pageSize": page_size,
            "imageId": image_id,
            "searchScene": "pcImageSearch",
            "appName": "pctusou",
        }
        data = {"appId": 32517, "params": json.dumps(params, separators=(",", ":"))}
        return self.session.request(
            "mtop.relationrecommend.WirelessRecommend.recommend",
            version="2.0",
            data=data,
        )

    def search_similar_by_image(
        self,
        image_address: str,
        page: int = 1,
        page_size: int = 60,
    ) -> MTOPResponse:
        """以图搜图 (按图片URL直接搜索相似款, 无需先上传)

        返回 data.data.OFFER:
          - found: 总结果数
          - items: 商品列表 (offerId/price/图片信息在 trackInfo.expoData 中)
          - imageAddress / imageRecognition: 识别信息

        Args:
            image_address: 图片的完整 URL
        """
        params = {
            "method": "imageSimilarSearchV2",
            "beginPage": page,
            "pageSize": page_size,
            "imageAddress": image_address,
            "searchScene": "pcImageSearch",
            "appName": "pctusou",
        }
        data = {"appId": 32517, "params": json.dumps(params, separators=(",", ":"))}
        return self.session.request(
            "mtop.relationrecommend.WirelessRecommend.recommend",
            version="2.0",
            data=data,
        )

    def search_by_image(
        self,
        image_source: str,
        page: int = 1,
        page_size: int = 60,
    ) -> MTOPResponse:
        """以图搜图：自动选择最佳方式

        远程 URL → imageSimilarSearchV2 (无需上传)
        本地文件 → 先 uploadBase64WithRequest → imageId → imageOfferSearchService
        """
        if image_source.startswith(("http://", "https://")):
            return self.search_similar_by_image(image_source, page, page_size)
        image_id = self.upload_image(image_source)
        return self.search_by_image_id(image_id, page=page, page_size=page_size)
