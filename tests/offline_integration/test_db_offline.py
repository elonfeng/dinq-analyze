import unittest


class TestLocalDatabaseOffline(unittest.TestCase):
    def test_select_1(self):
        from sqlalchemy import text
        from src.utils.db_utils import engine

        with engine.connect() as conn:
            val = conn.execute(text("SELECT 1")).scalar()
        self.assertEqual(val, 1)


if __name__ == "__main__":
    unittest.main()

