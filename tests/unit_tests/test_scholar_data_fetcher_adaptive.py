import unittest
from unittest.mock import patch


class TestScholarDataFetcherAdaptiveMaxPapers(unittest.TestCase):
    def _make_fetcher(self):
        from server.services.scholar.data_fetcher import ScholarDataFetcher

        fetcher = ScholarDataFetcher(use_crawlbase=False, api_token=None)
        # Force crawlbase path in get_full_profile without requiring a real token.
        fetcher.use_crawlbase = True
        return fetcher

    def test_adaptive_reduces_to_single_page_for_small_profile(self):
        fetcher = self._make_fetcher()
        fetch_calls = []

        def fake_fetch_html(_url, cancel_event=None, user_id=None):
            fetch_calls.append(1)
            return "<html></html>"

        page0 = {
            "scholar_id": "sid",
            "name": "Alice",
            "total_citations": 1200,
            "h_index": 10,
            "papers": [{"year": "2024"}] * 100,
            "has_next_page": True,
        }
        page1 = {
            "papers": [{"year": "2023"}] * 100,
            "has_next_page": False,
        }

        def fake_parse(_html, page_index=0, first_page=False, page_size=100):  # noqa: ARG001
            return page0 if page_index == 0 else page1

        with patch.object(fetcher, "fetch_html", side_effect=fake_fetch_html), patch.object(
            fetcher,
            "parse_google_scholar_html",
            side_effect=fake_parse,
        ):
            profile = fetcher.get_full_profile(
                {"scholar_id": "sid"},
                max_papers=200,
                adaptive_max_papers=True,
            )

        self.assertIsInstance(profile, dict)
        self.assertEqual(len(fetch_calls), 1, "expected adaptive mode to stop after the first page")

    def test_adaptive_keeps_two_pages_for_large_profile(self):
        fetcher = self._make_fetcher()
        fetch_calls = []

        def fake_fetch_html(_url, cancel_event=None, user_id=None):
            fetch_calls.append(1)
            return "<html></html>"

        page0 = {
            "scholar_id": "sid",
            "name": "Alice",
            "total_citations": 99999,
            "h_index": 99,
            "papers": [{"year": "2024"}] * 100,
            "has_next_page": True,
        }
        page1 = {
            "papers": [{"year": "2023"}] * 100,
            "has_next_page": False,
        }

        def fake_parse(_html, page_index=0, first_page=False, page_size=100):  # noqa: ARG001
            return page0 if page_index == 0 else page1

        with patch.object(fetcher, "fetch_html", side_effect=fake_fetch_html), patch.object(
            fetcher,
            "parse_google_scholar_html",
            side_effect=fake_parse,
        ):
            profile = fetcher.get_full_profile(
                {"scholar_id": "sid"},
                max_papers=200,
                adaptive_max_papers=True,
            )

        self.assertIsInstance(profile, dict)
        self.assertEqual(len(fetch_calls), 2, "expected large profile to fetch up to max_papers")


if __name__ == "__main__":
    unittest.main()
