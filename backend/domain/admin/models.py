# backend/domain/admin/models.py
"""管理域模型 — 管理员(RBAC) + 操作日志 + 系统配置 + 老师/排班 + 场馆"""

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel
from backend.common.types import AdminRole
from backend.domain.admin.rbac_models import Role


class Admin(BaseModel):
    """管理员模型 — RBAC: ADMIN/STAFF/TEACHER"""

    __tablename__ = "admin"
    __table_args__ = {"extend_existing": True}

    STATUS_ACTIVE = 1
    STATUS_DISABLED = 0

    username = Column(String(50), nullable=False, unique=True, comment="用户名")
    password_hash = Column(String(128), nullable=False, comment="密码哈希")
    name = Column(String(50), nullable=False, comment="姓名")
    role = Column(
        SmallInteger,
        default=AdminRole.STAFF,
        comment="@deprecated 角色: 0=超级管理员 1=运营 2=老师，请使用 admin_role_id",
    )
    venue_id = Column(BigInteger, nullable=True, comment="所属场馆ID")
    phone = Column(String(11), nullable=True, comment="手机号")
    status = Column(SmallInteger, default=STATUS_ACTIVE, comment="1=启用 0=禁用")
    token_generation = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Token版本号，改密码/禁用时+1使旧Token失效",
    )

    # RBAC 扩展字段（Phase 1）
    admin_role_id = Column(
        BigInteger, nullable=True, comment="RBAC角色ID (引用 role.id)"
    )
    teacher_id = Column(
        BigInteger, nullable=True, comment="关联教师ID (role=teacher时必填)"
    )

    # ── RBAC 权限方法 ──

    role_ref = relationship(
        Role,
        foreign_keys=[admin_role_id],
        primaryjoin="Admin.admin_role_id == Role.id",
        lazy="joined",
    )


class OperationLog(BaseModel):
    """操作日志"""

    __tablename__ = "operation_log"
    __table_args__ = {"extend_existing": True}

    admin_id = Column(BigInteger, nullable=True, comment="操作管理员ID")
    module = Column(String(50), nullable=True, comment="操作模块")
    operation = Column(String(50), nullable=True, comment="操作类型")
    content = Column(String(500), nullable=True, comment="操作内容")
    ip = Column(String(50), nullable=True, comment="IP地址")


