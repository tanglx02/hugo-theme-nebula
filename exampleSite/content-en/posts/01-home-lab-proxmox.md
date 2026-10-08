---
title: "Building a Home Security Lab from Scratch: Proxmox Virtualization and Network Isolation"
date: 2026-09-28
lastmod: 2026-09-28
description: "Build a repeatable pentest and incident-response lab on a second-hand server with Proxmox VE, focusing on network segmentation, snapshot strategy, and capacity planning."
author: "Tanglx"
tags: ["virtualization", "lab", "Proxmox"]
categories: ["environment"]
cover: "/img/cover/lab.svg"
toc: true
series: ["Home Lab 实战"]
series_order: 1
---

The biggest fear in security research is breaking your production environment. A local lab that can be reset at any time, with proper network isolation, lets you run exploit validation, malware analysis, and rule tuning without worry. This post documents the full build process on a single second-hand server.

## Hardware Selection

My requirements: run 8-12 VMs at once (including a Windows AD domain), reasonable power draw, and acceptable noise.

| Component | Choice | Notes |
| --- | --- | --- |
| CPU | Xeon E5-2680 v4 x2 | 28 cores / 56 threads; multithreading matters more than clock speed |
| RAM | 128GB ECC DDR4 | AD domain + traffic analysis love memory |
| Storage | 1TB NVMe + 4TB HDD | NVMe for the OS, HDD for image repos and cold backups |
| NIC | Quad-port gigabit | One management, one WAN simulation, two trunk ports |
