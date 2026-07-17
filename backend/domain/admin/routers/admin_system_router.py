# backend/domain/admin/routers/admin_system_router.py
"""系统管理路由"""

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.common.dependencies import (
    get_db,
    get_admin_system_service,
    get_admin_account_service,
    get_admin_message_service,
    get_admin_order_service,
    get_admin_refund_service,
    get_admin_user_service,
    get_admin_dashboard_service,
)
from backend.common.exceptions import ForbiddenError
from backend.middleware.admin_rbac import require_perm
from backend.domain.admin.admin_schemas import (
    SuccessResponse,
    AdminActionResponse,
    AdminDashboardResponse,
    SystemConfigResponse,
    ConfigResponse,
    UserListResponse,
    UpdateUserRequest,
    AdminCreateUserRequest,
    OrderListResponse,
    OperationLogResponse,
    RecycleBinResponse,
    MessageSendResponse,
    SendMessageRequest,
    MessageListAdminResponse,
    CreateAdminRequest,
    UpdateAdminRequest,
    ChangePasswordRequest,
    AdminCreateRefundRequest,
    AdminCreateOrderRequest,
    AdminOfflineCreateOrderRequest,
    UpdateOrderStatusRequest,
    ReceiveOplogsRequest,
)
from backend.domain.child.schemas import ChildCreate, ChildUpdate
from backend.domain.advancement.service import AdvancementService
from backend.domain.admin.services.account_service import AdminAccountService
from backend.domain.admin.services.dashboard_service import AdminDashboardService
from backend.domain.admin.services.message_service import AdminMessageService
from backend.domain.admin.services.order_service import AdminOrderService
from backend.domain.admin.services.refund_service import AdminRefundService
from backend.domain.admin.services.system_service import AdminSystemService
from backend.domain.admin.services.user_service import AdminUserService

router = APIRouter(prefix="/admin/api", tags=["系统管理"])


# ==================== 操作日志接收 ====================

@router.post("/oplogs", response_model=AdminActionResponse)
def receive_oplogs(
    data: ReceiveOplogsRequest,
    admin=Depends(require_perm("log.list")),
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
    admin=Depends(require_perm("dashboard.view")),
):
    """管理仪表盘"""
    return service.get_dashboard()


# ==================== 系统配置 ====================

@router.get("/config", response_model=ConfigResponse)
def get_all_configs(
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_perm("config.view")),
):
    """获取所有配置项"""
    return service.get_all_configs()


@router.get("/config/{key}", response_model=SystemConfigResponse | None)
def get_config(
    key: str,
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_perm("config.view")),
):
    """获取单个配置项"""
    return service.get_config(key)


@router.put("/config/{key}", response_model=SystemConfigResponse)
def set_config(
    key: str,
    value: str,
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_perm("config.edit")),
):
    """更新配置项"""
    result = service.set_config(key, value)
    service.write_operation_log(
        admin_id=admin.id,
        module="config",
        operation="update",
        content=f"更新配置: {key}={value}",
    )
    return result


@router.post("/config/init", response_model=AdminActionResponse)
def init_defaults(
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_perm("config.edit")),
):
    """初始化默认配置"""
    service.init_defaults()
    service.write_operation_log(
        admin_id=admin.id,
        module="config",
        operation="init",
        content="初始化默认配置",
    )
    return {"message": "默认配置已初始化"}


# ==================== 用户管理 ====================

