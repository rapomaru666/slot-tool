import sys
import unittest
from pathlib import Path

RENA_DIR = Path(__file__).resolve().parents[1] / "x-auto" / "rena"
sys.path.insert(0, str(RENA_DIR))

import buffer_client


class TestRenaChannelGuard(unittest.TestCase):
    def test_target_is_exact_rena_channel(self):
        self.assertEqual(buffer_client.TARGET_CHANNEL_ID, "6a9b8207065799be468fa585")
        self.assertEqual(buffer_client.TARGET_HANDLE, "renatotaikun")

    def test_rapomaru_channel_is_protected(self):
        self.assertIn("6a818a27ccaf649a67b736f1", buffer_client.PROTECTED_OTHER_CHANNEL_IDS)
        self.assertNotEqual(
            buffer_client.TARGET_CHANNEL_ID,
            "6a818a27ccaf649a67b736f1",
        )

    def test_handle_normalization(self):
        self.assertEqual(buffer_client._norm("@renatotaikun"), "renatotaikun")


if __name__ == "__main__":
    unittest.main()
