import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch


class _FakeRedis:
    def __init__(self):
        self._kv = {}
        self._counters = {}
        self.xadd_ops = []
        self.set_ops = []

    def get(self, key):
        return self._kv.get(key)

    def incr(self, key):
        cur = int(self._counters.get(key) or 0) + 1
        self._counters[key] = cur
        self._kv[key] = str(cur).encode("utf-8")
        return cur

    def xadd(self, key, values, id=None, maxlen=None, approximate=None):  # noqa: ARG002
        self.xadd_ops.append((key, values, id))
        return id

    def set(self, key, value):
        self._kv[key] = value if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8")
        self.set_ops.append((key, self._kv[key]))
        return True


class _CaptureSession:
    def __init__(self):
        self.added = []
        self.updated = []

    def add(self, obj):
        self.added.append(obj)

    def query(self, *args, **kwargs):  # noqa: ARG002
        return self

    def filter(self, *args, **kwargs):  # noqa: ARG002
        return self

    def update(self, patch, synchronize_session=False):  # noqa: ARG002
        self.updated.append(patch)
        return 1


@contextmanager
def _fake_db_session(sess: _CaptureSession):
    yield sess


class TestEventStoreRealtimeBootstrap(unittest.TestCase):
    def test_bootstrap_job_started_writes_to_redis_only(self):
        fake = _FakeRedis()
        env = {
            "DINQ_REDIS_JOB_TTL_SECONDS": "0",  # disable expire touch to keep assertions focused
            "DINQ_REDIS_CLEANUP_ON_JOB_COMPLETED": "0",
        }
        with patch.dict(os.environ, env, clear=False), patch("server.tasks.event_store.get_redis_client", return_value=fake):
            from server.tasks.event_store import EventStore

            store = EventStore()
            store.bootstrap_job_started_realtime(job_id="job123", source="github")

        self.assertTrue(fake.xadd_ops)
        key, values, rid = fake.xadd_ops[0]
        self.assertEqual(key, "dinq:job:job123:events")
        self.assertEqual(rid, "1-0")
        self.assertIn("v", values)

    def test_job_completed_persists_terminal_event_to_db(self):
        fake = _FakeRedis()
        sess = _CaptureSession()
        env = {
            "DINQ_REDIS_JOB_TTL_SECONDS": "0",  # disable expire touch to keep assertions focused
            "DINQ_REDIS_CLEANUP_ON_JOB_COMPLETED": "0",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("server.tasks.event_store.get_redis_client", return_value=fake),
            patch("server.tasks.event_store.get_db_session", lambda: _fake_db_session(sess)),
        ):
            from server.tasks.event_store import EventStore

            store = EventStore()
            store.append_event(job_id="job123", card_id=None, event_type="job.completed", payload={"status": "completed"})

        event_types = [getattr(ev, "event_type", None) for ev in sess.added]
        self.assertIn("job.completed", event_types)


if __name__ == "__main__":
    unittest.main()