@router.get("/users/export", response_model=AdminActionResponse)
def export_users_csv(
    search: str = None,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("user.export")),
):
    """导出用户列表为 CSV"""
    result = service.list_users_with_children(search, page=1, page_size=99999)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["家长姓名", "手机号", "孩子名", "年龄", "年级", "身份", "场馆", "注册时间"])
    status_map = {0: "体验课", 1: "观察期", 2: "正式会员", 3: "已过期", 4: "已退出"}
    for u in result.get("items", []):
        children = u.get("children", [])
        if children:
            for c in children:
                writer.writerow([
                    u.get("parent_name", ""),
                    u.get("phone", ""),
                    c.get("name", ""),
                    c.get("age", ""),
                    c.get("grade", ""),
                    status_map.get(c.get("status"), ""),
                    c.get("venue_name", ""),
                    u.get("create_time", ""),
                ])
        else:
            writer.writerow([
                u.get("parent_name", ""),
                u.get("phone", ""),
                "", "", "", "", "",
                u.get("create_time", ""),
            ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


@router.get("/users", response_model=UserListResponse)
def list_users(
    search: str = None,
    page: int = 1,
    page_size: int = 20,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("user.list")),
):
    """分页查询用户+孩子列表"""
    return service.list_users_with_children(search, page, page_size)


@router.post("/users", response_model=AdminActionResponse)
def create_user(
    data: AdminCreateUserRequest,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("user.create")),
):
    """管理员创建用户（家长+可选孩子）"""
    result = service.admin_create_user(data)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="user",
        operation="create",
        content=f"创建用户: {data.phone}",
    )
    return result


@router.get("/users/{user_id}", response_model=AdminActionResponse)
def get_user_detail(
    user_id: int,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("user.view")),
):
    """用户详情"""
    return service.get_user_detail(user_id)


@router.put("/users/{user_id}", response_model=AdminActionResponse)
def update_user(
    user_id: int,
    data: UpdateUserRequest,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("user.edit")),
):
    """更新用户/家长信息及主孩子状态"""
    result = service.update_user(user_id, data)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="user",
        operation="update",
        content=f"更新用户: {user_id}",
    )
    return result


@router.get("/children", response_model=list)
def list_children(
    limit: int = Query(500, ge=1, le=1000),
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("child.list")),
    db: Session = Depends(get_db),
):
    """获取孩子列表 — 借还等场景下拉框"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    return service.list_children(limit, child_ids=child_ids)


@router.get("/children/search", response_model=list)
def search_children(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("child.view")),
    db: Session = Depends(get_db),
):
    """搜索孩子（按姓名/英文名/家长手机号）"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    return service.search_children(keyword, child_ids=child_ids)


@router.get("/children/{child_id}", response_model=AdminActionResponse)
def get_child_detail(
    child_id: int,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("child.view")),
    db: Session = Depends(get_db),
):
    """孩子详情"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    if child_ids is not None and child_id not in child_ids:
        raise ForbiddenError("无权操作该孩子或无访问权限")
    return service.get_child_detail(child_id)


@router.post("/users/{user_id}/children", response_model=AdminActionResponse)
def admin_create_child(
    user_id: int,
    data: ChildCreate,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("child.create")),
):
    """管理员为孩子创建档案"""
    result = service.admin_create_child(user_id, data)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="child",
        operation="create",
        content=f"创建孩子: {data.name}",
    )
    return result


@router.put("/children/{child_id}", response_model=AdminActionResponse)
def admin_update_child(
    child_id: int,
    data: ChildUpdate,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("child.edit")),
    db: Session = Depends(get_db),
):
    """管理员更新孩子信息"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    if child_ids is not None and child_id not in child_ids:
        raise ForbiddenError("无权操作该孩子或无访问权限")
    result = service.admin_update_child(child_id, data)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="child",
        operation="update",
        content=f"更新孩子: {child_id}",
    )
    return result


@router.delete("/children/{child_id}", response_model=AdminActionResponse)
def admin_delete_child(
    child_id: int,
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("child.delete")),
    db: Session = Depends(get_db),
):
    """管理员删除孩子（软删除）"""
    child_ids = AdminAccountService(db).get_scoped_child_ids(admin)
    if child_ids is not None and child_id not in child_ids:
        raise ForbiddenError("无权操作该孩子或无访问权限")
    result = service.admin_delete_child(child_id)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="child",
        operation="delete",
        content=f"删除孩子: {child_id}",
    )
    return result


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
    admin=Depends(require_perm("order.list")),
):
    """分页查询订单列表"""
    return service.list_orders_paginated(page, page_size, order_type, pay_status, date_from, date_to, search)


