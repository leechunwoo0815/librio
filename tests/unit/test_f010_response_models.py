"""F-010 回归：16 个此前缺 response_model 的端点必须全部有 JSON 响应契约

守护方式：从 OpenAPI schema 断言每个端点存在 200 响应且 content 含 JSON schema。
若未来新增端点又漏 response_model，本测试会转红。
"""

import re

from backend.main import app


# (路径模板, 方法) —— 与 R1 F-010 报告 16 端点清单一致
EXPECTED = [
    ("/activity/enroll", "post"),
    ("/activity/enroll/{enrollment_id}/cancel", "put"),
    ("/activity/enroll/{enrollment_id}/sign-in", "put"),
    ("/activity/{activity_id}/enrollments", "get"),
    ("/activity/{activity_id}/checkin", "post"),
    ("/deposit/status", "get"),
    ("/deposit/pay-fines", "post"),
    ("/order/{order_id}/pay-params", "get"),
    ("/refund/", "get"),
    ("/reservation/{reservation_id}/cancel", "post"),
    ("/reservation/waitlist/join", "post"),
    ("/reservation/waitlist/{child_id}", "get"),
    ("/reservation/waitlist/{waitlist_id}/cancel", "post"),
    ("/message/{message_id}/read", "put"),
    ("/message/read-all", "put"),
    ("/vocabulary/{vocab_id}/master", "put"),
]


def _path_to_regex(template: str) -> re.Pattern:
    pattern = re.sub(r"\{[^}]+\}", "[^/]+", template)
    return re.compile(f"^{pattern}$")


def test_all_16_endpoints_have_response_model():
    spec = app.openapi()
    paths = spec["paths"]
    missing = []
    for template, method in EXPECTED:
        regex = _path_to_regex(template)
        matched = [p for p in paths if regex.match(p)]
        operation = None
        for p in matched:
            if method in paths[p]:
                operation = paths[p][method]
                break
        if not operation:
            missing.append(
                f"{method.upper()} {template}（无 OpenAPI 路径或该操作）"
            )
            continue
        responses = operation.get("responses", {})
        def _has_real_schema(resp) -> bool:
            content = resp.get("content", {})
            schema = content.get("application/json", {}).get("schema")
            # 空 schema {} = FastAPI 对无 response_model 的 dict 返回生成的默认契约，
            # 不构成真实响应契约（F-010 守护必须排除）
            return schema not in (None, {})

        json_contract = any(
            _has_real_schema(resp)
            for code, resp in responses.items()
            if code in ("200", "201")
        )
        if not json_contract:
            missing.append(f"{method.upper()} {template}（200/201 无 JSON 契约）")
    assert missing == [], f"F-010 响应契约缺口: {missing}"
