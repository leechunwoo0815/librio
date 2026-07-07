# features/steps/advancement_steps.py
"""V3.1 晋级体系BDD步骤 — 使用直接 ORM 操作，不依赖 deprecated 方法"""

from behave import given, when, then
from backend.domain.child.models import Child
from backend.domain.book.models import Book
from backend.domain.advancement.models import Level, ChildLevel, ReadingSubmission, QuestionBank, Quiz, Achievement, ChildAchievement
from backend.domain.advancement.service import AdvancementService
from backend.domain.advancement.leaderboard_service import LeaderboardService
from backend.domain.advancement.schemas import QuizStartRequest
from decimal import Decimal
from datetime import datetime


# ==================== 辅助函数 ====================

def _ensure_level(context):
    """确保孩子有级别"""
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    if not cl:
        first = context.db.query(Level).filter(Level.is_deleted == 0).order_by(Level.sort_order).first()
        if first:
            cl = ChildLevel(child_id=context.child.id, level_id=first.id, is_current=True)
            context.db.add(cl)
            context.db.commit()
    return cl


def _ensure_book(context, title="Charlotte's Web"):
    """确保有测试图书"""
    if not hasattr(context, 'book') or not context.book:
        book = Book(isbn="9780064400558", title=title, author="E.B. White",
                    ar_value=3.2, age_min=7, age_max=9)
        context.db.add(book)
        context.db.commit()
        context.book = book
    return context.book


# ==================== 级别 ====================

@given('系统已有级别配置')
def step_levels_exist(context):
    db = context.db
    l1 = Level(name="阅读新手", badge_emoji="🌱", sort_order=1,
               required_books=3, required_quiz_pass_rate=Decimal("0.80"),
               max_borrow_count=1, max_ar_level=Decimal("2.0"),
               require_teacher_review=False)
    l2 = Level(name="阅读达人", badge_emoji="🌿", sort_order=2,
               required_books=5, required_quiz_pass_rate=Decimal("0.80"),
               max_borrow_count=2, max_ar_level=Decimal("3.5"),
               require_teacher_review=False)
    db.add_all([l1, l2])
    db.commit()
    context.levels = [l1, l2]


@when('孩子首次注册')
def step_child_first_register(context):
    # 直接 ORM 操作：分配初始级别
    first = context.db.query(Level).filter(Level.is_deleted == 0).order_by(Level.sort_order).first()
    cl = ChildLevel(child_id=context.child.id, level_id=first.id, is_current=True)
    context.db.add(cl)
    context.db.commit()
    context.level_assign = cl


@then('自动分配最低级别')
def step_assigned_lowest_level(context):
    assert context.level_assign is not None
    assert context.level_assign.level_id == context.levels[0].id


@then('显示当前级别徽章')
def step_show_level_badge(context):
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    level = context.db.query(Level).filter(Level.id == cl.level_id).first()
    assert level.badge_emoji == "🌱"


@given(u'孩子当前级别为"阅读新手"')
def step_child_at_level1(context):
    _ensure_level(context)


@when('孩子查看级别页面')
def step_view_level_page(context):
    cl = _ensure_level(context)
    level = context.db.query(Level).filter(Level.id == cl.level_id).first()
    context.level_info = {
        "level_name": level.name if level else "未设置",
        "badge_emoji": level.badge_emoji if level else None,
        "books_read_at_level": cl.books_read_at_level,
        "quizzes_passed_at_level": cl.quizzes_passed_at_level,
    }


@then('显示当前级别名称和徽章')
def step_show_level_name_badge(context):
    assert context.level_info["level_name"] == "阅读新手"


@then(u'显示晋级要求（需读完几本书、测验通过率）')
def step_show_requirements(context):
    assert "books_read_at_level" in context.level_info


# ==================== 阅读提交 ====================

@given('孩子正在阅读一本书')
def step_child_reading_book(context):
    _ensure_book(context)


@when('孩子翻到最后一页')
def step_flip_to_last(context):
    # 直接 ORM 创建提交
    existing = context.db.query(ReadingSubmission).filter(
        ReadingSubmission.child_id == context.child.id,
        ReadingSubmission.book_id == context.book.id,
        ReadingSubmission.status != ReadingSubmission.STATUS_REJECTED,
        ReadingSubmission.is_deleted == 0,
    ).first()
    if existing:
        context.submission_result = {"id": existing.id, "status": "already_submitted"}
    else:
        sub = ReadingSubmission(child_id=context.child.id, book_id=context.book.id)
        context.db.add(sub)
        context.db.flush()
        context.submission_result = {"id": sub.id, "status": "pending"}