@router.get("/orders/{order_no}/refund", response_model=AdminActionResponse)
def get_order_refund(
    order_no: str,
    service: AdminOrderService = Depends(get_admin_order_service),
    admin=Depends(require_perm("order.view")),
):
    """按订单号查询退款申请"""
    return service.get_order_refund(order_no)


@router.post("/orders/{order_no}/refund", response_model=AdminActionResponse, status_code=201)
def admin_create_refund(
    order_no: str,
    data: AdminCreateRefundRequest,
    admin=Depends(require_perm("order.refund")),
    service: AdminRefundService = Depends(get_admin_refund_service),
):
    """管理员代客发起退款申请（超级管理员自动审核通过）"""
    result = service.create_refund(order_no, data.model_dump(), admin)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="order",
        operation="refund",
        content=f"发起退款: {order_no}",
    )
    return result


@router.post("/orders", response_model=AdminActionResponse, status_code=201)
def admin_create_order(
    data: AdminCreateOrderRequest,
    admin=Depends(require_perm("order.create")),
    service: AdminOrderService = Depends(get_admin_order_service),
):
    """管理员代客创建订单"""
    result = service.create_order(data.model_dump())
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="order",
        operation="create",
        content="创建订单",
    )
    return result


@router.post("/orders/offline", response_model=AdminActionResponse, status_code=201)
def admin_create_offline_order(
    data: AdminOfflineCreateOrderRequest,
    admin=Depends(require_perm("order.create")),
    service: AdminOrderService = Depends(get_admin_order_service),
):
    """管理员线下创建用户+订单（兜底场景）"""
    result = service.create_offline_order(data.model_dump())
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="order",
        operation="create",
        content="线下创建用户+订单",
    )
    return result


@router.put("/orders/{order_no}/status", response_model=AdminActionResponse)
def update_order_status(
    order_no: str,
    data: UpdateOrderStatusRequest,
    admin=Depends(require_perm("order.edit")),
    service: AdminOrderService = Depends(get_admin_order_service),
):
    """更新订单状态"""
    result = service.update_order_status(order_no, data.model_dump())
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="order",
        operation="update_status",
        content=f"更新订单状态: {order_no}",
    )
    return result


@router.delete("/orders/{order_no}", response_model=AdminActionResponse)
def delete_order(
    order_no: str,
    admin=Depends(require_perm("order.delete")),
    service: AdminOrderService = Depends(get_admin_order_service),
):
    """删除订单（软删除）"""
    result = service.delete_order(order_no)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="order",
        operation="delete",
        content=f"删除订单: {order_no}",
    )
    return result


# ==================== 提交审核 ====================

@router.get("/submissions", response_model=list)
def list_submissions_legacy(
    service: AdminUserService = Depends(get_admin_user_service),
    admin=Depends(require_perm("submission.list")),
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
    admin=Depends(require_perm("log.list")),
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
    admin=Depends(require_perm("recycle.list")),
):
    """获取回收站列表"""
    return service.list_recycle_bin(module, page, page_size)


@router.post("/recycle-bin/{module}/{item_id}/restore", response_model=AdminActionResponse)
def restore_item(
    module: str,
    item_id: int,
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_perm("recycle.restore")),
):
    """恢复软删除的数据"""
    result = service.restore_item(module, item_id)
    service.write_operation_log(
        admin_id=admin.id,
        module="recycle_bin",
        operation="restore",
        content=f"恢复 {module}: {item_id}",
    )
    return result


@router.delete("/recycle-bin/{module}/{item_id}", response_model=AdminActionResponse)
def permanent_delete_item(
    module: str,
    item_id: int,
    service: AdminSystemService = Depends(get_admin_system_service),
    admin=Depends(require_perm("recycle.delete")),
):
    """永久删除数据（不可恢复）"""
    result = service.permanent_delete_item(module, item_id)
    service.write_operation_log(
        admin_id=admin.id,
        module="recycle_bin",
        operation="permanent_delete",
        content=f"永久删除 {module}: {item_id}",
    )
    return result


