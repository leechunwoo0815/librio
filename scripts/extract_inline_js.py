"""Extract inline <script> blocks from admin templates to static JS files.

Phase 1 of inline JS consolidation — zero behavioral change.
"""

import re
import os

TEMPLATES_DIR = "backend/templates/admin"
JS_DIR = "backend/static/admin/js/pages"
BASE_JS_DIR = "backend/static/admin/js"

os.makedirs(JS_DIR, exist_ok=True)

TEMPLATES = [
    "achievements",
    "activity_checkin",
    "assessments",
    "audio",
    "benefit_transfers",
    "bookcopy",
    "certificates",
    "content",
    "dashboard",
    "deposit",
    "dictionary",
    "library",
    "message_manage",
    "operation_logs",
    "page_template",
    "profile",
    "questions",
    "quiz",
    "reading_data",
    "recycle_bin",
    "reservation",
    "roles",
    "settings",
    "submissions",
    "teachers",
    "venues",
]


def find_script_block(content, template_name):
    """Find the inline <script> block. Returns (full_match, js_code, indent) or None."""
    # Match indented <script> (but not <script src=)
    # Capture everything between <script> and </script>
    pattern = re.compile(
        r"^([ \t]*)<script>\n(.*?)\n[ \t]*</script>", re.MULTILINE | re.DOTALL
    )
    match = pattern.search(content)
    if match:
        return match.group(0), match.group(2), match.group(1)

    # Fallback: <script> at start of line
    pattern2 = re.compile(r"<script>\n(.*?)\n</script>", re.DOTALL)
    match2 = pattern2.search(content)
    if match2:
        return match2.group(0), match2.group(1), ""
    return None


def run():
    print("=" * 60)
    print("Phase 1: Extracting inline scripts to static JS files")
    print("=" * 60)

    # Handle base.html
    print("\n--- base.html ---")
    path = os.path.join(TEMPLATES_DIR, "base.html")
    with open(path, "r") as f:
        content = f.read()
    result = find_script_block(content, "base")
    if result:
        full_match, js_code, indent = result
        js_path = os.path.join(BASE_JS_DIR, "base-init.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js_code)
        print(f"  WROTE {js_path} ({len(js_code.splitlines())} lines)")
        new_tag = f'{indent}<script src="/static/admin/js/base-init.js"></script>'
        new_content = content.replace(full_match, new_tag, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  UPDATED {path}")
    else:
        print("  SKIP (no inline script)")

    # Handle login.html
    print("\n--- login.html ---")
    path = os.path.join(TEMPLATES_DIR, "login.html")
    with open(path, "r") as f:
        content = f.read()
    result = find_script_block(content, "login")
    if result:
        full_match, js_code, indent = result
        js_path = os.path.join(JS_DIR, "login.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js_code)
        print(f"  WROTE {js_path} ({len(js_code.splitlines())} lines)")
        new_tag = f'{indent}<script src="/static/admin/js/pages/login.js"></script>'
        new_content = content.replace(full_match, new_tag, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  UPDATED {path}")
    else:
        print("  SKIP (no inline script)")

    # Handle roles.html — add data attribute to body
    print("\n--- roles.html ---")
    path = os.path.join(TEMPLATES_DIR, "roles.html")
    with open(path, "r") as f:
        content = f.read()
    data_attr = (
        "data-can-edit-role=\"{{ 'true' if user_can('role.edit') else 'false' }}\""
    )
    if data_attr not in content:
        content = content.replace("<body>", f"<body {data_attr}>")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("  ADDED data-can-edit-role to <body>")

    # Handle page templates
    for name in TEMPLATES:
        print(f"\n--- {name}.html ---")
        path = os.path.join(TEMPLATES_DIR, f"{name}.html")
        with open(path, "r") as f:
            content = f.read()

        result = find_script_block(content, name)
        if not result:
            print("  SKIP (no inline script)")
            continue

        full_match, js_code, indent = result
        js_path = os.path.join(JS_DIR, f"{name}.js")

        # Special handling for roles.html: replace Jinja2 var with data-attribute accessor
        if name == "roles":
            js_code = js_code.replace(
                "{{ 'true' if user_can('role.edit') else 'false' }}",
                "document.body.dataset.canEditRole === 'true'",
            )

        with open(js_path, "w", encoding="utf-8") as f:
            f.write(js_code)
        print(f"  WROTE {js_path} ({len(js_code.splitlines())} lines)")
        new_tag = f'{indent}<script src="/static/admin/js/pages/{name}.js"></script>'
        new_content = content.replace(full_match, new_tag, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  UPDATED {path}")

    print("\n" + "=" * 60)
    print("Done! Verify with: ruff check backend/ && pytest")
    print("=" * 60)


if __name__ == "__main__":
    run()
