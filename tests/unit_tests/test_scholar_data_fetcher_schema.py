import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestScholarDataFetcherSchema(unittest.TestCase):
    def test_get_full_profile_returns_papers_without_crawlbase(self):
        from server.services.scholar.data_fetcher import ScholarDataFetcher

        fetcher = ScholarDataFetcher(use_crawlbase=False, api_token=None)
        fetch_calls = []

        def fake_fetch_html(_url, cancel_event=None, user_id=None):  # noqa: ARG001
            fetch_calls.append(1)
            return "<html></html>"

        page0 = {
            "name": "Alice",
            "total_citations": 10,
            "h_index": 3,
            "papers": [{"title": "P1", "year": "2024", "citations": "5"}] * 3,
            "has_next_page": False,
        }

        def fake_parse(_html, page_index=0, first_page=False, page_size=100):  # noqa: ARG001
            return page0

        with patch.object(fetcher, "fetch_html", side_effect=fake_fetch_html), patch.object(
            fetcher,
            "parse_google_scholar_html",
            side_effect=fake_parse,
        ):
            profile = fetcher.get_full_profile({"scholar_id": "sid"}, max_papers=30)

        self.assertIsInstance(profile, dict)
        self.assertGreaterEqual(len(fetch_calls), 1)
        self.assertIn("papers", profile)
        self.assertEqual(len(profile.get("papers") or []), 3)
        self.assertEqual(profile.get("scholar_id"), "sid")

    def test_fallback_scholarly_profile_is_coerced_to_include_papers(self):
        from server.services.scholar.data_fetcher import ScholarDataFetcher

        fetcher = ScholarDataFetcher(use_crawlbase=False, api_token=None)

        sample_profile = {
            "scholar_id": "sid",
            "name": "Alice",
            "citedby": 12,
            "publications": [
                {"bib": {"title": "Paper A", "pub_year": "2024", "citation": "venue"}, "num_citations": 5},
                {"bib": {"title": "Paper B", "pub_year": "2023", "citation": "venue"}, "num_citations": 7},
            ],
            "coauthors": [],
        }

        fake_scholarly = SimpleNamespace(fill=lambda *_args, **_kw: sample_profile)

        with patch("server.services.scholar.data_fetcher.scholarly", fake_scholarly), patch.object(
            fetcher,
            "_fetch_full_profile_via_html",
            return_value=None,
        ), patch.object(
            fetcher,
            "search_researcher",
            return_value={"container_type": "Author", "scholar_id": "sid", "name": "Alice"},
        ):
            profile = fetcher.get_full_profile({"scholar_id": "sid"}, max_papers=30)

        self.assertIsInstance(profile, dict)
        self.assertIn("papers", profile)
        self.assertEqual(len(profile.get("papers") or []), 2)
        self.assertEqual(profile.get("total_citations"), 12)
        self.assertEqual(profile.get("scholar_id"), "sid")


if __name__ == "__main__":
    unittest.main()

