import unittest

from server.analyze.input_resolver import resolve_scholar_identity


class TestResolveScholarIdentity(unittest.TestCase):
    def test_parses_bare_user_equals_id(self):
        scholar_id, query = resolve_scholar_identity({"content": "user=sGFyDIUAAAAJ"})
        self.assertEqual(scholar_id, "sGFyDIUAAAAJ")
        self.assertIsNone(query)

    def test_parses_scholar_shorthand_url(self):
        scholar_id, query = resolve_scholar_identity({"content": "scholar?user=sGFyDIUAAAAJ"})
        self.assertEqual(scholar_id, "sGFyDIUAAAAJ")
        self.assertIsNone(query)


if __name__ == "__main__":
    unittest.main()

