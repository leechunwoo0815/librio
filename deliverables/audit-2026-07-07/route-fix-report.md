# 图书管理路由修复报告

- **修复日期**：2026-07-07
- **修复人**：software-engineer

## 修改摘要

### 1. 路由模板调整

文件：`/Users/litianyu/cc-projects/librio/backend/domain/admin/admin_page_router.py`

- `/admin/view/books`（line 187）：`"admin/booklist.html"` → `"admin/books.html"`
- `/admin/view/library`（line 197）：`"admin/booklist.html"` → `"admin/books.html"`

### 2. 废弃文件清理

已删除：

- `/Users/litianyu/cc-projects/librio/backend/templates/admin/booklist.html`
- `/Users/litianyu/cc-projects/librio/backend/static/admin/js/pages/booklist.js`
- `/Users/litianyu/cc-projects/librio/backend/static/admin/css/pages/booklist.css`

`backend/` 目录下已无 `booklist.html` / `booklist.js` / `booklist.css` 的代码引用，仅历史文档/审计报告中保留旧记录。

## 验证结果

### 1. 语法检查

```bash
ruff check backend/
```

结果：All checks passed!

### 2. 单元测试

```bash
pytest tests/unit/ -q
```

结果：100 passed, 5 warnings

### 3. 行为测试

```bash
python -m behave features/ -q
```

结果：全部通过（无失败场景）

### 4. 全面正式测试

```bash
python scripts/formal_test_v2.py
```

结果：总计 119，通过 119，失败 0，通过率 100.0%

### 5. 路由渲染验证

使用 FastAPI `TestClient` 以管理员 token 访问以下路径：

| 路径 | 状态 | 说明 |
|------|------|------|
| `/admin/view/books` | 200 | 渲染 `books.html`，加载 `pages/books.js`，未加载 `booklist.js` |
| `/admin/view/library` | 200 | 同上，渲染新版图书管理页面 |
| `/admin/view/booklist` | 404 | 该路由未注册，按预期返回 404 |

验证输出：

```
/admin/view/books: status=200
  title found: True
  books.js loaded: True
  booklist.js NOT loaded: True
/admin/view/library: status=200
  title found: True
  books.js loaded: True
  booklist.js NOT loaded: True
/admin/view/booklist: status=404
```

## 结论

- `/admin/view/books` 与 `/admin/view/library` 现已统一渲染新版 `books.html`。
- 旧版 `booklist.html` 及对应 `booklist.js`/`booklist.css` 已清理，避免维护两套重复代码。
- 全部自动化测试通过，路由行为符合预期。
- 文档/审计报告中的历史 `booklist.html` 引用为记录性质，不影响线上代码。

---

*报告路径：`/Users/litianyu/cc-projects/librio/deliverables/audit-2026-07-07/route-fix-report.md`*
