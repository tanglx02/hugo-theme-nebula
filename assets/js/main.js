/* Nebula theme — interactions */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

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

  /* ---------- Mobile menu ---------- */
  var burger = $('#burger'), nav = $('#mainNav');
  if (burger && nav) {
    burger.addEventListener('click', function () { nav.classList.toggle('mobile-open'); });
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target) && !burger.contains(e.target)) nav.classList.remove('mobile-open');
    });
  }

  /* ---------- Scroll: progress / header shadow / back to top ---------- */
  var header = $('#siteHeader'), bar = $('#progressBar'), toTop = $('#toTop');
  function onScroll() {
    var st = window.pageYOffset || document.documentElement.scrollTop;
    var h = document.documentElement.scrollHeight - window.innerHeight;
    if (bar) bar.style.width = (h > 0 ? (st / h) * 100 : 0) + '%';
    if (header) header.classList.toggle('is-scrolled', st > 10);
    if (toTop) toTop.classList.toggle('show', st > 400);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  if (toTop) toTop.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  /* ---------- Code copy ----------
     使用 document 级事件委托 + 全路径保护：
     - 避免元素级监听器绑定时机问题（Firefox 下曾复现"首次点击无反馈"）
     - clipboard 写入的 Promise 在部分浏览器可能挂起，加超时兜底
     - 任何异常路径都会走到 done()，保证用户始终能看到反馈 */
  function copyFromButton(btn) {
    var block = btn.closest('.code-block');
    var code = block ? block.querySelector('pre') : null;
    if (!code) return;
    var text = code.innerText || code.textContent || '';
    var settled = false;

    function done() {
      if (settled) return;
      settled = true;
      var old = btn.innerHTML;
      btn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>已复制';
      btn.classList.add('copied');
      setTimeout(function () {
        btn.innerHTML = old;
        btn.classList.remove('copied');
      }, 1600);
    }

    function fallback() {
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.top = '-1000px';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta);
      } catch (e) {}
      done();                       // 无论回退是否成功都给出反馈
    }

    try {
      if (navigator.clipboard && navigator.clipboard.writeText && text) {
        var p = navigator.clipboard.writeText(text);
        if (p && typeof p.then === 'function') {
          p.then(done, fallback);
          setTimeout(function () { if (!settled) fallback(); }, 400);
          return;
        }
      }
    } catch (e) {}
    fallback();
  }

  document.addEventListener('click', function (e) {
    var t = e.target;
    var btn = (t && t.closest) ? t.closest('.code-copy') : null;
    if (btn) copyFromButton(btn);
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

  /* ---------- Image lightbox（无障碍版） ----------
     - 仅对"未被链接包裹"的图片启用，Markdown 的 [![img](x)](url) 会保持原有链接行为
     - 图片可获得键盘焦点（tabindex），Enter / 空格打开
     - 打开后焦点移入灯箱，Esc 关闭，关闭后焦点回到触发图片
     - 容器具备 dialog 语义与可访问名称（见 baseof.html）
  ------------------------------------------------ */
  var lightbox = $('#lightbox');
  if (lightbox) {
    var lbImg = lightbox.querySelector('img');
    var lastTrigger = null;

    function openLightbox(img) {
      lastTrigger = img;
      lbImg.src = img.currentSrc || img.src;
      lbImg.alt = img.alt || '';
      lightbox.classList.add('open');
      lightbox.setAttribute('aria-hidden', 'false');
      lightbox.focus();                       // 焦点移入 dialog
    }

    function closeLightbox() {
      if (!lightbox.classList.contains('open')) return;
      lightbox.classList.remove('open');
      lightbox.setAttribute('aria-hidden', 'true');
      if (lastTrigger && document.contains(lastTrigger)) {
        lastTrigger.focus();                  // 焦点归还触发元素
      }
      lastTrigger = null;
    }

    $$('.post-content img').forEach(function (img) {
      if (img.closest('a')) return;           // 被链接包裹：放行链接，不接管点击
      img.setAttribute('tabindex', '0');
      img.setAttribute('role', 'button');
      var label = img.alt ? ('放大图片：' + img.alt) : '放大图片';
      img.setAttribute('aria-label', label);
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
    lightbox.addEventListener('click', function (e) { closeLightbox(); });
    if (lbClose) {
      lbClose.addEventListener('click', function (e) { e.stopPropagation(); closeLightbox(); });
    }
    lbImg.addEventListener('click', function (e) {
      // 点击图片本身不关闭（避免误触），点击遮罩或关闭按钮关闭
      e.stopPropagation();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeLightbox();
    });
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
    var renderToken = 0, debounceTimer = null;

    function setStatus(text) { if (countEl) countEl.textContent = text; }

    /* 索引加载
       - 幂等：并发调用只会真正请求一次
       - 支持分片模式：正文为空且带 shard 字段时，并发拉取 /search/*.json
       - 失败可感知：供 UI 给出明确提示，而不是静默返回空结果
       - 关键点：render() 必须先 await 本函数，否则"用户打开搜索框立刻输入"
         会出现 INDEX 尚未就绪的竞态（P5） */
    function loadIndex() {
      if (INDEX) return Promise.resolve(INDEX);
      if (INDEX_PROMISE) return INDEX_PROMISE;

      INDEX_PROMISE = fetch(INDEX_URL)
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (d) {
          var list = Array.isArray(d) ? d : (d && d.items) ? d.items : [];
          var missing = list.filter(function (it) { return !it.content && it.shard; });
          if (!missing.length) return list;
          return Promise.all(missing.map(function (it) {
            return fetch(it.shard)
              .then(function (r) {
                if (!r.ok) throw new Error('shard HTTP ' + r.status);
                return r.json();
              })
              .then(function (c) {
                it.content = (typeof c === 'string') ? c : ((c && c.content) || '');
              })
              .catch(function () { it.content = ''; });
          })).then(function () { return list; });
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
        if (title.indexOf(t) > -1) s += 12;
        if (tags.indexOf(t) > -1) s += 6;
        if (cats.indexOf(t) > -1) s += 5;
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
        results.innerHTML = '<div class="search-empty">搜索索引加载失败，请刷新页面重试（' +
          esc(String(INDEX_ERROR.message || INDEX_ERROR)) + '）</div>';
        setStatus('');
        items = [];
        return;
      }
      if (!terms.length) {
        results.innerHTML = '<div class="search-empty">输入关键词开始搜索，支持标题 / 标签 / 正文全文匹配</div>';
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
      setStatus('共 ' + hits.length + ' 条结果');

      if (!hits.length) {
        results.innerHTML = '<div class="search-empty">没有找到与「' + esc(q) + '」相关的文章</div>';
        return;
      }
      results.innerHTML = hits.map(function (x, i) {
        var it = x.it;
        var snippet = snippetFor(it, terms);
        return '<a class="search-item' + (i === 0 ? ' sel' : '') + '" href="' + it.url + '">' +
          '<div class="t">' + highlight(it.title, terms) + '</div>' +
          '<div class="p">' + esc(it.date) + (snippet ? ' · ' + highlight(snippet, terms) : '') + '</div>' +
          '</a>';
      }).join('');
      bindHover();
    }

    /* 竞态修复：先 await 索引，再渲染；用 token 丢弃过期渲染 */
    function render(q) {
      var my = ++renderToken;
      if (!INDEX) {
        results.innerHTML = '<div class="search-empty">正在加载搜索索引…</div>';
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

    function open() {
      overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
      setTimeout(function () { input.focus(); }, 30);
      loadIndex();            // 打开即预取索引
      render(input.value);    // render 内部会 await 索引，避免竞态
    }
    function close() {
      overlay.classList.remove('open');
      document.body.style.overflow = '';
      input.blur();
    }

    if (trigger) trigger.addEventListener('click', open);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });

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
        if (els[selected]) { e.preventDefault(); window.location.href = els[selected].getAttribute('href'); }
      } else if (e.key === 'Escape') { close(); }
    });

    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); open(); }
      if (e.key === '/' && document.activeElement === document.body) { e.preventDefault(); open(); }
      if (e.key === 'Escape' && overlay.classList.contains('open')) close();
    });
  }
})();
