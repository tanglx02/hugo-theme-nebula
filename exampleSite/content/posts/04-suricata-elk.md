---
title: "用 Suricata + ELK 搭建轻量流量检测平台"
date: 2026-09-05
lastmod: 2026-09-05
description: "在一台 4 核 8G 的小机器上，用 Suricata 做旁路检测、Filebeat 收集、Elasticsearch 存储、Kibana 可视化，并给出规则调优的实践建议。"
author: "Tanglx"
tags: ["Suricata", "ELK", "流量分析"]
categories: ["安全监测"]
cover: "/img/cover/soc.svg"
toc: true
---

商业 NDR 动辄几十万，但在中小场景下一台 4 核 8G 的小机器 + 开源组件就能覆盖 80% 的需求。这篇讲完整搭建过程和踩过的坑。

## 架构

```text
交换机镜像口 ──► Suricata(AF_PACKET) ──► eve.json
                                          │
                                     Filebeat
                                          │
                                    Elasticsearch
                                          │
                                       Kibana
```

关键是**旁路镜像**，不串接、不影响业务流量，出问题直接拔网线即可。

## 安装与网卡配置

```bash
apt update && apt install -y suricata jq

# 关闭网卡 offload，否则大数据包会造成大量误报/漏报
IFACE=eth1
ethtool -K $IFACE gro off lro off gso off tso off rx off tx off sg off

# 持久化（重启后生效）
cat > /etc/network/if-up.d/suricata-offload <<'EOF'
#!/bin/sh
[ "$IFACE" = "eth1" ] || exit 0
ethtool -K eth1 gro off lro off gso off tso off rx off tx off sg off
EOF
chmod +x /etc/network/if-up.d/suricata-offload
```

{{< notice warning >}}
忘记关 offload 是新手最常见的坑：表现为 Suricata 报 "packet too large" 或大量 `decoder event`。
{{< /notice >}}

## suricata.yaml 关键配置

```yaml
af-packet:
  - interface: eth1
    cluster-id: 99
    cluster-type: cluster_flow
    defrag: yes
    use-mmap: yes
    ring-size: 200000
    buffer-size: 32768

vars:
  address-groups:
    HOME_NET: "[192.168.0.0/16,10.0.0.0/8]"
    EXTERNAL_NET: "!$HOME_NET"
  port-groups:
    HTTP_PORTS: "80,443,8080,8000,8443"
    SHELLCODE_PORTS: "!80"

outputs:
  - eve-log:
      enabled: yes
      filetype: regular
      filename: eve.json
      types:
        - alert:
            payload: yes
            payload-printable: yes
            packet: yes
            metadata: yes
        - http
        - dns
        - tls
        - flow
        - stats:
            totals: yes
            threads: no
```

内存与线程建议按 CPU 核数调整：

| 流量 | 建议配置 |
| --- | --- |
| < 100 Mbps | 2 核 4G，ring-size 100000 |
| 100–500 Mbps | 4 核 8G，ring-size 200000，开启 `cluster_flow` |
| > 1 Gbps | 8 核 16G + 多队列 RSS，考虑 PF_RING |

## 规则管理

别直接用全量 ET 规则集，先跑一周观察噪音量：

```bash
suricata-update update-sources
suricata-update list-sources
suricata-update enable-source et/open
suricata-update
```

自定义规则放在 `/etc/suricata/rules/local.rules`：

```text
# 内网横向：SMB 爆破特征
alert tcp $HOME_NET any -> $HOME_NET 445 (msg:"LOCAL Possible SMB Brute Force"; \
  flow:to_server,established; detection_filter:track by_src, count 30, seconds 10; \
  sid:9000001; rev:1;)

# 可疑外联：常见反弹 Shell 端口
alert tcp $HOME_NET any -> $EXTERNAL_NET [4444,5555,6666,7777,8888,9999] ( \
  msg:"LOCAL Suspicious Outbound Reverse Shell Port"; \
  sid:9000002; rev:1;)

# DNS 隧道：超长子域名
alert dns any any -> any any (msg:"LOCAL Possible DNS Tunneling - Long Subdomain"; \
  dns.query; content:"."; isdataat:!1,relative; \
  byte_test:1,>,50,0,relative,string; sid:9000003; rev:1;)
```

调规则的原则：**先关噪音，再加精度**。

```bash
# 统计 top 告警，找出噪音源
jq -r '.alert.signature' /var/log/suricata/eve.json | sort | uniq -c | sort -rn | head -20

# 用 disable.conf 关闭误报规则
echo "2020704" >> /etc/suricata/disable.conf
suricata-update
```

## Filebeat 接入

```yaml
# /etc/filebeat/filebeat.yml
filebeat.inputs:
  - type: filestream
    id: suricata-eve
    paths:
      - /var/log/suricata/eve.json
    parsers:
      - ndjson:
          target: ""
          overwrite_keys: true
    fields:
      log_type: suricata
    fields_under_root: true

processors:
  - add_host_metadata: ~
  - convert:
      fields:
        - {from: "flow.bytes_toserver", type: long}
        - {from: "flow.bytes_toclient", type: long}

output.elasticsearch:
  hosts: ["http://127.0.0.1:9200"]
  index: "suricata-%{+yyyy.MM.dd}"

setup.template.name: "suricata"
setup.template.pattern: "suricata-*"
setup.ilm.enabled: true
setup.ilm.rollover_alias: "suricata"
```

Elasticsearch 索引生命周期别忘了配，否则一周就撑爆磁盘：

```json
PUT _ilm/policy/suricata-policy
{
  "policy": {
    "phases": {
      "hot":    { "min_age": "0ms",  "actions": { "rollover": { "max_primary_shard_size": "30gb" } } },
      "warm":   { "min_age": "7d",  "actions": { "shrink": { "number_of_shards": 1 }, "forcemerge": { "max_num_segments": 1 } } },
      "delete": { "min_age": "30d", "actions": { "delete": {} } }
    }
  }
}
```

## Kibana 可视化

我做的一块看板包含这些维度：

1. **告警趋势**（按小时柱状图）— 判断是否突发
2. **Top 源 IP / 目的 IP** — 定位受害主机与攻击源
3. **告警分类饼图** — 判断攻击类型分布
4. **协议分布** — 异常协议占比突增值得关注
5. **DNS 查询 Top** — 发现 DGA 域名的利器

```text
# 一个实用的 KQL：找内网对外的高频连接
event_type:flow AND flow.age:>5 AND src_ip:192.168.0.0/16 AND NOT dst_ip:(192.168.0.0/16 OR 10.0.0.0/8)
```

## 小结

这套东西跑下来，单台 4 核 8G 机器能稳定处理 300 Mbps 左右的镜像流量。真正的价值不在装了多少规则，而在于**持续调规则、持续看告警**——装完不看，等于没装。
