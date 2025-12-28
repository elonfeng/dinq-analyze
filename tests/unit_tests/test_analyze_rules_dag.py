import unittest

from server.analyze import rules
from server.analyze.cache_policy import compute_options_hash


class TestAnalyzeRulesDAG(unittest.TestCase):
    def test_github_profile_subset_includes_only_needed_deps(self):
        cards = rules.normalize_cards("github", ["profile"])
        self.assertIn("profile", cards)
        self.assertIn("resource.github.profile", cards)
        self.assertNotIn("resource.github.preview", cards)
        self.assertNotIn("resource.github.data", cards)
        self.assertNotIn("resource.github.enrich", cards)
        self.assertNotIn("full_report", cards)

    def test_default_plan_marks_roots_ready(self):
        plan = rules.build_plan("github", None)
        by_type = {c["card_type"]: c for c in plan}
        # Plan creation starts everything as "pending"; JobStore.release_ready_cards() promotes root cards to "ready".
        self.assertEqual(by_type["resource.github.profile"]["status"], "pending")
        self.assertEqual(by_type["resource.github.profile"]["depends_on"], [])
        self.assertNotIn("resource.github.preview", by_type)
        self.assertEqual(by_type["resource.github.data"]["depends_on"], [])
        self.assertEqual(by_type["resource.github.enrich"]["depends_on"], ["resource.github.data"])
        self.assertEqual(by_type["profile"]["depends_on"], ["resource.github.profile"])

    def test_non_dag_source_keeps_full_report_root_ready(self):
        plan = rules.build_plan("twitter", None)
        by_type = {c["card_type"]: c for c in plan}
        # Non-DAG sources still create a full_report root card; it will be promoted to "ready" by release_ready_cards().
        self.assertEqual(by_type["full_report"]["status"], "pending")
        self.assertEqual(by_type["full_report"]["depends_on"], [])
        self.assertEqual(by_type["profile"]["status"], "pending")

    def test_options_hash_ignores_requested_cards_meta(self):
        base = compute_options_hash({"foo": "bar"})
        with_meta = compute_options_hash({"foo": "bar", "_requested_cards": ["profile"]})
        self.assertEqual(base, with_meta)
