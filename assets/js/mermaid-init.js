/*
 * Mermaid 按需初始化（功能四 / 6.2）。
 *
 * 仅在「当前页确实含 ```mermaid 围栏」时，由 layouts/partials/scripts.html
 * 按需注入（页面无图表 -> 0 字节额外资源）。库本体 / 自动加载器由用户通过
 * params.mermaid.* 明确指定（CDN 或自托管），默认不加载 —— 与主题"默认无第三方请求"一致。
 *
 * 设计：
 *   1. 浅/深主题跟随：读取 html[data-theme]，图表 theme 随之切换；切换主题时重渲染。
 *   2. 失败可回退：渲染异常时给容器加 .mermaid-error，CSS 保证原始代码仍可读
 *      （不丢内容、不空白）。
 *   3. 语言中立：错误提示文案来自 window.NEBULA_I18N，不硬编码。
 *   4. 不污染全局：整个逻辑包在 IIFE 中，只读取 window.__NEBULA_MERMAID__ 配置。
 */
(function () {
  "use strict";
  var cfg = window.__NEBULA_MERMAID__ || {};
  var nodes = document.querySelectorAll("pre.mermaid, .mermaid[data-mermaid]");
  if (!nodes.length) return;

  var i18n = window.NEBULA_I18N || {};

  function mark(el, cls, text) {
    el.classList.add(cls);
    if (text && !el.getAttribute("data-fallback")) {
      el.setAttribute("data-fallback", "1");
      el.setAttribute("aria-label", text);
    }
  }

  function themeOf() {
    return document.documentElement.getAttribute("data-theme") === "dark"
      ? (cfg.themeDark || "dark")
      : (cfg.themeLight || "default");
  }

  function run() {
    if (!window.mermaid || typeof window.mermaid.run !== "function") return;
    try {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: themeOf(),
        fontFamily: cfg.fontFamily || "inherit"
      });
      window.mermaid.run({ nodes: Array.prototype.slice.call(nodes) })
        .catch(function () {
          Array.prototype.forEach.call(nodes, function (el) {
            mark(el, "mermaid-error", i18n.mermaidError || "diagram error");
          });
        });
    } catch (e) {
      Array.prototype.forEach.call(nodes, function (el) {
        mark(el, "mermaid-error", i18n.mermaidError || "diagram error");
      });
    }
  }

  // 库可能已加载（同步）或仍在加载（defer/async）。两种都等一下，最多重试 ~3s。
  var tries = 0;
  (function wait() {
    if (window.mermaid && typeof window.mermaid.run === "function") return run();
    if (tries++ > 30) {
      Array.prototype.forEach.call(nodes, function (el) {
        mark(el, "mermaid-error", i18n.mermaidError || "diagram error");
      });
      return;
    }
    setTimeout(wait, 100);
  })();

  // 主题切换 -> 重渲染（保留原始源码，避免二次解析失败）
  var raw = Array.prototype.map.call(nodes, function (el) {
    return el.getAttribute("data-original") || el.textContent;
  });
  Array.prototype.forEach.call(nodes, function (el, i) {
    if (!el.getAttribute("data-original")) el.setAttribute("data-original", raw[i]);
  });
  var last = document.documentElement.getAttribute("data-theme");
  new MutationObserver(function () {
    var now = document.documentElement.getAttribute("data-theme");
    if (now === last) return;
    last = now;
    Array.prototype.forEach.call(nodes, function (el, i) {
      el.removeAttribute("data-processed");
      el.classList.remove("mermaid-error");
      el.textContent = raw[i];
    });
    run();
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();