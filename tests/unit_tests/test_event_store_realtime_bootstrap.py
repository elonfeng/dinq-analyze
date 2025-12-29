import unittest
from contextlib import contextmanager
from unittest.mock import patch


class _FakeCard:
    def __init__(self, *, card_id: int, output=None):
        self.id = int(card_id)
        self.output = output
        self.updated_at = None


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):  # noqa: ARG002
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self._result


class _FakeSession:
    def __init__(self, *, card: _FakeCard):
        self._card = card
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def query(self, *args, **kwargs):  # noqa: ARG002
        return _FakeQuery(self._card)


@contextmanager
def _fake_db_session(sess: _FakeSession):
    yield sess


class TestEventStoreDbOnly(unittest.TestCase):
    def test_append_event_applies_card_delta_to_snapshot_stream(self):
        from server.tasks.event_store import EventStore

        store = EventStore()
        store._next_seq = lambda session, job_id: 1  # type: ignore[method-assign]  # noqa: ARG005

        card = _FakeCard(card_id=1, output=None)
        sess = _FakeSession(card=card)

        with patch("server.tasks.event_store.get_db_session", lambda: _fake_db_session(sess)):
            store.append_event(
                job_id="job123",
                card_id=1,
                event_type="card.delta",
                payload={"delta": "hello", "field": "content", "section": "main", "format": "markdown"},
            )

        stream = (card.output or {}).get("stream") or {}
        content = stream.get("content") or {}
        sections = content.get("sections") or {}
        self.assertEqual(sections.get("main"), "hello")


if __name__ == "__main__":
    unittest.main()
