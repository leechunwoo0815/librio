#!/usr/bin/env python3
"""验证管理端 data-action 事件绑定完整性 — CI Gate 10

检查拓扑（按页核查 + 全局池）：
  1. page.html (所有 data-action 引用) + page.js (动态渲染的 data-action)
     → 必须能在 page.js handler 分支或全局池中找到
  2. base.html (所有 data-action 引用)
     → 必须能在任一 pages/*.js 或全局池中找到
  3. 全局池：admin.js / base-init.js / admin-pages.js 的 handler 对所有页面生效

handler 模式覆盖（共 6 种）：
  a. action === 'x' / action == 'x'
  b. 'x' === action / 'x' == action
  c. closest('[data-action="x"]')     — 直接 closest 指定动作名
  d. querySelector('[data-action="x"]')  — querySelector 指定动作名
  e. getAttribute('data-action') === 'x' — getAttribute 模式
  f. case 'x':                         — switch 分支

id/class 绑定豁免：通过 # wiring-exempt: action-name 注释标记。
  已知豁免：logout (admin.js .logout-btn), toggle-target-user (message_manage.js #msgTarget)

退出码：0=通过 1=有死动作（--strict）或始终 0（默认报告模式）
"""

import argparse
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TEMPLATES = BASE / "backend" / "templates" / "admin"
JS_PAGES = BASE / "backend" / "static" / "admin" / "js" / "pages"
JS_GLOBAL_FILES = [
    BASE / "backend" / "static" / "admin" / "js" / "admin.js",
    BASE / "backend" / "static" / "admin" / "js" / "base-init.js",
    BASE / "backend" / "static" / "admin" / "js" / "admin-pages.js",
]

# ── 已知豁免：通过 id/class 绑定（非 data-action 模式）──
KNOWN_EXEMPTIONS = {
    "logout",              # admin.js:277 .logout-btn click → auth.logout()
    "toggle-target-user",  # message_manage.js:151 #msgTarget change → toggleTargetUser()
}


def extract_html_actions_from_file(html_path: Path) -> set[str]:
    """从单个 HTML 文件提取所有 data-action="xxx"（属性级精确匹配）"""
    content = html_path.read_text(encoding="utf-8")
    actions: set[str] = set()
    for m in re.finditer(r'data-action\s*=\s*["\']([^"\']+)["\']', content):
        actions.add(m.group(1))
    return actions


def extract_js_render_actions(js_file: Path) -> set[str]:
    """从 JS 文件提取 data-action="xxx" 字面量"""
    content = js_file.read_text(encoding="utf-8")
    actions: set[str] = set()
    for m in re.finditer(r'data-action\s*=\s*["\']([^"\']+)["\']', content):
        actions.add(m.group(1))
    return actions


def extract_js_handlers(js_file: Path) -> set[str]:
    """从 JS 文件提取所有匹配的 data-action handler（6 种模式）

    规则：
    - 模式 a/b (action === 'x') 仅在文件没有用 .value 赋给 action 变量时匹配
      （防止混淆 select.value 与 getAttribute('data-action')）
    - 模式 c-f 直接匹配（它们明确引用 data-action 属性）
    """
    content = js_file.read_text(encoding="utf-8")
    handlers: set[str] = set()
    lines = content.split("\n")

    # 判断 action 变量来源：如果文件有 .value 赋给 action，禁用模式 a/b
    has_action_from_value = bool(
        re.search(r"""action\s*=\s*(.*?)\.value""", content)
    )

    # 模式 a: action === 'x' / action == 'x'
    # 模式 b: 'x' === action / "x" === action
    if not has_action_from_value:
        for m in re.finditer(r"""action\s*=={1,2}\s*["']([^"']+)["']""", content):
            handlers.add(m.group(1))
        for m in re.finditer(r"""["']([^"']+)["']\s*=={1,2}\s*action""", content):
            handlers.add(m.group(1))
    else:
        # 文件同时有 data-action 和 .value 来源，只能用上下文精确匹配
        # 当 ±10 行内有 getAttribute('data-action') 时才匹配
        for i, line in enumerate(lines):
            m = re.search(r"""action\s*=={1,2}\s*["']([^"']+)["']""", line)
            if m:
                ctx_start = max(0, i - 10)
                ctx_end = min(len(lines), i + 11)
                context = "\n".join(lines[ctx_start:ctx_end])
                if re.search(
                    r"""getAttribute\s*\(\s*['"]data-action['"]\s*\)""", context
                ):
                    handlers.add(m.group(1))
        for i, line in enumerate(lines):
            m = re.search(r"""["']([^"']+)["']\s*=={1,2}\s*action""", line)
            if m:
                ctx_start = max(0, i - 10)
                ctx_end = min(len(lines), i + 11)
                context = "\n".join(lines[ctx_start:ctx_end])
                if re.search(
                    r"""getAttribute\s*\(\s*['"]data-action['"]\s*\)""", context
                ):
                    handlers.add(m.group(1))

    # 模式 c: closest('[data-action="x"]') — 仅当动作名明确非泛型
    for m in re.finditer(
        r"""closest\(\s*['"]\[data-action=(['"])([^\1]+?)\1\]""", content
    ):
        handlers.add(m.group(2))

    # 模式 d: querySelector('[data-action="x"]') — 仅当动作名明确
    for m in re.finditer(
        r"""querySelector\(\s*['"]\[data-action=(['"])([^\1]+?)\1\]""", content
    ):
        handlers.add(m.group(2))

    # 模式 e: getAttribute('data-action') === 'x'
    for m in re.finditer(
        r"""getAttribute\(\s*['"]data-action['"]\s*\)\s*=={1,2}\s*["']([^"']+)["']""",
        content,
    ):
        handlers.add(m.group(1))

    # 模式 f: case 'x':
    for m in re.finditer(r"""case\s+["']([^"']+)["']\s*:""", content):
        handlers.add(m.group(1))

    return handlers


