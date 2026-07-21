# backend/domain/admin/admin_schemas.py
"""管理端统一 Schema — 合并自 schemas.py + admin_schemas.py

架构约束：
  - 所有管理端 Schema 集中在此文件
  - 禁止在其他文件定义管理端 Schema
  - 所有 Request Schema 必须使用 model_config = ConfigDict(extra="forbid")
  - 字段类型必须与数据库模型 Column 定义完全一致
"""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator


# ==================== 通用响应 ====================


class SuccessResponse(BaseModel):
    """通用成功响应"""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    message: str | None = None


class AdminActionResponse(BaseModel):
    """管理端操作响应 — 允许额外字段（sent_count, report_id 等）

    当 Service 返回其他 Pydantic Response 对象时，
    通过 model_validator(before) 自动转换为 dict，保留所有字段。
    """

    model_config = ConfigDict(extra="allow")

    success: bool = True
    message: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _handle_basemodel(cls, data):
        """将 BaseModel 实例转为 dict，避免 Pydantic V2 model_type 验证错误"""
        if isinstance(data, BaseModel):
            return data.model_dump()
        return data


class PaginatedResponse(BaseModel):
    """分页响应"""

    model_config = ConfigDict(extra="forbid")

    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False


class AdminDashboardResponse(BaseModel):
    """管理后台仪表盘"""

    model_config = ConfigDict(extra="forbid")

    total_users: int = 0
    total_children: int = 0
    total_orders: int = 0
    total_revenue: float = 0
    daily_active_users: int = 0
    new_users_this_week: int = 0
    active_borrows: int = 0
    quiz_pass_rate: float = 0.0
    today_reading_minutes: int = 0
    today_new_words: int = 0
    today_voice_count: int = 0


class ConfigResponse(BaseModel):
    """配置响应"""

    model_config = ConfigDict(extra="forbid")

    items: dict = {}
    total: int = 0


class UpdateUserRequest(BaseModel):
    """更新用户/家长信息请求"""

    model_config = ConfigDict(extra="forbid")

    parent_name: str | None = Field(None, min_length=1, max_length=50)
    phone: str | None = Field(None, min_length=1, max_length=11)
    child_status: int | None = Field(
        None,
        ge=0,
        le=4,
        description="主孩子状态: 0=体验课 1=观察期 2=正式会员 3=已过期 4=已退出",
    )


class UserListResponse(BaseModel):
    """用户列表响应"""

    model_config = ConfigDict(extra="forbid")

    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False


class OrderListResponse(BaseModel):
    """订单列表响应"""

    model_config = ConfigDict(extra="forbid")

    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False


class OperationLogResponse(BaseModel):
    """操作日志响应"""

    model_config = ConfigDict(extra="forbid")

    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False


class RecycleBinResponse(BaseModel):
    """回收站响应"""

    model_config = ConfigDict(extra="forbid")

    items: list = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_next: bool = False


class MessageSendResponse(BaseModel):
    """消息发送响应"""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    sent_count: int = 0


class ReadingStatsResponse(BaseModel):
    """阅读统计响应"""

    model_config = ConfigDict(extra="allow")

    stats: dict = {}


class ReadingTrendsResponse(BaseModel):
    """阅读趋势响应"""

    model_config = ConfigDict(extra="allow")

    trends: list = []


# ==================== 场馆管理 ====================


class VenueResponse(BaseModel):
    """场馆响应"""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    business_hours: str | None = None
    status: str | None = None
    capacity: int | None = None
    create_time: datetime | None = None


class CreateVenueRequest(BaseModel):
    """创建场馆请求"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    address: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=20)
    business_hours: str | None = Field(None, max_length=100)
    status: str | None = Field("active", max_length=20)
    capacity: int | None = Field(0, ge=0)


class UpdateVenueRequest(BaseModel):
    """更新场馆请求"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    address: str | None = Field(None, min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=20)
    business_hours: str | None = Field(None, max_length=100)
    status: str | None = Field(None, max_length=20)
    capacity: int | None = Field(None, ge=0)


# ==================== 老师管理 ====================