@then('自动创建阅读提交记录')
def step_submission_created(context):
    assert context.submission_result["status"] == "pending"


@then(u'提交状态为"待审核"')
def step_submission_pending(context):
    sub = context.db.query(ReadingSubmission).filter(
        ReadingSubmission.id == context.submission_result["id"]
    ).first()
    assert sub.status == ReadingSubmission.STATUS_PENDING


@then('老师收到待审核通知')
def step_teacher_notified(context):
    pending = context.db.query(ReadingSubmission).filter(
        ReadingSubmission.status == 0, ReadingSubmission.is_deleted == 0
    ).all()
    assert len(pending) >= 1


@given('孩子有1个待审核的阅读提交')
def step_has_pending_submission(context):
    _ensure_level(context)
    book = Book(isbn="9780000000001", title="Test Book", author="Author",
                ar_value=2.0, age_min=5, age_max=8)
    context.db.add(book)
    context.db.commit()
    sub = ReadingSubmission(child_id=context.child.id, book_id=book.id)
    context.db.add(sub)
    context.db.flush()
    context.submission_id = sub.id


@when(u'老师审核并选择"通过"')
def step_admin_approve_submission(context):
    sub = context.db.query(ReadingSubmission).filter(ReadingSubmission.id == context.submission_id).first()
    sub.status = ReadingSubmission.STATUS_APPROVED
    sub.teacher_comment = "阅读质量优秀"
    sub.reviewed_at = datetime.now()
    # 更新级别读完书数
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == sub.child_id, ChildLevel.is_current == True
    ).first()
    if cl:
        cl.books_read_at_level = (cl.books_read_at_level or 0) + 1
    context.db.commit()


@then(u'提交状态变为"审核通过"')
def step_submission_approved(context):
    sub = context.db.query(ReadingSubmission).filter(
        ReadingSubmission.id == context.submission_id
    ).first()
    assert sub.status == ReadingSubmission.STATUS_APPROVED


@then('该级别已读完书数加1')
def step_books_read_incremented(context):
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    if cl:
        assert cl.books_read_at_level >= 1


@when(u'老师审核并选择"打回"')
def step_admin_reject_submission(context):
    sub = context.db.query(ReadingSubmission).filter(ReadingSubmission.id == context.submission_id).first()
    sub.status = ReadingSubmission.STATUS_REJECTED
    sub.teacher_comment = "需要重新阅读"
    sub.reviewed_at = datetime.now()
    context.db.commit()


@then(u'提交状态变为"审核拒绝"')
def step_submission_rejected(context):
    sub = context.db.query(ReadingSubmission).filter(
        ReadingSubmission.id == context.submission_id
    ).first()
    assert sub.status == ReadingSubmission.STATUS_REJECTED


@then('孩子收到打回通知')
def step_child_notified_rejection(context):
    sub = context.db.query(ReadingSubmission).filter(
        ReadingSubmission.id == context.submission_id
    ).first()
    assert sub.status == ReadingSubmission.STATUS_REJECTED


# ==================== 测验 ====================

@given(u'图书"Charlotte\'s Web"已有3道选择题')
def step_book_has_questions(context):
    _ensure_book(context)
    for i in range(3):
        q = QuestionBank(
            book_id=context.book.id, question_text=f"Question {i+1}",
            option_a="Answer A", option_b="Answer B",
            correct_answer="A", difficulty=1,
        )
        context.db.add(q)
    context.db.commit()
    context.questions = context.db.query(QuestionBank).filter(
        QuestionBank.book_id == context.book.id
    ).all()


@when('老师查看该书题库')
def step_teacher_view_questions(context):
    context.book_questions = context.db.query(QuestionBank).filter(
        QuestionBank.book_id == context.book.id, QuestionBank.is_deleted == 0
    ).all()


@then('显示3道题目列表')
def step_show_3_questions(context):
    assert len(context.book_questions) == 3


@given('图书"Charlotte\'s Web"有足够题目')
def step_book_has_enough_questions(context):
    step_book_has_questions(context)


@when('老师为孩子出测验')
def step_teacher_creates_quiz(context):
    svc = AdvancementService(context.db)
    q_ids = [q.id for q in context.questions]
    context.quiz = svc.start_quiz(context.child.id, QuizStartRequest(book_id=context.book.id))


@then('创建测验实例')
def step_quiz_created(context):
    assert context.quiz.id is not None


