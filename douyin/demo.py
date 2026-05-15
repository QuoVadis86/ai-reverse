"""抖音 a_bogus 使用示例"""
from abogus import ABogus, get_a_bogus, get_a_bogus_from_params, quote

# 你的 User-Agent
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

# 方式1: 从 URL query string 生成
url = "https://www.douyin.com/aweme/v1/web/feed/?aid=6383&device_platform=webapp"
a_bogus = get_a_bogus(url, UA)
print(f"方式1: {a_bogus}")

# 方式2: 从参数字典生成（自动按 key 排序）
params = {
    "aid": "6383",
    "device_platform": "webapp",
    "channel": "channel_pc_web",
}
a_bogus = get_a_bogus_from_params(params, UA)
print(f"方式2: {a_bogus}")

# 方式3: 直接使用 ABogus 类
bogus = ABogus(user_agent=UA)
# 注意: 传入的 query string 顺序必须与最终 URL 一致
a_bogus = bogus.generate("aid=6383&device_platform=webapp")
print(f"方式3: {a_bogus}")

# URL 编码后的值（追加到 URL）
print(f"URL编码: {quote(a_bogus, safe='')}")