class TeacherResponse(BaseModel):
    """老师响应"""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: int
    name: str | None = None
    english_name: str | None = None
    phone: str | None = None
    venue_id: int | None = None
    title: str | None = None
    introduction: str | None = None
    expertise: str | None = None
    status: str | None = None
    student_count: int | None = None
    venue_name: str | None = None
    admin_id: int | None = None
    admin_role_name: str | None = None
    create_time: datetime | None = None


class CreateTeacherRequest(BaseModel):
    """创建老师请求"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=50)
    english_name: str | None = Field(None, max_length=50)
    phone: str = Field(..., min_length=1, max_length=11)
    venue_id: int
    title: str | None = Field(None, max_length=50)
    introduction: str | None = None
    expertise: str | None = None
    status: str | None = Field("online", max_length=20)


class UpdateTeacherRequest(BaseModel):
    """更新老师请求"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=50)
    english_name: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, min_length=1, max_length=11)
    venue_id: int | None = None
    title: str | None = Field(None, max_length=50)
    introduction: str | None = None
    expertise: str | None = None
    status: str | None = Field(None, max_length=20)


class AssignTeacherRequest(BaseModel):
    """分配老师请求"""

    model_config = ConfigDict(extra="forbid")

    child_id: int
    teacher_id: int


class TeacherScheduleResponse(BaseModel):
    """排班响应"""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    teacher_id: int
    weekday: int
    start_time: str
    end_time: str
    is_available: int = 1


class CreateScheduleRequest(BaseModel):
    """创建排班请求"""

    model_config = ConfigDict(extra="forbid")

    teacher_id: int
    weekday: int = Field(..., ge=1, le=7)
    start_time: str = Field(..., min_length=1)
    end_time: str = Field(..., min_length=1)


# ==================== 系统配置 ====================


class SystemConfigResponse(BaseModel):
    """系统配置响应"""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    config_key: str
    config_value: str | None = None
    description: str | None = None
    update_time: datetime | None = None


class ConfigItemResponse(BaseModel):
    """配置项响应（含类型和说明）"""

    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    type: str = "string"
    description: str | None = None


class ConfigListResponse(BaseModel):
    """所有配置响应"""

    model_config = ConfigDict(extra="forbid")

    pass  # Dynamic dict, returned as-is


# ==================== 消息管理 ====================


class SendMessageRequest(BaseModel):
    """运营消息发送请求"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    msg_type: int = Field(
        default=1,
        ge=1,
        le=5,
        description="1=系统通知 2=活动通知 3=借阅通知 4=老师消息 5=阅读提醒",
    )
    priority: int = Field(default=0, ge=0, le=2, description="0=低 1=中 2=高")
    target: str = Field(
        default="all",
        description="all=全部用户, user=指定用户, teacher=指定老师/全部老师",
    )
    target_user_id: int | None = Field(
        None, description="指定用户ID，target=user时必填"
    )
    target_teacher_id: int | None = Field(
        None, description="指定老师ID，target=teacher时可选"
    )
    target_role_groups: list[str] | None = Field(
        None,
        description="目标用户分组: trial/observation/member, target=all时可选, 默认全部",
    )

    @field_validator("target_role_groups")
    @classmethod
    def validate_target_role_groups(cls, v):
        if v is not None:
            allowed = {"trial", "observation", "member"}
            for g in v:
                if g not in allowed:
                    raise ValueError(
                        f"无效用户分组 '{g}'，允许值: {', '.join(sorted(allowed))}"
                    )
        return v


class MessageRecord(BaseModel):
    """消息记录响应"""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    user_id: int | None = None
    title: str
    content: str
    msg_type: int
    priority: int
    is_read: int = 0
    create_time: datetime
    target_groups: list[str] | None = None


class MessageListAdminResponse(BaseModel):
    """管理端消息列表响应"""

    model_config = ConfigDict(extra="forbid")

    items: list[MessageRecord]
    total: int
    page: int
    page_size: int


# ==================== 活动管理 ====================


class CreateActivityRequest(BaseModel):
    """创建活动请求"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    type: int = Field(..., ge=1, le=6)
    is_free: bool = True
    price: Decimal = Field(Decimal("0"), ge=0)
    start_time: str
    end_time: str
    location: str | None = None
    max_participants: int = Field(20, ge=1)
    description: str | None = None


