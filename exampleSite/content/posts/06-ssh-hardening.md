---
title: "SSH 加固从入门到实用：密钥、端口敲门与审计"
date: 2026-08-16
lastmod: 2026-08-16
description: "一份递进式的 SSH 加固方案：从密钥登录、失败锁定，到端口敲门、双因子与会话审计，含可直接复制的配置文件。"
author: "Tanglx"
tags: ["SSH", "加固", "Linux"]
categories: ["主机加固"]
cover: "/img/cover/ssh.svg"
toc: true
---

SSH 是运维的命脉，也是攻击者最先盯的入口。这篇按"能用 → 好用 → 安全"的顺序给一套递进方案。

## 第一层：关掉最危险的三件事

```bash
# /etc/ssh/sshd_config
PermitRootLogin no
PasswordAuthentication no
PermitEmptyPasswords no
```

改之前**务必先验证密钥能登录**，否则直接把自己锁在门外：

```bash
# 本地生成 ed25519 密钥
ssh-keygen -t ed25519 -C "tanglx@lab" -f ~/.ssh/id_ed25519_lab

# 推送公钥（密码登录还没关的时候）
ssh-copy-id -i ~/.ssh/id_ed25519_lab.pub user@host

# 另开一个终端验证，确认能进再关密码登录
ssh -i ~/.ssh/id_ed25519_lab user@host
```

{{< notice danger >}}
永远不要在不保持一个已登录会话的情况下修改 sshd 配置。改完用 `sshd -t` 检查语法，再 `systemctl reload sshd`（reload 不会踢掉现有连接）。
{{< /notice >}}

## 第二层：一份完整的加固配置

```conf
# /etc/ssh/sshd_config.d/10-hardening.conf
Port 22
Protocol 2

# 认证
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM yes
MaxAuthTries 3
LoginGraceTime 30
AllowUsers tanglx ops

# 转发限制（绝大多数场景都不需要）
AllowAgentForwarding no
AllowTcpForwarding no
X11Forwarding no
PermitTunnel no

# 会话
ClientAliveInterval 300
ClientAliveCountMax 2
TCPKeepAlive no

# 加密套件
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,diffie-hellman-group-exchange-sha256
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes256-ctr
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com

# 日志
SyslogFacility AUTH
LogLevel VERBOSE

# 横幅（法律上的"警告"作用）
Banner /etc/ssh/banner.txt
```

```bash
sudo sshd -t && sudo systemctl reload sshd
```

## 第三层：失败锁定（fail2ban）

```ini
# /etc/fail2ban/jail.d/sshd.local
[sshd]
enabled  = true
port     = ssh
filter   = sshd
logpath  = /var/log/auth.log
maxretry = 3
findtime = 600
bantime  = 86400
bantime.increment = true
bantime.factor = 2
bantime.maxtime = 604800
action   = iptables-multiport[name=sshd, port="ssh", protocol=tcp]
```

```bash
# 查看与解封
fail2ban-client status sshd
fail2ban-client set sshd unbanip 1.2.3.4
```

## 第四层：端口敲门（Port Knocking）

让 SSH 端口默认关闭，只有按正确顺序"敲"几个端口才临时开放：

```bash
apt install -y knockd
```

```ini
# /etc/knockd.conf
[options]
    UseSyslog
    Interface = eth0

[openSSH]
    sequence    = 7000,8000,9000
    seq_timeout = 10
    command     = /sbin/iptables -I INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
    tcpflags    = syn

[closeSSH]
    sequence    = 9000,8000,7000
    seq_timeout = 10
    command     = /sbin/iptables -D INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
    tcpflags    = syn
```

客户端使用：

```bash
knock -v host 7000 8000 9000 && ssh user@host
```

{{< notice info >}}
端口敲门防的是扫描器和自动化爆破，防不了定向攻击者（流量可被抓包重放）。更稳的方案是 **SPA（Single Packet Authentication）**，比如 fwknop。
{{< /notice >}}

## 第五层：会话审计

开启 `LogLevel VERBOSE` 后能看到密钥指纹，配合 auditd 记录命令：

```bash
# 记录所有 execve（生产环境请按用户过滤，量很大）
-a exit,always -F arch=b64 -F euid>=1000 -S execve -k user_cmd

# 或者更轻量：给每个用户配 bash 审计
cat >> /etc/profile.d/audit.sh <<'EOF'
export PROMPT_COMMAND='RETRN_VAL=$?; logger -p local6.debug "$(whoami) [$$]: $(history 1 | sed "s/^[ ]*[0-9]*[ ]*//")"'
EOF
```

## 效果验证

| 检查项 | 命令 | 期望结果 |
| --- | --- | --- |
| root 登录 | `ssh root@host` | Permission denied |
| 密码登录 | `ssh -o PubkeyAuthentication=no user@host` | Permission denied |
| 端口状态 | `nmap -p 22 host` | filtered（敲门场景下） |
| 协议与算法 | `nmap --script ssh2-enum-algos host` | 无 arcfour / CBC / SHA1 |

## 小结

安全与便利永远在做权衡。我的建议是：**对公网暴露的机器做到第三层，核心资产做到第四层，有合规要求的做全五层**。
