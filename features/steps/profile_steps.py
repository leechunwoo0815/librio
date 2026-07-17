# features/steps/profile_steps.py
"""个人名片BDD步骤"""

from behave import given, when, then
from backend.domain.advancement.models import (
    Level,
    ChildLevel,
    Achievement,
    ChildAchievement,
)
from backend.domain.profile.service import ProfileService


@given("孩子已读完{count:d}本书共{words:d}词")
def step_reading_done(context, count, words):
    context.child.total_books_finished = count
    context.child.total_words_read = words
    context.db.commit()


@when("请求生成个人名片")
def step_request_profile(context):
    svc = ProfileService(context.db)
    context.profile = svc.get_profile(context.child.id)


@then("名片包含孩子姓名")
def step_profile_has_name(context):
    assert context.profile["name"] == context.child.name


@then("名片包含阅读本数{count:d}")
def step_profile_books(context, count):
    assert context.profile["total_books_finished"] == count


@then("名片包含阅读词数{words:d}")
def step_profile_words(context, words):
    assert context.profile["total_words_read"] == words


@given("孩子当前级别为A级")
def step_current_level_a(context):
    level = context.db.query(Level).filter(Level.name == "A").first()
    if not level:
        level = Level(
            name="A",
            sort_order=1,
            required_books=10,
            max_borrow_count=20,
            badge_emoji="🌱",
        )
        context.db.add(level)
        context.db.commit()
    cl = ChildLevel(child_id=context.child.id, level_id=level.id, is_current=True)
    context.db.add(cl)
    context.db.commit()


@then("名片包含当前级别")
def step_profile_has_level(context):
    assert context.profile["current_level"] is not None


@given("孩子已获得{count:d}个成就")
def step_has_achievements(context, count):
    for i in range(count):
        ach = Achievement(
            name=f"成就{i + 1}", type=Achievement.TYPE_BOOK_MILESTONE, badge_emoji="📚"
        )
        context.db.add(ach)
        context.db.commit()
        ca = ChildAchievement(child_id=context.child.id, achievement_id=ach.id)
        context.db.add(ca)
    context.db.commit()


@then("名片包含成就数量{count:d}")
def step_profile_achievement_count(context, count):
    assert context.profile["achievement_count"] == count
