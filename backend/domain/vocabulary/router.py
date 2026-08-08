# backend/domain/vocabulary/router.py
"""词汇域 API 路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.common.dependencies import get_vocabulary_service
from backend.common.exceptions import ValidationError
from backend.database import get_db
from backend.middleware.ownership import (
    GetOwnedChild,
    GetOwnedVocab,
    verify_child_ownership,
)
from backend.middleware.auth import get_current_user
from backend.domain.vocabulary.schemas import (
    WordLookupResponse,
    AddVocabRequest,
    VocabResponse,
    VocabStatsResponse,
    VocabMasterResponse,
)
from backend.domain.vocabulary.service import VocabularyService

router = APIRouter(prefix="/vocabulary", tags=["词汇"])


@router.get("/lookup/{word}", response_model=WordLookupResponse | None)
def lookup_word(
    word: str,
    child_id: int | None = None,
    book_id: int | None = None,
    service: VocabularyService = Depends(get_vocabulary_service),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查词 — 受开关和次数限制；传 child_id 时自动记录生词本（C3）"""
    service.check_lookup_allowed(current_user.id)
    result = service.lookup_word(word)
    if result:
        # F-072：child_id 缺省时用当前孩子兜底——查词必须计数，
        # 否则试读用户不传 child_id 可无限绕过每日限额
        eff_child_id = child_id or getattr(current_user, "current_child_id", None)
        if eff_child_id:
            verify_child_ownership(eff_child_id, current_user, db)
            service.record_lookup(eff_child_id, word, book_id=book_id)
    return result


@router.post("/", response_model=VocabResponse, status_code=201)
def add_to_vocabulary(
    data: AddVocabRequest,
    service: VocabularyService = Depends(get_vocabulary_service),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """添加到生词本"""
    child_id = data.child_id or getattr(current_user, "current_child_id", None)
    if not child_id:
        raise ValidationError("请先选择孩子")
    verify_child_ownership(child_id, current_user, db)
    return service.add_to_vocabulary(child_id, word=data.word, book_id=data.book_id)


@router.put("/{vocab_id}/master", response_model=VocabMasterResponse)
def mark_mastered(
    service: VocabularyService = Depends(get_vocabulary_service),
    result=Depends(GetOwnedVocab()),
):
    """标记为已掌握"""
    _, vocab = result
    return service.mark_mastered(vocab.id)


@router.delete("/{vocab_id}")
def remove_from_vocabulary(
    vocab_id: int,
    service: VocabularyService = Depends(get_vocabulary_service),
    result=Depends(GetOwnedVocab()),
):
    """从生词本移除"""
    _, vocab = result
    return service.remove_from_vocabulary(vocab.id)


@router.get("/{child_id}", response_model=list[VocabResponse])
def get_vocabulary_list(
    status: int | None = None,
    sort_by: str = "time",
    child=Depends(GetOwnedChild()),
    service: VocabularyService = Depends(get_vocabulary_service),
):
    """获取生词列表"""
    return service.get_vocabulary_list(child.id, status, sort_by)


@router.get("/{child_id}/learning-words", response_model=list[str])
def get_learning_words(
    child=Depends(GetOwnedChild()),
    service: VocabularyService = Depends(get_vocabulary_service),
):
    """获取学习中（status=0）的生词列表（用于阅读页高亮）"""
    return service.get_learning_words(child.id)


@router.get("/{child_id}/stats", response_model=VocabStatsResponse)
def get_vocab_stats(
    child=Depends(GetOwnedChild()),
    service: VocabularyService = Depends(get_vocabulary_service),
):
    """生词统计"""
    return service.get_vocab_stats(child.id)
