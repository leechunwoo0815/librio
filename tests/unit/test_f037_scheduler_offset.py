"""F-037 回归：月报任务与周报任务错峰（周一恰逢 1 号时不得 8:00 并行）"""


def test_monthly_report_offset_from_weekly(monkeypatch):
    from backend.tasks import scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "scheduler", sched_mod.BackgroundScheduler())
    sched_mod.init_scheduler(None)

    jobs = {job.id: job.trigger for job in sched_mod.scheduler.get_jobs()}
    weekly = jobs["generate_weekly_reports"]
    monthly = jobs["generate_monthly_reports"]

    def _field(trigger, name):
        for f in trigger.fields:
            if f.name == name:
                return f
        return None

    weekly_hour = _field(weekly, "hour").expressions[0]
    monthly_hour = _field(monthly, "hour").expressions[0]
    weekly_minute = _field(weekly, "minute").expressions[0]
    monthly_minute = _field(monthly, "minute").expressions[0]

    assert weekly_hour.first == 8
    assert monthly_hour.first == 8
    # F-037：月报 8:15，与周报 8:00 错开 15 分钟
    assert monthly_minute.first == 15
    assert monthly_minute.first != weekly_minute.first
