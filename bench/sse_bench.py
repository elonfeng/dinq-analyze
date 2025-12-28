#!/usr/bin/env python3
"""
微基准：SSE streaming 事件吞吐（纯本地，不联网）。

用途：
- 观察 run_streaming_task 的纯协议/队列/序列化开销
- 用于回归对比（不建议作为严格门禁阈值）
"""

import argparse
import time

from server.utils.stream_task import run_streaming_task


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=2000)
    args = parser.parse_args()

    n = max(1, int(args.events))

    def task_fn(progress_cb, result_queue, cancel_event=None):
        for i in range(n):
            progress_cb({"event_type": "progress", "message": "tick", "progress": (i / n) * 100.0})
        result_queue.put(("success", {"ok": True, "events": n}))

    started = time.perf_counter()
    chunks = list(
        run_streaming_task(
            source="bench",
            task_fn=task_fn,
            timeout_seconds=30,
        )
    )
    elapsed = time.perf_counter() - started

    data_lines = [c for c in chunks if isinstance(c, str) and c.startswith("data: ")]
    print(f"events_requested={n}")
    print(f"sse_chunks={len(chunks)} data_lines={len(data_lines)} elapsed_seconds={elapsed:.4f}")
    if elapsed > 0:
        print(f"data_lines_per_second={len(data_lines)/elapsed:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
