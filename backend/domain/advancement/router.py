# backend/domain/advancement/router.py
"""晋级域 API 路由 — 级别/测验/成就"""

from fastapi import APIRouter, Depends, Query

from backend.common.exceptions import ValidationError
from backend.common.dependencies import get_advancement_service, get_leaderboard_service
from backend.middleware.ownership import GetOwnedChild, GetOwnedQuiz
from backend.middleware.auth import get_current_user
from backend.domain.advancement.schemas import (
    LevelResponse,
    ChildLevelResponse,
    QuizStartRequest,
    QuizResponse,
    SubmitAnswerRequest,
    QuizResultResponse,
    QuestionResponse,
    AchievementResponse,
    ChildAchievementResponse,
    LeaderboardEntryResponse,
    CreateQuestionRequest,
)
from backend.domain.advancement.service import AdvancementService
from backend.domain.advancement.leaderboard_service import LeaderboardService

router = APIRouter(prefix="/advancement", tags=["晋级"])


# ==================== 级别 ====================


@router.get("/levels", response_model=list[LevelResponse])
def get_levels(
    service: AdvancementService = Depends(get_advancement_service),
    current_user=Depends(get_current_user),
):
    """获取所有级别"""
    return service.get_levels()


@router.get("/level/{child_id}", response_model=ChildLevelResponse | None)
def get_current_level(
    child=Depends(GetOwnedChild()),
    service: AdvancementService = Depends(get_advancement_service),
):
    """获取孩子当前级别"""
    return service.get_current_level(child.id)


# ==================== 测验 ====================


@router.post("/quiz/start", response_model=QuizResponse, status_code=201)
def start_quiz(
    data: QuizStartRequest,
    child_id: int | None = None,
    service: AdvancementService = Depends(get_advancement_service),
    current_user=Depends(get_current_user),
):
    """开始测验"""
    # 优先使用 query 参数 child_id，其次 current_child_id
    cid = child_id or getattr(current_user, "current_child_id", None)
    if not cid:
        raise ValidationError("请先选择孩子")
    return service.start_quiz(cid, data)


@router.get("/quiz/questions/{book_id}", response_model=list[QuestionResponse])
def get_quiz_questions(
    book_id: int,
    service: AdvancementService = Depends(get_advancement_service),
    current_user=Depends(get_current_user),
):
    """获取图书测验题目"""
    return service.get_quiz_questions(book_id)


@router.post("/questions", status_code=201)
def create_question(
    data: CreateQuestionRequest,
    service: AdvancementService = Depends(get_advancement_service),
    current_user=Depends(get_current_user),
):
    """创建题库题目"""
    return service.create_question(**data.model_dump())


@router.post("/quiz/{quiz_id}/submit", response_model=QuizResultResponse)
def submit_quiz_answers(
    answers: list[SubmitAnswerRequest],
    service: AdvancementService = Depends(get_advancement_service),
    result=Depends(GetOwnedQuiz()),
):
    """提交测验答案"""
    _, quiz = result
    return service.submit_answers(quiz.id, answers)


# ==================== 成就 ====================


@router.get("/achievements", response_model=list[AchievementResponse])
def get_achievements(
    service: AdvancementService = Depends(get_advancement_service),
    current_user=Depends(get_current_user),
):
    """获取所有成就"""
    return service.get_achievements()


@router.get("/achievements/{child_id}", response_model=list[ChildAchievementResponse])
def get_child_achievements(
    child=Depends(GetOwnedChild()),
    service: AdvancementService = Depends(get_advancement_service),
):
    """获取孩子已获得的成就"""
    return service.get_child_achievements(child.id)


# ==================== 排行榜 ====================


@router.get("/leaderboard", response_model=list[LeaderboardEntryResponse])
def get_leaderboard(
    period: str = Query("total", description="7d/15d/30d/month/year/total"),
    level_id: int = Query(None, description="按级别筛选"),
    month: int = Query(None, description="月排行榜的月份"),
    year: int = Query(None, description="月/年排行榜的年份"),
    limit: int = Query(20, ge=1, le=100),
    service: LeaderboardService = Depends(get_leaderboard_service),
    current_user=Depends(get_current_user),
):
    """获取排行榜"""
    return service.get_leaderboard(
        period=period,
        level_id=level_id,
        month=month,
        year=year,
        limit=limit,
    )
