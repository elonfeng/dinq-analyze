import os
import unittest
from unittest.mock import patch


from server.analyze.freeform import is_ambiguous_input, resolve_candidates


class _FakeTavilyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, *, query: str, max_results: int = 5):
        _ = query
        _ = max_results
        return {
            "results": [
                {
                    "title": "Jane Doe | LinkedIn",
                    "url": "https://www.linkedin.com/in/jane-doe-123/?originalSubdomain=us",
                    "content": "Profile snippet",
                },
                {
                    "title": "Christopher D. Manning - Google Scholar",
                    "url": "https://scholar.google.com/citations?user=Y-ql3zMAAAAJ&hl=en",
                    "content": "Stanford University - Google Scholar profile",
                },
                {
                    "title": "Company Page",
                    "url": "https://www.linkedin.com/company/acme/",
                },
                {
                    "title": "Not LinkedIn",
                    "url": "https://example.com/jane",
                },
            ]
        }


class TestAnalyzeFreeform(unittest.TestCase):
    def test_is_ambiguous_input_linkedin(self):
        self.assertTrue(is_ambiguous_input("linkedin", "Jane Doe"))
        self.assertFalse(is_ambiguous_input("linkedin", "https://www.linkedin.com/in/jane-doe-123"))

    def test_resolve_candidates_linkedin(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test"}):
            with patch("tavily.TavilyClient", _FakeTavilyClient):
                candidates = resolve_candidates("linkedin", "Jane Doe", user_id="u1")

        # Only /in/ profile URLs should be included and should be cleaned (no query params).
        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["input"]["content"], "https://www.linkedin.com/in/jane-doe-123")
        self.assertIn("label", candidates[0])

    def test_resolve_candidates_scholar_via_tavily(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test"}):
            with patch("tavily.TavilyClient", _FakeTavilyClient):
                candidates = resolve_candidates("scholar", "Christopher D Manning", user_id="u1")

        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["input"]["content"], "Y-ql3zMAAAAJ")