# ==================== 消息管理 ====================

@router.post("/messages/send", response_model=MessageSendResponse)
def send_message(
    data: SendMessageRequest,
    service: AdminMessageService = Depends(get_admin_message_service),
    admin=Depends(require_perm("message.send")),
):
    """运营消息推送"""
    result = service.send_message(
        title=data.title,
        content=data.content,
        msg_type=data.msg_type,
        priority=data.priority,
        target=data.target,
        target_user_id=data.target_user_id,
        target_teacher_id=data.target_teacher_id,
        target_role_groups=data.target_role_groups,
    )
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="message",
        operation="send",
        content=f"发送消息: {data.title}",
    )
    return result


@router.get("/messages", response_model=MessageListAdminResponse)
def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: AdminMessageService = Depends(get_admin_message_service),
    admin=Depends(require_perm("message.list")),
):
    """管理端查看已发送消息列表"""
    return service.list_messages(page, page_size)


@router.delete("/messages/{message_id}", response_model=AdminActionResponse)
def delete_message(
    message_id: int,
    admin=Depends(require_perm("message.delete")),
    service: AdminMessageService = Depends(get_admin_message_service),
):
    """删除消息"""
    result = service.delete_message(message_id)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="message",
        operation="delete",
        content=f"删除消息: {message_id}",
    )
    return result


# ==================== 管理员管理 ====================

@router.get("/admins", response_model=AdminActionResponse)
def list_admins(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("admin.list")),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """获取管理员列表 — 带分页"""
    return service.list_admins(page, page_size)


@router.post("/admins", response_model=AdminActionResponse, status_code=201)
def create_admin(
    data: CreateAdminRequest,
    admin=Depends(require_perm("admin.create")),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """创建管理员"""
    result = service.create_admin(data, admin.id)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="admin",
        operation="create",
        content=f"创建管理员: {data.username}",
    )
    return result


@router.get("/admins/{admin_id}", response_model=AdminActionResponse)
def get_admin(
    admin_id: int,
    admin=Depends(require_perm("admin.list")),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """获取单个管理员信息"""
    return service.get_admin(admin_id)


@router.put("/admins/{admin_id}", response_model=SuccessResponse)
def update_admin(
    admin_id: int,
    data: UpdateAdminRequest,
    admin=Depends(require_perm("admin.edit")),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """更新管理员"""
    result = service.update_admin(admin_id, data, admin.id)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="admin",
        operation="update",
        content=f"更新管理员: {admin_id}",
    )
    return result


@router.put("/admins/{admin_id}/password", response_model=SuccessResponse)
def change_password(
    admin_id: int,
    data: ChangePasswordRequest,
    admin=Depends(require_perm("admin.password")),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """修改管理员密码 — 校验旧密码"""
    result = service.change_password(admin_id, data.old_password, data.new_password, admin.id)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="admin",
        operation="change_password",
        content=f"修改管理员密码: {admin_id}",
    )
    return result


@router.delete("/admins/{admin_id}", response_model=SuccessResponse)
def delete_admin(
    admin_id: int,
    admin=Depends(require_perm("admin.delete")),
    service: AdminAccountService = Depends(get_admin_account_service),
):
    """删除管理员"""
    result = service.delete_admin(admin_id, admin.id)
    system_service = AdminSystemService(service.db)
    system_service.write_operation_log(
        admin_id=admin.id,
        module="admin",
        operation="delete",
        content=f"删除管理员: {admin_id}",
    )
    return result


# ==================== 证书管理别名（兼容 ARCHITECTURE.md 文档规范） ====================

@router.get("/certificates", response_model=AdminActionResponse)
def list_certificates_alias(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_perm("certificate.list")),
    db: Session = Depends(get_db),
):
    """获取证书列表 — `/admin/api/advancement/certificates` 的别名"""
    service = AdvancementService(db)
    data = service.list_certificates(page, page_size)
    return {"success": True, "message": "获取证书列表成功", **data}