def extract_js_wiring_exemptions(js_file: Path) -> set[str]:
    """从 JS 文件提取 wiring-exempt 注释标记的豁免动作"""
    content = js_file.read_text(encoding="utf-8")
    exemptions: set[str] = set()
    for m in re.finditer(r'#\s*wiring-exempt:\s*([^\n]+)', content):
        for name in re.split(r'[,，\s]+', m.group(1).strip()):
            name = name.strip()
            if name:
                exemptions.add(name)
    return exemptions
    """将 'teachers.html' 转为 'teachers.js'"""
    return html_name.replace(".html", ".js")


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 data-action 绑定完整性")
    parser.add_argument(
        "--strict", action="store_true", help="严格模式：发现任何问题即返回 1"
    )
    global args
    args = parser.parse_args()

    has_error = False

    # ── 加载全局池 handler ──
    global_handlers: set[str] = set()
    for gf in JS_GLOBAL_FILES:
        if gf.exists():
            global_handlers.update(extract_js_handlers(gf))

    # 加载全局池渲染的 data-action（供 orphan 检测用）
    global_render_actions: set[str] = set()
    for gf in JS_GLOBAL_FILES:
        if gf.exists():
            global_render_actions.update(extract_js_render_actions(gf))

    print(f"[INFO] 全局池 handler: {len(global_handlers)} 个")
    if global_handlers:
        for h in sorted(global_handlers):
            print(f"  · {h} (全局池)")

    # ── 加载所有 pages/*.js 的 handler、render、和豁免 ──
    page_js_handlers: dict[str, set[str]] = {}  # "teachers.js" → {actions}
    page_js_renders: dict[str, set[str]] = {}  # "teachers.js" → {actions rendered}
    page_js_exemptions: dict[str, set[str]] = {}  # "teachers.js" → {exempted actions}

    for js_file in sorted(JS_PAGES.glob("*.js")):
        fname = js_file.name
        handlers = extract_js_handlers(js_file)
        if handlers:
            page_js_handlers[fname] = handlers
        renders = extract_js_render_actions(js_file)
        if renders:
            page_js_renders[fname] = renders
        exemptions = extract_js_wiring_exemptions(js_file)
        if exemptions:
            page_js_exemptions[fname] = exemptions

    print(f"\n[INFO] pages/*.js handler 文件: {len(page_js_handlers)} 个")
    print(f"[INFO] pages/*.js render 文件: {len(page_js_renders)} 个")

    # ── 按页核查 ──
    print("\n" + "=" * 60)
    print("按页核查（page.html ↔ page.js + 全局池）")
    print("=" * 60)

    all_html_actions_per_page: dict[str, set[str]] = {}
    all_render_actions_per_page: dict[str, set[str]] = {}

    for html_file in sorted(TEMPLATES.glob("*.html")):
        page = html_file.name  # e.g. "teachers.html"
        js_name = filename_to_page_basename(page)

        # 提取本页 HTML data-action
        html_actions = extract_html_actions_from_file(html_file)
        all_html_actions_per_page[page] = html_actions

        # 提取本页 JS render
        js_render_actions = page_js_renders.get(js_name, set())
        all_render_actions_per_page[page] = js_render_actions

        # 本页需要处理的 action = HTML + JS render
        page_actions = html_actions | js_render_actions
        if not page_actions:
            continue

        # 本页可用 handler = 对应 page.js + 全局池
        page_handlers = set(global_handlers)
        if js_name in page_js_handlers:
            page_handlers.update(page_js_handlers[js_name])

        # 检测死动作
        dead = page_actions - page_handlers
        # 应用豁免
        dead = dead - KNOWN_EXEMPTIONS

        if dead:
            has_error = True
            print(f"\n❌ {page}: {len(dead)} 个死动作")
            for action in sorted(dead):
                sources = []
                if action in html_actions:
                    sources.append("html")
                if action in js_render_actions:
                    sources.append("js:render")
                print(f"  · {action} (来源: {', '.join(sources)})")
        else:
            live = page_actions & page_handlers
            if page_actions:
                print(f"  ✅ {page}: {len(page_actions)} 个 action, 全部匹配")

    # ── base.html 特殊处理（用全站 handler 池）──
    base_file = TEMPLATES / "base.html"
    if base_file.exists():
        base_actions = extract_html_actions_from_file(base_file)
        # 全站 handler = 所有 pages/*.js + 全局池
        all_page_handlers = set(global_handlers)
        for h in page_js_handlers.values():
            all_page_handlers.update(h)
        base_dead = base_actions - all_page_handlers - KNOWN_EXEMPTIONS
        if base_dead:
            has_error = True
            print(f"\n❌ base.html: {len(base_dead)} 个死动作")
            for a in sorted(base_dead):
                print(f"  · {a}")
        elif base_actions:
            print(f"\n  ✅ base.html: {len(base_actions)} 个 action, 全部匹配")

    # ── 孤儿处理检测（按页）──
    print("\n" + "=" * 60)
    print("孤儿处理检测（JS 有 handler 但本页 HTML/render 无引用）")
    print("=" * 60)

    orphan_found = False
    for js_file in sorted(JS_PAGES.glob("*.js")):
        fname = js_file.name
        handlers = page_js_handlers.get(fname, set())
        if not handlers:
            continue

        html_name = fname.replace(".js", ".html")
        html_acts = all_html_actions_per_page.get(html_name, set())
        render_acts = all_render_actions_per_page.get(html_name, set())
        page_actions = html_acts | render_acts

        orphans = handlers - page_actions
        # 检查是否在全局 render 或 base.html 中
        # 或本页 render 但 handler 更完整
        # 不应包含 KNOWN_EXEMPTIONS
        if orphans:
            # 只在孤儿不在任何 HTML 或全局 render 中时才报告
            orphans_in_any_html = set()
            for acts in all_html_actions_per_page.values():
                orphans_in_any_html.update(orphans & acts)
            orphans_in_global_render = orphans & global_render_actions
            real_orphans = (
                orphans - orphans_in_any_html - orphans_in_global_render
            )

            if real_orphans:
                orphan_found = True
                print(f"\n  ⚠ {fname}: {len(real_orphans)} 个孤儿处理")
                for a in sorted(real_orphans):
                    print(f"    · {a}")

    if not orphan_found:
        print("  ✅ 无孤儿处理 — 所有 handler 均有对应 data-action 引用")

    # ── data-pg 模式检查（books.js）──
    print("\n" + "=" * 60)
    print("data-pg 模式检查")
    print("=" * 60)
    for js_file in JS_PAGES.glob("*.js"):
        content = js_file.read_text(encoding="utf-8")
        pg_actions = set()
        for m in re.finditer(r'data-pg\s*=\s*["\']([^"\']+)["\']', content):
            pg_actions.add(m.group(1))
        if pg_actions:
            pg_handlers = set()
            for pg in pg_actions:
                if re.search(
                    r"window\.\w+Page\s*=\s*\{[^}]*\b" + re.escape(pg) + r"\b",
                    content,
                ) or re.search(
                    r"(?:function\s+)?\b"
                    + re.escape(pg)
                    + r"\s*(?:=|:?\s*function\s*\()",
                    content,
                ):
                    pg_handlers.add(pg)
            missing_pg = pg_actions - pg_handlers
            if missing_pg:
                has_error = True
                print(f"  ❌ {js_file.name}: {len(missing_pg)} 个 data-pg 可能缺失函数")
                for a in sorted(missing_pg):
                    print(f"    · {a}")
            else:
                print(f"  ✅ {js_file.name}: {len(pg_actions)} 个 data-pg, 全部匹配")

    # ── 汇总 ──
    print()
    if has_error:
        msg = "❌ verify_action_wiring: 不通过 — 存在未修复的动作绑定问题"
        print(msg)
        if args.strict:
            return 1
        else:
            print("⚠ （传递 --strict 则返回 1）")
            return 0
    else:
        print("✅ verify_action_wiring: 通过 — 所有 data-action 绑定完整")
        return 0


if __name__ == "__main__":
    sys.exit(main())
