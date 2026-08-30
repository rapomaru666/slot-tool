from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common.buffer_client import BufferClient
from common.publication_state import (
    atomic_write_json,
    content_sha256,
    evening_receipt_path,
    extract_x_post_id,
    is_verified_sent_receipt,
    make_morning_entry,
    morning_receipt_path,
    read_json,
)
from common.x_text import (
    TARGET_MAX_WEIGHT,
    TARGET_MIN_WEIGHT,
    append_verified_fillers,
    normalize_text,
    truncate_to_weight,
    validate_x_text,
    x_weighted_length,
)


JST = timezone(timedelta(hours=9))
START_DATE = datetime(2026, 8, 18, tzinfo=JST).date()
TARGET_NAME = "rapomaru777"
PUBLISHED_PATH = Path("x-auto/morning-published.json")

RANKING_PATTERNS = [r"\d+位", r"ランキング", r"順位", r"🌈[①②③④⑤⑥⑦⑧⑨⑩]"]
RESULT_FILLERS = [
    "公開ページを複数確認した結果です。",
    "確認できた数値だけを掲載しています。",
    "未確認の内容は断定していません。",
    "要確認。",
]


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RAPOMARU-X-Auto/2.0)",
            "Accept-Language": "ja,en;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def find_result_text(html: str, hall: str) -> str | None:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
    position = text.find(hall)
    if position < 0:
        return None
    chunk = text[position : position + 900]
    numbers = []
    for pattern, label in [
        (r"平均[^+\-\d]{0,12}([+\-]?\d[\d,]*)\s*枚", "平均差枚"),
        (r"勝率[^\d]{0,8}(\d+(?:\.\d+)?)%", "勝率"),
        (r"平均[^\d]{0,12}(\d[\d,]*)\s*G", "平均G"),
    ]:
        match = re.search(pattern, chunk)
        if match:
            unit = "%" if label == "勝率" else ("G" if label == "平均G" else "枚")
            numbers.append(f"{label}{match.group(1)}{unit}")
    return " / ".join(numbers) if numbers else None


def validate_content(text: str) -> None:
    if "答え合わせ" in text or "🌈Result" not in text:
        raise RuntimeError("Morning label must be 🌈Result; 答え合わせ is forbidden")
    if "掲載確認継続" in text:
        raise RuntimeError("Morning result must be final; 掲載確認継続 is forbidden")
    for pattern in RANKING_PATTERNS:
        if re.search(pattern, text):
            raise RuntimeError(f"Ranking expression is forbidden: {pattern}")


def fit_result_post(text: str) -> str:
    result = normalize_text(text)
    if x_weighted_length(result) > TARGET_MAX_WEIGHT:
        lines = result.splitlines()
        hashtag_line = lines[-1] if lines and lines[-1].startswith("#") else ""
        body = "\n".join(lines[:-1] if hashtag_line else lines)
        suffix = f"…\n{hashtag_line}" if hashtag_line else "…"
        result = truncate_to_weight(body, TARGET_MAX_WEIGHT, suffix=suffix)
    result = append_verified_fillers(
        result,
        RESULT_FILLERS,
        min_weight=TARGET_MIN_WEIGHT,
        max_weight=TARGET_MAX_WEIGHT,
    )
    validate_content(result)
    validate_x_text(
        result,
        min_weight=TARGET_MIN_WEIGHT,
        max_weight=TARGET_MAX_WEIGHT,
        label="morning result",
    )
    return result


def write_job_summary(result: dict) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as summary:
        summary.write("## RAPOMARU 朝8時RESULT\n\n")
        summary.write(f"- 状態: {result['status']}\n")
        summary.write(f"- 対象日: {result['target_date']}\n")
        summary.write(f"- 投稿数: {result.get('post_count', 0)}\n")
        for item in result.get("posts", []):
            summary.write(f"- {item['hall']}: {item['external_link']}\n")


