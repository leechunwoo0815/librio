# backend/domain/admin/routers/admin_system_router.py
"""系统管理路由"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.common.dependencies import (
    get_db,
    get_admin_system_service,
    get_admin_account_service,
    get_admin_message_service,
    get_admin_borrow_service,
    get_admin_order_service,
    get_admin_refund_service,
    get_admin_user_service,
    get_admin_dashboard_service,
)
from backend.middleware.admin_auth import get_current_admin, require_role, ROLE_ADMIN, ROLE_STAFF
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    AdminDashboardResponse,
    SystemConfigResponse,
    ConfigResponse,
    UserListResponse,
    OrderListResponse,
    OperationLogResponse,
    RecycleBinResponse,
    MessageSendResponse,
    SendMessageRequest,
    MessageListAdminResponse,
    CreateAdminRequest,
    UpdateAdminRequest,
    AdminCreateRefundRequest,
    AdminCreateOrderRequest,
    UpdateOrderStatusRequest,
    ReceiveOplogsRequest,
)
from backend.domain.advancement.service import AdvancementService
from backend.domain.admin.services.account_service import AdminAccountService
from backend.domain.admin.services.borrow_service import AdminBorrowService
from backend.domain.admin.services.dashboard_service import AdminDashboardService
from backend.domain.admin.services.message_service import AdminMessageService
from backend.domain.admin.services.order_service import AdminOrderService
from backend.domain.admin.services.refund_service import AdminRefundService
from backend.domain.admin.services.system_service import AdminSystemService
from backend.domain.admin.services.user_service import AdminUserService

router = APIRouter(prefix="/admin/api", tags=["系统管理"])


# ==================== 操作日志接收 ====================

@router.post("/oplogs")
def receive_oplogs(
    data: ReceiveOplogsRequest,
    admin=Depends(get_current_admin),
    service: AdminSystemService = Depends(get_admin_system_service),
):
    """接收前端操作日志 — 写入数据库"""
    for log in data.logs:
        ts = log.get("ts", "")
        page = log.get("page", "")
        category = log.get("category", "")
        action = log.get("action", "")
        detail = log.get("detail", "")

        content = f"[{ts}] {action} {detail}"
        service.write_operation_log(
            admin_id=admin.id,
            module=page or category,
            operation=action,
            content=content,
        )

    return {"ok": True}


# ==================== 仪表盘 ====================

@router.get("/dashboard", response_model=AdminDashboardResponse)
def get_dashboard(
    service: AdminDashboardService = Depends(get_admin_dashboard_service),
    admin=Depends(get_current_admin),
):
    """管理仪表盘"""
    return service.get_dashboard()


# ==================== 系统配置 ====================

@router.get("/config", response_model=ConfigResponse)
def get_all_configs(
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(get_current_admin),
):
    """获取所有配置项"""
    return service.get_all_configs()


@router.get("/config/{key}", response_model=SystemConfigResponse | None)
def get_config(
    key: str,
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(get_current_admin),
):
    """获取单个配置项"""
    return service.get_config(key)


@router.put("/config/{key}", response_model=SystemConfigResponse)
def set_config(
    key: str,
    value: str,
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    """更新配置项"""
    return service.set_config(key, value)


@router.post("/config/init", response_model=AdminActionResponse)
def init_defaults(
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    """初始化默认配置"""
    service.init_defaults()
    return {"message": "默认配置已初始化"}


# ==================== 用户管理 ====================

@router.get("/users", response_model=UserListResponse)
def list_users(
    search: str = None,
    page: int = 1,
    page_size: int = 20,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(get_current_admin),
):
    """分页查询用户+孩子列表"""
    return service.list_users_with_children(search, page, page_size)


@router.get("/users/{user_id}", response_model=AdminActionResponse)
def get_user_detail(
    user_id: int,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(get_current_admin),
):
    """用户详情"""
    return service.get_user_detail(user_id)


@router.get("/children/search", response_model=list)
def search_children(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    service: AdminBorrowService = Depends(get_admin_borrow_service),
    admin=Depends(get_current_admin),
):
    """搜索孩子"""
    return service.search_children(keyword)


# ==================== 订单管理 ====================

@router.get("/orders", response_model=OrderListResponse)
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_type: int = Query(None),
    pay_status: int = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    search: str = Query(None),
    service: AdminOrderService = Depends(get_admin_order_service),
    admin=Depends(get_current_admin),
):
    """分页查询订单列表"""
    return service.list_orders_paginated(page, page_size, order_type, pay_status, date_from, date_to, search)


@router.get("/orders/{order_no}/refund", response_model=AdminActionResponse)
def get_order_refund(
    order_no: str,
    service: AdminOrderService = Depends(get_admin_order_service),
    admin=Depends(get_current_admin),
):
    """按订单号查询退款申请"""
    return service.get_order_refund(order_no)


@router.post("/orders/{order_no}/refund", response_model=AdminActionResponse, status_code=201)
def admin_create_refund(
    order_no: str,
    data: AdminCreateRefundRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    service: AdminRefundService = Depends(get_admin_refund_service),
):
    """管理员代客发起退款申请"""
    return service.create_refund(order_no, data.model_dump())


@router.post("/orders", response_model=AdminActionResponse, status_code=201)
def admin_create_order(
    data: AdminCreateOrderRequest,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    service: AdminOrderService = Depends(get_admin_order_service),
):
    """管理员代客创建订单"""
    return service.create_order(data.model_dump())


@router.put("/orders/{order_no}/status", response_model=AdminActionResponse)
def update_order_status(
    order_no: str,
    data: UpdateOrderStatusRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    service: AdminOrderService = Depends(get_admin_order_service),
):
    """更新订单状态"""
    return service.update_order_status(order_no, data.model_dump())


@router.delete("/orders/{order_no}", response_model=AdminActionResponse)
def delete_order(
    order_no: str,
    admin=Depends(require_role(ROLE_ADMIN)),
    service: AdminOrderService = Depends(get_admin_order_service),
):
    """删除订单（软删除）"""
    return service.delete_order(order_no)


# ==================== 提交审核 ====================

@router.get("/submissions", response_model=list)
def list_submissions_legacy(
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(get_current_admin),
):
    """获取待审核提交列表（兼容旧路径）"""
    return service.list_pending_submissions()


# ==================== 操作日志 ====================

@router.get("/operation-logs", response_model=OperationLogResponse)
def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module: str = Query(None),
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(get_current_admin),
):
    """获取操作日志"""
    return service.list_operation_logs(page, page_size, module)


# ==================== 回收站 ====================

@router.get("/recycle-bin", response_model=RecycleBinResponse)
def list_recycle_bin(
    module: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(get_current_admin),
):
    """获取回收站列表"""
    return service.list_recycle_bin(module, page, page_size)


@router.post("/recycle-bin/{module}/{item_id}/restore", response_model=AdminActionResponse)
def restore_item(
    module: str,
    item_id: int,
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    """恢复软删除的数据"""
    return service.restore_item(module, item_id)


@router.delete("/recycle-bin/{module}/{item_id}", response_model=AdminActionResponse)
def permanent_delete_item(
    module: str,
    item_id: int,
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_role(ROLE_ADMIN)),
):
    """永久删除数据（不可恢复）"""
    return service.permanent_delete_item(module, item_id)


# ==================== 消息管理 ====================

@router.post("/messages/send", response_model=MessageSendResponse)
def send_message(
    data: SendMessageRequest,
    service: AdminMessageService = Depends(get_admin_message_service),
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
):
    """运营消息推送"""
    return service.send_message(
        title=data.title,
        content=data.content,
        msg_type=data.msg_type,
        priority=data.priority,
        target=data.target,
        target_user_id=data.target_user_id,
    )


@router.get("/messages", response_model=MessageListAdminResponse)
def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: AdminMessageService = Depends(get_admin_message_service),
    admin=Depends(get_current_admin),
):
    """管理端查看已发送消息列表"""
    return service.list_messages(page, page_size)


@router.delete("/messages/{message_id}", response_model=AdminActionResponse)
def delete_message(
    message_id: int,
    admin=Depends(require_role(ROLE_ADMIN, ROLE_STAFF)),
    service: AdminMessageService = Depends(get_admin_message_service),
):
    """删除消息"""
    return service.delete_message(message_id)


# ==================== 管理员管理 ====================

@router.get("/admins", response_model=AdminActionResponse)
def list_admins(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """获取管理员列表 — 带分页"""
    return service.list_admins(page, page_size)


@router.post("/admins", response_model=AdminActionResponse, status_code=201)
def create_admin(
    data: CreateAdminRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """创建管理员"""
    return service.create_admin(data, admin.id)


@router.get("/admins/{admin_id}", response_model=AdminActionResponse)
def get_admin(
    admin_id: int,
    admin=Depends(get_current_admin),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """获取单个管理员信息"""
    return service.get_admin(admin_id)


@router.put("/admins/{admin_id}", response_model=SuccessResponse)
def update_admin(
    admin_id: int,
    data: UpdateAdminRequest,
    admin=Depends(require_role(ROLE_ADMIN)),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """更新管理员"""
    return service.update_admin(admin_id, data, admin.id)


@router.delete("/admins/{admin_id}", response_model=SuccessResponse)
def delete_admin(
    admin_id: int,
    admin=Depends(require_role(ROLE_ADMIN)),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """删除管理员"""
    return service.delete_admin(admin_id, admin.id)


# ==================== 证书管理别名（兼容 ARCHITECTURE.md 文档规范） ====================

@router.get("/certificates", response_model=AdminActionResponse)
def list_certificates_alias(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取证书列表 — `/admin/api/advancement/certificates` 的别名"""
    service = AdvancementService(db)
    data = service.list_certificates(page, page_size)
    return {"success": True, "message": "获取证书列表成功", **data}
