from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "x-auto" / "scripts"))

from buffer_publish_thread import fit_post, structured_halls, validate_evening_payload
from common.buffer_client import BufferClient
from common.publication_state import (
    atomic_write_json,
    content_sha256,
    extract_x_post_id,
    hall_id,
)
from common.x_text import (
    TARGET_MAX_WEIGHT,
    TARGET_MIN_WEIGHT,
    truncate_to_weight,
    validate_x_text,
    x_weighted_length,
)
from generate_tomorrow_thread import build_thread
from morning_rainbow_report import fit_result_post


class XTextTests(unittest.TestCase):
    def test_official_boundaries(self):
        self.assertEqual(x_weighted_length("a" * 280), 280)
        self.assertEqual(x_weighted_length("日" * 140), 280)
        self.assertEqual(x_weighted_length("日" * 141), 282)

    def test_url_and_emoji(self):
        self.assertEqual(x_weighted_length("https://example.com/a/very/long/path"), 23)
        self.assertEqual(x_weighted_length("👨‍👩‍👧‍👦"), 2)
        self.assertEqual(x_weighted_length("1️⃣"), 2)

    def test_truncation_keeps_url_atomic(self):
        url = "https://example.com/a/very/long/path"
        text = "日" * 100 + "\n" + url + "\n" + "日" * 30
        truncated = truncate_to_weight(text, 250, suffix="…")
        self.assertIn(url, truncated)
        self.assertLessEqual(x_weighted_length(truncated), 250)

    def test_fit_posts_reaches_editorial_range(self):
        fitted = fit_post("🌈テスト店\n確認済み情報。", "test")
        metric = validate_x_text(
            fitted,
            min_weight=TARGET_MIN_WEIGHT,
            max_weight=TARGET_MAX_WEIGHT,
        )
        self.assertGreaterEqual(metric.weighted_length, TARGET_MIN_WEIGHT)
        self.assertLessEqual(metric.weighted_length, TARGET_MAX_WEIGHT)

    def test_morning_result_reaches_editorial_range(self):
        text = fit_result_post(
            "🌈Result 8/30\n🌈 テスト店\n"
            "現時点では公開データから実績数値を確認できず。\n"
            "当日の状況や差枚をご存じの方は、リプで情報提供をお願いします。\n"
            "#スロット #パチスロ"
        )
        self.assertGreaterEqual(x_weighted_length(text), TARGET_MIN_WEIGHT)
        self.assertLessEqual(x_weighted_length(text), TARGET_MAX_WEIGHT)


class StructuredDataTests(unittest.TestCase):
    def test_legacy_thread_is_structured_once(self):
        thread = {
            "root": (
                "🎰8/31 関東注目\n"
                "🌈店舗A｜確認済み情報\n"
                "🏆店舗B｜確認済み情報\n"
                "#スロット"
            ),
            "replies": [],
        }
        halls = structured_halls(thread)
        self.assertEqual([hall["name"] for hall in halls], ["店舗A", "店舗B"])
        self.assertEqual([hall["category"] for hall in halls], ["rainbow", "trophy"])

    def test_generator_outputs_structured_halls(self):
        thread = build_thread(
            date(2026, 8, 31),
            [
                {
                    "hall": "テストホール",
                    "score": 16.5,
                    "rank": "S",
                    "details": "公開スケジュールと過去傾向を確認",
                    "source": "hall-navi",
                }
            ],
        )
        self.assertEqual(thread["selected_halls"][0]["name"], "テストホール")
        self.assertEqual(thread["selected_halls"][0]["hall_id"], hall_id("テストホール"))
        self.assertGreaterEqual(x_weighted_length(thread["root"]), TARGET_MIN_WEIGHT)
        self.assertLessEqual(x_weighted_length(thread["root"]), TARGET_MAX_WEIGHT)
        validate_evening_payload(
            "2026-08-31",
            [thread["root"]],
            thread["selected_halls"],
        )

    def test_evening_payload_rejects_missing_date(self):
        text = fit_post("🌈テストホール\n確認済み情報。", "test")
        with self.assertRaisesRegex(RuntimeError, "Target date"):
            validate_evening_payload(
                "2026-08-31",
                [text],
                [{"hall_id": hall_id("テストホール"), "name": "テストホール"}],
            )

    def test_atomic_state_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            atomic_write_json(path, {"hash": content_sha256(["a", "b"])})
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["hash"], content_sha256(["a", "b"]))

    def test_x_link_validation(self):
        self.assertEqual(
            extract_x_post_id("https://twitter.com/rapomaru777/status/12345"),
            "12345",
        )
        self.assertIsNone(extract_x_post_id("https://example.com/status/12345"))


class FakeBufferClient(BufferClient):
    def __init__(self, existing=None):
        self.existing = existing
        self.created = 0

    def find_existing(self, **kwargs):
        return self.existing

    def create_post(self, **kwargs):
        self.created += 1
        return {
            "id": "buffer-1",
            "text": kwargs["root_text"],
            "status": "sent",
            "sentAt": "2026-08-30T11:00:00Z",
            "externalLink": "https://x.com/rapomaru777/status/12345",
        }

    def wait_until_sent(self, post, **kwargs):
        return post


class IdempotencyTests(unittest.TestCase):
    def test_existing_post_is_not_created_again(self):
        existing = {
            "id": "buffer-existing",
            "text": "same",
            "status": "sent",
            "sentAt": "2026-08-30T11:00:00Z",
            "externalLink": "https://x.com/rapomaru777/status/12345",
        }
        client = FakeBufferClient(existing=existing)
        post, outcome = client.publish_verified(
            channel={"id": "channel", "organization_id": "org"},
            root_text="same",
            posts=["same"],
        )
        self.assertEqual(outcome, "already_sent_verified")
        self.assertEqual(post["id"], "buffer-existing")
        self.assertEqual(client.created, 0)

    def test_missing_post_is_created_once(self):
        client = FakeBufferClient(existing=None)
        _, outcome = client.publish_verified(
            channel={"id": "channel", "organization_id": "org"},
            root_text="new",
            posts=["new"],
        )
        self.assertEqual(outcome, "sent")
        self.assertEqual(client.created, 1)


if __name__ == "__main__":
    unittest.main()
