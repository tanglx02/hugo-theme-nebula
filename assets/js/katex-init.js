/*
 * KaTeX 按需初始化（功能四 / 6.3）。
 *
 * 仅在「当前页确实出现数学定界符」时，由 layouts/partials/scripts.html 按需注入。
 * 库本体（katex + auto-render）由用户通过 params.math.* 明确指定，默认不加载。
 *
 * 设计：
 *   1. 定界符：行内 $...$ / \(...\)，块级 $$...$$ / \[...\]；\$ 转义不触发。
 *      （定界符可在 params.math.delimiters 里覆盖，见 partial。）
 *   2. 失败可回退：auto-render 缺失或抛错时，保持原文可读（不空白、不崩）。
 *   3. 逐页开关：HTML 注释 <!-- nebula:no-math --> 可让当前页跳过（见 partial 说明）。
 *   4. 语言中立：不硬编码任何文案。
 */
(function () {
  "use strict";
  var cfg = window.__NEBULA_MATH__ || {};
  var i18n = window.NEBULA_I18N || {};

  // 逐页关闭标记（由作者在正文写 HTML 注释；注释不会进入渲染文本，这里扫描原始 DOM 注释）
  function pageOptedOut() {
    try {
      var w = document.createTreeWalker(document.body, NodeFilter.SHOW_COMMENT, null);
      var n;
      while ((n = w.nextNode())) {
        if ((n.nodeValue || "").indexOf("nebula:no-math") !== -1) return true;
      }
    } catch (e) {}
    return false;
  }
  if (pageOptedOut()) return;

  // 默认定界符（若配置提供则以其为准）
  var delims = Array.isArray(cfg.delimiters) && cfg.delimiters.length
    ? cfg.delimiters
    : [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false }
      ];

  function attachFallback() {
    var scopes = document.querySelectorAll(cfg.selector || ".post-content");
    Array.prototype.forEach.call(scopes, function (el) {
      el.setAttribute("data-math-unrendered", "1");
      el.setAttribute("aria-label", i18n.mathError || "math error");
    });
  }

  function run() {
    if (!window.renderMathInElement) {
      attachFallback();
      return;
    }
    var scopes = document.querySelectorAll(cfg.selector || ".post-content");
    Array.prototype.forEach.call(scopes, function (el) {
      try {
        window.renderMathInElement(el, {
          delimiters: delims,
          throwOnError: false,
          errorColor: "currentColor",
          ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "option"]
        });
      } catch (e) {
        attachFallback();
      }
    });
  }

  var tries = 0;
  (function wait() {
    if (window.renderMathInElement) return run();
    if (tries++ > 30) return attachFallback();
    setTimeout(wait, 100);
  })();
})();