class SystemConfig(BaseModel):
    """系统配置 — 管理员可动态修改的参数"""

    __tablename__ = "system_config"
    __table_args__ = {"extend_existing": True}

    config_key = Column(
        String(50), nullable=False, unique=True, index=True, comment="配置键"
    )
    config_value = Column(String(255), nullable=False, comment="配置值")
    config_type = Column(
        String(20), default="string", comment="值类型: int/string/bool/json"
    )
    description = Column(String(255), nullable=True, comment="配置说明")

    # 默认配置项
    DEFAULTS = {
        # ── 未付费体验用户 ──
        "trial_pages": (
            "20",
            "int",
            "未付费体验用户试读页数（仅status=0体验用户，C7决策）",
        ),
        "vocab_lookup_limit": (
            "30",
            "int",
            "未付费体验用户查词次数上限（仅status=0体验用户，C3决策）",
        ),
        "enable_trial_reading": ("true", "bool", "是否开启未付费用户试读功能"),
        "enable_vocab_lookup": ("true", "bool", "是否开启查词功能"),
        # ── 会员管理 ──
        "observation_days": ("45", "int", "观察期天数（A3决策：45天）"),
        "member_days": ("365", "int", "正式会员有效期（天）"),
        "member_grace_days": ("15", "int", "会员到期缓冲天数"),
        "renewal_discount": ("0.9", "string", "缓冲期内续费折扣"),
        "multi_child_discount": ("0.9", "string", "第2孩起折扣"),
        "refund_free_days": (
            "7",
            "int",
            "退款无理由全退天数（A4决策：前N天全退，第N+1天起按天扣）",
        ),
        "upgrade_deduct_enabled": (
            "true",
            "bool",
            "观察期中途升级按剩余天数抵扣会员费（A6决策）",
        ),
        "deposit_pending_expire_minutes": (
            "30",
            "int",
            "押金支付单超时未回调的复位分钟数（F39：废弃 PENDING 复位 UNPAID 允许重缴）",
        ),
        # ── 借阅规则 ──
        "borrow_limit": ("10", "int", "每个孩子最大同时借阅数（B14决策：10本）"),
        "borrow_period_days": ("21", "int", "单次借阅期限（天）"),
        "due_remind_days": (
            "5,3,1,0",
            "string",
            "到期前提醒天数列表（逗号分隔，0=当天）",
        ),
        "overdue_fine_per_day": ("1", "int", "逾期服务费（元/天，B7决策措辞）"),
        "overdue_grace_days": (
            "3",
            "int",
            "逾期宽限期天数（B7/B8决策：前N天免罚、音频不锁，第N+1天起算）",
        ),
        "overdue_fine_cap_ratio": (
            "0.5",
            "string",
            "单本逾期服务费上限比例（B7决策：≤图书定价×比例）",
        ),
        "first_overdue_free": (
            "true",
            "bool",
            "每孩子首次逾期免罚（B7决策：培养习惯优先）",
        ),
        "lost_book_fine_multiplier": ("1.5", "string", "丢书罚款倍率（图书定价×倍率）"),
        "lost_search_days": (
            "7",
            "int",
            "丢失寻找期天数（B10：期内找回免赔）",
        ),
        "damage_dual_review": (
            "true",
            "bool",
            "损坏定责双人复核（B9：重度/丢失财务效应需第二管理员复核）",
        ),
        # ── 押金 ──
        "deposit_amount": ("1200", "int", "押金金额（元）"),
        "deposit_refund_auto_approve": (
            "true",
            "bool",
            "押金退款满足条件自动审核通过（E1决策）",
        ),
        "deposit_partial_refund_amount": (
            "600",
            "int",
            "押金减半退还金额（A2：借满N本无逾期可退，元）",
        ),
        "deposit_partial_refund_books": (
            "10",
            "int",
            "押金减半退还所需已归还本数（A2）",
        ),
        "refund_auto_approve_max": (
            "500",
            "int",
            "退款自动审核通过金额上限（E1决策：≤N元自动通过，元）",
        ),
        "review_sla_hours": (
            "24",
            "int",
            "人工审核 SLA 小时数（E2：超 N 小时未审升级提醒超管，范围1-168）",
        ),
        "parent_course_required": (
            "false",
            "bool",
            "观察期报名是否强制要求完成亲子课（A1决策：双轨制默认false）",
        ),
        # ── 预约 ──
        "reservation_expire_hours": ("72", "int", "预约过期时间（小时）"),
        "reservation_remind_hours": (
            "24",
            "int",
            "预约取书提醒提前量（B4：到期前N小时未取提醒）",
        ),
        # ── 晋级规则 ──
        "default_required_books": (
            "5",
            "int",
            "每级默认需读完书数（预留，当前读取 Level.required_books 字段）",
        ),
        "quiz_pass_rate": ("0.80", "string", "测验最低通过率（每本书5题答对4题=80%）"),
        "quiz_total_questions": ("5", "int", "每本书测验默认题数"),
        "quiz_pass_count": (
            "5",
            "int",
            "每级需通过测验的最少书数（默认=required_books，全部通过）",
        ),
        "require_teacher_review": ("false", "bool", "晋级是否需要老师审核"),
        "submission_auto_approve": (
            "true",
            "bool",
            "提交达标自动通过（D4：测验通过且阅读时长达标）",
        ),
        "submission_min_minutes": (
            "10",
            "int",
            "提交自动通过所需最低阅读分钟数（D4）",
        ),
        "quiz_cooldown_minutes": (
            "10",
            "int",
            "测验未通过后重考冷却时间（分钟，范围5-1440，C2决策：10分钟）",
        ),
        "quiz_low_level_max_sort": (
            "6",
            "int",
            "低龄级别上限 sort_order（C2：A-F 级=1-6 走低龄测验规则）",
        ),
        "quiz_low_level_questions": (
            "3",
            "int",
            "低龄测验题数（C2：A-F 级 3 题）",
        ),
        "quiz_low_level_pass_count": (
            "2",
            "int",
            "低龄测验通过所需答对题数（C2：3 题对 2）",
        ),
        # ── 打卡规则 ──
        "checkin_min_minutes": ("10", "int", "打卡最低阅读分钟数"),
        "checkin_min_vocab": ("5", "int", "打卡最低生词数"),
        "daily_checkin_limit": (
            "4",
            "int",
            "每天最多打卡次数（C1：每类型各1次，共4种）",
        ),
        # ── 书架 ──
        "bookshelf_limit": ("100", "int", "想读清单上限（C4：默认100本，0=无限制）"),
        # ── 场馆信息 ──
        "venue_name": (
            "人广馆",
            "string",
            "场馆名称（预留，当前读取 Venue 表 name 字段）",
        ),
        "venue_address": (
            "上海市黄浦区",
            "string",
            "场馆地址（预留，当前读取 Venue 表 address 字段）",
        ),
        "service_wechat": (
            "",
            "string",
            "微信客服号（G2：错误提示人工兜底入口）",
        ),
        # ── 订单 ──
        "order_expire_minutes": ("30", "int", "订单未支付自动关闭时间（分钟）"),
        "amount_override_alert_ratio": (
            "0.5",
            "string",
            "代客下单/线下建单金额覆盖偏离系统价告警阈值（F11：|实收-系统|/系统 > 阈值即告警）",
        ),
        "price_parent_course": ("99", "string", "亲子课价格（元）"),
        "price_observation": ("500", "string", "观察期价格（元）"),
        "price_official_member": ("5400", "string", "正式会员年费（元）"),
        "price_quarterly": ("1350", "string", "季度会员价格（元）"),
        "price_semi_annual": ("2700", "string", "半年会员价格（元）"),
        "original_price_parent_course": (
            "199",
            "int",
            "亲子课原价/划线价（元，展示用）",
        ),
        "original_price_official_member": (
            "6000",
            "int",
            "正式会员原价/划线价（元，展示用）",
        ),
        # ── 管理员 ──
        "admin_token_expire_hours": ("8", "int", "管理员 Token 有效期（小时）"),
        # ── 活动 ──
        "activity_cancel_hours": ("24", "int", "活动开始前多少小时内不可取消"),
        # ── 通知 ──
        "member_expire_remind_days": (
            "30,15,7,3,2,1,0",
            "string",
            "会员到期提醒天数列表",
        ),
        "observation_remind_days": ("7,5,3,2,1,0", "string", "观察期到期提醒天数列表"),
        # ── 数据保留（H5 隐私合规，单位见各键说明）──
        "data_retention_finance_years": (
            "5",
            "int",
            "财务类数据保留年数（H5：订单/押金/退款/罚款/借阅/损坏/权益转让）",
        ),
        "data_retention_behavior_years": (
            "2",
            "int",
            "行为类数据保留年数（H5：EXITED 孩子的学习数据，退出后计）",
        ),
        "data_retention_message_years": (
            "1",
            "int",
            "消息类数据保留年数（H5：系统消息/老师消息）",
        ),
        "voice_retention_months": (
            "6",
            "int",
            "语音录音保留月数（H5：到期物理删除含音频文件）",
        ),
    }


