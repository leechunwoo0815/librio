"""F-021 终审闭环：调度任务入口生成 trace_id（TASK_START/TASK_END 可关联，任务内层日志同 ID）"""

import logging
from contextlib import contextmanager

from backend.common import distributed_lock as dl

JOB_LOGGER = logging.getLogger("backend.common.distributed_lock")


def test_distributed_task_logs_trace_id_start_end(caplog, monkeypatch):
    calls = []

    @contextmanager
    def fake_redis_lock(lock_key, timeout=300):
        yield True

    monkeypatch.setattr(dl, "redis_lock", fake_redis_lock)

    @dl.distributed_lock("job:f021", timeout=10)
    def sample_job():
        calls.append(1)
        JOB_LOGGER.info("JOB_INNER first")

    with caplog.at_level(logging.INFO):
        sample_job()

    assert calls == [1]
    starts = [
        r.getMessage()
        for r in caplog.records
        if r.getMessage().startswith("TASK_START")
    ]
    ends = [
        r.getMessage() for r in caplog.records if r.getMessage().startswith("TASK_END")
    ]
    assert len(starts) == 1
    assert len(ends) == 1
    start_trace = starts[0].split("trace_id=")[1].split(" ")[0]
    end_trace = ends[0].split("trace_id=")[1].split(" ")[0]
    assert start_trace == end_trace
    assert len(start_trace) == 12

    inner = [r for r in caplog.records if r.getMessage().startswith("JOB_INNER")]
    assert len(inner) == 1
    # F-021 终审同类：任务内层日志必须携带同一 trace_id（撤 contextvar set 必红）
    assert getattr(inner[0], "trace_id", None) == start_trace, (
        "任务内层日志未带 trace_id——任务日志无法与 TASK_START/END 关联"
    )
