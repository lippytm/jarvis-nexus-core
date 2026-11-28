"""Run with: python -m unittest discover -s tests -v"""
import unittest
from datetime import datetime, timezone
from control_tower.events import validate_event, ingest

def sample(**kwargs):
    event = {
        "event_id": "evt-demo-001",
        "event_type": "newsletter_optin",
        "source": "linkedin",
        "occurred_at": "2026-10-21T09:30:00-07:00",
        "project_id": "education",
        "consent_status": "opted_in",
        "approval_state": "pending",
        "utm_source": "linkedin",
        "evidence_url": "https://example.com/evidence/demo",
        "payload": {"synthetic": True},
    }
    event.update(kwargs)
    return event

class EventContractTests(unittest.TestCase):
    def test_accept_valid_synthetic_event(self):
        self.assertEqual(validate_event(sample()), [])
    def test_reject_missing_consent(self):
        self.assertIn("explicit opt-in required", validate_event(sample(consent_status="opted_out")))
    def test_reject_sensitive_fields_nested(self):
        self.assertIn("disallowed sensitive field", validate_event(sample(payload={"x": [{"ssn": "fake"}]})))
    def test_reject_naive_timestamp(self):
        self.assertTrue(validate_event(sample(occurred_at="2026-10-21T09:30:00")))
    def test_duplicate_event(self):
        seen = set()
        self.assertEqual(ingest(sample(), seen)[0], "accepted")
        self.assertEqual(ingest(sample(), seen)[0], "duplicate")
    def test_reject_unknown_event_type(self):
        self.assertIn("unsupported event_type", validate_event(sample(event_type="wire_transfer")))
    def test_reject_insecure_evidence(self):
        self.assertIn("evidence_url must be HTTPS", validate_event(sample(evidence_url="http://example.com")))

if __name__ == "__main__":
    unittest.main()
