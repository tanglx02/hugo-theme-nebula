---
title: "应急响应手册：Linux 主机入侵排查的 20 个检查点"
date: 2026-09-12
lastmod: 2026-09-12
description: "一份可以直接照着敲的 Linux 入侵排查清单，覆盖进程、网络、账号、持久化、日志与取证保全。"
author: "Tanglx"
tags: ["应急响应", "Linux", "取证"]
categories: ["应急响应"]
cover: "/img/cover/ir.svg"
toc: true
---

接到告警后最忌讳的就是上来就 `kill -9`。正确的顺序是：**先保全，再断链，最后清理**。下面这份清单是我在多次应急中沉淀下来的，可以直接照着执行。

## 0. 现场保全（动手前必做）

任何操作都会破坏证据。先做三件事：

```bash
# 1. 记录当前时间与时区（后面做时间线关联要用）
date -u && date && cat /etc/timezone

# 2. 保存内存中的进程与网络连接快照
ps auxf > /tmp/ir_$(date +%s)_ps.txt
ss -tunap > /tmp/ir_$(date +%s)_ss.txt
lsof -nP > /tmp/ir_$(date +%s)_lsof.txt

# 3. 记录登录态与历史命令（不要清空！）
last -a > /tmp/ir_last.txt
who /var/log/wtmp > /tmp/ir_who.txt
cat /root/.bash_history > /tmp/ir_history_root.txt
```

{{< notice warning >}}
绝对不要第一时间 `rm` 可疑文件、不要 `history -c`、不要重启。重启会丢失内存中的网络连接与未落盘的恶意进程。
{{< /notice >}}

## 1. 账号检查（1-5）

```bash
# 检查点 1：UID 为 0 的账号，理论上只有 root
awk -F: '$3==0 {print $1, $3, $7}' /etc/passwd

# 检查点 2：可登录 shell 的账号（排除 nologin/false）
awk -F: '$7 !~ /(nologin|false|sync)/ {print $1, $7}' /etc/passwd

# 检查点 3：近期新增/修改的账号（对比 /etc/passwd 与备份）
ls -l --time-style=full-iso /etc/passwd /etc/shadow /etc/group

# 检查点 4：空口令账号
awk -F: '($2=="") {print $1}' /etc/shadow

# 检查点 5：sudo 权限异常
grep -vE '^#|^$' /etc/sudoers /etc/sudoers.d/* 2>/dev/null
```

## 2. 进程与网络（6-11）

```bash
# 检查点 6：CPU/内存异常进程
ps -eo pid,ppid,user,pcpu,pmem,etime,comm --sort=-pcpu | head -20

# 检查点 7：进程可执行文件已被删除（典型的无文件落地攻击）
ls -l /proc/*/exe 2>/dev/null | grep -i deleted

# 检查点 8：进程树关系异常的孤儿进程
ps -eo pid,ppid,cmd | awk '$2==1' 

# 检查点 9：对外监听端口
ss -tunlp

# 检查点 10：已建立的外部连接（重点看非常规端口）
ss -tanp state established | awk '{print $5}' | sort | uniq -c | sort -rn | head

# 检查点 11：DNS 与 hosts 劫持
cat /etc/resolv.conf && cat /etc/hosts
```

排查网络连接时，我习惯先做一次"基数统计"，异常往往一眼可见：

```bash
ss -tan | awk '{print $4}' | cut -d: -f1 | sort | uniq -c | sort -rn | head -15
```

## 3. 持久化检查（12-17）

| # | 检查项 | 命令 |
| --- | --- | --- |
| 12 | crontab | `crontab -l -u root; ls /etc/cron.d/ /var/spool/cron/` |
| 13 | systemd 单元 | `systemctl list-unit-files --type=service --state=enabled` |
| 14 | 启动脚本 | `ls -l /etc/rc.local /etc/rc.d/ /etc/init.d/` |
| 15 | 动态链接库劫持 | `cat /etc/ld.so.preload 2>/dev/null` |
| 16 | SSH 公钥 | `ls -l /root/.ssh/ ~/.ssh/authorized_keys` |
| 17 | profile 后门 | `grep -rn "curl\|wget\|nc -" /etc/profile.d/ ~/.bashrc ~/.profile` |

第 15 项 `ld.so.preload` 经常被忽略，但它是非常隐蔽的持久化手段：

```bash
# 如果这里有内容且你不认识，几乎可以确定被入侵了
cat /etc/ld.so.preload

# 排查方式：比对已知库文件
ldd /bin/ls
strace -f -e trace=file /bin/ls 2>&1 | grep -i preload
```

## 4. 文件与日志（18-20）

```bash
# 检查点 18：近 3 天被修改的系统二进制（用包管理器校验）
rpm -Va 2>/dev/null | head -30          # RHEL/CentOS
dpkg -V 2>/dev/null | head -30          # Debian/Ubuntu

# 检查点 19：/tmp /dev/shm 下的可执行文件
find /tmp /dev/shm /var/tmp -type f -perm -u+x -ls 2>/dev/null

# 检查点 20：SSH 登录失败与成功记录
grep -E "Failed password|Accepted" /var/log/auth.log 2>/dev/null | tail -50
journalctl -u sshd --since "3 days ago" 2>/dev/null | grep -E "Failed|Accepted"
```

## 时间线整理

排查完把关键事件按时间排序，能快速还原攻击链：

```bash
# 找出 web 目录下 7 天内新增的脚本文件
find /var/www -type f \( -name "*.php" -o -name "*.jsp" \) -mtime -7 -ls

# 与日志时间做关联
grep -F "$(date -d '3 days ago' +%b' '%d)" /var/log/nginx/access.log | \
  awk '{print $1, $4, $6, $7}' | sort | uniq -c | sort -rn | head -20
```

## 处置建议

| 阶段 | 动作 |
| --- | --- |
| 断链 | 隔离主机（不改配置的前提下加防火墙规则）、下线对外服务 |
| 清根治 | 删除后门文件、清理恶意账号、修漏洞入口 |
| 恢复 | 从可信备份重建，或重装后回放配置 |
| 复盘 | 输出攻击链时间线，补齐检测规则 |

{{< notice info >}}
如果条件允许，尽量做一次完整的磁盘镜像（`dd` 或 `e01`）再重建。事后复盘时你会发现，很多细节只有原始镜像能回答。
{{< /notice >}}
