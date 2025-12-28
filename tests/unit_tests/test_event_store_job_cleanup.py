import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch


class _FakePipeline:
    def __init__(self, redis):
        self._redis = redis
        self._ops = []

    def expire(self, key, ttl):
        self._ops.append(("expire", key, int(ttl)))
        return self

    def unlink(self, *keys):
        self._ops.append(("unlink", list(keys)))
        return self

    def delete(self, *keys):
        self._ops.append(("delete", list(keys)))
        return self

    def execute(self):
        self._redis.pipeline_ops.extend(self._ops)
        self._ops = []
        return []


class _FakeRedis:
    def __init__(self, *, scan_keys):
        self._counters = {}
        self.scan_keys = list(scan_keys)
        self.pipeline_ops = []
        self.set_ops = []
        self.xadd_ops = []

    def incr(self, key):
        cur = int(self._counters.get(key) or 0) + 1
        self._counters[key] = cur
        return cur

    def xadd(self, key, values, id=None, maxlen=None, approximate=None):
        self.xadd_ops.append((key, values, id, maxlen, approximate))
        return id

    def set(self, key, value):
        self.set_ops.append((key, value))
        return True

    def pipeline(self):
        return _FakePipeline(self)

    def scan_iter(self, match=None, count=None):
        # Best-effort: return the provided keys (test controls the namespace via the key names).
        for k in self.scan_keys:
            yield k

    def unlink(self, *keys):
        # Existence is used by EventStore to decide between UNLINK and DEL.
        return 0


class _DummySession:
    def add(self, obj):  # noqa: ARG002
        return None

    def query(self, *args, **kwargs):  # noqa: ARG002
        return self

    def filter(self, *args, **kwargs):  # noqa: ARG002
        return self

    def update(self, *args, **kwargs):  # noqa: ARG002
        return 1


@contextmanager
def _fake_db_session():
    yield _DummySession()


class TestEventStoreJobCompletedCleanup(unittest.TestCase):
    def test_job_completed_sets_post_ttl_and_deletes_artifacts(self):
        fake = _FakeRedis(
            scan_keys=[
                b"dinq:artifact:job123:aaa",
                b"dinq:artifact:job123:bbb",
            ]
        )

        env = {
            "DINQ_REDIS_JOB_TTL_SECONDS": "0",  # disable general touch TTL to keep assertions focused
            "DINQ_REDIS_CLEANUP_ON_JOB_COMPLETED": "1",
            "DINQ_REDIS_POST_JOB_TTL_SECONDS": "123",
        }

        with (
            patch.dict(os.environ, env, clear=False),
            patch("server.tasks.event_store.get_redis_client", return_value=fake),
            patch("server.tasks.event_store.get_db_session", _fake_db_session),
        ):
            from server.tasks.event_store import EventStore

            store = EventStore()
            store.append_event(job_id="job123", card_id=None, event_type="job.completed", payload={"job_id": "job123"})

        expires = [(op[1], op[2]) for op in fake.pipeline_ops if op and op[0] == "expire"]
        self.assertIn(("dinq:job:job123:events", 123), expires)
        self.assertIn(("dinq:job:job123:last_seq", 123), expires)
        self.assertIn(("dinq:job:job123:terminal_seq", 123), expires)

        unlink_ops = [op for op in fake.pipeline_ops if op and op[0] == "unlink"]
        self.assertTrue(unlink_ops)
        deleted_keys = []
        for op in unlink_ops:
            deleted_keys.extend(op[1])
        self.assertIn(b"dinq:artifact:job123:aaa", deleted_keys)
        self.assertIn(b"dinq:artifact:job123:bbb", deleted_keys)


if __name__ == "__main__":
    unittest.main()
