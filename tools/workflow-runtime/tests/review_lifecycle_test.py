from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/workflow-runtime/review"))
from review_support.binding import requires_full_review
from review_support.events import findings_stale
from review_support.types import JsonObject


class ReviewLifecycleTest(unittest.TestCase):
    def test_scope_topology_requires_a_new_full_review(self) -> None:
        self.assertTrue(requires_full_review({"scope_topology"}))
        self.assertFalse(requires_full_review({"wording"}))

    def test_rebound_is_the_only_transition_that_clears_stale_state(self) -> None:
        events: list[JsonObject] = [
            {"event_type": "findings_stale"},
            {"event_type": "findings-rebound"},
        ]
        self.assertFalse(findings_stale(events))


if __name__ == "__main__":
    unittest.main()
