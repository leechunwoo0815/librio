# backend/tasks/jobs/report_generation.py
"""报告生成定时任务"""

import logging

logger = logging.getLogger(__name__)


def generate_weekly():
    """
    [What] 生成周报
    [Why] 每周一自动生成上周阅读报告
    [How] 查询每个child上周的阅读数据，生成报告
    """
    from backend.database import get_session
    from backend.domain.child.models import Child
    from backend.domain.report.service import ReportService

    db = get_session()()
    try:
        children = (
            db.query(Child)
            .filter(
                Child.status.in_([Child.STATUS_OBSERVATION, Child.STATUS_OFFICIAL]),
                Child.is_deleted == 0,
            )
            .all()
        )

        svc = ReportService(db)
        count = 0
        for child in children:
            try:
                report = svc.generate_weekly_report(child.id)
                logger.info(
                    f"WEEKLY_REPORT: child={child.id}, "
                    f"minutes={report['total_minutes']}, books={report['books_finished']}"
                )
                count += 1
            except Exception as e:
                logger.error(f"Weekly report failed for child {child.id}: {e}")

        db.commit()
        logger.info(f"Weekly reports generated: {count}")
    except Exception as e:
        db.rollback()
        logger.error(f"Weekly report generation failed: {e}", exc_info=True)
    finally:
        db.close()


def generate_monthly():
    """
    [What] 生成月报
    [Why] 每月1日自动生成上月阅读报告
    [How] 查询每个child上月的阅读数据
    """
    from backend.database import get_session
    from backend.domain.child.models import Child
    from backend.domain.report.service import ReportService

    db = get_session()()
    try:
        children = (
            db.query(Child)
            .filter(
                Child.status.in_([Child.STATUS_OBSERVATION, Child.STATUS_OFFICIAL]),
                Child.is_deleted == 0,
            )
            .all()
        )

        svc = ReportService(db)
        count = 0
        for child in children:
            try:
                report = svc.generate_monthly_report(child.id)
                logger.info(
                    f"MONTHLY_REPORT: child={child.id}, minutes={report['total_minutes']}, "
                    f"books={report['books_finished']}, checkin_rate={report['checkin_rate']}%"
                )
                count += 1
            except Exception as e:
                logger.error(f"Monthly report failed for child {child.id}: {e}")

        db.commit()
        logger.info(f"Monthly reports generated: {count}")
    except Exception as e:
        db.rollback()
        logger.error(f"Monthly report generation failed: {e}", exc_info=True)
    finally:
        db.close()
