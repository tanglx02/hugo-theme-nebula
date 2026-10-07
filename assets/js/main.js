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

  /* ---------- Code copy ---------- */
  $$('.code-copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var block = btn.closest('.code-block');
      var code = block ? block.querySelector('pre') : null;
      if (!code) return;
      var text = code.innerText;
      var settled = false;
      var done = function () {
        if (settled) return;          // 防止重复反馈
        settled = true;
        var old = btn.innerHTML;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>已复制';
        btn.classList.add('copied');
        setTimeout(function () {
          btn.innerHTML = old;
          btn.classList.remove('copied');
        }, 1600);
      };
      function fallback() {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta);
        done();
      }
      // navigator.clipboard 在部分浏览器（Firefox 无权限时）可能既不 resolve 也不 reject，
      // 因此增加超时兜底，保证用户始终能看到复制反馈。
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          var p = navigator.clipboard.writeText(text);
          if (p && typeof p.then === 'function') {
            p.then(done, fallback);
            setTimeout(function () { if (!settled) fallback(); }, 600);
          } else {
            fallback();
          }
        } else {
          fallback();
        }
      } catch (e) {
        fallback();
      }
    });
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

  /* ---------- Image lightbox ---------- */
  var lightbox = $('#lightbox');
  if (lightbox) {
    $$('.post-content img').forEach(function (img) {
      img.addEventListener('click', function () {
        var lbImg = lightbox.querySelector('img');
        lbImg.src = img.src;
        lbImg.alt = img.alt || '';
        lightbox.classList.add('open');
      });
    });
    lightbox.addEventListener('click', function () { lightbox.classList.remove('open'); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') lightbox.classList.remove('open');
    });
  }

  /* ---------- Search ---------- */
  var overlay = $('#searchOverlay'),
      input = $('#search-input'),
      results = $('#searchResults'),
      trigger = $('#searchTrigger'),
      countEl = $('#searchCount');

  if (overlay && input && results) {
    var INDEX = null, selected = 0, items = [];

    function loadIndex() {
      if (INDEX) return Promise.resolve(INDEX);
      return fetch('{{ "index.json" | relURL }}')
        .then(function (r) { return r.json(); })
        .then(function (d) { INDEX = d || []; return INDEX; })
        .catch(function () { INDEX = []; return INDEX; });
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

    function render(q) {
      var terms = q.trim().split(/\s+/).filter(Boolean);
      if (!terms.length) {
        results.innerHTML = '<div class="search-empty">输入关键词开始搜索，支持标题 / 标签 / 正文匹配</div>';
        countEl.textContent = '';
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
      countEl.textContent = '共 ' + hits.length + ' 条结果';

      if (!hits.length) {
        results.innerHTML = '<div class="search-empty">没有找到与「' + esc(q) + '」相关的文章</div>';
        return;
      }
      results.innerHTML = hits.map(function (x, i) {
        var it = x.it;
        var snippet = (it.summary || '').slice(0, 90);
        return '<a class="search-item' + (i === 0 ? ' sel' : '') + '" href="' + it.url + '">' +
          '<div class="t">' + highlight(it.title, terms) + '</div>' +
          '<div class="p">' + esc(it.date) + (snippet ? ' · ' + highlight(snippet, terms) : '') + '</div>' +
          '</a>';
      }).join('');
      bindHover();
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
      loadIndex();
      render(input.value);
    }
    function close() {
      overlay.classList.remove('open');
      document.body.style.overflow = '';
      input.blur();
    }

    if (trigger) trigger.addEventListener('click', open);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });

    input.addEventListener('input', function () { render(input.value); });
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