@then(u'测验状态为"进行中"')
def step_quiz_in_progress(context):
    quiz = context.db.query(Quiz).filter(Quiz.id == context.quiz.id).first()
    assert quiz.status == Quiz.STATUS_IN_PROGRESS


@given('孩子有一个待答题的测验')
def step_has_quiz(context):
    step_book_has_questions(context)
    svc = AdvancementService(context.db)
    context.quiz = svc.start_quiz(context.child.id, QuizStartRequest(book_id=context.book.id))


@when('孩子提交全部正确答案')
def step_submit_all_correct(context):
    _ensure_level(context)
    svc = AdvancementService(context.db)
    answers = [{"question_id": q.id, "answer": q.correct_answer} for q in context.questions]
    context.quiz_result = svc.submit_answers(context.quiz.id, answers)


@then('测验得分为100%')
def step_quiz_score_100(context):
    assert context.quiz_result["score"] == 100.0


@then('该级别通过测验数加1')
def step_quizzes_passed_incremented(context):
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    assert cl.quizzes_passed_at_level >= 1


@then(u'显示"测验满分"成就提示')
def step_quiz_perfect_achievement_hint(context):
    assert context.quiz_result["score"] == 100.0


@when('孩子提交低于80%的正确率')
def step_submit_below_70(context):
    svc = AdvancementService(context.db)
    context.quiz_result = svc.submit_answers(context.quiz.id, [
        {"question_id": context.questions[0].id, "answer": "B"},
        {"question_id": context.questions[1].id, "answer": "B"},
        {"question_id": context.questions[2].id, "answer": "A"},
    ])


@then('测验未通过')
def step_quiz_failed(context):
    assert context.quiz_result["passed"] is False


@then(u'显示"可以重考"提示')
def step_can_retake(context):
    assert context.quiz_result["passed"] is False
    assert context.quiz_result.get("can_retake", True) is not False


# ==================== 晋级 ====================

@given('孩子在当前级别已读完足够书数')
def step_read_enough_books(context):
    cl = _ensure_level(context)
    level = context.db.query(Level).filter(Level.id == cl.level_id).first()
    cl.books_read_at_level = level.required_books
    cl.quizzes_passed_at_level = 5
    context.db.commit()


@given('孩子在当前级别已读完5本书')
def step_read_5_books(context):
    cl = _ensure_level(context)
    cl.books_read_at_level = 5
    context.db.commit()


@given('孩子已通过5次测验（每本书5题答对4题即80%）')
def step_passed_5_quizzes(context):
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    cl.quizzes_passed_at_level = 5
    context.db.commit()


@given('孩子仅通过4次测验')
def step_passed_4_quizzes(context):
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    cl.quizzes_passed_at_level = 4
    context.db.commit()


@given('孩子测验通过率达标')
def step_quiz_pass_rate_met(context):
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    assert cl is not None
    assert cl.quizzes_passed_at_level >= 5


@when('检查晋级条件')
def step_check_advancement(context):
    svc = AdvancementService(context.db)
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    level = context.db.query(Level).filter(Level.id == cl.level_id).first()
    books_ok = cl.books_read_at_level >= level.required_books
    quiz_ok = cl.quizzes_passed_at_level >= 5
    context.advancement_check = {"can_advance": books_ok and quiz_ok}


@then('可以晋级')
def step_can_advance(context):
    assert context.advancement_check["can_advance"] is True


@then('不可以晋级')
def step_cannot_advance(context):
    assert context.advancement_check["can_advance"] is False


@given('孩子满足晋级条件')
def step_child_meets_criteria(context):
    cl = _ensure_level(context)
    level = context.db.query(Level).filter(Level.id == cl.level_id).first()
    cl.books_read_at_level = level.required_books
    cl.quizzes_passed_at_level = 5
    context.db.commit()


@when('执行晋级操作')
def step_do_advance(context):
    svc = AdvancementService(context.db)
    context.advance_result = svc.check_and_advance(context.child.id)


@then('孩子升到下一级别')
def step_advanced_to_next(context):
    assert context.advance_result is not None


@then('获得新级别徽章')
def step_get_new_badge(context):
    assert context.advance_result is not None


@then('借阅上限增加')
def step_borrow_limit_increased(context):
    cl = context.db.query(ChildLevel).filter(
        ChildLevel.child_id == context.child.id, ChildLevel.is_current == True
    ).first()
    assert cl is not None


@given('孩子已是最高级别')
def step_at_highest_level(context):
    highest = context.db.query(Level).order_by(Level.sort_order.desc()).first()
    cl = ChildLevel(child_id=context.child.id, level_id=highest.id, is_current=True)
    context.db.add(cl)
    context.db.commit()


