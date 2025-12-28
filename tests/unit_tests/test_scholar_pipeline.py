import unittest

from server.services.scholar.pipeline import ScholarPipelineDeps, run_scholar_pipeline


class _DummyFetcher:
    def __init__(self):
        self.search_calls = []
        self.profile_calls = []

    def search_researcher(self, name=None, scholar_id=None, user_id=None):
        self.search_calls.append({"name": name, "scholar_id": scholar_id, "user_id": user_id})
        return {"scholar_id": "sid123", "name": name}

    def get_full_profile(
        self,
        author_info,
        *,
        max_papers=None,
        adaptive_max_papers=None,
        cancel_event=None,
        user_id=None,
        progress_callback=None,
    ):
        self.profile_calls.append(
            {
                "author_info": author_info,
                "user_id": user_id,
                "max_papers": max_papers,
                "adaptive_max_papers": adaptive_max_papers,
                "progress_callback": bool(progress_callback),
            }
        )
        return {
            "name": "Alice",
            "abbreviated_name": "Alice",
            "affiliation": "Test University",
            "email": "",
            "research_fields": [],
            "total_citations": 10,
            "citations_5y": 5,
            "h_index": 3,
            "h_index_5y": 2,
            "yearly_citations": {},
            "scholar_id": author_info.get("scholar_id", ""),
        }


class _DummyAnalyzer:
    def __init__(self):
        self.analyze_pub_calls = 0
        self.analyze_coauthor_calls = 0

    def analyze_publications(self, author_data, cancel_event=None):
        self.analyze_pub_calls += 1
        return {
            "total_papers": 1,
            "most_cited_paper": {"title": "Most Cited Paper"},
        }

    def analyze_coauthors(self, author_data, cancel_event=None):
        self.analyze_coauthor_calls += 1
        return {"top_coauthors": []}

    def calculate_researcher_rating(self, author_data, pub_stats):
        return {"score": 1}


class TestScholarPipeline(unittest.TestCase):
    def test_runs_minimal_pipeline_and_propagates_user_id(self):
        fetcher = _DummyFetcher()
        analyzer = _DummyAnalyzer()
        events = []

        def status_sender(message, _cb, progress=None, **_extra):
            events.append((message, progress))

        deps = ScholarPipelineDeps(
            data_fetcher=fetcher,
            analyzer=analyzer,
            use_cache=False,
            avatar_provider=lambda: "avatar",
            description_provider=lambda _name: "desc",
        )

        report = run_scholar_pipeline(
            deps=deps,
            researcher_name="Alice",
            user_id="u1",
            max_papers=123,
            status_sender=status_sender,
        )

        self.assertIsInstance(report, dict)
        self.assertEqual(report["researcher"]["name"], "Alice")
        self.assertEqual(report["researcher"]["scholar_id"], "sid123")
        self.assertEqual(fetcher.search_calls[0]["user_id"], "u1")
        self.assertEqual(fetcher.profile_calls[0]["user_id"], "u1")
        self.assertEqual(fetcher.profile_calls[0]["max_papers"], 123)
        self.assertEqual(analyzer.analyze_pub_calls, 1)
        self.assertEqual(analyzer.analyze_coauthor_calls, 1)

    def test_cache_hit_skips_fetch_and_analyze(self):
        fetcher = _DummyFetcher()
        analyzer = _DummyAnalyzer()

        def cache_get(_scholar_id, _max_age_days, name=None):
            return {"researcher": {"name": "Cached"}, "publication_stats": {}}

        deps = ScholarPipelineDeps(
            data_fetcher=fetcher,
            analyzer=analyzer,
            use_cache=True,
            cache_max_age_days=3,
            cache_get=cache_get,
            cache_validate=lambda cached, *_args, **_kw: cached,
        )

        report = run_scholar_pipeline(
            deps=deps,
            scholar_id="sid123",
            researcher_name="Alice",
            user_id="u1",
        )

        self.assertEqual(report["researcher"]["name"], "Cached")
        self.assertEqual(len(fetcher.profile_calls), 0)
        self.assertEqual(analyzer.analyze_pub_calls, 0)

    def test_persist_calls_cache_save(self):
        fetcher = _DummyFetcher()
        analyzer = _DummyAnalyzer()
        saved = []

        deps = ScholarPipelineDeps(
            data_fetcher=fetcher,
            analyzer=analyzer,
            use_cache=True,
            cache_get=lambda *_args, **_kw: None,
            cache_save=lambda report, sid: saved.append((sid, report.get("researcher", {}).get("name"))),
            avatar_provider=lambda: "avatar",
            description_provider=lambda _name: "desc",
        )

        report = run_scholar_pipeline(
            deps=deps,
            scholar_id="sid123",
            researcher_name="Alice",
            user_id="u1",
            max_papers=456,
        )

        self.assertIsNotNone(report)
        self.assertEqual(saved, [("sid123", "Alice")])
        self.assertEqual(fetcher.profile_calls[0]["max_papers"], 456)


if __name__ == "__main__":
    unittest.main()
