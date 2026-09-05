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
        rapomaru_id = "6a818a27ccaf649a67b736f1"
        self.assertIn(rapomaru_id, buffer_client.PROTECTED_OTHER_CHANNEL_IDS)
        self.assertEqual(buffer_client.PROTECTED_OTHER_CHANNEL_IDS[rapomaru_id], "rapomaru777")
        self.assertNotEqual(buffer_client.TARGET_CHANNEL_ID, rapomaru_id)

    def test_handle_normalization(self):
        self.assertEqual(buffer_client._norm("@renatotaikun"), "renatotaikun")


if __name__ == "__main__":
    unittest.main()