def main() -> None:
    today = datetime.now(JST).date()
    if today < START_DATE:
        raise RuntimeError("Morning reports have not started yet")
    override = os.environ.get("TARGET_DATE", "").strip()
    target = (
        datetime.strptime(override, "%Y-%m-%d").date()
        if override
        else today - timedelta(days=1)
    )
    target_date = target.isoformat()

    evening_receipt = read_json(evening_receipt_path(target_date))
    if not is_verified_sent_receipt(evening_receipt):
        raise RuntimeError(f"Verified evening receipt is missing: {target_date}")

    halls = [
        hall
        for hall in evening_receipt.get("selected_halls", [])
        if hall.get("category") == "rainbow"
    ]
    if not halls:
        state_path = morning_receipt_path(target_date)
        existing_state = read_json(state_path)
        if not existing_state or existing_state.get("status") != "not_required":
            atomic_write_json(
                state_path,
                {
                    "publication_key": f"morning:{target_date}",
                    "target_date": target_date,
                    "status": "not_required",
                    "entries": {},
                    "verified_at": datetime.now(JST).isoformat(),
                },
            )
        result = {
            "ok": True,
            "status": "not_required",
            "target_date": target_date,
            "post_count": 0,
            "posts": [],
        }
        write_job_summary(result)
        print(json.dumps(result, ensure_ascii=False))
        return

    legacy_history = read_json(PUBLISHED_PATH, {})
    legacy_posts = legacy_history.get(target_date, {}).get("posts", [])
    legacy_links = [
        post.get("buffer", {}).get("post", {}).get("externalLink")
        for post in legacy_posts
    ]
    legacy_halls = [post.get("hall") for post in legacy_posts]
    expected_halls = [hall.get("name") for hall in halls]
    if (
        legacy_posts
        and legacy_halls == expected_halls
        and all(extract_x_post_id(link) for link in legacy_links)
    ):
        result = {
            "ok": True,
            "status": "already_sent_verified",
            "target_date": target_date,
            "post_count": len(legacy_links),
            "posts": [
                {"hall": hall.get("name"), "external_link": link}
                for hall, link in zip(halls, legacy_links)
            ],
        }
        write_job_summary(result)
        print(json.dumps(result, ensure_ascii=False))
        return

    urls = [
        f"https://hall-navi.com/osusume_list?ymd={target_date}",
        f"https://hall-navi.com/?ymd={target_date}",
    ]
    pages: list[tuple[str, str]] = []
    for url in urls:
        for attempt in range(3):
            try:
                pages.append((url, fetch(url)))
                break
            except Exception:
                if attempt == 2:
                    break
                time.sleep(5 * (attempt + 1))

    state_path = morning_receipt_path(target_date)
    state = read_json(
        state_path,
        {
            "publication_key": f"morning:{target_date}",
            "target_date": target_date,
            "status": "in_progress",
            "entries": {},
        },
    )
    client = BufferClient()
    channel = client.find_channel(TARGET_NAME)
    completed = []
    sources = set()

    for hall in halls:
        hall_key = hall["hall_id"]
        hall_name = hall["name"]
        existing_entry = state.get("entries", {}).get(hall_key)
        if existing_entry and existing_entry.get("status") == "sent":
            if not (
                existing_entry.get("text")
                and existing_entry.get("content_sha256")
                == content_sha256([existing_entry["text"]])
                and existing_entry.get("buffer_post_id")
                and existing_entry.get("sent_at")
                and extract_x_post_id(existing_entry.get("external_link"))
            ):
                raise RuntimeError(f"Morning receipt is invalid: {hall_name}")
            completed.append(existing_entry)
            if existing_entry.get("source"):
                sources.add(existing_entry["source"])
            continue

        found = None
        source = None
        for url, page in pages:
            found = find_result_text(page, hall_name)
            if found:
                source = url
                break
        if found:
            body = found
        else:
            body = (
                "現時点では公開データから実績数値を確認できず。"
                "\n当日の状況や差枚をご存じの方は、リプで情報提供をお願いします。"
            )
        text = fit_result_post(
            f"🌈Result {target.month}/{target.day}\n"
            f"🌈 {hall_name}\n"
            f"{body}\n"
            "#スロット #パチスロ"
        )

        buffer_post, _ = client.publish_verified(
            channel=channel,
            root_text=text,
            posts=[text],
        )
        entry = make_morning_entry(
            target_date=target_date,
            hall=hall,
            text=text,
            buffer_post=buffer_post,
            source=source,
        )
        state.setdefault("entries", {})[hall_key] = entry
        atomic_write_json(state_path, state)
        completed.append(entry)
        if source:
            sources.add(source)
        time.sleep(5)

    state["status"] = "sent"
    state["verified_at"] = datetime.now(JST).isoformat()
    atomic_write_json(state_path, state)

    legacy_history[target_date] = {
        "reported_at_jst": datetime.now(JST).isoformat(),
        "halls": [hall["name"] for hall in halls],
        "posts": [
            {
                "hall": entry["hall"]["name"],
                "text": entry["text"],
                "chars": len(entry["text"]),
                "weighted_chars": x_weighted_length(entry["text"]),
                "buffer": {
                    "post": {
                        "id": entry["buffer_post_id"],
                        "status": "sent",
                        "sentAt": entry["sent_at"],
                        "externalLink": entry["external_link"],
                    }
                },
                "source": entry.get("source"),
            }
            for entry in completed
        ],
        "sources": sorted(sources),
    }
    atomic_write_json(PUBLISHED_PATH, legacy_history)

    result = {
        "ok": True,
        "status": "sent",
        "target_date": target_date,
        "post_count": len(completed),
        "posts": [
            {
                "hall": entry["hall"]["name"],
                "external_link": entry["external_link"],
                "weighted_chars": x_weighted_length(entry["text"]),
            }
            for entry in completed
        ],
    }
    write_job_summary(result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
