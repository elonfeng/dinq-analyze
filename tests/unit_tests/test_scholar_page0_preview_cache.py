import unittest
from unittest.mock import patch

from server.analyze.resources import scholar as scholar_resource
from server.services.scholar.pipeline import ScholarPipelineDeps


class TestScholarPage0PreviewCache(unittest.TestCase):
    def test_cache_hit_emits_preview_prefill_and_append(self):
        events = []

        def progress(event, message, data):
            events.append((event, message, data))

        cached_report = {
            "researcher": {
                "name": "Cached Researcher",
                "total_citations": 123,
                "h_index": 10,
                "yearly_citations": {"2024": 10},
            },
            "publication_stats": {"papers_loaded": 1},
            "papers_preview": [
                {"id": "scholar:sid123:paper1", "title": "Paper 1", "citations": 1},
            ],
        }

        def cache_get(_scholar_id, _max_age_days, name=None):
            return cached_report

        deps = ScholarPipelineDeps(
            data_fetcher=object(),
            analyzer=object(),
            use_cache=True,
            cache_max_age_days=3,
            cache_get=cache_get,
        )

        with patch.object(scholar_resource, "_build_deps", return_value=deps):
            out = scholar_resource.run_scholar_page0(
                scholar_id="sid123",
                researcher_name=None,
                user_id="u1",
                progress=progress,
            )

        self.assertIsInstance(out, dict)
        self.assertEqual(out.get("researcher", {}).get("name"), "Cached Researcher")
        self.assertEqual(out.get("researcher", {}).get("scholar_id"), "sid123")

        event_names = [e[0] for e in events]
        self.assertIn("preview.scholar.cards", event_names)

        cards_payloads = [e[2] for e in events if e[0] == "preview.scholar.cards"]
        self.assertTrue(cards_payloads)
        prefill_cards = cards_payloads[-1].get("prefill_cards", [])
        self.assertTrue(any(c.get("card") == "researcherInfo" for c in prefill_cards))


if __name__ == "__main__":
    unittest.main()
