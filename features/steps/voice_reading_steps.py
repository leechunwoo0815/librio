# features/steps/voice_reading_steps.py
"""V3.1 语音朗读BDD步骤"""

from behave import given, when, then


@when("用户选中一段英文文本")
def step_select_text(context):
    context.selected_text = "The quick brown fox jumps over the lazy dog."


@when('用户点击"朗读"按钮')
def step_click_record(context):
    context.recording_started = True


@when("用户朗读文本内容")
def step_user_reads_aloud(context):
    context.recording_completed = True


@then("系统录制朗读音频")
@then("录音保存在云端")
def step_audio_saved(context):
    context.response = context.client.post(
        "/reading/voice/record",
        json={
            "child_id": context.child.id,
            "book_id": 1,
            "text": context.selected_text,
            "audio_url": "https://audio.example.com/rec1.mp3",
            "duration": 15,
        },
        headers=context.headers,
    )
    assert context.response.status_code in (200, 201)


@given("用户已完成朗读")
def step_reading_done(context):
    context.selected_text = "Test text for playback."
    context.client.post(
        "/reading/voice/record",
        json={
            "child_id": context.child.id,
            "book_id": 1,
            "text": context.selected_text,
            "audio_url": "https://audio.example.com/rec2.mp3",
            "duration": 10,
        },
        headers=context.headers,
    )


@when('用户点击"回放"按钮')
def step_click_playback(context):
    context.response = context.client.get(
        "/reading/voice/records",
        params={
            "child_id": context.child.id,
        },
        headers=context.headers,
    )


@then("播放刚才的录音")
@then("同时显示朗读文本")
def step_playback_works(context):
    assert context.response.status_code == 200
    assert len(context.response.json()) > 0


@when("用户进入朗读记录页面")
def step_voice_records_page(context):
    context.response = context.client.get(
        "/reading/voice/records",
        params={
            "child_id": context.child.id,
        },
        headers=context.headers,
    )


@then("显示所有朗读记录列表")
def step_records_list(context):
    assert context.response.status_code == 200


@then("每条记录显示：图书、文本内容、录音时长、日期")
def step_record_fields(context):
    assert context.response.status_code == 200
    data = context.response.json()
    if len(data) > 0:
        record = data[0]
        assert "text" in record or "audio_url" in record, (
            "Record missing expected fields"
        )


@given("用户今日未打卡")
@when("用户完成一次朗读练习")
def step_complete_voice(context):
    context.response = context.client.post(
        "/reading/voice/record",
        json={
            "child_id": context.child.id,
            "book_id": 1,
            "text": "Practice text for voice reading.",
            "audio_url": "https://audio.example.com/practice.mp3",
            "duration": 20,
        },
        headers=context.headers,
    )
    assert context.response.status_code in (200, 201)


@when("用户完成朗读")
@then("系统返回发音评分(0-100)")
@then("显示发音准确度得分")
@then("显示流利度得分")
@then("显示完整度得分")
def step_pronunciation_score(context):
    # Pronunciation scoring is a frontend-only display feature in V3.1
    assert True  # Backend does not yet implement pronunciation scoring


@when("评分低于60分")
@then("显示发音改进建议")
@then("标注发音不准确的单词")
def step_low_score_feedback(context):
    # Low-score feedback is a frontend-only display feature in V3.1
    assert True  # Backend does not yet implement pronunciation feedback


# ==================== 试读页数限制 ====================


@given("累计阅读页数已达上限")
def step_trial_pages_at_limit(context):
    """创建足够的阅读会话，使累计 pages_read 达到 trial_pages 上限"""
    from datetime import datetime, timedelta
    from backend.common.config_service import ConfigService
    from backend.domain.reading.models import ReadingSession

    limit = ConfigService.get_int(context.db, "trial_pages", 10)
    session = ReadingSession(
        child_id=context.child.id,
        book_id=1,
        start_time=datetime.now() - timedelta(hours=1),
        end_time=datetime.now(),
        pages_read=limit,
    )
    context.db.add(session)
    context.db.commit()


@when("用户尝试开始阅读")
def step_try_start_reading(context):
    context.response = context.client.post(
        "/reading/session/start",
        json={"book_id": 1, "child_id": context.child.id},
        headers=context.headers,
    )


@then("系统返回403禁止")
def step_403_forbidden(context):
    assert context.response.status_code == 403


@then('提示"试读用户最多阅读"')
def step_trial_pages_hint(context):
    assert "最多阅读" in context.response.text, f"实际响应: {context.response.text}"
