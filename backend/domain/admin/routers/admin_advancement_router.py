# backend/domain/admin/routers/admin_advancement_router.py
"""晋级管理路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import get_db, get_admin_book_service
from backend.middleware.admin_rbac import require_perm
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    CreateLevelRequest,
    UpdateLevelRequest,
    CreateAchievementRequest,
    UpdateAchievementRequest,
    ReviewSubmissionRequest,
    CreateQuestionRequest,
    UpdateQuestionRequest,
    BulkImportQuestionItem,
)
from backend.domain.advancement.service import AdvancementService
from backend.domain.admin.services.book_service import AdminBookService
from backend.domain.admin.services.account_service import AdminAccountService

router = APIRouter(prefix="/admin/api/advancement", tags=["晋级管理"])


# ==================== 级别管理 ====================


@router.get("/levels", response_model=list)
def list_levels(
    admin=Depends(require_perm("level.list")),
    db: Session = Depends(get_db),
):
    """获取级别列表"""
    service = AdvancementService(db)
    return service.get_levels()


@router.post("/levels", response_model=AdminActionResponse, status_code=201)
def create_level(
    data: CreateLevelRequest,
    admin=Depends(require_perm("level.create")),
    db: Session = Depends(get_db),
):
    """创建级别"""
    service = AdvancementService(db)
    result = service.create_level(data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="level",
        operation="create",
        content=f"创建级别: {data.name}",
    )
    return result


@router.put("/levels/{level_id}", response_model=SuccessResponse)
def update_level(
    level_id: int,
    data: UpdateLevelRequest,
    admin=Depends(require_perm("level.edit")),
    db: Session = Depends(get_db),
):
    """更新级别"""
    service = AdvancementService(db)
    result = service.update_level(level_id, data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="level",
        operation="update",
        content=f"更新级别 #{level_id}",
    )
    return result


@router.delete("/levels/{level_id}", response_model=SuccessResponse)
def delete_level(
    level_id: int,
    admin=Depends(require_perm("level.delete")),
    db: Session = Depends(get_db),
):
    """删除级别"""
    service = AdvancementService(db)
    result = service.delete_level(level_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="level",
        operation="delete",
        content=f"删除级别 #{level_id}",
    )
    return result


# ==================== 成就管理 ====================


@router.get("/achievements", response_model=list)
def list_achievements(
    admin=Depends(require_perm("achievement.list")),
    db: Session = Depends(get_db),
):
    """获取成就列表"""
    service = AdvancementService(db)
    return service.get_achievements()


@router.post("/achievements", response_model=AdminActionResponse, status_code=201)
def create_achievement(
    data: CreateAchievementRequest,
    admin=Depends(require_perm("achievement.create")),
    db: Session = Depends(get_db),
):
    """创建成就"""
    service = AdvancementService(db)
    result = service.create_achievement(data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="achievement",
        operation="create",
        content=f"创建成就: {data.name}",
    )
    return result


@router.put("/achievements/{achievement_id}", response_model=SuccessResponse)
def update_achievement(
    achievement_id: int,
    data: UpdateAchievementRequest,
    admin=Depends(require_perm("achievement.edit")),
    db: Session = Depends(get_db),
):
    """更新成就"""
    service = AdvancementService(db)
    result = service.update_achievement(achievement_id, data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="achievement",
        operation="update",
        content=f"更新成就 #{achievement_id}",
    )
    return result


@router.delete("/achievements/{achievement_id}", response_model=SuccessResponse)
def delete_achievement(
    achievement_id: int,
    admin=Depends(require_perm("achievement.delete")),
    db: Session = Depends(get_db),
):
    """删除成就"""
    service = AdvancementService(db)
    result = service.delete_achievement(achievement_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="achievement",
        operation="delete",
        content=f"删除成就 #{achievement_id}",
    )
    return result


@router.get("/achievements/records", response_model=AdminActionResponse)
def list_achievement_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("achievement.list")),
    db: Session = Depends(get_db),
):
    """获取成就记录 — 带分页"""
    service = AdvancementService(db)
    return service.list_achievement_records(page, page_size)


# ==================== 证书管理 ====================


@router.get("/certificates", response_model=AdminActionResponse)
def list_certificates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("certificate.list")),
    db: Session = Depends(get_db),
):
    """获取证书列表"""
    service = AdvancementService(db)
    return service.list_certificates(page, page_size)


@router.post(
    "/certificates/{certificate_id}/regenerate", response_model=AdminActionResponse
)
def regenerate_certificate(
    certificate_id: int,
    admin=Depends(require_perm("certificate.regenerate")),
    db: Session = Depends(get_db),
):
    """重新生成证书"""
    service = AdvancementService(db)
    result = service.regenerate_certificate(certificate_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="certificate",
        operation="regenerate",
        content=f"重新生成证书 #{certificate_id}",
    )
    return result


@router.delete("/certificates/{certificate_id}", response_model=AdminActionResponse)
def delete_certificate(
    certificate_id: int,
    admin=Depends(require_perm("certificate.delete")),
    db: Session = Depends(get_db),
):
    """删除证书"""
    service = AdvancementService(db)
    result = service.delete_certificate(certificate_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="certificate",
        operation="delete",
        content=f"删除证书 #{certificate_id}",
    )
    return result


# ==================== 测验记录 ====================


@router.get("/quizzes", response_model=AdminActionResponse)
def list_quizzes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("quiz.list")),
    db: Session = Depends(get_db),
):
    """获取测验记录列表"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    service = AdvancementService(db)
    return service.list_quizzes(page, page_size, child_ids=child_ids)


