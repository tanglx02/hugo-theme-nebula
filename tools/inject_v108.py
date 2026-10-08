"""v1.0.8 故障注入 A-E。

    A 删除搜索 focus trap        -> verify_search_modal.py 必须 FAIL
    B 删除搜索焦点恢复           -> verify_search_modal.py 必须 FAIL
    C 相关文章日期改回硬编码      -> check_date_format.py 必须 FAIL
    D audit.py docstring 改回旧表述 -> check_docs.py 必须 FAIL
    E inventory 出现 URL 冲突    -> html_inventory.py / test_inventory.py 必须 FAIL

用法：python3 tools/inject_v108.py <A|B|C|D|E>
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def patch(rel, pairs):
    p = os.path.join(ROOT, rel)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        assert s.count(old) >= 1, f"{rel}: anchor not found -> {old[:70]}"
        s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print(f"  patched {rel}")


def case_A():
    """A：删掉搜索的 focus trap（Tab 不再循环，焦点可逃出 dialog）。"""
    patch("assets/js/main.js", [(
        """      if (e.key !== 'Tab') return;
      var f = focusables();
      if (!f.length) { e.preventDefault(); root.focus(); return; }
      var first = f[0], last = f[f.length - 1];
      var active = document.activeElement;
      if (!root.contains(active)) { e.preventDefault(); first.focus(); return; }
      if (e.shiftKey && (active === first || active === root)) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault(); first.focus();
      }""",
        """      // INJECTED-A: focus trap removed
      if (e.key !== 'Tab') return;""")])
    # 同时移除搜索侧的 trap 绑定（模拟只留灯箱的 trap）
    patch("assets/js/main.js", [(
        "      keyHandler = onKeydown;\n      document.addEventListener('keydown', keyHandler, true);",
        "      keyHandler = null;  // INJECTED-A: no key handler for search modal")])


def case_B():
    """B：删掉焦点恢复（关闭后焦点不回到触发元素）。"""
    patch("assets/js/main.js", [(
        """      if (lastTrigger && document.contains(lastTrigger) &&
          typeof lastTrigger.focus === 'function') {
        try { lastTrigger.focus(); } catch (e) { try { root.focus(); } catch (e2) {} }
      } else if (!root.contains(document.activeElement)) {""",
        """      if (false) {   // INJECTED-B: focus restore removed
        try { root.focus(); } catch (e) {}
      } else if (!root.contains(document.activeElement)) {""")])


def case_C():
    """C：相关文章日期改回硬编码 2006-01-02。"""
    patch("layouts/_default/single.html", [(
        '<div class="d">{{ .Date.Format (i18n "common.dateFormat") }} · {{ .ReadingTime }} min</div>',
        '<div class="d">{{ .Date.Format "2006-01-02" }} · {{ .ReadingTime }} min</div>')])


def case_D():
    """D：audit.py docstring 改回「sitemap 中全部可审计 HTML 页面」。"""
    patch("tools/audit.py", [(
        "Release 全站审计以构建产物 HTML inventory 为真值；sitemap 作为独立 SEO 索引质量检查；分页 crawler 用于交叉验证额外分页，不再作为全站真值。",
        "`AUDIT_FULL=1`（全站）：sitemap 中**全部可审计 HTML 页面** —— Release 门禁")])
    patch("tools/audit.py", [(
        "  * 发现任一问题 / 浏览器启动失败 / sitemap 获取失败 / inventory 覆盖不完整 /\n"
        "    分页发现失败或未耗尽 / 站点不可达 / 脚本异常 -> exit 1",
        "  * 发现任一问题 / 浏览器启动失败 / sitemap 获取失败 / 站点不可达 / 脚本异常 -> exit 1")])


def case_E():
    """E：让 inventory 出现 normalize URL 冲突。

    模拟真实故障：规范化逻辑被改坏（这里退化成把所有目录压成同一个名字），
    212 个 HTML 文件会映射到同一个 URL —— inventory 失去可信度，必须 exit 1。
    """
    patch("tools/html_inventory.py", [(
        "    return \"/\" + quote(p, safe=\"/~!*()'-._%\")",
        "    p = p.split('/')[-1]  # INJECTED-E: collapse to basename -> mass collision\n"
        "    return \"/\" + quote(p, safe=\"/~!*()'-._%\")")])


CASES = {"A": case_A, "B": case_B, "C": case_C, "D": case_D, "E": case_E}

if __name__ == "__main__":
    import sys
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what in CASES:
        print(f"INJECT {what}:")
        CASES[what]()
    else:
        print(__doc__)
        print("cases:", ", ".join(CASES))
