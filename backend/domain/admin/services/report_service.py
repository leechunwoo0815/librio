# backend/domain/admin/services/report_service.py
"""管理端报告/阅读统计 Service — 从 AdminService 拆分出来的独立域服务。"""

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.domain.child.models import Child


class AdminReportService:
    """观察期报告与阅读数据统计/趋势。"""

    def __init__(self, db: Session):
        self.db = db

    def list_observation_reports(
        self,
        page: int = 20,
        page_size: int = 20,
        keyword: str = None,
        child_ids: list[int] | None = None,
    ) -> dict:
        """获取观察报告列表 — 带分页"""
        from backend.domain.report.models import ObservationReport

        query = self.db.query(ObservationReport).filter(
            ObservationReport.is_deleted == 0
        )

        if child_ids is not None:
            if not child_ids:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_next": False,
                }
            query = query.filter(ObservationReport.child_id.in_(child_ids))

        # 如果有关键词，先搜索匹配的 child
        if keyword:
            matched_children = (
                self.db.query(Child.id)
                .filter(
                    Child.name.ilike(f"%{keyword}%"),
                    Child.is_deleted == 0,
                )
                .all()
            )
            child_ids = [c.id for c in matched_children]
            if child_ids:
                query = query.filter(ObservationReport.child_id.in_(child_ids))
            else:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_next": False,
                }

        total = query.count()
        reports = (
            query.order_by(ObservationReport.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # 批量查询 child，避免 N+1
        report_child_ids = list(set(r.child_id for r in reports if r.child_id))
        children = {}
        if report_child_ids:
            for c in (
                self.db.query(Child)
                .filter(Child.id.in_(report_child_ids), Child.is_deleted == 0)
                .all()
            ):
                children[c.id] = c.name

        result = []
        for r in reports:
            result.append(
                {
                    "id": r.id,
                    "child_id": r.child_id,
                    "child_name": children.get(r.child_id),
                    "start_date": r.start_date.isoformat() if r.start_date else None,
                    "end_date": r.end_date.isoformat() if r.end_date else None,
                    "total_reading_minutes": r.total_reading_minutes or 0,
                    "total_books_read": r.total_books_read or 0,
                    "total_words_read": r.total_words_read or 0,
                    "avg_daily_minutes": r.avg_daily_minutes or 0,
                    "level_at_start": r.level_at_start,
                    "level_at_end": r.level_at_end,
                    "teacher_comment": r.teacher_comment,
                    "recommendation": r.recommendation,
                    "status": r.status,
                    "create_time": r.create_time.isoformat() if r.create_time else None,
                }
            )

        return {
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": page * page_size < total,
        }

    def get_reading_stats(self, start_date: str = None, end_date: str = None) -> dict:
        """获取阅读统计数据 — 使用 SQL 聚合"""
        from backend.domain.reading.models import ReadingSession, CheckIn

        # 默认最近 30 天
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        # SQL 聚合查询
        stats = (
            self.db.query(
                func.count(ReadingSession.id).label("total_sessions"),
                func.sum(ReadingSession.duration_seconds).label("total_seconds"),
                func.count(func.distinct(ReadingSession.child_id)).label(
                    "active_children"
                ),
            )
            .filter(
                ReadingSession.is_deleted == 0,
                ReadingSession.create_time >= start_date,
                ReadingSession.create_time <= end_date,
            )
            .first()
        )

        # 今日在线人数
        online_today = (
            self.db.query(func.count(func.distinct(ReadingSession.child_id)))
            .filter(
                ReadingSession.is_deleted == 0,
                func.date(ReadingSession.create_time) == func.current_date(),
            )
            .scalar()
        )

        # 总儿童数
        total_children = self.db.query(Child).filter(Child.is_deleted == 0).count()

        total_seconds = int(stats.total_seconds or 0)
        total_minutes = total_seconds // 60
        total_hours = round(total_minutes / 60, 1)

        # 打卡率
        today_str = datetime.now().strftime("%Y-%m-%d")
        checkin_today = (
            self.db.query(func.count(func.distinct(CheckIn.child_id)))
            .filter(
                CheckIn.check_date == today_str,
                CheckIn.is_deleted == 0,
            )
            .scalar()
            or 0
        )
        checkin_rate = round(checkin_today / max(total_children, 1) * 100, 1)

        # 阅读排行榜 Top 10
        top_readers_raw = (
            self.db.query(
                ReadingSession.child_id,
                func.sum(ReadingSession.duration_seconds).label("total_seconds"),
            )
            .filter(
                ReadingSession.is_deleted == 0,
                ReadingSession.create_time >= start_date,
                ReadingSession.create_time <= end_date,
            )
            .group_by(ReadingSession.child_id)
            .order_by(func.sum(ReadingSession.duration_seconds).desc())
            .limit(10)
            .all()
        )

        top_child_ids = [r.child_id for r in top_readers_raw]
        top_children = {}
        if top_child_ids:
            for c in self.db.query(Child).filter(Child.id.in_(top_child_ids)).all():
                top_children[c.id] = c.name

        top_readers = [
            {
                "child_name": top_children.get(r.child_id, "未知"),
                "minutes": int(r.total_seconds or 0) // 60,
            }
            for r in top_readers_raw
        ]

        return {
            "stats": {
                "total_sessions": stats.total_sessions or 0,
                "total_minutes": total_minutes,
                "total_hours": total_hours,
                "active_children": stats.active_children or 0,
                "online_today": online_today or 0,
                "total_children": total_children,
                "avg_minutes": round(
                    total_minutes / max(stats.active_children or 1, 1), 1
                ),
                "checkin_rate": checkin_rate,
            },
            "top_readers": top_readers,
        }

    def get_reading_trends(self, start_date: str = None, end_date: str = None) -> dict:
        """获取阅读趋势数据 — 使用 SQL 聚合"""
        from backend.domain.reading.models import ReadingSession

        # 默认最近 30 天
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        # SQL 聚合查询每日数据
        daily_stats = (
            self.db.query(
                func.date(ReadingSession.create_time).label("date"),
                func.count(ReadingSession.id).label("sessions"),
                func.sum(ReadingSession.duration_seconds).label("seconds"),
                func.count(func.distinct(ReadingSession.child_id)).label("children"),
            )
            .filter(
                ReadingSession.is_deleted == 0,
                ReadingSession.create_time >= start_date,
                ReadingSession.create_time <= end_date,
            )
            .group_by(func.date(ReadingSession.create_time))
            .order_by(func.date(ReadingSession.create_time))
            .all()
        )

        return {
            "trends": [
                {
                    "date": str(d.date),
                    "sessions": d.sessions or 0,
                    "minutes": int(d.seconds or 0) // 60,
                    "children": d.children or 0,
                    "online": d.children or 0,
                }
                for d in daily_stats
            ]
        }
