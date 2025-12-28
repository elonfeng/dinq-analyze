import unittest

from server.analyze.subject import resolve_subject_key


class TestResolveSubjectKey(unittest.TestCase):
    def test_scholar(self):
        self.assertEqual(resolve_subject_key("scholar", {"content": "Y-ql3zMAAAAJ"}), "id:Y-ql3zMAAAAJ")
        self.assertEqual(resolve_subject_key("scholar", {"content": "Andrew Ng"}), "name:Andrew Ng")

    def test_github(self):
        self.assertEqual(resolve_subject_key("github", {"content": "torvalds"}), "login:torvalds")
        self.assertEqual(resolve_subject_key("github", {"content": "Linus Torvalds"}), "query:Linus Torvalds")

    def test_linkedin(self):
        self.assertEqual(
            resolve_subject_key("linkedin", {"content": "https://www.linkedin.com/in/someone/"}),
            "url:https://linkedin.com/in/someone",
        )
        self.assertEqual(resolve_subject_key("linkedin", {"content": "Jane Doe"}), "name:Jane Doe")

    def test_twitter(self):
        self.assertEqual(resolve_subject_key("twitter", {"content": "ElonMusk"}), "username:elonmusk")

    def test_openreview(self):
        self.assertEqual(resolve_subject_key("openreview", {"content": "Someone@Example.com"}), "id:someone@example.com")

    def test_huggingface(self):
        self.assertEqual(resolve_subject_key("huggingface", {"content": "SomeUser"}), "username:someuser")
