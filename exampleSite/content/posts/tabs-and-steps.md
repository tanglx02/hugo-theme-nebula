---
title: "标签页与步骤：多平台命令与流程化操作"
date: 2026-10-02
lastmod: 2026-10-02
description: "技术内容组件演示：tabs/tab 呈现 Linux/Windows/macOS 命令与多种安装方式，steps/step 呈现逐步流程。面板内代码块自动带语言标签与一键复制；无 JavaScript 时内容全部可见。"
tags: ["标签页", "步骤", "技术写作"]
categories: ["功能演示"]
toc: true
---

本页演示**功能三（技术内容组件）**的第二、三项：**标签页**与**步骤**。

两者都是 shortcode，都**不依赖 JavaScript** 才能显示内容——
标签页在无脚本时把全部面板顺序展开，步骤的编号由 CSS 生成。

## 一、标签页：同一件事的不同平台做法

最典型的用途：一条命令，三个系统。

{{< tabs >}}
{{< tab "Linux" >}}

Debian / Ubuntu 系：

```bash
sudo apt update
sudo apt install -y build-essential git curl
```

{{< /tab >}}
{{< tab "macOS" >}}

需要先装 Xcode Command Line Tools：

```bash
xcode-select --install
brew install git curl
```

{{< /tab >}}
{{< tab "Windows" >}}

PowerShell（推荐 winget）：

```powershell
winget install --id Git.Git -e
winget install --id cURL.cURL -e
```

{{< /tab >}}
{{< /tabs >}}

每个面板里的代码块都带**语言标签**和**一键复制**按钮 —— 这一点是自动的，
面板内容走的仍是主题统一的代码块渲染管线，没有为标签页另做一套。

## 二、标签页：同一件事的不同安装方式

{{< tabs >}}
{{< tab "包管理器" >}}

```bash
sudo apt install neovim
```

优点：随系统更新，卸载干净。

{{< /tab >}}
{{< tab "官方二进制" >}}

从 GitHub Releases 下载对应架构的压缩包：

```bash
curl -LO https://github.com/neovim/neovim/releases/latest/download/nvim-linux-x86_64.tar.gz
sudo tar -C /opt -xzf nvim-linux-x86_64.tar.gz
sudo ln -sf /opt/nvim-linux-x86_64/bin/nvim /usr/local/bin/nvim
```

优点：版本新，不依赖发行版仓库。

{{< /tab >}}
{{< tab "容器" >}}

```bash
docker run --rm -it -v "$PWD:/work" -w /work alpine:3.20 sh
```

优点：不污染宿主机，适合临时环境。

{{< /tab >}}
{{< /tabs >}}

## 三、步骤：一次完整的操作流程

步骤用 `<ol>` 语义输出，编号由 CSS 计数器生成，因此**不需要 JavaScript**，
读屏软件也会按"第 N 步 / 共 M 步"朗读。

{{< steps >}}
{{< step "准备环境" >}}

先确认系统与版本，避免装错包：

```bash
uname -m && cat /etc/os-release | head -2
```

{{< /step >}}
{{< step "安装依赖" >}}

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
```

{{< /step >}}
{{< step "添加软件源并安装" >}}

```bash
curl -fsSL https://example.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/demo.gpg
echo "deb [signed-by=/usr/share/keyrings/demo.gpg] https://example.com/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/demo.list
sudo apt update && sudo apt install -y demo-agent
```

{{< /step >}}
{{< step "验证安装" >}}

输出版本号即为成功：

```bash
demo-agent --version
```

若提示找不到命令，回到第 3 步检查软件源地址与密钥路径。

{{< /step >}}
{{< /steps >}}

步骤标题是**可选**的 —— 不写标题就只显示序号：

{{< steps >}}
{{< step >}}

先看当前状态：

```bash
systemctl status nginx --no-pager
```

{{< /step >}}
{{< step >}}

再决定是否重载：

```bash
sudo systemctl reload nginx
```

{{< /step >}}
{{< /steps >}}

## 四、两者可以嵌套

标签页里放步骤，或步骤里放标签页，都可以：

{{< tabs >}}
{{< tab "方式 A：脚本安装" >}}

{{< steps >}}
{{< step >}}

```bash
curl -fsSL https://example.com/install.sh | bash
```

{{< /step >}}
{{< step >}}

```bash
demo-agent --version
```

{{< /step >}}
{{< /steps >}}

{{< /tab >}}
{{< tab "方式 B：手动安装" >}}

{{< steps >}}
{{< step "下载" >}}

```bash
curl -LO https://example.com/demo-agent.tar.gz
```

{{< /step >}}
{{< step "解压并放置" >}}

```bash
tar -xzf demo-agent.tar.gz
sudo mv demo-agent /usr/local/bin/
```

{{< /step >}}
{{< /steps >}}

{{< /tab >}}
{{< /tabs >}}

## 五、没有 JavaScript 会怎样

这是本组件的核心设计约束：**内容不依赖脚本**。

- **标签页**：脚本缺席时，导航条自动隐藏（避免出现"点了没反应"的按钮），
  全部面板**顺序展开**，并在每个面板内显示它自己的标题。
  也就是说，禁用 JavaScript 只会失去"点选切换"这一种交互，**不会丢内容**。
- **步骤**：本来就不需要脚本，编号由 CSS `counter` 生成，无脚本时完全一致。

可以试试在浏览器里禁用 JavaScript 后刷新本页，或搜索"无 JS"相关说明。

## 六、键盘与无障碍

脚本可用时，标签页升级为标准的 WAI-ARIA 标签页模式
（W3C APG 的 `patterns/tabs/`，此处不放出站外链以避免示例站点引入第三方请求）：

| 按键 | 行为 |
| --- | --- |
| `Tab` | 焦点进入标签条（整条只占**一个** Tab 位） |
| `←` `→` | 在标签间移动并立即切换 |
| `↑` `↓` | 窄屏下标签条纵向排列时等价于左右 |
| `Home` `End` | 跳到第一个 / 最后一个标签 |
| `Enter` `Space` | 由原生按钮负责，无需额外操作 |

状态通过 `aria-selected`、`aria-controls`、`aria-labelledby` 与面板的 `hidden`
同步，读屏软件能正确播报"已选中 / 未选中"与面板归属。

## 七、打印

打印本页（或导出 PDF）时，**全部面板会被展开**，
不会只打印当前选中的那一个；导航条、复制按钮等交互元素会被移除，
步骤的圆点改为高对比度黑白色以适应黑白打印。

## 八、版本兼容说明

`tabs` / `tab` / `steps` / `step` 全部由 shortcode 与 CSS 实现，
在主题支持的全部 Hugo 版本（0.128.0 起）上行为一致，
面板内的代码块渲染管线与普通代码块**完全相同**。