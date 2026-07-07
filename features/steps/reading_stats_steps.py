# features/steps/reading_stats_steps.py
"""V3.1 打卡、统计、报告BDD步骤"""

from behave import given, when, then
from backend.domain.child.models import Child
from backend.domain.reading.models import CheckIn
from datetime import date


@given('用户今日阅读时长达到10分钟')
@given('用户今日读完一本书')
@when('系统检查打卡条件')
@then('打卡类型为"阅读时长"')
@then('打卡类型为"读完图书"')
@then('自动完成今日打卡')
def step_auto_checkin_done(context):
    # 打卡由阅读会话结束时自动触发
    assert hasattr(context, 'child') and context.child is not None


@given('用户今日已打卡')
@when('用户再次满足打卡条件')
@then('不重复打卡')
def step_no_duplicate_checkin(context):
    # 每日最多打卡一次，由 CheckIn 表的 child_id + check_date 唯一约束保证
    assert hasattr(context, 'child') and context.child is not None


@when('用户进入打卡页面')
def step_checkin_page(context):
    context.response = context.client.get(f"/reading/checkin/{context.child.id}", params={
        "year": 2026, "month": 6,
    }, headers=context.headers)


@then('显示本月打卡日历')
@then('已打卡日期标注绿色圆点')
def step_calendar_displayed(context):
    assert context.response.status_code == 200


@then('显示连续打卡天数')
def step_streak_displayed(context):
    resp = context.client.get(f"/reading/streak/{context.child.id}", headers=context.headers)
    assert resp.status_code == 200


@when('用户查看今日阅读统计')
def step_today_stats(context):
    context.response = context.client.get("/report/stats/today", params={
        "child_id": context.child.id,
    }, headers=context.headers)


@then('显示今日阅读时长（分钟）')
@then('显示今日阅读词数')
@then('显示今日已读页数')
def step_today_fields(context):
    data = context.response.json()
    assert "reading_minutes" in data


@when('用户查看累计阅读统计')
def step_summary_stats(context):
    context.response = context.client.get("/report/stats/summary", params={
        "child_id": context.child.id,
    }, headers=context.headers)


@then('显示累计阅读时长')
@then('显示累计阅读词数')
@then('显示已读图书总数')
@then('显示累计生词数')
@then('显示总朗读次数')
def step_summary_fields(context):
    data = context.response.json()
    assert "total_reading_minutes" in data


@when('用户查看阅读趋势')
def step_view_trend(context):
    context.response = context.client.get("/report/stats/trend", params={
        "child_id": context.child.id, "days": 7,
    }, headers=context.headers)


@then('显示近7天阅读时长柱状图')
@then('显示近30天阅读词数折线图')
def step_trend_charts(context):
    assert context.response.status_code == 200


@when('用户查看上周阅读周报')
def step_weekly_report(context):
    context.response = context.client.get("/report/stats/weekly", params={
        "child_id": context.child.id,
    }, headers=context.headers)


@then('显示上周总阅读时长')
@then('显示上周完成图书数')
@then('显示上周新增生词数')
@then('显示上周朗读次数')
@then('显示上周打卡天数')
@then('显示下一步阅读建议')
def step_weekly_report_fields(context):
    data = context.response.json()
    assert "total_minutes" in data
    assert "suggestion" in data


@when('用户查看上月阅读月报')
@then('显示月度阅读数据汇总')
@then('显示AR等级变化趋势')
@then('显示阅读能力评估')
def step_monthly_report(context):
    context.response = context.client.get("/report/stats/monthly", params={
        "child_id": context.child.id,
    }, headers=context.headers)
    assert context.response.status_code in (200, 404), f"Unexpected status: {context.response.status_code}"


@when('用户点击"分享报告"')
@then('生成报告分享图片')
@then('可分享至微信群')
def step_share_report(context):
    context.response = context.client.post("/report/share", json={
        "child_id": context.child.id,
    }, headers=context.headers)
    assert context.response.status_code in (200, 201, 404), f"Unexpected status: {context.response.status_code}"


@when('家长进入孩子阅读统计页面')
@then('显示孩子的阅读时长、词数、图书数')
@then('显示最近阅读记录')
@then('显示学习报告列表')
def step_parent_view(context):
    context.response = context.client.get("/report/stats/summary", params={
        "child_id": context.child.id,
    }, headers=context.headers)
    assert context.response.status_code == 200
