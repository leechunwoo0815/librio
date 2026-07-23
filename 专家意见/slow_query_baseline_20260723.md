# 慢查询基线报告

- 阈值: 0.3s | 端点数: 11 | 慢查询条数: 0

## 端点耗时

| 端点 | 角色 | 状态 | 耗时(s) |
|------|------|------|---------|
| /book/search?keyword=the | user | 200 | 0.011 |
| /child/ | user | 200 | 0.006 |
| /user/info | user | 200 | 0.003 |
| /admin/api/dashboard | admin | 200 | 0.024 |
| /admin/api/users?page=1&page_size=20 | admin | 200 | 0.008 |
| /admin/api/books?page=1&page_size=20 | admin | 200 | 0.011 |
| /admin/api/borrows?page=1&page_size=20 | admin | 200 | 0.008 |
| /admin/api/orders?page=1&page_size=20 | admin | 200 | 0.006 |
| /admin/api/bookcopy | admin | 200 | 0.005 |
| /admin/api/damage-reports | admin | 200 | 0.009 |
| /admin/api/reports/observation?page=1&page_size=20 | admin | 200 | 0.010 |

## 慢查询明细

| query_time | rows_examined | db | sql_text(截断200) |
|-----------|---------------|----|-----------------|
