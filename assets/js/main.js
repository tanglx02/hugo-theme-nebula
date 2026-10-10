/* Nebula theme — interactions */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var T_ = window.NEBULA_I18N || {};      // 由 templates/partials/scripts.html 注入
  function tf(str, vars) {                 // 简易 {n} 占位符替换
    if (!str) return '';
    return String(str).replace(/\{(\w+)\}/g, function (m, k) {
      return (vars && vars[k] != null) ? vars[k] : m;
    });
  }

  /* ---------- Theme toggle ---------- */
  var toggle = $('#themeToggle');
  if (toggle) {
    var setIcon = function () {
      var dark = document.documentElement.getAttribute('data-theme') === 'dark';
      var sun = $('.i-sun', toggle), moon = $('.i-moon', toggle);
      if (sun) sun.style.display = dark ? 'none' : 'block';
      if (moon) moon.style.display = dark ? 'block' : 'none';
    };
    setIcon();
    toggle.addEventListener('click', function () {
      var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('nebula-theme', next); } catch (e) {}
      setIcon();
    });
  }

  /* ---------- Mobile menu ----------
     下拉面板（非全屏 modal），因此不锁定背景滚动。
     可访问性：aria-expanded 必须反映展开状态（WCAG 4.1.2），Escape 可关闭（WCAG 2.1.2）。 */
  var burger = $('#burger'), nav = $('#mainNav');
  if (burger && nav) {
    var setMenu = function (open) {
      nav.classList.toggle('mobile-open', open);
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    };
    if (!burger.hasAttribute('aria-controls') && nav.id) {
      burger.setAttribute('aria-controls', nav.id);
    }
    burger.setAttribute('aria-expanded',
      nav.classList.contains('mobile-open') ? 'true' : 'false');
    burger.addEventListener('click', function () {
      setMenu(!nav.classList.contains('mobile-open'));
    });
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target) && !burger.contains(e.target)) setMenu(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('mobile-open')) {
        setMenu(false);
        /* preventScroll：焦点归还汉堡按钮，但**不得**改变页面滚动位置
           （BUG-R2-004：Chromium/WebKit 会因 focus() 把文档滚到触发元素处）。 */
        try { burger.focus({ preventScroll: true }); } catch (err) { try { burger.focus(); } catch (e2) {} }
      }
    });
  }

  /* ---------- Scroll: progress / header shadow / back to top ----------
     进度条（功能二）：宽度按**真实阅读区**计算，而不是整篇文档。
       - 阅读区优先取 .post-content（正文 prose），退化为 <article>，再退化为整篇文档；
       - 起点 = 阅读区顶部与视口顶端对齐时；终点 = 阅读区底部抵达视口底部时；
         正文比视口还短时直接记满（ratio=1），不会卡在 0 或冲出 100。
     默认外观（位置 / 尺寸 / 渐变 / 过渡）与历史完全一致，只是"滚动量→宽度"的
     映射改为围绕正文，语义更准确（此前是整篇文档，含页脚 / 相关文章）。 */
  var header = $('#siteHeader'), bar = $('#progressBar'), toTop = $('#toTop');

  /* 尊重系统"减少动态效果"：平滑滚动降级为瞬时跳转 */
  var REDUCE_MOTION = false;
  try { REDUCE_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  function readingArea() {
    var pc = $('.post-content');
    if (pc) return pc;
    return $('article');
  }

  function onScroll() {
    var st = window.pageYOffset || document.documentElement.scrollTop || 0;
    if (bar) {
      var area = readingArea();
      var ratio;
      if (area && area.offsetHeight > 0) {
        var top = area.getBoundingClientRect().top + st;   // 阅读区顶部的文档绝对坐标
        var start = top;
        var end = top + area.offsetHeight - window.innerHeight;
        var span = end - start;
        ratio = span > 0 ? (st - start) / span : (st >= start ? 1 : 0);
      } else {
        var h = document.documentElement.scrollHeight - window.innerHeight;
        ratio = h > 0 ? st / h : 0;
      }
      if (!isFinite(ratio)) ratio = 0;
      ratio = Math.min(1, Math.max(0, ratio));
      bar.style.width = (ratio * 100) + '%';
    }
    if (header) header.classList.toggle('is-scrolled', st > 10);
    if (toTop) toTop.classList.toggle('show', st > 400);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });
  onScroll();
  /* 返回顶部：<button> 天然键盘可达（Tab 聚焦、Enter / Space 触发），
     此处只需在减少动效时避免平滑滚动。 */
  if (toTop) toTop.addEventListener('click', function () {
    try { window.scrollTo({ top: 0, behavior: REDUCE_MOTION ? 'auto' : 'smooth' }); }
    catch (e) { window.scrollTo(0, 0); }
  });

  /* ---------- Focus mode（功能二：专注阅读） ----------
     设计约束（对应验收要求）：
       - **不隐藏正文**：只收起侧栏 / 相关文章 / 系列 等次要区块（CSS 负责）；
       - **不失去导航**：站点头部导航始终保留，随时可离开当前页；
       - **不破坏焦点**：被收起元素用 display:none（移除 Tab 序），
         按钮本身是原生 <button>，aria-pressed 反映当前状态；
       - 偏好持久化到 localStorage，并在 head 中**提前应用**避免刷新闪动；
       - Escape 可退出（有浮层打开时让位给浮层的 Escape）。 */
  var focusBtn = $('#focusToggle');
  if (focusBtn) {
    var focusLabel = $('.focus-label', focusBtn);
    var setFocus = function (on, persist) {
      document.documentElement.classList.toggle('focus-on', on);
      focusBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
      var text = on ? (T_.focusExit || 'Exit focus mode') : (T_.focusMode || 'Focus mode');
      if (focusLabel) focusLabel.textContent = text;
      focusBtn.setAttribute('aria-label', text);
      focusBtn.setAttribute('title', text);
      if (persist) {
        try {
          if (on) localStorage.setItem('nebula-focus', 'on');
          else localStorage.removeItem('nebula-focus');
        } catch (e) {}
      }
    };
    /* 初始态由 head 里的提前脚本写入 html.focus-on，这里同步按钮状态即可 */
    setFocus(document.documentElement.classList.contains('focus-on'), false);
    focusBtn.addEventListener('click', function () {
      setFocus(!document.documentElement.classList.contains('focus-on'), true);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (!document.documentElement.classList.contains('focus-on')) return;
      /* 浮层打开时 Escape 属于浮层（工厂会处理），这里不抢 */
      if ($('.lightbox.open') || $('.search-overlay.open')) return;
      setFocus(false, true);
    });
  }

  /* ---------- Clipboard（统一实现） ----------
     代码块复制 / 分享复制 / 微信复制共用同一实现，结果只有 success / failure。

     规则（**不允许"超时算成功"**）：
       1) navigator.clipboard.writeText  resolve -> success；reject -> 走 fallback
       2) 无 Clipboard API        -> 直接 fallback
       3) fallback 用 document.execCommand('copy')，**必须检查返回值**，非 true 即 failure
       4) Promise 长时间 pending  -> 超时（默认 1200ms）先尝试 fallback；
          仍失败即 failure，绝不显示成功
       5) 任何路径下回调只触发一次                                                 */
  var COPY_TIMEOUT_MS = 1200;

  function copyText(text, cb) {
    var settled = false;
    function finish(ok) {
      if (settled) return;
      settled = true;
      cb(ok === true);
    }

    function execFallback() {
      var ok = false;
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.top = '-1000px';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { ok = document.execCommand('copy') === true; } catch (e) { ok = false; }
        document.body.removeChild(ta);
      } catch (e) { ok = false; }
      finish(ok);                     // execCommand 返回 false 时不能显示成功
    }

    try {
      if (text && navigator.clipboard && navigator.clipboard.writeText) {
        var pr = navigator.clipboard.writeText(text);
        if (pr && typeof pr.then === 'function') {
          pr.then(function () { finish(true); }, execFallback);
          setTimeout(function () { if (!settled) execFallback(); }, COPY_TIMEOUT_MS);
          return;
        }
      }
    } catch (e) { /* 落回 fallback */ }
    execFallback();
  }

  /* ---------- Code copy ---------- */
  function copyFromButton(btn) {
    var block = btn.closest('.code-block');
    var code = block ? block.querySelector('pre') : null;
    if (!code) return;
    var text = code.innerText || code.textContent || '';
    /* 恢复用的原文案取自按钮**服务端渲染**的内容（首次点击时缓存），
       而不是 JS 里再拼一个常量：文案随站点语言（i18n）走，也不会因
       按钮内含 SVG 而被清空。 */
    var old = btn.getAttribute('data-label');
    if (old == null) {
      old = (btn.textContent || '').trim();
      btn.setAttribute('data-label', old);
    }
    var ICON_OK = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';

    copyText(text, function (ok) {
      btn.innerHTML = ok
        ? ICON_OK + (T_.copied || 'Copied')
        : (T_.copyFailed || 'Copy failed');
      btn.classList.toggle('copied', ok);
      btn.classList.toggle('copy-failed', !ok);
      setTimeout(function () {
        btn.textContent = old;
        btn.classList.remove('copied', 'copy-failed');
      }, ok ? 1600 : 2200);
    });
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var copyBtn = t.closest('.code-copy');
    if (copyBtn) { copyFromButton(copyBtn); return; }
    var shareBtn = t.closest('[data-share="copy"]');
    if (shareBtn) {
      var url = shareBtn.getAttribute('data-url') || location.href;
      var oldText = shareBtn.textContent;
      copyText(url, function (ok) {
        shareBtn.textContent = ok ? (T_.linkCopied || 'Link copied')
                                  : (T_.copyFailed || 'Copy failed');
        shareBtn.classList.toggle('copy-failed', !ok);
        setTimeout(function () {
          shareBtn.textContent = oldText;
          shareBtn.classList.remove('copy-failed');
        }, ok ? 1600 : 2200);
      });
    }
  });

  /* ---------- TOC active highlight ---------- */
  var tocLinks = $$('.toc a');
  if (tocLinks.length) {
    var map = {};
    tocLinks.forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute('href').split('#')[1] || '');
      var el = id ? document.getElementById(id) : null;
      if (el) map[id] = { link: a, el: el };
    });
    var ids = Object.keys(map);
    var current = null;
    function updateTOC() {
      var pos = window.pageYOffset + 120, activeId = null;
      ids.forEach(function (id) {
        if (map[id].el.offsetTop <= pos) activeId = id;
      });
      if (activeId === null && ids.length) activeId = ids[0];
      if (activeId !== current) {
        tocLinks.forEach(function (a) { a.classList.remove('active'); });
        if (activeId && map[activeId]) map[activeId].link.classList.add('active');
        current = activeId;
      }
    }
    window.addEventListener('scroll', updateTOC, { passive: true });
    updateTOC();
  }

  /* ================================================================
   * 页面滚动锁定（多模态安全，引用计数）
   *
   * 所有 dialog 型浮层（搜索弹窗 / 灯箱）共用这一份锁：
   *   - 打开时记住 body **打开前真实的 inline overflow**，再置 hidden
   *   - 只有最后一个打开的浮层关闭时才恢复原值（不是无条件置空）
   *   - 嵌套 / 快速重复开关按计数平衡，不会残留 hidden，也不会误解锁
   *
   * 为什么集中在这里：历史缺陷（BUG-P1-001）是搜索模块**自己的** close() 才恢复
   * overflow，而遮罩点击与 Escape 走的是 createModalA11y 内部的 close()，
   * 于是 Overflow 永远停在 hidden，页面彻底滚不动。把锁交给工厂后，
   * 无论从哪条路径关闭都必然走到同一处恢复逻辑。
   * ================================================================ */
  var scrollLockCount = 0;
  var scrollLockPrev = null;

  function lockBodyScroll() {
    if (scrollLockCount === 0) {
      scrollLockPrev = document.body.style.overflow;   // 记住打开前的真实值
      document.body.style.overflow = 'hidden';
    }
    scrollLockCount++;
  }

  function unlockBodyScroll() {
    if (scrollLockCount > 0) scrollLockCount--;
    if (scrollLockCount === 0) {
      document.body.style.overflow = (scrollLockPrev == null) ? '' : scrollLockPrev;
      scrollLockPrev = null;
    }
  }

  /* ================================================================
   * createModalA11y —— 轻量 Modal 无障碍工厂（零依赖）
   *
   * 为所有 dialog 型浮层（搜索弹窗、灯箱）提供同一套交互契约：
   *   - 打开：焦点移入 initialFocus；背景 inert + aria-hidden；锁定页面滚动
   *   - Tab / Shift+Tab 在 dialog 内循环，焦点无法逃出
   *   - Escape 关闭；可选点击遮罩关闭
   *   - 关闭：解除 inert、恢复滚动、并把焦点还给触发元素
   *   - 快速重复 open/close 幂等，不会残留 inert / 滚动锁 / 焦点错乱
   *   - 无触发元素时（如 ?q= 深链自动打开）退化为聚焦 dialog 自身，不报错
   *
   * 抽成工厂而不是各自复制：任何新增 modal 调用它即可满足同一份契约
   * （见 docs/测试说明.md 的 Modal 无障碍标准）。
   * ================================================================ */
  function createModalA11y(opts) {
    var root = opts.root;
    if (!root) return null;

    var OPEN_CLASS = opts.openClass || 'open';
    var CLOSE_ON_OVERLAY = opts.closeOnOverlay !== false;
    var LOCK_SCROLL = opts.lockScroll !== false;   // 默认开启；如需禁用可显式传 false
    var BG_SELECTORS = ['.progress-bar', '.site-header', 'main', '.site-footer', '.to-top'];
    var inertNodes = [];
    var lastTrigger = null;
    var isOpen = false;
    var keyHandler = null;

    function focusables() {
      return $$('button, [href], input, select, textarea, [tabindex]', root)
        .filter(function (el) {
          return el.getAttribute('tabindex') !== '-1' &&
            el.offsetWidth > 0 && el.offsetHeight > 0;
        });
    }

    /* 背景不可键盘交互：原生 inert 优先；旧浏览器退化为 aria-hidden，
       此时 focus trap 仍保证焦点不会落到背景上 */
    function setBackgroundInert(on) {
      if (on) {
        inertNodes = [];
        BG_SELECTORS.forEach(function (sel) {
          $$(sel).forEach(function (n) {
            if (!n || n === root || root.contains(n)) return;
            if (n.hasAttribute('inert')) return;   // 已被其它 modal 标记，避免误解除
            inertNodes.push({ node: n, hadAria: n.getAttribute('aria-hidden') });
            n.setAttribute('inert', '');
            n.setAttribute('aria-hidden', 'true');
          });
        });
        // 另一个浮层（灯箱 / 搜索）若已打开，同样标记为背景
        $$('.lightbox, .search-overlay').forEach(function (n) {
          if (!n || n === root) return;
          if (n.classList.contains(OPEN_CLASS) && !n.hasAttribute('inert')) {
            inertNodes.push({ node: n, hadAria: null });
            n.setAttribute('inert', '');
            n.setAttribute('aria-hidden', 'true');
          }
        });
      } else {
        inertNodes.forEach(function (r) {
          r.node.removeAttribute('inert');
          if (r.hadAria == null) r.node.removeAttribute('aria-hidden');
          else r.node.setAttribute('aria-hidden', r.hadAria);
        });
        inertNodes = [];
      }
    }

    function onKeydown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
        return;
      }
      if (e.key !== 'Tab') return;
      var f = focusables();
      if (!f.length) { e.preventDefault(); root.focus(); return; }
      var first = f[0], last = f[f.length - 1];
      var active = document.activeElement;
      if (!root.contains(active)) { e.preventDefault(); first.focus(); return; }
      if (e.shiftKey && (active === first || active === root)) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault(); first.focus();
      }
    }

    function open(triggerEl, initialText) {
      if (isOpen) close();                 // 幂等：重复打开先清理上一轮
      isOpen = true;
      lastTrigger = triggerEl || null;
      root.classList.add(OPEN_CLASS);
      root.setAttribute('aria-hidden', 'false');
      if (root.getAttribute('tabindex') === null) root.setAttribute('tabindex', '-1');
      setBackgroundInert(true);
      if (LOCK_SCROLL) lockBodyScroll();
      keyHandler = onKeydown;
      document.addEventListener('keydown', keyHandler, true);
      if (initialText != null) {
        var inp = opts.input || $('input, textarea', root);
        if (inp) inp.value = initialText;
      }
      var target = opts.initialFocus || focusables()[0] || root;
      requestAnimationFrame(function () { target.focus(); });
    }

    function close() {
      if (!isOpen) return;                 // 幂等
      isOpen = false;
      root.classList.remove(OPEN_CLASS);
      root.setAttribute('aria-hidden', 'true');
      setBackgroundInert(false);
      if (LOCK_SCROLL) unlockBodyScroll();
      if (keyHandler) {
        document.removeEventListener('keydown', keyHandler, true);
        keyHandler = null;
      }
      /* 焦点恢复：优先还给触发元素；深链等无触发场景退化为 dialog 自身。
         **preventScroll:true** —— 只归还焦点，绝不改变页面滚动位置。
         历史缺陷（BUG-R2-004）：触发按钮（如 .search-trigger）在文档流中位于页面顶部，
         Chromium/WebKit 会因 focus() 把文档滚回其静态位置，用户读完长文开关搜索后
         页面位置被拉走。preventScroll 在不牺牲焦点可访问性的前提下消除该副作用。 */
      if (lastTrigger && document.contains(lastTrigger) &&
          typeof lastTrigger.focus === 'function') {
        try { lastTrigger.focus({ preventScroll: true }); }
        catch (e) { try { lastTrigger.focus(); } catch (e2) { try { root.focus({ preventScroll: true }); } catch (e3) {} } }
      } else if (!root.contains(document.activeElement)) {
        try { root.focus({ preventScroll: true }); } catch (e) {}
      }
      lastTrigger = null;
    }

    if (CLOSE_ON_OVERLAY) {
      root.addEventListener('click', function (e) {
        if (e.target === root) close();
      });
    }

    return {
      open: open,
      close: close,
      isOpen: function () { return isOpen; },
      focusables: focusables
    };
  }

  /* ---------- Image lightbox（完整 modal：dialog 语义 + Focus Trap） ----------
     - 仅对"未被链接包裹"的图片启用；[![img](x)](url) 保持浏览器原生跳转
     - 图片可键盘聚焦：Enter / Space 打开
     - 交互契约由 createModalA11y 提供：焦点移入、背景 inert、Tab/Shift+Tab 循环、Escape
     - 关闭：Esc / 关闭按钮 / 点击遮罩；关闭后焦点归还触发图片
  ------------------------------------------------------------------ */
  var lightbox = $('#lightbox');
  var lightboxEnabled = document.body.getAttribute('data-lightbox') !== 'false';
  if (lightbox && lightboxEnabled) {
    var lbImg = lightbox.querySelector('img');

    var lbA11y = createModalA11y({ root: lightbox, closeOnOverlay: false });

    function openLightbox(img) {
      lbImg.src = img.getAttribute('data-zoom-src') || img.currentSrc || img.src;
      lbImg.alt = img.alt || '';
      lbA11y.open(img);                       // 工厂负责 focus trap / inert / 焦点归还
    }

    function closeLightbox() {
      lbA11y.close();
    }

    $$('.post-content img').forEach(function (img) {
      if (img.closest('a')) return;           // 链接包裹：放行浏览器原生行为
      img.setAttribute('tabindex', '0');
      img.setAttribute('role', 'button');
      img.setAttribute('aria-label', (img.alt ? (T_.zoomPrefix || '') + img.alt : (T_.zoom || 'Zoom')));
      img.classList.add('zoomable');

      img.addEventListener('click', function () { openLightbox(img); });
      img.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
          e.preventDefault();
          openLightbox(img);
        }
      });
    });

    var lbClose = lightbox.querySelector('.lightbox-close');
    lightbox.addEventListener('click', function () { closeLightbox(); });
    if (lbClose) {
      lbClose.addEventListener('click', function (e) { e.stopPropagation(); closeLightbox(); });
    }
    lbImg.addEventListener('click', function (e) { e.stopPropagation(); });

    /* Escape / Tab 由 createModalA11y 统一处理（capture 阶段），
       此处不再重复监听，避免双重触发 */
  }

  /* 当前焦点是否处于文本输入上下文（输入框 / textarea / contenteditable） */
  function isTypingContext() {
    var a = document.activeElement;
    if (!a) return false;
    var tag = a.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    return a.isContentEditable === true;
  }

  /* ---------- Search ---------- */
  var overlay = $('#searchOverlay'),
      input = $('#search-input'),
      results = $('#searchResults'),
      trigger = $('#searchTrigger'),
      countEl = $('#searchCount');

  if (overlay && input && results) {
    var INDEX_URL = '{{ "index.json" | relURL }}';
    var INDEX = null, INDEX_PROMISE = null, INDEX_ERROR = null, selected = 0, items = [];
    var SHARD_FAILED = [];
    var renderToken = 0, debounceTimer = null;

    var statusEl = $('#searchStatus'), statusTextEl = $('#searchStatusText'), retryBtn = $('#searchRetry');

    function setStatus(text) { if (countEl) countEl.textContent = text; }
    function showStatus(text) {
      if (!statusEl || !statusTextEl) return;
      statusTextEl.textContent = text;
      statusEl.hidden = false;
    }
    function hideStatus() { if (statusEl) statusEl.hidden = true; }

    function resetIndex() {
      INDEX = null; INDEX_PROMISE = null; INDEX_ERROR = null; SHARD_FAILED = [];
    }

    /* 索引加载
       - 幂等：并发调用只请求一次
       - 主索引失败 -> INDEX_ERROR（UI 明确报错 + 重试）
       - 分片失败 -> 记入 SHARD_FAILED（UI 提示"部分索引加载失败"，其余文章仍可搜索）
       - render() 必须先 await 本函数，避免"打开后立即输入"的竞态 */
    function loadIndex() {
      if (INDEX) return Promise.resolve(INDEX);
      if (INDEX_PROMISE) return INDEX_PROMISE;
      SHARD_FAILED = [];

      INDEX_PROMISE = fetch(INDEX_URL)
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (d) {
          var list = Array.isArray(d) ? d : (d && d.items) ? d.items : [];
          var chunkURLs = (d && d.chunks) ? d.chunks : null;

          /* 结构 A（推荐）：体积分块 { chunks: [...], items: [...] }
             把正文按体积合并成少量 chunk 文件，请求数与体积成正比而非与文章数成正比 */
          if (chunkURLs && chunkURLs.length) {
            return Promise.all(chunkURLs.map(function (u) {
              return fetch(u, { cache: 'force-cache' })
                .then(function (r) {
                  if (!r.ok) throw new Error('HTTP ' + r.status);
                  return r.json();
                })
                .catch(function (err) {
                  SHARD_FAILED.push({ url: u, error: String((err && err.message) || err) });
                  return null;
                });
            })).then(function (maps) {
              var merged = {};
              maps.forEach(function (m) {
                if (m) { Object.keys(m).forEach(function (k) { merged[k] = m[k]; }); }
              });
              list.forEach(function (it) {
                if (!it.content && it.key && typeof merged[it.key] === 'string') {
                  it.content = merged[it.key];
                }
              });
              var affected = list.filter(function (it) { return !it.content && it.key; }).length;
              if (affected) {
                SHARD_FAILED.affected = affected;   // 受影响的文章数（用于提示）
                console.warn('[Nebula] some search content chunks failed to load:', SHARD_FAILED);
              }
              return list;
            });
          }

          /* 结构 B（兼容旧版）：按文章分片，条目带 shard 字段 */
          var missing = list.filter(function (it) { return !it.content && it.shard; });
          if (!missing.length) return list;
          return Promise.all(missing.map(function (it) {
            return fetch(it.shard, { cache: 'force-cache' })
              .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
              })
              .then(function (c) {
                if (typeof c === 'string') { it.content = c; }
                else if (c && typeof c.content === 'string') { it.content = c.content; }
                else { throw new Error('invalid shard payload'); }
              })
              .catch(function (err) {
                it.content = '';
                SHARD_FAILED.push({ url: it.shard, title: it.title, error: String((err && err.message) || err) });
              });
          })).then(function () {
            if (SHARD_FAILED.length) {
              console.warn('[Nebula] some search shards failed to load:', SHARD_FAILED);
            }
            return list;
          });
        })
        .then(function (list) { INDEX = list || []; INDEX_ERROR = null; return INDEX; })
        .catch(function (err) { INDEX = []; INDEX_ERROR = err; return INDEX; });

      return INDEX_PROMISE;
    }

    function esc(s) {
      return String(s || '').replace(/[&<>"]/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
    }

    /* 搜索结果链接的 scheme 白名单（SEC-01）。
       索引数据若被篡改（例如把 url 改成 javascript:alert(1)），直接写进 href
       就会在用户点击时执行脚本。这里只放行同源相对路径与 http(s) 绝对地址，
       其余（javascript: / data: / vbscript: …）返回 null，渲染为不可点击的文本。 */
    function safeHref(u) {
      var s = String(u == null ? '' : u).trim();
      if (!s) return null;
      if (/^https?:\/\//i.test(s)) return s;
      if (s.charAt(0) === '/' || s.charAt(0) === '.' || s.charAt(0) === '#') return s;
      return null;
    }

    /* 日期标签：直接取构建产物里的 dateDisplay（Hugo 在构建期已按站点语言格式化）。

       前端**不做**语言判断、也不重复实现日期格式化 —— 否则会和模板里的一分为二，
       出现"UI 日期已本地化、搜索结果仍是 2026-09-28"这类不一致缺陷。

       兼容：新索引一定带 dateDisplay（缺失日期时为空串）；只有遇到旧版索引
       （字段完全不存在）才退回机器格式的 date，避免直接不显示日期。 */
    function dateLabel(it) {
      if (Object.prototype.hasOwnProperty.call(it, 'dateDisplay')) return it.dateDisplay || '';
      return it.date || '';
    }

    function highlight(text, terms) {
      var out = esc(text);
      terms.forEach(function (t) {
        if (!t) return;
        var re = new RegExp('(' + t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
        out = out.replace(re, '<mark>$1</mark>');
      });
      return out;
    }

    function score(item, terms) {
      var total = 0;
      for (var i = 0; i < terms.length; i++) {
        var t = terms[i].toLowerCase(), s = 0;
        var title = (item.title || '').toLowerCase();
        var summary = (item.summary || '').toLowerCase();
        var content = (item.content || '').toLowerCase();
        var tags = (item.tags || []).join(' ').toLowerCase();
        var cats = (item.categories || []).join(' ').toLowerCase();
        var series = (item.series || []).join(' ').toLowerCase();
        if (title.indexOf(t) > -1) s += 12;
        if (tags.indexOf(t) > -1) s += 6;
        if (cats.indexOf(t) > -1) s += 5;
        /* series 与 tags 同为"用户自定义的多值分组标签"，此前索引写了 series
           却从不参与匹配（BUG-P2-005），导致按系列名搜索 0 结果。 */
        if (series.indexOf(t) > -1) s += 6;
        if (summary.indexOf(t) > -1) s += 4;
        if (content.indexOf(t) > -1) s += 2;
        if (s === 0) return 0; // AND semantics
        total += s;
      }
      return total;
    }

    /* 摘要片段：优先用 description；若关键词只出现在正文深处，
       则从正文匹配位置附近截取，避免用户"搜到了却看不到为什么命中" */
    function snippetFor(it, terms) {
      var s = (it.summary || '').slice(0, 100);
      for (var i = 0; i < terms.length; i++) {
        if (s.toLowerCase().indexOf(terms[i].toLowerCase()) > -1) return s;
      }
      var c = it.content || '', pos = -1;
      for (var j = 0; j < terms.length; j++) {
        pos = c.toLowerCase().indexOf(terms[j].toLowerCase());
        if (pos > -1) break;
      }
      if (pos < 0) return s;
      var start = Math.max(0, pos - 40);
      return (start > 0 ? '…' : '') + c.slice(start, start + 100);
    }

    function renderNow(q) {
      var terms = q.trim().split(/\s+/).filter(Boolean);

      if (INDEX_ERROR) {
        var errMsg = tf(T_.searchFailed || 'Search index failed to load');
        showStatus(errMsg + '（' + esc(String(INDEX_ERROR.message || INDEX_ERROR)) + '）');
        results.innerHTML = '<div class="search-empty">' + esc(errMsg) + '</div>';
        setStatus('');
        items = [];
        return;
      }
      /* 分片部分失败：明确提示；此时绝不能把"索引不全"显示成"没有找到" */
      var partial = SHARD_FAILED.length > 0;
      var affected = SHARD_FAILED.affected || SHARD_FAILED.length;
      if (partial) {
        showStatus(tf(T_.searchPartialFailed ||
          'Some search index parts failed to load ({n} posts); results may be incomplete',
          { n: affected }));
      } else {
        hideStatus();
      }
      if (!terms.length) {
        results.innerHTML = '<div class="search-empty">' +
          esc(T_.searchHint || 'Type keywords to search') + '</div>';
        setStatus('');
        items = [];
        return;
      }

      var hits = INDEX.map(function (it) {
        return { it: it, s: score(it, terms) };
      }).filter(function (x) { return x.s > 0; })
        .sort(function (a, b) { return b.s - a.s; })
        .slice(0, 20);

      items = hits.map(function (x) { return x.it; });
      selected = 0;
      setStatus(tf(T_.resultCount || '{n} results', { n: hits.length }));

      if (!hits.length) {
        /* 索引不完整时给出"可能不完整/请重试"而不是"没有找到"，避免把失败误报成不存在 */
        var emptyMsg = partial
          ? tf(T_.searchPartialNoResult ||
               'Some search index parts failed to load ({n} posts); results may be incomplete',
               { n: affected })
          : (T_.noResultPrefix || 'No results for "') + q + (T_.noResultSuffix || '"');
        results.innerHTML = '<div class="search-empty">' + esc(emptyMsg) + '</div>';
        return;
      }
      results.innerHTML = hits.map(function (x, i) {
        var it = x.it;
        var snippet = snippetFor(it, terms);
        var dateText = dateLabel(it);
        var inner =
          '<div class="t">' + highlight(it.title, terms) + '</div>' +
          '<div class="p">' +
            (dateText ? esc(dateText) : '') +
            (snippet ? (dateText ? ' · ' : '') + highlight(snippet, terms) : '') +
          '</div>';
        var href = safeHref(it.url);
        if (!href) {
          // 非法 scheme：不生成链接，避免 javascript: 之类被点击执行
          return '<span class="search-item' + (i === 0 ? ' sel' : '') +
                 ' no-link" title="blocked by scheme allowlist">' + inner + '</span>';
        }
        return '<a class="search-item' + (i === 0 ? ' sel' : '') + '" href="' + esc(href) + '">' +
          inner + '</a>';
      }).join('');
      bindHover();
    }

    /* 竞态修复：先 await 索引，再渲染；用 token 丢弃过期渲染 */
    function render(q) {
      var my = ++renderToken;
      if (!INDEX) {
        results.innerHTML = '<div class="search-empty">' + esc(T_.searchLoading || 'Loading search index…') + '</div>';
        setStatus('');
      }
      return loadIndex().then(function () {
        if (my !== renderToken) return;   // 已有更新的输入，本次渲染作废
        renderNow(q);
      });
    }

    function bindHover() {
      $$('.search-item', results).forEach(function (el, i) {
        el.addEventListener('mouseenter', function () { select(i); });
      });
    }

    function select(i) {
      var els = $$('.search-item', results);
      if (!els.length) return;
      selected = (i + els.length) % els.length;
      els.forEach(function (el, j) { el.classList.toggle('sel', j === selected); });
      els[selected].scrollIntoView({ block: 'nearest' });
    }

    /* 搜索弹窗接入统一 Modal 契约：焦点 trap / 背景 inert / Escape /
       遮罩关闭 / 焦点恢复 / 幂等开关 / **页面滚动锁定与恢复**，
       全部由工厂实现 —— 这里不再自己动 body.style.overflow，
       否则遮罩点击与 Escape 走工厂 close() 时会绕过它（历史 BUG-P1-001）。 */
    var searchA11y = createModalA11y({
      root: overlay,
      input: input,
      initialFocus: input
    });

    function open(initialQuery, triggerEl) {
      searchA11y.open(triggerEl || null, initialQuery);   // 工厂负责其余交互（含滚动锁）
      loadIndex();            // 打开即预取索引
      render(input.value);    // render 内部会 await 索引，避免竞态
    }
    function close() {
      searchA11y.close();
    }

    if (retryBtn) {
      retryBtn.addEventListener('click', function () {
        resetIndex();
        hideStatus();
        results.innerHTML = '<div class="search-empty">' + esc(T_.searchLoading || 'Loading search index…') + '</div>';
        loadIndex().then(function () { renderNow(input.value); });
      });
    }

    if (trigger) trigger.addEventListener('click', function () { open('', trigger); });

    // 支持 ?q= 深链（与 JSON-LD SearchAction 对应）
    try {
      var initialQ = new URLSearchParams(window.location.search).get('q');
      if (initialQ) { open(initialQ, null); }   // deep link: no trigger element
    } catch (e) {}

    // 输入防抖：大索引下避免每次按键都全量扫描
    input.addEventListener('input', function () {
      var q = input.value;
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () { render(q); }, 120);
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); select(selected + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); select(selected - 1); }
      else if (e.key === 'Enter') {
        var els = $$('.search-item', results);
        var target = els[selected];
        var href = target && target.getAttribute ? target.getAttribute('href') : null;
        // href 为 null 表示该条被 scheme 白名单拦截（SEC-01），不跳转
        if (target && href) { e.preventDefault(); window.location.href = href; }
      } else if (e.key === 'Escape') { close(); }
    });

    document.addEventListener('keydown', function (e) {
      if (overlay.classList.contains('open')) return;   // 打开时 Escape/Tab 由工厂处理
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        open('', document.activeElement && document.activeElement !== document.body
          ? document.activeElement : null);
      }
      /* "/" 快捷键：在**非输入上下文**时打开（焦点在 body、链接或按钮上都可以，
         正在输入文本时不应劫持按键） */
      if (e.key === '/' && !isTypingContext()) {
        e.preventDefault();
        open('', null);
      }
    });
  }
})();