class Teacher(BaseModel):
    """老师模型"""

    __tablename__ = "teacher"
    __table_args__ = {"extend_existing": True}

    name = Column(String(50), nullable=False, comment="老师姓名")
    english_name = Column(String(50), nullable=True, comment="英文名")
    phone = Column(String(11), nullable=False, comment="手机号")
    venue_id = Column(BigInteger, nullable=False, comment="所属场馆ID")
    avatar = Column(String(255), nullable=True, comment="头像URL")
    introduction = Column(Text, nullable=True, comment="老师简介")
    expertise = Column(String(255), nullable=True, comment="擅长领域")
    title = Column(String(50), nullable=True, comment="职称")
    status = Column(
        String(20),
        default="online",
        comment="在线状态: online=在线 offline=离线 leave=休假中",
    )

    schedules = relationship(
        "TeacherSchedule",
        back_populates="teacher",
        foreign_keys="TeacherSchedule.teacher_id",
    )

    def __repr__(self):
        return f"<Teacher(id={self.id}, name='{self.name}')>"


class TeacherSchedule(BaseModel):
    """老师排班表"""

    __tablename__ = "teacher_schedule"
    __table_args__ = {"extend_existing": True}

    teacher_id = Column(
        BigInteger,
        ForeignKey("teacher.id"),
        nullable=False,
        index=True,
        comment="老师ID",
    )
    weekday = Column(SmallInteger, nullable=False, comment="星期几: 1=周一 ... 7=周日")
    start_time = Column(String(10), nullable=False, comment="开始时间 HH:MM")
    end_time = Column(String(10), nullable=False, comment="结束时间 HH:MM")
    is_available = Column(SmallInteger, default=1, comment="0=不可用 1=可用")

    teacher = relationship(
        "Teacher", back_populates="schedules", foreign_keys=[teacher_id]
    )

    def __repr__(self):
        return f"<Schedule(teacher={self.teacher_id}, weekday={self.weekday}, {self.start_time}-{self.end_time})>"


class Venue(BaseModel):
    """场馆模型"""

    __tablename__ = "venue"
    __table_args__ = {"extend_existing": True}

    name = Column(String(100), nullable=False, comment="场馆名称")
    address = Column(String(255), nullable=True, comment="场馆地址")
    phone = Column(String(20), nullable=True, comment="联系电话")
    business_hours = Column(String(100), nullable=True, comment="营业时间")
    status = Column(
        String(20),
        default="active",
        comment="运营状态: active=运营中 maintenance=维护中 inactive=已关闭",
    )
    capacity = Column(BigInteger, default=0, comment="容量/工位数")

    def __repr__(self):
        return f"<Venue(id={self.id}, name='{self.name}')>"