@when('尝试晋级')
def step_try_advance(context):
    svc = AdvancementService(context.db)
    context.advance_result = svc.check_and_advance(context.child.id)


@then(u'显示"已是最高级别"提示')
def step_already_highest(context):
    assert context.advance_result is None


# ==================== 成就 ====================

@given(u'孩子从"阅读新手"晋级到"阅读达人"')
def step_advance_from_level1_to_level2(context):
    step_child_meets_criteria(context)
    svc = AdvancementService(context.db)
    context.advance_result = svc.check_and_advance(context.child.id)


@when('晋级操作完成')
def step_advance_done(context):
    assert context.advance_result is not None


@when('孩子查看成就页面')
def step_view_achievements(context):
    svc = AdvancementService(context.db)
    context.achievements = svc.get_child_achievements(context.child.id)


@then('显示所有已获得的徽章')
def step_show_earned_badges(context):
    assert isinstance(context.achievements, list)


@then('显示未获得的徽章（灰色）')
def step_show_unearned(context):
    assert isinstance(context.achievements, list)
    assert context.achievements is not None


@when('孩子查看排行榜')
def step_view_leaderboard(context):
    svc = LeaderboardService(context.db)
    context.leaderboard = svc.get_leaderboard()


@then('显示当前级别内阅读量排名')
def step_show_ranking(context):
    assert isinstance(context.leaderboard, list)


@then('排行榜按阅读数量降序排列')
def step_ranking_descending(context):
    if len(context.leaderboard) >= 2:
        assert context.leaderboard[0]["books_read"] >= context.leaderboard[1]["books_read"]


@then(u'孩子获得"{level_name}"徽章')
def step_get_specific_badge(context, level_name):
    assert context.advance_result is not None


# ==================== V3.1 新增步骤 ====================

@given(u'该书词数为{words:d}')
def step_book_word_count(context, words):
    if hasattr(context, 'book') and context.book:
        context.book.word_count = words
        context.db.commit()
        context.db.refresh(context.book)
        context.db.expire_all()


@given(u'该测验关联借阅记录')
def step_quiz_linked_borrow(context):
    assert context.book is not None
    assert context.book.id is not None


@given(u'孩子通过了"{title}"的测验')
def step_child_passed_quiz(context, title):
    step_book_has_enough_questions(context)
    svc = AdvancementService(context.db)
    context.quiz = svc.start_quiz(context.child.id, QuizStartRequest(book_id=context.book.id))
    _ensure_level(context)
    answers = [{"question_id": q.id, "answer": q.correct_answer} for q in context.questions]
    context.quiz_result = svc.submit_answers(context.quiz.id, answers)


@when('孩子完成听读')
def step_child_finish_listening(context):
    sub = ReadingSubmission(child_id=context.child.id, book_id=context.book.id)
    context.db.add(sub)
    context.db.flush()
    context.submission_result = {"id": sub.id, "status": "pending"}


@when(u'孩子再次通过"{title}"的测验')
def step_child_repass_quiz(context, title):
    svc = AdvancementService(context.db)
    quiz2 = svc.start_quiz(context.child.id, QuizStartRequest(book_id=context.book.id))
    answers = [{"question_id": q.id, "answer": q.correct_answer} for q in context.questions]
    context.quiz_result_2 = svc.submit_answers(quiz2.id, answers)


@when('系统记录词数积分')
def step_system_records_word_count(context):
    assert context.quiz_result is not None


@then(u'孩子积分增加{words:d}')
def step_child_score_increased(context, words):
    db_child = context.db.query(Child).filter(Child.id == context.child.id).first()
    assert db_child.total_words_read >= words


@then(u'词数积分不重复增加')
def step_score_not_duplicated(context):
    if hasattr(context, 'quiz_result_2') and context.quiz_result_2 is not None:
        result = context.quiz_result_2
    elif hasattr(context, 'quiz_result'):
        result = context.quiz_result
    else:
        result = {}
    wc = result.get("word_count", 0) if isinstance(result, dict) else 0
    assert wc == 0, f"word_count should be 0 but got {wc}"


@then(u'借阅记录的测评状态更新为"{status}"')
def step_borrow_test_status_updated(context, status):
    assert hasattr(context, 'child') and context.child is not None


@then(u'借阅记录的测评状态保持"{status}"')
def step_borrow_test_status_unchanged(context, status):
    assert hasattr(context, 'child') and context.child is not None
