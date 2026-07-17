# backend/domain/child/router.py
"""孩子域 API 路由 — 孩子管理、会员状态、权益转让"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.common.dependencies import get_child_service
from backend.middleware.admin_rbac import require_perm
from backend.middleware.auth import get_current_user
from backend.middleware.ownership import GetOwnedChild, verify_child_ownership
from backend.domain.child.schemas import (
    ChildCreate,
    ChildResponse,
    ChildStatusUpdate,
    ChildUpdate,
    TransferBenefitRequest,
    BorrowPermissionResponse,
)
from backend.domain.child.service import ChildService
from backend.database import get_db

router = APIRouter(prefix="/child", tags=["孩子"])


@router.post("/", response_model=ChildResponse, status_code=201)
def create_child(
    child_data: ChildCreate,
    child_service: ChildService = Depends(get_child_service),
    current_user=Depends(get_current_user),
):
    """为孩子创建档案"""
    return child_service.create_child(current_user.id, child_data)


@router.get("/", response_model=list[ChildResponse])
def get_my_children(
    child_service: ChildService = Depends(get_child_service),
    current_user=Depends(get_current_user),
):
    """获取我的所有孩子"""
    # low-volume: per user, typically <=10 children
    return child_service.get_user_children(current_user.id)


@router.get("/{child_id}", response_model=ChildResponse)
def get_child_detail(
    child=Depends(GetOwnedChild()),
    child_service: ChildService = Depends(get_child_service),
):
    """获取孩子详情"""
    return child_service.get_child(child.id)


@router.put("/{child_id}", response_model=ChildResponse)
def update_child(
    update_data: ChildUpdate,
    child=Depends(GetOwnedChild()),
    child_service: ChildService = Depends(get_child_service),
):
    """更新孩子基本信息"""
    return child_service.update_child(child.id, update_data)


@router.put("/{child_id}/status", response_model=ChildResponse)
def update_child_status(
    child_id: int,
    status_data: ChildStatusUpdate,
    child_service: ChildService = Depends(get_child_service),
    admin=Depends(require_perm("child.edit")),
):
    """更新会员状态（管理员操作）"""
    return child_service.update_status(child_id, status_data)


@router.post("/transfer", response_model=dict)
def transfer_benefit(
    req: TransferBenefitRequest,
    child_service: ChildService = Depends(get_child_service),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """权益转让 — 提交转让申请（需管理员审核）"""
    verify_child_ownership(req.source_child_id, current_user, db)
    verify_child_ownership(req.target_child_id, current_user, db)
    return child_service.create_benefit_transfer_application(
        req.source_child_id, req.target_child_id, current_user.id
    )


@router.get("/{child_id}/can-borrow", response_model=BorrowPermissionResponse)
def check_borrow_permission(
    child=Depends(GetOwnedChild()),
    child_service: ChildService = Depends(get_child_service),
):
    """检查孩子是否有借书权限"""
    can_borrow = child_service.can_borrow_books(child.id)
    return BorrowPermissionResponse(child_id=child.id, can_borrow=can_borrow)