class UpdateActivityRequest(BaseModel):
    """更新活动请求"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    type: int | None = Field(None, ge=1, le=6)
    is_free: bool | None = None
    price: Decimal | None = Field(None, ge=0)
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    venue: str | None = None
    max_participants: int | None = Field(None, ge=1)
    description: str | None = None
    status: int | None = Field(None, ge=0, le=5)


class BatchCheckinRequest(BaseModel):
    """批量签到请求"""

    model_config = ConfigDict(extra="forbid")

    child_ids: list[int] = Field(..., min_length=1)


# ==================== 图书管理 ====================


class CreateBookRequest(BaseModel):
    """创建图书请求"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    isbn: str = Field(..., min_length=10, max_length=20)
    author: str = Field(..., max_length=100)
    publisher: str | None = Field(None, max_length=100)
    ar_value: float = Field(..., description="AR阅读等级")
    age_min: int = Field(..., ge=3, le=15)
    age_max: int = Field(..., ge=3, le=15)
    word_count: int | None = None
    summary: str | None = None
    cover: str | None = None
    total_pages: int | None = None


class UpdateBookRequest(BaseModel):
    """更新图书请求"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    isbn: str | None = Field(None, min_length=10, max_length=20)
    author: str | None = Field(None, max_length=100)
    publisher: str | None = Field(None, max_length=100)
    ar_value: float | None = None
    age_min: int | None = Field(None, ge=3, le=15)
    age_max: int | None = Field(None, ge=3, le=15)
    word_count: int | None = None
    summary: str | None = None
    cover: str | None = None
    total_pages: int | None = None
    is_published: int | None = None
    total_stock: int | None = Field(None, ge=0)
    available_stock: int | None = Field(None, ge=0)
    offline_available: int | None = Field(None, ge=0)


class BulkImportBookItem(BaseModel):
    """批量导入图书项"""

    model_config = ConfigDict(extra="forbid")

    isbn: str = Field(..., min_length=10, max_length=20)
    title: str = ""
    author: str = ""
    ar_value: float | None = None
    age_min: int = 3
    age_max: int = 15
    word_count: int = 0


class CreateBookCopyRequest(BaseModel):
    """创建图书副本请求（支持扫码枪故障时手动输入条码）"""

    model_config = ConfigDict(extra="forbid")

    barcode: str | None = Field(
        None, min_length=1, max_length=50, description="副本条码，为空时系统自动生成"
    )
    location: str | None = Field(None, max_length=50, description="存放位置")
    condition_note: str | None = Field(None, max_length=255, description="入库状况备注")


class SaveBookPageRequest(BaseModel):
    """保存图书页面内容请求"""

    model_config = ConfigDict(extra="forbid")

    text_content: str | None = Field(None, description="页面文本内容")
    image_url: str | None = Field(None, max_length=255, description="页面图片URL")
    audio_url: str | None = Field(None, max_length=255, description="页面音频URL")


# ==================== 借阅管理 ====================


class BorrowBookRequest(BaseModel):
    """借书请求"""

    model_config = ConfigDict(extra="forbid")

    child_id: int
    book_id: int
    book_copy_id: int | None = None
    operator_id: int | None = None


class ReturnBookRequest(BaseModel):
    """还书请求"""

    model_config = ConfigDict(extra="forbid")

    borrow_record_id: int


# ==================== 押金管理 ====================


class RequestRefundRequest(BaseModel):
    """申请退款请求"""

    model_config = ConfigDict(extra="forbid")

    child_id: int


class AdminPayDepositRequest(BaseModel):
    """管理员代缴押金请求"""

    model_config = ConfigDict(extra="forbid")

    child_id: int


# ==================== 预约管理 ====================


class FulfillReservationRequest(BaseModel):
    """完成预约请求"""

    model_config = ConfigDict(extra="forbid")

    reservation_id: int
    child_id: int


class AdminCreateReservationRequest(BaseModel):
    """管理员创建预约请求"""

    model_config = ConfigDict(extra="forbid")

    child_id: int
    book_id: int


# ==================== 订单管理 ====================


class AdminCreateRefundRequest(BaseModel):
    """管理员代客退款请求"""

    model_config = ConfigDict(extra="forbid")

    reason: str = "管理员代发起退款"
    used_days: int = 0


class AdminCreateOrderRequest(BaseModel):
    """管理员代客创建订单请求"""

    model_config = ConfigDict(extra="forbid")

    child_id: int
    order_type: int
    remark: str = ""
    amount: Decimal | None = Field(
        None, gt=0, decimal_places=2, description="实收金额（已支付时必填）"
    )
    pay_type: int | None = Field(
        None, ge=1, le=6, description="付款方式（已支付时必填）"
    )


class UpdateOrderStatusRequest(BaseModel):
    """更新订单状态请求"""

    model_config = ConfigDict(extra="forbid")

    pay_status: int | None = None


class AdminOfflineCreateOrderRequest(BaseModel):
    """管理员线下创建用户+订单请求"""

    model_config = ConfigDict(extra="forbid")

    parent_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=11, max_length=11)
    child_name: str = Field(..., min_length=1, max_length=50)
    child_age: int = Field(..., ge=3, le=15)
    child_grade: str = Field(..., max_length=20)
    venue_id: int | None = None
    order_type: int = Field(..., ge=1, le=5)
    amount: Decimal | None = Field(
        None, gt=0, decimal_places=2, description="实收金额（已支付时必填）"
    )
    pay_type: int | None = Field(
        None, ge=1, le=6, description="付款方式（已支付时必填）"
    )
    remark: str = ""


# ==================== 报告管理 ====================


class AddObservationCommentRequest(BaseModel):
    """添加观察期评语请求"""

    model_config = ConfigDict(extra="forbid")

    comment: str


class ReceiveOplogsRequest(BaseModel):
    """接收前端操作日志请求"""

    model_config = ConfigDict(extra="forbid")

    logs: list = []


# ==================== 晋级管理 ====================


class CreateLevelRequest(BaseModel):
    """创建级别请求"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=50)
    code: str | None = Field(None, max_length=10, description="级别代码（如 A-Z）")
    badge_emoji: str | None = Field(None, max_length=20)
    sort_order: int | None = None
    required_books: int = Field(5, ge=1)
    pass_rate: float = Field(0.80, ge=0, le=1)
    max_borrow_count: int | None = None
    max_ar_level: float | None = None
    require_teacher_review: bool = False


