import unittest

from server.analyze.cache_policy import compute_options_hash, is_cacheable_subject


class TestComputeOptionsHash(unittest.TestCase):
    def test_ignores_freeform_and_force_refresh(self):
        base = {"foo": 1, "bar": {"x": True}}
        h1 = compute_options_hash(base)
        h2 = compute_options_hash({**base, "freeform": True})
        h3 = compute_options_hash({**base, "force_refresh": True})
        self.assertEqual(h1, h2)
        self.assertEqual(h1, h3)

    def test_semantic_option_changes_hash(self):
        h1 = compute_options_hash({"locale": "en"})
        h2 = compute_options_hash({"locale": "zh"})
        self.assertNotEqual(h1, h2)

    def test_order_independent(self):
        h1 = compute_options_hash({"a": 1, "b": 2})
        h2 = compute_options_hash({"b": 2, "a": 1})
        self.assertEqual(h1, h2)


class TestIsCacheableSubject(unittest.TestCase):
    def test_scholar_cacheable_only_for_id(self):
        self.assertTrue(is_cacheable_subject(source="scholar", subject_key="id:Y-ql3zMAAAAJ"))
        self.assertFalse(is_cacheable_subject(source="scholar", subject_key="name:Andrew Ng"))

    def test_github_cacheable_only_for_login(self):
        self.assertTrue(is_cacheable_subject(source="github", subject_key="login:torvalds"))
        self.assertFalse(is_cacheable_subject(source="github", subject_key="query:Linus Torvalds"))

    def test_linkedin_cacheable_only_for_url(self):
        self.assertTrue(is_cacheable_subject(source="linkedin", subject_key="url:https://www.linkedin.com/in/x"))
        self.assertFalse(is_cacheable_subject(source="linkedin", subject_key="name:Jane Doe"))

    def test_other_sources_default_true(self):
        self.assertTrue(is_cacheable_subject(source="twitter", subject_key="username:elonmusk"))
        self.assertTrue(is_cacheable_subject(source="openreview", subject_key="id:someone@example.com"))
        self.assertTrue(is_cacheable_subject(source="huggingface", subject_key="username:somebody"))
        self.assertTrue(is_cacheable_subject(source="youtube", subject_key="channel:UCxxxx"))

