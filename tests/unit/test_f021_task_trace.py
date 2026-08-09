"""F-021 终审闭环：调度任务入口生成 trace_id（TASK_START/TASK_END 可关联）"""

import logging
from contextlib import contextmanager

from backend.common import distributed_lock as dl


def test_distributed_task_logs_trace_id_start_end(caplog, monkeypatch):
    calls = []

    @contextmanager
    def fake_redis_lock(lock_key, timeout=300):
        yield True

    monkeypatch.setattr(dl, "redis_lock", fake_redis_lock)

    @dl.distributed_lock("job:f021", timeout=10)
    def sample_job():
        calls.append(1)

    with caplog.at_level(logging.INFO, logger="backend.common.distributed_lock"):
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