class UpdateLevelRequest(BaseModel):
    """更新级别请求"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=50)
    code: str | None = Field(None, max_length=10, description="级别代码（如 A-Z）")
    badge_emoji: str | None = Field(None, max_length=20)
    sort_order: int | None = None
    required_books: int | None = Field(None, ge=1)
    pass_rate: float | None = Field(None, ge=0, le=1)
    max_borrow_count: int | None = None
    max_ar_level: float | None = None
    require_teacher_review: bool | None = None


class LevelResponse(BaseModel):
    """级别响应"""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str
    code: str | None = None
    badge_emoji: str | None = None
    sort_order: int | None = None
    required_books: int | None = None
    required_quiz_pass_rate: float | None = None
    require_teacher_review: bool | None = None
    max_borrow_count: int | None = None
    max_ar_level: float | None = None


class CreateAchievementRequest(BaseModel):
    """创建成就请求"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    type: int = Field(
        1, ge=1, le=4
    )  # 1=level_up, 2=book_milestone, 3=streak, 4=perfect_score
    badge_emoji: str | None = Field(None, max_length=20)
    trigger_condition: str | None = None


class UpdateAchievementRequest(BaseModel):
    """更新成就请求"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    type: int | None = Field(None, ge=1, le=4)
    badge_emoji: str | None = Field(None, max_length=20)
    trigger_condition: str | None = None


class AchievementResponse(BaseModel):
    """成就响应"""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str
    description: str | None = None
    type: int | None = None
    badge_emoji: str | None = None
    trigger_condition: str | None = None


class ReviewSubmissionRequest(BaseModel):
    """审核提交请求"""

    model_config = ConfigDict(extra="forbid")

    status: int = Field(..., ge=0, le=2)  # 0=待审核, 1=通过, 2=打回
    comment: str | None = None


class CreateQuestionRequest(BaseModel):
    """创建题目请求"""

    model_config = ConfigDict(extra="forbid")

    book_id: int
    question_text: str = Field(..., min_length=1)
    option_a: str = Field(..., min_length=1)
    option_b: str = Field(..., min_length=1)
    option_c: str | None = None
    option_d: str | None = None
    correct_answer: str = Field(..., pattern="^[ABCD]$")
    difficulty: int = Field(1, ge=1, le=5)
    explanation: str | None = None


class UpdateQuestionRequest(BaseModel):
    """更新题目请求"""

    model_config = ConfigDict(extra="forbid")

    question_text: str | None = None
    option_a: str | None = None
    option_b: str | None = None
    option_c: str | None = None
    option_d: str | None = None
    correct_answer: str | None = Field(None, pattern="^[ABCD]$")
    difficulty: int | None = Field(None, ge=1, le=5)
    explanation: str | None = None


class QuestionResponse(BaseModel):
    """题目响应"""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    book_id: int | None = None
    question_text: str
    option_a: str
    option_b: str
    option_c: str | None = None
    option_d: str | None = None
    correct_answer: str
    difficulty: int | None = None
    explanation: str | None = None


class BulkImportQuestionItem(BaseModel):
    """批量导入题目项"""

    model_config = ConfigDict(extra="forbid")

    isbn: str = Field(..., min_length=1)
    question_text: str = ""
    option_a: str = ""
    option_b: str = ""
    option_c: str | None = None
    option_d: str | None = None
    correct_answer: str = "A"
    difficulty: int = 1


# ==================== 退款管理 ====================


class AuditRefundRequest(BaseModel):
    """审核退款请求"""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., pattern="^(approve|reject)$")
    comment: str | None = None


class RefundResponse(BaseModel):
    """退款响应"""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    order_no: str | None = None
    child_id: int | None = None
    amount: Decimal | None = None
    status: int | None = None
    reason: str | None = None
    admin_comment: str | None = None
    create_time: str | None = None


# ==================== 管理员管理 ====================


class CreateAdminRequest(BaseModel):
    """创建管理员请求"""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    name: str | None = None
    role: int = Field(1, ge=0, le=2)
    admin_role_id: int | None = Field(None, description="RBAC角色ID，优先于 role")
    teacher_id: int | None = Field(None, description="关联教师ID (role=teacher时必填)")


class UpdateAdminRequest(BaseModel):
    """更新管理员请求"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    role: int | None = Field(None, ge=0, le=2)
    admin_role_id: int | None = Field(None, description="RBAC角色ID，优先于 role")
    teacher_id: int | None = Field(None, description="关联教师ID (role=teacher时必填)")
    status: int | None = Field(None, ge=0, le=1)
    phone: str | None = None
    password: str | None = Field(None, min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    model_config = ConfigDict(extra="forbid")

    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)


class AdminCreateUserRequest(BaseModel):
    """管理员创建用户请求"""

    model_config = ConfigDict(extra="forbid")

    parent_name: str = Field(..., min_length=1, max_length=50, description="家长姓名")
    phone: str = Field(..., min_length=11, max_length=11, description="手机号")
    password: str | None = Field(
        None,
        min_length=6,
        max_length=128,
        description="初始密码（可选，默认手机号后6位）",
    )
    # 同时创建孩子（可选）
    child_name: str | None = Field(None, max_length=50, description="孩子姓名")
    child_age: int | None = Field(None, ge=3, le=15, description="孩子年龄")
    child_grade: str | None = Field(None, max_length=20, description="孩子年级")
    venue_id: int | None = Field(None, description="所属场馆ID")
