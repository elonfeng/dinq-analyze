import unittest

from server.api.scholar_pk.utils import create_pk_data_message, create_pk_report_data_message


class TestScholarPKMessages(unittest.TestCase):
    def test_pk_data_message_has_unified_and_legacy_fields(self):
        payload = {"a": 1, "b": {"c": 2}}
        msg = create_pk_data_message(payload)

        self.assertEqual(msg.get("source"), "scholar")
        self.assertEqual(msg.get("event_type"), "data")
        self.assertEqual(msg.get("type"), "pkData")
        self.assertEqual(msg.get("payload"), payload)
        self.assertEqual(msg.get("content"), payload)

    def test_pk_report_message_has_unified_and_legacy_fields(self):
        report_urls = {
            "pk_json_url": "http://localhost/reports/pk.json",
            "researcher1_name": "A",
            "researcher2_name": "B",
            "scholar_id1": "id1",
            "scholar_id2": "id2",
        }
        msg = create_pk_report_data_message(report_urls)

        self.assertEqual(msg.get("source"), "scholar")
        self.assertEqual(msg.get("event_type"), "data")
        self.assertEqual(msg.get("type"), "reportData")
        self.assertIsInstance(msg.get("payload"), dict)
        self.assertIsInstance(msg.get("content"), dict)

        self.assertEqual(msg["payload"]["jsonUrl"], report_urls["pk_json_url"])
        self.assertEqual(msg["payload"]["researcher1Name"], report_urls["researcher1_name"])
        self.assertEqual(msg["payload"]["researcher2Name"], report_urls["researcher2_name"])
        self.assertEqual(msg["payload"]["scholarId1"], report_urls["scholar_id1"])
        self.assertEqual(msg["payload"]["scholarId2"], report_urls["scholar_id2"])


if __name__ == "__main__":
    unittest.main()

