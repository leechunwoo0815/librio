# features/steps/observation_report_steps.py
"""观察期报告BDD步骤"""

from behave import given, when, then
from datetime import datetime, timedelta
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.advancement.models import ReadingSubmission, Quiz
from backend.domain.report.models import ObservationReport
from backend.domain.report.service import ReportService as ObservationReportService


@given("孩子已进入观察期30天")
def step_observation_30_days(context):
    context.child.create_time = datetime.now() - timedelta(days=31)
    context.child.member_start_time = datetime.now() - timedelta(days=31)
    context.child.status = Child.STATUS_OBSERVATION
    context.db.commit()


@given("孩子进入观察期仅15天")
def step_observation_15_days(context):
    context.child.create_time = datetime.now() - timedelta(days=15)
    context.child.member_start_time = datetime.now() - timedelta(days=15)
    context.child.status = Child.STATUS_OBSERVATION
    context.db.commit()


@when("系统执行观察期报告生成任务")
def step_generate_reports(context):
    svc = ObservationReportService(context.db)
    context.generate_results = svc.generate_due_reports()


@then("生成观察期报告")
def step_report_generated(context):
    assert len(context.generate_results) >= 1


@then('报告状态为"已生成"')
def step_report_status_generated(context):
    svc = ObservationReportService(context.db)
    report = svc.get_report(context.child.id)
    assert report is not None
    assert report["status"] == ObservationReport.STATUS_GENERATED


@then("不生成新报告")
def step_no_new_report(context):
    assert len(context.generate_results) == 0


@given("孩子观察期内读了5本书共15000词")
def step_reading_stats(context):
    context.child.create_time = datetime.now() - timedelta(days=31)
    context.child.member_start_time = datetime.now() - timedelta(days=31)
    context.child.status = Child.STATUS_OBSERVATION
    context.db.commit()

    book = Book(
        isbn="978REP1",
        title="ReportBook",
        author="A",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        word_count=3000,
    )
    context.db.add(book)
    context.db.commit()

    for i in range(5):
        sub = ReadingSubmission(
            child_id=context.child.id,
            book_id=book.id,
            status=ReadingSubmission.STATUS_APPROVED,
            submitted_at=datetime.now() - timedelta(days=10),
            word_count=3000,
        )
        context.db.add(sub)
    context.db.commit()


@when("查看观察期报告")
def step_view_report(context):
    svc = ObservationReportService(context.db)
    # 先确保报告已生成
    svc.generate_due_reports()
    context.report = svc.get_report(context.child.id)


@then("报告显示阅读本数为{count:d}")
def step_report_books(context, count):
    assert context.report is not None
    assert context.report["total_books_read"] == count


@then("报告显示阅读词数为{words:d}")
def step_report_words(context, words):
    assert context.report is not None
    assert context.report["total_words_read"] == words


@given("孩子观察期内通过了3次测验")
def step_quiz_passed(context):
    context.child.create_time = datetime.now() - timedelta(days=31)
    context.child.member_start_time = datetime.now() - timedelta(days=31)
    context.child.status = Child.STATUS_OBSERVATION
    context.db.commit()

    book = Book(
        isbn="978REP2",
        title="QuizReportBook",
        author="B",
        ar_value=2.0,
        age_min=5,
        age_max=9,
        word_count=2000,
    )
    context.db.add(book)
    context.db.commit()

    for i in range(3):
        quiz = Quiz(
            child_id=context.child.id,
            book_id=book.id,
            status=Quiz.STATUS_COMPLETED,
            score=90,
            total_questions=5,
            create_time=datetime.now() - timedelta(days=10),
        )
        context.db.add(quiz)
    context.db.commit()


@then("报告显示通过测验数为{count:d}")
def step_report_quizzes(context, count):
    assert context.report is not None
    assert context.report["quizzes_passed"] == count


@given("老师已提交观察期评价")
def step_teacher_comment_exists(context):
    context.child.create_time = datetime.now() - timedelta(days=31)
    context.child.member_start_time = datetime.now() - timedelta(days=31)
    context.child.status = Child.STATUS_OBSERVATION
    context.db.commit()

    svc = ObservationReportService(context.db)
    svc.generate_due_reports()
    report = svc.get_report(context.child.id)
    assert report is not None, "报告应该已生成"
    svc.add_teacher_comment(
        report["id"], teacher_id=1, comment="表现优秀，建议继续学习"
    )


@then("报告显示老师评语")
def step_report_has_comment(context):
    assert context.report is not None
    assert context.report["teacher_comment"] is not None
    assert len(context.report["teacher_comment"]) > 0


@given("孩子已有观察期报告")
def step_has_report(context):
    context.child.create_time = datetime.now() - timedelta(days=31)
    context.child.member_start_time = datetime.now() - timedelta(days=31)
    context.child.status = Child.STATUS_OBSERVATION
    context.db.commit()
    svc = ObservationReportService(context.db)
    svc.generate_due_reports()


@when("家长请求查看报告")
def step_request_report(context):
    svc = ObservationReportService(context.db)
    context.report = svc.get_report(context.child.id)


@then("返回报告详情")
def step_report_returned(context):
    assert context.report is not None
    assert "total_books_read" in context.report


@given("孩子尚无观察期报告")
def step_no_report(context):
    context.child.status = Child.STATUS_OBSERVATION
    context.db.commit()


@then("返回空结果")
def step_report_empty(context):
    assert context.report is None
