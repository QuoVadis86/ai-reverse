# 抖音 a_bogus 逆向分析报告

> 版本: 2026-05  |  抖音版本: 17.4.0 (version_code=170400)  |  SDK: webmssdk 1.0.0.20

---

## 目录

1. [概述](#1-概述)
2. [入口定位](#2-入口定位)
3. [算法流程](#3-算法流程)
4. [核心数据结构](#4-核心数据结构)
5. [关键中间检查点](#5-关键中间检查点)
6. [浏览器断点调试指南](#6-浏览器断点调试指南)
7. [版本更新适配指南](#7-版本更新适配指南)
8. [已知问题与陷阱](#8-已知问题与陷阱)
9. [参考](#9-参考)

---

## 1. 概述

`a_bogus` 是抖音 Web 端（PC 网页版）的请求签名参数，附加在每个 API 请求的 query string 末尾。

**性质**: 纯算法签名（非环境指纹验证类），不依赖登录态 cookie。

**组成部分**: 随机前缀(12B) + RC4加密数据(可变长) → 自定义Base64编码

**输出特征**: 约 164 字符，以 `Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe` 码表中的字符开头。

---

## 2. 入口定位

### 2.1 浏览器全局入口

```
window.byted_acrawler
```

暴露的方法:

| 方法 | 用途 | 是否 a_bogus |
|---|---|---|
| `frontierSign(input)` | 生成 X-Bogus（旧签名） | ❌ 返回 X-Bogus |
| `init(config)` | 初始化 SDK | — |
| `setTTWebid(id)` | 设置 webid | — |
| `getReferer()` | 获取 referer | — |
| `isWebmssdk` | 标记位 | `true` |

> **关键发现**: `byted_acrawler.frontierSign` 生成的是 **X-Bogus**，不是 a_bogus。a_bogus 的生成代码在 Douyin webpack 主 bundle 中，通过 `_$webrt_1668687510` 字节码解码器动态加载。

### 2.2 核心解码器

```
window._$webrt_1668687510(hexString) => Function
```

这是一个字节码解码器，接收十六进制字符串返回可执行函数。存在于:

```
https://lf-c-flwb.bytetos.com/obj/rc-client-security/c-webmssdk/1.0.0.20/webmssdk.es5.js
```

### 2.3 涉及的 SDK 文件

| 文件 | 角色 | 更新频率 |
|---|---|---|
| `c-webmssdk/1.0.0.XX/webmssdk.es5.js` | 安全 SDK 核心（含 _$webrt 解码器） | 中 |
| `runtime_bundler_XX.js` | 安全策略运行时 | 低 |
| `bdms_1.0.1.XX_fix.js` | 设备指纹/数据收集 | 中 |
| `collect.dy.js` | 日志收集 | 低 |
| `sdk-glue.js` | SDK 胶水层 | 低 |

### 2.4 网络请求写出点

a_bogus 追加在所有 `/aweme/v1/web/*` 和 `/webcast/*` 请求的 URL query 末尾。

```
GET /aweme/v1/web/feed/?device_platform=webapp&aid=6383&...&a_bogus=xvUjDzSwdd...
```

**Hook 方式**:

```js
// Hook fetch
const origFetch = window.fetch;
window.fetch = function(url, opts) {
  if (typeof url === 'string' && url.includes('aweme')) {
    console.log('[a_bogus request]', url);
  }
  return origFetch.apply(this, arguments);
};

// Hook XMLHttpRequest
const origOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(method, url) {
  if (typeof url === 'string' && url.includes('aweme')) {
    console.log('[a_bogus XHR]', url);
  }
  return origOpen.apply(this, arguments);
};
```

---

## 3. 算法流程

### 总览

```
输入集合
  ├─ URL query string       ← 所有 param=value 按 key 排序 & 连接
  ├─ HTTP method             ← "GET" / "POST"
  ├─ User-Agent              ← 浏览器 UA
  ├─ 浏览器窗口信息           ← "1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|MacIntel"
  ├─ 时间戳 (ms)             ← start_time / end_time (end = start + 随机 4~8ms)
  └─ 随机种子                ← 3 组, 每组基于 Math.random() 的 4 字节
        │
        ▼
┌──────────────────────────────────────────────┐
│  Step 1: 双 SM3 哈希                          │
│  params_hash = SM3( SM3( query + "cus" ) )   │  ← 32 bytes
│  method_hash = SM3( SM3( method + "cus" ) )   │  ← 32 bytes
│  ua_code     = SM3( SM3( UA + "cus" ) )       │  ← 32 bytes
└──────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────┐
│  Step 2: 构造 50 位主数组 (list_4)            │
│  [44, et3,0,0,0,0, 24, ph[21], ua[23], et2,  │
│   0,0,0,1, 0,239, ph[22], ua[24], et1, et0,   │
│   0,0,0,0, 0,0, 0,14, st3, st2, st1, st0,     │
│   0, mh[21], mh[22], 3, bl, 1, bl, 0,0,0]     │
└──────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────┐
│  Step 3: 拼接 50 + 41 + 1 字节               │
│  [50位主数组] + [browser_code(41)] + [XOR]    │
└──────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────┐
│  Step 4: RC4 加密 (key="y")                   │
│  rc4_output = RC4(key="y", input_bytes)       │
└──────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────┐
│  Step 5: 拼接随机 12 字节前缀                 │
│  rand_12bytes = random_4bytes x 3 组          │
│  final = rand_12bytes + rc4_output            │
└──────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────┐
│  Step 6: 自定义 Base64 编码 (s4 码表)         │
│  a_bogus = custom_b64(final, S4_ALPHABET)     │
└──────────────────────────────────────────────┘
        │
        ▼
  输出: a_bogus (~164 字符)
```

### 3.1 Step 1: 双 SM3

```python
def double_sm3(data_str: str) -> list[int]:
    h1 = sm3(data_str + "cus")           # 第一层 SM3
    h2 = sm3(h1)                          # 第二层 SM3（对第一层输出做哈希）
    return list(h2)                       # 32 bytes
```

关键点:
- 输入拼接固定后缀 `"cus"`（对应 JS 中的 `end_string = "cus"`）
- **三处用到**: params query、method、user_agent
- 两次 SM3 的目的是防逆向（直接搜 SM3 常量搜不到）

### 3.2 Step 2: 50 位主数组

50 字节的固定结构，按 index 说明:

| Index | 字节 | 来源 | 说明 |
|---|---|---|---|
| 0 | `44` | 固定 | 数组标记头 |
| 1 | `end_time >> 24 & 0xFF` | end_time | 时间高位 |
| 2-5 | `0,0,0,0` | 固定填充 | |
| 6 | `24` | 固定 | |
| 7 | `params_hash[21]` | params SM3 | 第 22 字节 |
| 8 | `ua_code[23]` | UA code | 第 24 字节 |
| 9 | `end_time >> 16 & 0xFF` | end_time | |
| 10-12 | `0,0,0` | 固定填充 | |
| 13 | `1` | 固定 | |
| 14 | `0` | 固定 | |
| 15 | `239` | 固定 | |
| 16 | `params_hash[22]` | params SM3 | 第 23 字节 |
| 17 | `ua_code[24]` | UA code | 第 25 字节 |
| 18 | `end_time >> 8 & 0xFF` | end_time | |
| 19 | `end_time & 0xFF` | end_time | 时间低位 |
| 20-23 | `0,0,0,0` | 固定填充 | |
| 24-25 | `0,0` | 固定填充 | |
| 26 | `0` | 固定 | |
| 27 | `14` | 固定 | |
| 28-31 | `start_time 4 bytes` | start_time | 大端序 |
| 32 | `0` | 固定 | |
| 33 | `method_hash[21]` | method SM3 | 第 22 字节 |
| 34 | `method_hash[22]` | method SM3 | 第 23 字节 |
| 35 | `3` | 固定 | |
| 36 | `browser_len` | 浏览器信息字符串长度 | |
| 37 | `1` | 固定 | |
| 38 | `browser_len` | 同 36 | |
| 39-41 | `0,0,0` | 固定填充 | |

**共 44 个元素**（对应 Python `list_4` 返回长度 44，但概念上是 50 字节的主数据区）。

### 3.3 Step 3: 拼接 + XOR

```
input_stream = arr50_bytes + browser_code_bytes + [xor_check]

browser_code: 浏览器窗口信息字符串的 char codes
  来源: window.innerWidth|innerHeight|outerWidth|...|platform
  示例: "1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|MacIntel"
  长度: 41 字节（取决于 platform 字符串长度）

xor_check: 对 arr50 所有字节逐位 XOR
  let xor = 0;
  for (let b of arr50) xor ^= b;
```

### 3.4 Step 4: RC4

标准 RC4 算法，key = `"y"`（单字符）。

```
key = "y"
S = [0..255]
for i in 0..255:
    j = (j + S[i] + key[i % len(key)]) & 0xFF
    swap(S[i], S[j])
// 对 input_stream 每个字节:
    i = (i+1) & 0xFF
    j = (j + S[i]) & 0xFF
    swap(S[i], S[j])
    output = S[(S[i] + S[j]) & 0xFF] ^ input_byte
```

### 3.5 Step 5: 随机前缀

生成 12 字节随机数。JS 源码中通过 `random()` 种子构造 3 组各 4 字节:

```js
list_1: [v1&170|1, v1&85|2, v2&170|5, v2&85|0]    // a=170,b=85, set bits
list_2: [v1&170|1, v1&85|0, v2&170|0, v2&85|0]    // minimal
list_3: [v1&170|1, v1&85|0, v2&170|5, v2&85|0]    // with v2&170|5
```

### 3.6 Step 6: 自定义 Base64

使用码表 `s4`:

```
Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe
```

与标准 Base64 唯一区别是码表不同，编码逻辑完全相同（3 字节 → 4 字符，不足补 `=`）。

---

## 4. 核心数据结构

### 4.1 params SM3 输出 (32 bytes)

```
SM3(SM3(url_query + "cus"))

示例输入: "aid=6383&device_platform=webapp&..."
示例输出: [99, 45, 182, 13, ...]  (32 个 0~255 整数)
```

**用途**: 用于 50 位数组的 index 21, 22

### 4.2 method SM3 输出 (32 bytes)

```
SM3(SM3(method + "cus"))

method = "GET" 或 "POST"
```

**用途**: 用于 50 位数组的 index 33, 34

### 4.3 UA code (32 bytes)

```
SM3(SM3(user_agent + "cus"))

例: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ..."
```

**用途**: 用于 50 位数组的 index 8, 17

### 4.4 Browser code (41 bytes)

浏览器窗口尺寸和平台信息的 char code 序列:

```
"{innerWidth}|{innerHeight}|{outerWidth}|{outerHeight}|{screenX}|{screenY}|0|0|{outerWidth}|{outerHeight}|{outerWidth}|{outerHeight}|{innerWidth}|{innerHeight}|24|24|{platform}"
```

示例: `"1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|MacIntel"`

**用途**: 直接拼接到主数组后参与 RC4 加密

### 4.5 时间戳

| 变量 | 类型 | 来源 |
|---|---|---|
| `start_time` | 毫秒时间戳 | `Date.now()` 或 `int(time.time() * 1000)` |
| `end_time` | 毫秒时间戳 | `start_time + randint(4, 8)` |

end_time 比 start_time 大 4~8ms，模拟网络处理耗时。

---

## 5. 关键中间检查点

调试时必须对齐以下 8 个检查点，任何一个不匹配则最终 a_bogus 必错：

| # | 检查点 | 长度 | 赋值来源 | 对齐方法 |
|---|---|---|---|---|
| ① | params SM3 输出 | 32B | url query + "cus" | 本地 Python vs 浏览器 logpoint |
| ② | method SM3 输出 | 32B | method + "cus" | 同上 |
| ③ | UA code | 32B | UA + "cus" | 同上 |
| ④ | 50 位主数组 | 44B | 基于 ①②③ + 时间 | 在 `list_4` 函数入口 logpoint |
| ⑤ | browser code | ~41B | 窗口信息 char codes | 确保 UA/platform 一致 |
| ⑥ | XOR 校验字节 | 1B | 50 位数组逐位异或 | 验证 `xor_check` |
| ⑦ | RC4 输出 | ~86B | key="y" | 本地 Python 实现 |
| ⑧ | 最终 Base64 | ~164B | s4 码表 | 验证末尾 `=` 数量 |

**调试日志模板 (建议在 JS 中打 logpoint)**:

```js
console.log('[CKPT1] params_hash:', params_hash.slice(20, 25).join(','));
console.log('[CKPT2] method_hash:', method_hash.slice(20, 25).join(','));
console.log('[CKPT4] arr50:', list_4_result.join(','));
console.log('[CKPT6] xor:', xor_check);
console.log('[CKPT7] rc4_out:', rc4_out.substring(0, 20));
console.log('[CKPT8] a_bogus:', final_result);
```

---

## 6. 浏览器断点调试指南

### 6.1 找到签名函数

```js
// 在 Console 中执行:
Object.keys(window.byted_acrawler)
// → ["frontierSign", "getReferer", "init", ...]

// frontSign 生成 X-Bogus，不是 a_bogus!
window.byted_acrawler.frontierSign("test")
// → {X-Bogus: "60a2hEKaXX8C3v0p"}
```

### 6.2 追踪 a_bogus 生成

a_bogus 在 webpack bundle 中生成，推荐方式:

**方式 A**: Hook fetch + 打印调用栈

```js
const origFetch = window.fetch;
window.fetch = function(url, opts) {
  if (typeof url === 'string' && url.includes('a_bogus')) {
    console.log(new Error().stack);
  }
  return origFetch.apply(this, arguments);
};
```

**方式 B**: 在 Security SDK 中打 logpoint

在 Chrome DevTools → Sources → 搜索 `"cus"`（固定后缀字符串）

找到包含 `"cus"` 的函数后，在以下位置打 logpoint:
- 双 SM3 调用处（看输入和输出）
- `list_4` 返回值（看 50 位数组构造）
- RC4 加密前后
- 自定义 Base64 之前

**方式 C**: 直接在 webpack bundle 中搜索 `a_bogus`

```js
// 列出所有加载的脚本
document.querySelectorAll('script[src]')
// 搜索包含 a_bogus 的脚本
// a_bogus 在 webpack 模块中, 通过 _$webrt 解码运行
```

### 6.3 验证本地实现

与浏览器对齐的标准流程:

```
1. 捕获一个请求 URL（含 a_bogus）
2. 提取 query string（不含 a_bogus）
3. 获取浏览器 UA 和 platform
4. 用 Python 实现生成 a_bogus
5. 本地生成值替换 URL 中原始值
6. 请求 API → 200 则算法正确
```

---

## 7. 版本更新适配指南

### 7.1 如何判断算法已变

以下信号提示 a_bogus 算法已更新:

| 信号 | 说明 |
|---|---|
| 现有 a_bogus 请求返回 403/非 200 | 最直接信号 |
| `webmssdk.es5.js` 版本号升高 | URL 中 `1.0.0.XX` 变更 |
| `bdms_*.js` 版本号升高 | `bdms_1.0.1.XX_fix.js` |
| 新参数出现在 query 中 | 如 `x_bogus`, `msToken` 等 |
| a_bogus 长度变化 | 当前 ~164 字符 |

### 7.2 更新检查清单

当怀疑算法更新时，按此清单排查:

- [ ] 版本号对比（SDK 文件版本、version_code）
- [ ] 50 位数组结构是否变化（位置/含义/长度）
- [ ] 双 SM3 后缀 `"cus"` 是否变更
- [ ] RC4 key 是否变化
- [ ] Base64 码表 `s4` 是否变化
- [ ] browser_info 格式是否变化（增/减字段）
- [ ] ua_code 计算方式是否变化
- [ ] 随机前缀生成逻辑是否变化
- [ ] browser_code 是否新增/减少字段
- [ ] ua_code 是否还是 32 字节

### 7.3 快速定位变更

```
1. 用浏览器抓一个成功的请求（含旧 a_bogus）
2. 用本地代码生成 a_bogus（保持相同输入）
3. 对比差异 → 确定哪个环节变了

如果只是 URL param 顺序/数量变化:
   → 只更新 `get_a_bogus_from_params` 的排序逻辑

如果 SDK 文件版本变了:
   → 下载新 SDK → 搜索 "cus" → 看双 SM3 逻辑
   → 搜索 "return 44" 或类似 → 看 list_4

如果输出长度变了:
   → Base64 解码 → 看原始数据长度
   → 反推哪个环节增加了输入
```

### 7.4 代码更新 SOP

```
1. 修改对应函数（保留旧版本注释）
2. 更新所有 8 个检查点的预期值
3. 用浏览器真实请求做 end-to-end 验证
4. 更新本文件顶部的版本号
```

---

## 8. 已知问题与陷阱

### 8.1 参数顺序敏感

a_bogus 的 SM3 输入是 **URL query string 原文**，参数顺序不同则哈希不同。

**陷阱**: Python dict 的插入顺序 vs JS object 的 key 顺序可能不同。

**对策**:
- 如果 URL 构造顺序固定 → 用有序结构（list of tuple）传入
- 如果 URL 顺序不确定 → 按 key 排序（与当前实现一致）
- 最佳实践: 直接从 URL 提取 query string，不做 dict 转换

### 8.2 UA 必须如实传递

user_agent 直接影响 `ua_code` 的 SM3 输出。`Mozilla/5.0` 的版本号、平台等任何差异导致 a_bogus 不同。

**陷阱**: 使用 requests 库的默认 UA，或随意换 UA，会导致签名失效。

### 8.3 浏览器窗口信息

`browser_info` 字符串中的 `innerWidth`, `outerWidth` 等值与 UA 的 platform 部分必须匹配。无头浏览器的默认值可能与真实浏览器不一致。

### 8.4 时间戳窗口

end_time = start_time + randint(4, 8)。如果服务器端有时间窗口校验（如签名过期），偏差太大会被拒绝。

### 8.5 "DeviceId 异常"

某些接口（如 `/query/user/`）返回 `status_code: 12, "DeviceId 异常"` 是因为缺少必要的 cookie（`sessionid`、`ttwid`），**不是 a_bogus 签名错误**。这属于鉴权层面，不是签名层面。

---

## 9. 参考

### 9.1 文件清单

```
douyin/
├── abogus.py              # Python 实现（可直接用）
├── demo.py                # 使用示例
├── REVERSE_ANALYSIS.md    # 本文件
└── requirements.txt       # 依赖: gmssl>=3.2.2
```

### 9.2 SDK 文件地址

```
webmssdk:
  https://lf-c-flwb.bytetos.com/obj/rc-client-security/c-webmssdk/1.0.0.20/webmssdk.es5.js

bdms:
  https://p-pc-weboff.byteimg.com/tos-cn-i-9r5gewecjs/bdms_1.0.1.19_fix.js

runtime_bundler:
  https://lf-security.bytegoofy.com/obj/security-secsdk/runtime_bundler_34.js

sdk-glue:
  https://lf-c-flwb.bytetos.com/obj/rc-client-security/web/glue/1.0.0.64-fix.01/sdk-glue.js
```

### 9.3 开源参考

- [Evil0ctal/Douyin_TikTok_Download_API - abogus.py](https://github.com/Evil0ctal/Douyin_TikTok_Download_API/blob/main/crawlers/douyin/web/abogus.py)
- [JoeanAmier/TikTokDownloader](https://github.com/JoeanAmier/TikTokDownloader)
- [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)

### 9.4 验证命令

```bash
# 本地单元测试
python3 abogus.py

# 实际 API 验证
python3 -c "
from abogus import get_a_bogus_from_params, quote, urlencode
from urllib.request import urlopen
import json

params = {'device_platform': 'webapp', 'aid': '6383'}
a_bogus = get_a_bogus_from_params(params, 'Mozilla/5.0 ...')
query = urlencode(sorted(params.items()))
url = f'https://www.douyin.com/aweme/v1/web/feed/?{query}&a_bogus={quote(a_bogus, safe=\"\")}'
resp = urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0 ...'}))
print(json.loads(resp.read()))
"

# 检查 SDK 版本
curl -sI 'https://lf-c-flwb.bytetos.com/obj/rc-client-security/c-webmssdk/1.0.0.20/webmssdk.es5.js' | grep -i 'version\|x-version'
```
