/* Nebula theme — 标签页渐进增强（功能三）
 *
 * 职责边界（严格遵守）：**只负责"切换"这一个动作**。
 *   - 结构、角色、aria-* 全部由服务端模板输出（layouts/shortcodes/tabs.html）；
 *   - 本脚本由 scripts.html 按需加载（仅当页面用了 tabs 时），增强后才给容器
 *     加 .tabs-enhanced，把 CSS 从"默认全展开"切到"标签页"；
 *   - 无 JS（或本文件被禁用 / 被 CSP 拦掉）时，CSS 的默认态即"面板顺序展开、
 *     导航条隐藏"，因此本文件缺席也不会丢失任何内容，也不会闪动。
 *
 * 无障碍：实现 WAI-ARIA APG "Tabs with Automatic Activation" ——
 *   - 只有一个 tab 处于 Tab 序（roving tabindex）；
 *   - ←/→ 在标签间移动并立即激活（自动激活模式），Home/End 跳首/尾；
 *   - ↑/↓ 在垂直排列（窄屏）时等价于 ←/→；
 *   - Enter/Space 由原生 <button> 负责，无需额外处理；
 *   - 选中态同时更新 aria-selected 与 tabindex，面板同步 hidden。
 *
 * 为什么不用 .tabs 的 nav 顺序做 index：面板上有 data-index（来自服务端
 * Scratch 累积顺序），与 aria-controls 的编号可能因「同页多个 tabs 组件」
 * 而不同，因此一律按 **DOM 内的数组下标** 对齐 nav 与 panels —— 两者在模板里
 * 由同一个 range 输出，下标天然一致。
 */
(function () {
  'use strict';

  var containers = document.querySelectorAll('.tabs');
  if (!containers.length) return;

  var KEY_LEFT = 37, KEY_UP = 38, KEY_RIGHT = 39, KEY_DOWN = 40, KEY_HOME = 36, KEY_END = 35;

  Array.prototype.forEach.call(containers, function (root) {
    var nav = root.querySelector('.tabs-nav');
    var panelBox = root.querySelector('.tabs-panels');
    if (!nav || !panelBox) return;

    var tabs = Array.prototype.slice.call(nav.querySelectorAll('.tabs-tab'));
    var panels = Array.prototype.slice.call(panelBox.querySelectorAll('.tabs-panel'));
    if (tabs.length < 2 || tabs.length !== panels.length) return;

    root.classList.add('tabs-enhanced');

    function select(idx, moveFocus) {
      for (var i = 0; i < tabs.length; i++) {
        var on = i === idx;
        tabs[i].setAttribute('aria-selected', on ? 'true' : 'false');
        tabs[i].setAttribute('tabindex', on ? '0' : '-1');
        tabs[i].classList.toggle('is-active', on);
        if (on) { panels[i].removeAttribute('hidden'); }
        else { panels[i].setAttribute('hidden', ''); }
      }
      if (moveFocus) {
        try { tabs[idx].focus({ preventScroll: true }); }
        catch (e) { try { tabs[idx].focus(); } catch (e2) {} }
      }
    }

    function current() {
      for (var i = 0; i < tabs.length; i++) {
        if (tabs[i].getAttribute('aria-selected') === 'true') return i;
      }
      return 0;
    }

    nav.addEventListener('click', function (e) {
      var t = e.target && e.target.closest ? e.target.closest('.tabs-tab') : null;
      if (!t) return;
      var idx = tabs.indexOf(t);
      if (idx >= 0) select(idx, false);
    });

    nav.addEventListener('keydown', function (e) {
      var idx = tabs.indexOf(document.activeElement);
      if (idx < 0) return;
      var next = -1;
      switch (e.keyCode) {
        case KEY_LEFT: case KEY_UP:  next = (idx - 1 + tabs.length) % tabs.length; break;
        case KEY_RIGHT: case KEY_DOWN: next = (idx + 1) % tabs.length; break;
        case KEY_HOME: next = 0; break;
        case KEY_END:  next = tabs.length - 1; break;
        default: return;
      }
      e.preventDefault();
      select(next, true);
    });

    /* 初始态对齐：以 aria-selected 为准（模板已把第 0 个设为选中，
       但若用户/第三方脚本改过，这里做一次归一，保证 DOM 与视觉一致）。 */
    select(current(), false);
  });
})();