# ==================== 提交审核 ====================


@router.get("/submissions", response_model=AdminActionResponse)
def list_submissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = None,
    admin=Depends(require_perm("submission.list")),
    db: Session = Depends(get_db),
):
    """获取审核列表 — 带分页"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    service = AdvancementService(db)
    return service.list_submissions(page, page_size, status, child_ids=child_ids)


@router.put("/submissions/{submission_id}/review", response_model=AdminActionResponse)
def review_submission(
    submission_id: int,
    data: ReviewSubmissionRequest,
    admin=Depends(require_perm("submission.approve")),
    db: Session = Depends(get_db),
):
    """审核提交"""
    service = AdvancementService(db)
    result = service.review_submission(submission_id, data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="submission",
        operation="review",
        content=f"审核提交 #{submission_id}",
    )
    return result


# ==================== 题库管理 ====================


@router.get("/questions", response_model=AdminActionResponse)
def list_questions(
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("question.list")),
    db: Session = Depends(get_db),
):
    """获取题目列表 — 带分页"""
    service = AdvancementService(db)
    return service.list_questions(page, page_size, keyword)


@router.post("/questions", response_model=AdminActionResponse, status_code=201)
def create_question(
    data: CreateQuestionRequest,
    admin=Depends(require_perm("question.create")),
    db: Session = Depends(get_db),
):
    """创建题目"""
    service = AdvancementService(db)
    result = service.create_question(data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="question",
        operation="create",
        content=f"创建题目: {data.question_text[:50]}",
    )
    return result


@router.put("/questions/{question_id}", response_model=AdminActionResponse)
def update_question(
    question_id: int,
    data: UpdateQuestionRequest,
    admin=Depends(require_perm("question.edit")),
    db: Session = Depends(get_db),
):
    """更新题目"""
    service = AdvancementService(db)
    result = service.update_question(question_id, data)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="question",
        operation="update",
        content=f"更新题目 #{question_id}",
    )
    return result


@router.delete("/questions/{question_id}", response_model=SuccessResponse)
def delete_question(
    question_id: int,
    admin=Depends(require_perm("question.delete")),
    db: Session = Depends(get_db),
):
    """删除题目"""
    service = AdvancementService(db)
    result = service.delete_question(question_id)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="question",
        operation="delete",
        content=f"删除题目 #{question_id}",
    )
    return result


@router.get("/questions/search", response_model=AdminActionResponse)
def search_questions_by_book(
    keyword: str = Query(..., description="书名或ISBN关键词"),
    admin=Depends(require_perm("question.list")),
    service: AdminBookService = Depends(get_admin_book_service),
):
    """按书名/ISBN搜索题库"""
    return service.search_questions_by_book(keyword)


@router.post("/questions/bulk-import", response_model=AdminActionResponse)
def bulk_import_questions(
    questions: list[BulkImportQuestionItem],
    admin=Depends(require_perm("question.import")),
    service: AdminBookService = Depends(get_admin_book_service),
):
    """批量导入题目"""
    result = service.bulk_import_questions(questions)
    from backend.domain.admin.services.system_service import AdminSystemService

    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="question",
        operation="bulk_import",
        content=f"批量导入 {len(questions)} 道题目",
    )
    return result
