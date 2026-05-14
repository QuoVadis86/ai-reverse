# SpiderDemo 挑战分析文档

## 概述

本文档记录了 [SpiderDemo](https://spiderdemo.cn/) 反爬虫练习平台的逆向分析过程与解法。

---

## T1-请求头检测 (Header Check Challenge)

### 题目信息
- **URL**: `/sec1/header_check/`
- **难度**: 简单 | **分数**: 10
- **描述**: header顺序反爬，控制台发包检测

### 服务端校验逻辑

服务端（istio-envoy）会校验 HTTP 请求头的**发送顺序**。Chrome 原生 fetch() 发送的请求头有固定的顺序：

```
host → connection → sec-ch-ua → sec-ch-ua-mobile → sec-ch-ua-platform
→ user-agent → accept → referer → accept-encoding → accept-language → cookie
```

如果请求头的发送顺序不匹配，返回 400 "检测到爬虫模式，访问被拒绝"。

### 关键发现

| 库 | 行为 | 结果 |
|---|------|:----:|
| `requests` (urllib3) | 自动重排标准头（User-Agent、Accept 等提前） | ❌ 400 |
| `httpx` | 保留插入顺序 | ✅ 200 |
| `http.client` | 保留插入顺序 | ✅ 200 |

**原因**: Python `requests` 底层 `urllib3` 会在发送前对标准头做重排，打乱了 Chrome 原生顺序。

### 解法

使用 `httpx` 或 `http.client`，严格按照 Chrome 顺序构造请求头字典：
```python
headers = [
    ("Host", HOST),
    ("Connection", "keep-alive"),
    ("sec-ch-ua", '"Chromium";v="148", ...'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"macOS"'),
    ("User-Agent", "Mozilla/5.0 ..."),
    ("Accept", "*/*"),
    ("Referer", "https://spiderdemo.cn/sec1/header_check/"),
    ("Accept-Encoding", "gzip, deflate, br"),
    ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
    ("Cookie", cookie),
]
```

### 脚本

`spiderdemo/t1_header_check.py` — 双实现（http.client + httpx）

---

## T2-加解密 (Obfuscation Challenge)

### 题目信息
- **URL**: `/ob/ob_challenge1?challenge_type=ob_challenge1`
- **难度**: 中等 | **分数**: 20
- **描述**: 很恶心的混淆

### 保护机制

1. **请求头顺序检测**（同 T1）
2. **每页数据需带 sign 签名**
3. **重度 ob 混淆 JS**（控制流平坦化 + 字符串编码）

### 签名逆向

`hex_md5` 定义在 `/static/js/obfuscation/ob_challenge1.js` 中：

```javascript
function hex_md5(input) {
    input += '\xa3\xac\xa1\xa3\x66\x64\x6a\x66' +
             '\x2c\x6a\x6b\x67\x66\x6b\x6c';  // 追加 salt
    return hex(md5(string_to_array(input), input.length * 8));
}
```

- **Salt 字节**: `\xa3\xac\xa1\xa3` + `fdjf,jkgfkl`
- **算法**: 标准 MD5
- **编码**: **必须使用 latin-1**（非 utf-8），因为 salt 包含非 UTF-8 字节

### API 端点

| 功能 | 方法 | URL |
|------|------|-----|
| 初始化 | GET | `/ob/api/challenge/init/?challenge_type=ob_challenge1` |
| 分页 | GET | `/ob/api/ob_challenge1/page/{page}/?challenge_type=...&sign={md5}&timestamp={ts}` |
| 提交 | POST | `/ob/api/challenge/submit/` |

### 签名计算

```python
SALT = bytes([0xa3, 0xac, 0xa1, 0xa3, 0x66, 0x64, 0x6a, 0x66,
              0x2c, 0x6a, 0x6b, 0x67, 0x66, 0x6b, 0x6c]).decode("latin-1")
raw = str(int(time.time() * 1000)) + str(page) + SALT
sign = hashlib.md5(raw.encode("latin-1")).hexdigest()
```

### 脚本

`spiderdemo/t2_ob_challenge1.py` — 纯 httpx

---

## T3-protobuf加密 (Protobuf Challenge)

### 题目信息
- **URL**: `/authentication/protobuf_challenge?challenge_type=protobuf_challenge`
- **难度**: 中等 | **分数**: 20
- **描述**: 魔改md5，魔改protobuf加密

### 保护机制

1. **请求头顺序检测**（同 T1）
2. **POST 请求，Content-Type: application/x-protobuf**
3. **自定义 3 轮魔改 MD5 签名**
4. **Protobuf 编解码**

### 签名逆向

`md_sign.OooO` — 3 轮（48 步）魔改 MD5：

```
常量: A=0x67452301 B=0xEFCDAB89 C=0x98BADCFE D=0x10325476
Round 1: F(x,y,z)=(~x&z)|(y&x), shifts 3,7,11,19
Round 2: G(x,y,z)=(x&y)|(x&z)|(y&z), +0x5A827999, shifts 3,5,9,13
Round 3: H(x,y,z)=x^y^z, +0x6ED9EBA1, shifts 3,9,11,15
```

**JavaScript 坑点**:
- `>>>` 对 ≥32 的移位会取模 32（`x >>> 32` ≡ `x >>> 0`）
- Python 的 `>>` 没有此行为，需手动模拟

**输入**: `timestamp.toString()` 的字符串，字符按 int 值处理

### Protobuf 消息结构

**请求**:
```
field 1: page (varint)
field 2: ROT3(challenge_type) (string)  # "surwrexibfkdoohqjh"
field 3: timestamp (varint)
field 4: signature (string, 32 hex chars)
```

**响应**:
```
field 1 (repeated): Number { index, value }
field 2: current_page (varint)
field 3: total_pages (varint)
field 4: timestamp (varint)
```

### 脚本

`spiderdemo/t3_protobuf_challenge.py` — 纯 httpx + Python 实现的 3 轮魔改 MD5

---

## T4-WASM挑战 (WASM Challenge)

### 题目信息
- **URL**: `/sec1/wasm_challenge?challenge_type=wasm_challenge`
- **难度**: 入门 | **分数**: 10
- **描述**: 反调试+基本wasm，请使用hook方式过反调试

### 保护机制

1. **请求头顺序检测**（同 T1）
2. **WASM 加密签名**: `encrypt_simple(verifyString, timestamp)`
3. **Rust 编译的 WASM 模块**（aes 加密 + hex 编码）

### WASM 分析

**模块**: `wasm_anti_bg.wasm`（49KB，Rust wasm-bindgen）

**导出函数**:
| 函数 | 签名 | 说明 |
|------|------|------|
| `encrypt_simple` | `(string, string) -> string` | 加密 + hex 输出 |
| `aes_encrypt` | `(输入) -> bytes` | AES 加密核心 |
| `get_timestamp` | `() -> f64` | 返回 Date.now() |

**依赖**:
- `aes-0.8.4` crate（fixslice32 实现）
- `hex-0.4.3` crate（编码）
- wasm-bindgen 胶水代码

### 调用方式

```python
import wasmtime
engine = wasmtime.Engine()
module = wasmtime.Module(engine, open("wasm_anti_bg.wasm", "rb").read())
```

### 签名计算

```python
verify = f"wasm_challenge_page_{page}"
ts = str(int(time.time()))
auth = encrypt_simple(verify, ts)  # 64-char hex
```

### 脚本

`spiderdemo/t4_wasm_challenge.py` — wasmtime + httpx

---

## T5-柳暗花明又一墙 (OB1 Challenge)

### 题目信息
- **URL**: `/authentication/ob1_challenge?challenge_type=ob1_challenge`
- **难度**: 入门 | **分数**: 10
- **描述**: 变种ob

### 保护机制

1. **Canvas 浏览器指纹签名**
2. **重度 ob 混淆 + 反调试**

### 签名分析

`O0o0O0O0()` 函数生成的签名格式：
```
base64(canvas_fingerprint + random_salt + timestamp)
```

**签名与页码无关**：同一个签名可以用于所有页码。

### API 端点

| 功能 | 方法 | URL |
|------|------|-----|
| 初始化 | GET | `/authentication/api/ob1_challenge/init/?challenge_type=ob1_challenge` |
| 分页 | GET | `/authentication/api/ob1_challenge/page/{page}/?challenge_type=...&signature={sig}` |
| 提交 | POST | `/authentication/api/ob1_challenge/submit/` |

### 签名格式

```
signature = b64encode(core_fingerprint + timestamp)
```

### 脚本

`spiderdemo/t5_ob1_challenge.py` — 一次捕获 + 纯 httpx

---

## T7-CSS偏移挑战 (CSS Offset Challenge)

### 题目信息
- **URL**: `/css_anti/CSS1_challenge`
- **难度**: 中等
- **描述**: 数字通过 CSS left/right 偏移打乱顺序

### 核心解法

1. **CSS calc 表达式解析**: 使用括号计数法正确处理嵌套 calc()
2. **字符宽度**: 15px（base unit = `3 * 5px`）
3. **视觉位置计算**: `visual_pos = nat_pos + offset_px / 15`
4. **排序**: 按视觉位置升序，同位置按自然位置升序

### 关键点

CSS 变量名包含连字符（如 `--offset-0-1234`），不能使用 `\w+` 匹配。

### 脚本

`spiderdemo/t7_css_challenge.py` — 纯 httpx

---

## T8-字体反爬 (Font Anti-Crawl)

### 题目信息
- **URL**: `/font_anti/font_anti_challenge`
- **难度**: 中等
- **描述**: 自定义字体混淆数字

### 核心解法

1. 使用 fontTools 解析 WOFF2 字体文件
2. 提取每个 glyph 的坐标哈希作为指纹
3. 通过 init 的正确答案建立 glyph→digit 映射
4. 后续页面匹配 glyph 指纹

### 脚本

`spiderdemo/t8_font_anti.py` — fontTools + httpx

---

## T9-字体反爬+雪碧图 (Font Sprites)

### 题目信息
- **URL**: `/font_anti/font_sprites_challenge`
- **难度**: 中等
- **描述**: 数字用雪碧图 + CSS background-position 渲染

### 核心解法

1. 用 init 返回的 page_data 反向推导 class→digit 映射
2. 从 page 1 响应提取 sprite PNG + css_code
3. 对后续页面：渲染 sprite，像素模板匹配识别各位置数字

### 关键点

- 每页 class 名不同，但 sprite 中 digit 位置（background-position）总是 8, 58, 108, ... 458（50px 间隔）
- 字符宽度 25px，高度 45px

### 脚本

`spiderdemo/t9_font_sprites.py` — PIL + httpx

---

## x系列 — 额外挑战

| 脚本 | 技术 |
|------|------|
| x01_fsymmetry_challenge.py | JSEncrypt RSA 加密/签名 |
| x02_symmetry_challenge.py | AES-256-CTR + DES-CBC via Node.js CryptoJS |
| x03_hash_challenge.py | HMAC-SHA256 + MD5 + SHA256 + SHA3-256 |

---

## 待完成

| 关卡 | 挑战 | 难点 |
|:-----|:-----|:-----|
| T6 | jsvmp_challenge | JSVMP + Protobuf，需要反混淆 |
| T10 | font_svg_challenge | SVG path→数字识别 |
| T11 | cap1-4 captcha | 验证码 OCR |
| T12 | cap5-8 captcha | 验证码 + 滑块拼图 |

---

## 文件结构

```
spiderdemo/
├── t1_header_check.py        # T1 请求头检测
├── t2_ob_challenge1.py       # T2 加解密
├── t3_protobuf_challenge.py  # T3 protobuf加密
├── t4_wasm_challenge.py      # T4 WASM挑战 (+ .wasm)
├── t5_ob1_challenge.py       # T5 ob1挑战
├── t7_css_challenge.py       # T7 CSS偏移挑战
├── t8_font_anti.py           # T8 字体反爬
├── t9_font_sprites.py        # T9 雪碧图反爬
├── t10_font_svg.py           # T10 SVG字体反爬 (stub)
├── x01_fsymmetry_challenge.py # x01 对称加密
├── x02_symmetry_challenge.py # x02 对称加密
├── x03_hash_challenge.py     # x03 哈希
└── analysis.md               # 本文档
```

## 总计

| 关卡 | 分数 | 状态 |
|:-----|:----:|:----:|
| T1 请求头检测 | 10 | ✅ |
| T2 加解密 | 20 | ✅ |
| T3 protobuf加密 | 20 | ✅ |
| T4 WASM挑战 | 10 | ✅ |
| T5 ob1挑战 | 10 | ✅ |
| T7 CSS偏移 | 20 | ✅ |
| T8 字体反爬 | 20 | ✅ |
| T9 雪碧图 | 20 | ✅ |
| x01 对称 | 10 | ✅ |
| x02 对称 | 10 | ✅ |
| x03 哈希 | 10 | ✅ |
| T6 JSVMP | 25 | ❌ |
| T10 SVG字体 | 20 | ❌ |
| T11-T12 验证码 | - | ❌ |
