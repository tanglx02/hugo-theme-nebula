---
title: "从零搭建家庭安全实验室：Proxmox 虚拟化与网络隔离实践"
date: 2026-09-28
lastmod: 2026-09-28
description: "用一台二手服务器 + Proxmox VE 搭建可反复重置的渗透测试与应急响应实验环境，重点讲网络分区、快照策略和资源规划。"
author: "Tanglx"
tags: ["虚拟化", "实验室", "Proxmox"]
categories: ["环境搭建"]
cover: "/img/cover/lab.svg"
sticky: true
series: ["Home Lab 实战"]
series_order: 1
toc: true
---

做安全研究最怕的就是把生产环境搞崩。一个可随时重置、网络隔离的本地实验室，能让你放心地跑漏洞验证、恶意样本分析和规则调优。这篇记录我用一台二手服务器搭建的完整过程。

## 硬件选型

我的需求是：能同时跑 8～12 台虚拟机（含 Windows AD 域环境）、功耗可控、噪音可接受。

| 组件 | 选型 | 说明 |
| --- | --- | --- |
| CPU | Xeon E5-2680 v4 ×2 | 28 核 56 线程，多线程比单核频率重要 |
| 内存 | 128GB ECC DDR4 | AD 域 + 流量分析很吃内存，128G 是舒适线 |
| 存储 | 1TB NVMe + 4TB HDD | NVMe 放系统盘，HDD 做镜像仓库与冷备份 |
| 网卡 | 四口千兆 | 一个管理口、一个 WAN 模拟口、两个 trunk |

{{< notice warning >}}
二手服务器噪音普遍在 50dB 以上，放客厅会后悔。条件允许的话优先塔式工作站，或者直接上家用 NAS 机箱改。
{{< /notice >}}

## 网络分区设计

这是整个实验室最关键的部分。我的划分原则：**靶场流量绝不与管理网互通**。

```bash
# /etc/network/interfaces （Proxmox 宿主机）
auto lo
iface lo inet loopback

# 管理口：只有这一口能进 Web 管理界面
iface eno1 inet manual

auto vmbr0
iface vmbr0 inet static
    address 192.168.1.10/24
    gateway 192.168.1.1
    bridge-ports eno1
    bridge-stp off
    bridge-fd 0
    comment 'Management'

# 靶场内网：虚拟机之间互通，但不能主动出网
auto vmbr10
iface vmbr10 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    comment 'Range-LAN'

# 隔离网：恶意样本分析专用，单向隔离
auto vmbr20
iface vmbr20 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    comment 'Malware-Isolated'
```

规则落地用 iptables 在宿主机上做：

```bash
# 禁止靶场网段访问管理网段
iptables -A FORWARD -s 10.10.10.0/24 -d 192.168.1.0/24 -j DROP
# 允许靶场访问外网（便于下载工具），但限制单 IP 连接数
iptables -A FORWARD -s 10.10.10.0/24 -o vmbr0 -p tcp --syn -m connlimit --connlimit-above 40 -j REJECT
# 恶意样本隔离网段：只允许 DNS 和本机日志回传
iptables -A FORWARD -s 172.16.99.0/24 -o vmbr0 -p udp --dport 53 -j ACCEPT
iptables -A FORWARD -s 172.16.99.0/24 -o vmbr0 -j DROP
```

## 虚拟机模板化

不要每台机器都重装一遍。我准备了 4 个模板：

1. `tpl-ubuntu2204` — 基础 Linux，预装 auditd、sysmon-for-linux
2. `tpl-win10` — 关闭 Defender 与 UAC，装 Sysmon + 常见办公软件
3. `tpl-winsrv2019` — AD 域控基线，含 LDAPS 与日志审计策略
4. `tpl-kali` — 攻击机，配置好代理与工具链

用 cloud-init 做初始化，省去逐台配置的麻烦：

```yaml
# /var/lib/vz/snippets/ubuntu.yaml
#cloud-config
hostname: lab-node
manage_etc_hosts: true
package_update: true
packages:
  - auditd
  - audispd-plugins
  - curl
  - vim
  - htop
users:
  - name: lab
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-ed25519 AAAA...your-key...
runcmd:
  - sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
  - systemctl restart sshd
```

```bash
# 绑定 cloud-init
qm set 9001 --cicustom "user=local:snippets/ubuntu.yaml"
qm set 9001 --ipconfig0 ip=10.10.10.50/24,gw=10.10.10.1
qm template 9001
```

## 快照与重置策略

我的经验是**快照不要乱拍**，否则三个月后磁盘就满了。规定：

- 装完系统、装完工具各拍一次"基线快照"，之后只读
- 每次实验前 `qm rollback` 回基线，实验结束直接销毁
- 真正需要长期保存的，用 `vzdump` 导出到 HDD

```bash
# 批量回滚整个靶场
for id in 101 102 103 104; do
  qm rollback $id base --start 1
done

# 每周日凌晨全量备份，保留 2 份
0 3 * * 0 vzdump 101,102,103,104 --mode snapshot --compress zstd \
  --storage hdd-backup --maxfiles 2
```

## 小结

搭好之后，这套环境支撑我完成了 AD 域横向移动复现、Suricata 规则调优和几个恶意样本的动静态分析。核心就三句话：**网络要分区、模板要复用、实验要可回滚**。

下一步我打算把流量镜像口接上，做一个旁路检测的常驻探针。
