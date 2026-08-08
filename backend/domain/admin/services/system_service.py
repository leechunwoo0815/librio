# backend/domain/admin/services/system_service.py
"""管理端系统 Service — 从 AdminService 拆分出来的独立域服务。"""

from sqlalchemy.orm import Session

from backend.common.config_service import ConfigService
from backend.common.exceptions import NotFoundError, ValidationError
from backend.common.sql_utils import escape_like
from backend.domain.admin.models import SystemConfig
from backend.domain.admin.repository import SystemConfigRepository
from backend.domain.admin.schemas import SystemConfigResponse


class AdminSystemService:
    """系统配置、操作日志、回收站。"""

    def __init__(self, db: Session):
        self.db = db
        self.config_repo = SystemConfigRepository(db)
        self._instance_config_cache: dict = {}

    # ==================== 系统配置 ====================

    def get_config(self, key: str) -> SystemConfigResponse | None:
        config = self.config_repo.get_by_key(key)
        return SystemConfigResponse.model_validate(config) if config else None

    def set_config(self, key: str, value: str) -> SystemConfigResponse:
        config = self.config_repo.get_by_key(key)
        if config:
            config.config_value = value
            self.config_repo.update(config)
        else:
            config = SystemConfig(config_key=key, config_value=value)
            self.config_repo.create(config)
        self.db.commit()
        self._instance_config_cache.pop(key, None)
        # 同步清除 ConfigService 缓存
        ConfigService.invalidate(key)
        return SystemConfigResponse.model_validate(config)

    def get_config_value(self, key: str) -> str | None:
        """获取配置值，优先从缓存读取"""
        if key in self._instance_config_cache:
            return self._instance_config_cache[key]
        config = self.config_repo.get_by_key(key)
        if config:
            self._instance_config_cache[key] = config.config_value
            return config.config_value
        default = SystemConfig.DEFAULTS.get(key)
        return default[0] if default else None

    def get_config_int(self, key: str) -> int:
        val = self.get_config_value(key)
        return int(val) if val else 0

    def get_config_bool(self, key: str) -> bool:
        val = self.get_config_value(key)
        return val and val.lower() in ("true", "1", "yes")

    def get_all_configs(self) -> dict:
        """获取所有配置（含默认值 + E3 管控级别）"""
        from backend.domain.admin.config_levels import level_of

        self._load_config_cache()
        items = {}
        for key, (default_val, _type, desc) in SystemConfig.DEFAULTS.items():
            items[key] = {
                "value": self._instance_config_cache.get(key, default_val),
                "type": _type,
                "description": desc,
                "level": level_of(key),
            }
        return {"items": items, "total": len(items)}

    def init_defaults(self) -> None:
        """初始化默认配置到数据库（首次部署时调用）"""
        for key, (value, _type, desc) in SystemConfig.DEFAULTS.items():
            existing = self.config_repo.get_by_key(key)
            if not existing:
                self.config_repo.create(
                    SystemConfig(
                        config_key=key,
                        config_value=value,
                        config_type=_type,
                        description=desc,
                    )
                )
        self.db.commit()
        self._load_config_cache()

    def _load_config_cache(self) -> None:
        """从数据库加载全部配置到缓存"""
        self._instance_config_cache = {}
        configs = self.config_repo.get_all_configs()
        for row in configs:
            self._instance_config_cache[row.config_key] = row.config_value

    # ==================== 操作日志 ====================

    def write_operation_log(
        self,
        admin_id: int | None,
        module: str,
        operation: str,
        content: str = "",
        ip: str | None = None,
    ) -> None:
        """写入操作日志到数据库"""
        from backend.domain.admin.models import OperationLog

        log = OperationLog(
            admin_id=admin_id,
            module=module,
            operation=operation,
            content=content,
            ip=ip,
        )
        self.db.add(log)
        self.db.commit()

    def list_operation_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        module: str = None,
    ) -> dict:
        """获取操作日志"""
        from backend.domain.admin.models import OperationLog

        q = self.db.query(OperationLog).filter(OperationLog.is_deleted == 0)
        if module:
            q = q.filter(
                OperationLog.module.like(f"%{escape_like(module)}%", escape="\\")
            )
        total = q.count()
        logs = (
            q.order_by(OperationLog.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [
                {
                    "id": entry.id,
                    "admin_id": entry.admin_id,
                    "module": entry.module,
                    "operation": entry.operation,
                    "content": entry.content,
                    "ip": entry.ip,
                    "create_time": entry.create_time.isoformat()
                    if entry.create_time
                    else None,
                }
                for entry in logs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,  # F-102
        }

    # ==================== 死信事件（F-029） ====================

    def list_dead_letters(
        self,
        page: int = 1,
        page_size: int = 20,
        resolved: bool | None = None,
    ) -> dict:
        """死信列表（运维可观测：原只写不读，无任何查询入口）"""
        from backend.common.dead_letter_model import DeadLetterEvent

        q = self.db.query(DeadLetterEvent)
        if resolved is not None:
            q = (
                q.filter(DeadLetterEvent.resolved_at.isnot(None))
                if resolved
                else q.filter(DeadLetterEvent.resolved_at.is_(None))
            )
        total = q.count()
        entries = (
            q.order_by(DeadLetterEvent.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "handler_name": e.handler_name,
                    "error_message": e.error_message,
                    "retry_count": e.retry_count or 0,
                    "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
                    "create_time": e.create_time.isoformat() if e.create_time else None,
                }
                for e in entries
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
        }

    def replay_dead_letter(self, dead_letter_id: int) -> dict:
        """重放死信：恢复事件 → 复用已注册 handler 独立事务执行 → 成功标记 resolved_at

        失败时不改原记录（人工可再次重放）；handler 内部失败由重放方异常暴露。
        """
        import dataclasses
        import json
        from datetime import datetime

        from backend.common.dead_letter_model import DeadLetterEvent
        from backend.common import events

        entry = (
            self.db.query(DeadLetterEvent)
            .filter(DeadLetterEvent.id == dead_letter_id)
            .first()
        )
        if not entry:
            raise NotFoundError("死信记录不存在")

        event_class = None
        for cls in vars(events).values():
            if (
                dataclasses.is_dataclass(cls)
                and isinstance(cls, type)
                and issubclass(cls, events.DomainEvent)
                and getattr(cls, "event_type", "") == entry.event_type
            ):
                event_class = cls
                break
        if event_class is None:
            raise ValidationError(f"未知事件类型: {entry.event_type}，无法重放")

        data = json.loads(entry.event_data or "{}")
        field_names = {f.name for f in dataclasses.fields(event_class)}
        event = event_class(**{k: v for k, v in data.items() if k in field_names})

        handlers = events.event_bus._handlers.get(event.event_type, [])
        if not handlers:
            raise ValidationError(f"事件 {event.event_type} 无已注册处理器，无法重放")

        from backend.database import get_session

        session = get_session()()
        try:
            for handler in handlers:
                handler(event, session)
            session.commit()
        except Exception as e:
            session.rollback()
            raise ValidationError(f"重放失败（原死信保留，可稍后重试）: {e}") from e
        finally:
            session.close()

        entry.resolved_at = datetime.now()
        entry.retry_count = (entry.retry_count or 0) + 1
        self.db.commit()
        return {
            "success": True,
            "message": f"死信 {entry.id} 重放成功",
            "event_type": entry.event_type,
        }

    def delete_dead_letter(self, dead_letter_id: int) -> dict:
        """删除单条死信（运维清扫）"""
        from backend.common.dead_letter_model import DeadLetterEvent

        entry = (
            self.db.query(DeadLetterEvent)
            .filter(DeadLetterEvent.id == dead_letter_id)
            .first()
        )
        if not entry:
            raise NotFoundError("死信记录不存在")
        self.db.delete(entry)
        self.db.commit()
        return {"success": True, "message": f"死信 {dead_letter_id} 已删除"}

    def cleanup_resolved_dead_letters(self) -> dict:
        """批量清扫已解决死信（resolved_at 非空，只进不出现象的出口）"""
        from backend.common.dead_letter_model import DeadLetterEvent

        rows = (
            self.db.query(DeadLetterEvent)
            .filter(DeadLetterEvent.resolved_at.isnot(None))
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return {"success": True, "message": f"已清理 {rows} 条已解决死信"}

    # ==================== 回收站（PC-001） ====================

    def list_recycle_bin(
        self,
        module: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取回收站列表（软删除的数据）"""
        from backend.domain.book.models import Book
        from backend.domain.activity.models import Activity
        from backend.domain.admin.models import Teacher, Venue

        model_map = {
            "book": Book,
            "activity": Activity,
            "teacher": Teacher,
            "venue": Venue,
        }
        results = []

        models_to_check = (
            {module: model_map[module]} if module and module in model_map else model_map
        )

        # F-104：跨模块合并后统一分页（原每模块各取 page_size → 首页 4×20 条、
        # total=本页条数、翻页语义错误）。回收站为低频小数据，全量收集可接受。
        all_items = []
        for name, Model in models_to_check.items():
            q = (
                self.db.query(Model)
                .filter(Model.is_deleted == 1)
                .order_by(Model.update_time.desc())
            )
            for item in q.all():
                all_items.append(
                    {
                        "id": item.id,
                        "module": name,
                        "name": getattr(item, "title", None)
                        or getattr(item, "name", None)
                        or str(item.id),
                        "deleted_at": item.update_time.isoformat()
                        if hasattr(item, "update_time") and item.update_time
                        else None,
                        "deleted_time": item.update_time,
                    }
                )

        all_items.sort(key=lambda x: x["deleted_time"], reverse=True)
        total = len(all_items)
        start = (page - 1) * page_size
        results = [
            {k: v for k, v in item.items() if k != "deleted_time"}
            for item in all_items[start : start + page_size]
        ]
        return {
            "items": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (page * page_size) < total,
        }

    def restore_item(self, module: str, item_id: int) -> dict:
        """恢复软删除的数据"""
        from backend.domain.book.models import Book
        from backend.domain.activity.models import Activity
        from backend.domain.admin.models import Teacher, Venue

        model_map = {
            "book": Book,
            "activity": Activity,
            "teacher": Teacher,
            "venue": Venue,
        }
        Model = model_map.get(module)
        if not Model:
            raise ValidationError(f"不支持的模块: {module}")

        item = (
            self.db.query(Model)
            .filter(Model.id == item_id, Model.is_deleted == 1)
            .first()
        )
        if not item:
            raise NotFoundError("记录不存在或未被删除")

        item.is_deleted = 0
        self.db.commit()
        return {"success": True, "message": f"已恢复 {module} #{item_id}"}

    def permanent_delete_item(self, module: str, item_id: int) -> dict:
        """永久删除数据（不可恢复）"""
        from backend.domain.book.models import Book
        from backend.domain.activity.models import Activity
        from backend.domain.admin.models import Teacher, Venue

        model_map = {
            "book": Book,
            "activity": Activity,
            "teacher": Teacher,
            "venue": Venue,
        }
        Model = model_map.get(module)
        if not Model:
            raise ValidationError(f"不支持的模块: {module}")

        item = (
            self.db.query(Model)
            .filter(Model.id == item_id, Model.is_deleted == 1)
            .first()
        )
        if not item:
            raise NotFoundError("记录不存在或未被删除")

        # F-103：物理删除前检查下游关联（FK 环境会 500，无 FK 环境留孤儿数据——
        # 统一改为明确拒绝并提示先处理关联）
        from backend.common.exceptions import ConflictError

        if module == "book":
            from backend.domain.book.models import BookCopy
            from backend.domain.advancement.models import QuestionBank

            copy_count = (
                self.db.query(BookCopy)
                .filter(BookCopy.book_id == item_id)
                .count()
            )
            question_count = (
                self.db.query(QuestionBank)
                .filter(QuestionBank.book_id == item_id)
                .count()
            )
            if copy_count > 0 or question_count > 0:
                raise ConflictError(
                    f"该图书仍有 {copy_count} 个副本、{question_count} 道题目关联，"
                    "请先永久删除副本/题目后再删除图书"
                )

        self.db.delete(item)
        self.db.commit()
        return {"success": True, "message": f"已永久删除 {module} #{item_id}"}
