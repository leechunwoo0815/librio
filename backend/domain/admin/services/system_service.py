# backend/domain/admin/services/system_service.py
"""管理端系统 Service — 从 AdminService 拆分出来的独立域服务。"""

from sqlalchemy.orm import Session

from backend.common.config_service import ConfigService
from backend.common.exceptions import NotFoundError, ValidationError
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
        """获取所有配置（含默认值）"""
        self._load_config_cache()
        items = {}
        for key, (default_val, _type, desc) in SystemConfig.DEFAULTS.items():
            items[key] = {
                "value": self._instance_config_cache.get(key, default_val),
                "type": _type,
                "description": desc,
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
            q = q.filter(OperationLog.module.like(f"%{module}%"))
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
        }

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

        for name, Model in models_to_check.items():
            q = self.db.query(Model).filter(Model.is_deleted == 1)
            items = q.limit(50).all()
            for item in items:
                results.append(
                    {
                        "id": item.id,
                        "module": name,
                        "name": getattr(item, "title", None)
                        or getattr(item, "name", None)
                        or str(item.id),
                        "deleted_at": item.update_time.isoformat()
                        if hasattr(item, "update_time") and item.update_time
                        else None,
                    }
                )

        return {"items": results[:page_size], "total": len(results)}

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

        self.db.delete(item)
        self.db.commit()
        return {"success": True, "message": f"已永久删除 {module} #{item_id}"}
