from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common.buffer_client import BufferClient
from common.publication_state import (
    atomic_write_json,
    content_sha256,
    evening_receipt_path,
    hall_id,
    is_verified_sent_receipt,
    make_evening_receipt,
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


TARGET_NAME = "rapomaru777"
JST = timezone(timedelta(hours=9))
PUBLISHED_PATH = Path("x-auto/published.json")
EXPANSION_LINES = [
    "公開情報を基に選定。",
    "取材重複と旧イベ日を重視。",
    "過去傾向も確認。",
    "当日の状況は要確認。",
    "対象日の公開スケジュールを確認済み。",
    "店舗名と開催日を照合済み。",
    "確認できた情報だけを掲載。",
    "要確認。",
]
FORBIDDEN_PATTERNS = ("確定", "必ず", "間違いない")


def determine_target_date(now_jst: datetime) -> str:
    if os.environ.get("GITHUB_EVENT_NAME") == "push":
        override = Path("x-auto/publish-target.txt")
        if override.exists() and override.read_text(encoding="utf-8").strip():
            return override.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        return now_jst.date().isoformat()
    override = os.environ.get("TARGET_DATE", "").strip()
    return override or (now_jst.date() + timedelta(days=1)).isoformat()


def fit_post(text: str, label: str) -> str:
    result = normalize_text(text)
    if x_weighted_length(result) > TARGET_MAX_WEIGHT:
        lines = result.splitlines()
        hashtag_line = lines[-1] if lines and lines[-1].startswith("#") else ""
        body = "\n".join(lines[:-1] if hashtag_line else lines)
        suffix = f"…\n{hashtag_line}" if hashtag_line else "…"
        result = truncate_to_weight(body, TARGET_MAX_WEIGHT, suffix=suffix)
    result = append_verified_fillers(
        result,
        EXPANSION_LINES,
        min_weight=TARGET_MIN_WEIGHT,
        max_weight=TARGET_MAX_WEIGHT,
    )
    validate_x_text(
        result,
        min_weight=TARGET_MIN_WEIGHT,
        max_weight=TARGET_MAX_WEIGHT,
        label=label,
    )
    return result


def structured_halls(thread_data: dict) -> list[dict]:
    supplied = thread_data.get("selected_halls")
    if supplied:
        halls = []
        for item in supplied:
            name = str(item.get("name", "")).strip()
            if name:
                halls.append({**item, "hall_id": item.get("hall_id") or hall_id(name), "name": name})
        if halls:
            return halls

    halls: list[dict] = []
    seen: set[str] = set()
    for line in str(thread_data.get("root", "")).splitlines():
        stripped = line.strip()
        marker = next((value for value in ("🌈", "🏆", "🎯") if stripped.startswith(value)), None)
        if not marker or "｜" not in stripped:
            continue
        name = stripped[len(marker) :].split("｜", 1)[0].strip()
        key = hall_id(name)
        if name and key not in seen:
            category = {"🌈": "rainbow", "🏆": "trophy", "🎯": "fallback"}[marker]
            halls.append({"hall_id": key, "name": name, "category": category})
            seen.add(key)
    return halls


def hall_marker(hall: dict) -> str:
    return {
        "rainbow": "🌈",
        "trophy": "🏆",
        "fallback": "🎯",
    }.get(str(hall.get("category", "")).strip(), "🎯")


def build_required_hall_post(target_date: str, hall: dict) -> str:
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    name = str(hall.get("name", "")).strip()
    reason = normalize_text(str(hall.get("reason", "")).strip())
    marker = hall_marker(hall)
    body = f"{marker}{name}\n{target.month}/{target.day}の対象店舗。"
    if reason:
        body += f"\n選定材料：{reason}"
    body += "\n公開情報で確認できた内容だけを掲載。\n#スロット #パチスロ"
    return fit_post(body, f"required hall {name}")


def ensure_selected_hall_coverage(target_date: str, posts: list[str], halls: list[dict]) -> list[str]:
    """Treat selected_halls as the source of truth and never silently drop a target hall."""
    result = list(posts)
    combined = "\n".join(result)
    for hall in halls:
        name = str(hall.get("name", "")).strip()
        if name and name not in combined:
            result.append(build_required_hall_post(target_date, hall))
            combined = "\n".join(result)
    return result


def validate_evening_payload(target_date: str, posts: list[str], halls: list[dict]) -> None:
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    combined = "\n".join(posts)
    if f"{target.month}/{target.day}" not in combined:
        raise RuntimeError(f"Target date is missing from evening post: {target_date}")

    identifiers = [hall.get("hall_id") or hall_id(str(hall.get("name", ""))) for hall in halls]
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("Duplicate halls are present in evening payload")

    for hall in halls:
        name = str(hall.get("name", "")).strip()
        if not name or name not in combined:
            raise RuntimeError(f"Target hall is missing from evening post: {name!r}")

    for pattern in FORBIDDEN_PATTERNS:
        if pattern in combined:
            raise RuntimeError(f"Forbidden expression is present: {pattern}")

    for index, text in enumerate(posts, 1):
        validate_x_text(
            text,
            min_weight=TARGET_MIN_WEIGHT,
            max_weight=TARGET_MAX_WEIGHT,
            label=f"post {index}",
        )


def migrate_legacy_receipt(target_date: str, thread_data: dict, legacy: dict) -> dict:
    original_posts = [thread_data["root"]] + thread_data.get("replies", [])
    receipt = make_evening_receipt(
        target_date=target_date,
        posts=original_posts,
        selected_halls=structured_halls(thread_data),
        buffer_post={
            "id": legacy.get("buffer_post_id"),
            "status": "sent",
            "sentAt": legacy.get("sent_at"),
            "externalLink": legacy.get("external_link"),
        },
    )
    receipt["migrated_from"] = "x-auto/published.json"
    atomic_write_json(evening_receipt_path(target_date), receipt)
    return receipt


def write_job_summary(result: dict) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as summary:
        summary.write("## RAPOMARU 20時投稿\n\n")
        summary.write(f"- 状態: {result['status']}\n")
        summary.write(f"- 対象日: {result['target_date']}\n")
        if result.get("external_link"):
            summary.write(f"- X: {result['external_link']}\n")
        summary.write(f"- 文字数: {result.get('weighted_lengths', [])}\n")


def main() -> None:
    target_date = determine_target_date(datetime.now(JST))
    thread_path = Path(f"x-auto/thread-{target_date}.json")
    if not thread_path.exists():
        raise RuntimeError(f"Required thread file is missing: {thread_path}")

    thread_data = read_json(thread_path)
    original_posts = [thread_data["root"]] + thread_data.get("replies", [])
    halls = structured_halls(thread_data)
    if not halls:
        raise RuntimeError("No structured target halls found")

    published = read_json(PUBLISHED_PATH, [])
    legacy = next(
        (
            item
            for item in published
            if item.get("target_date") == target_date and item.get("status") == "sent"
        ),
        None,
    )
    if legacy:
        receipt = read_json(evening_receipt_path(target_date))
        if not is_verified_sent_receipt(receipt):
            receipt = migrate_legacy_receipt(target_date, thread_data, legacy)
        result = {
            "ok": True,
            "status": "already_sent_verified",
            "target_date": target_date,
            "external_link": receipt["external_link"],
            "weighted_lengths": [x_weighted_length(text) for text in original_posts],
        }
        write_job_summary(result)
        print(json.dumps(result, ensure_ascii=False))
        return

    posts = [fit_post(text, f"post {index}") for index, text in enumerate(original_posts, 1)]
    posts = ensure_selected_hall_coverage(target_date, posts, halls)
    validate_evening_payload(target_date, posts, halls)
    expected_hash = content_sha256(posts)
    receipt = read_json(evening_receipt_path(target_date))
    if receipt and receipt.get("status") == "sent":
        if not is_verified_sent_receipt(receipt, expected_hash):
            raise RuntimeError("Published receipt exists but content or verification does not match")
        result = {
            "ok": True,
            "status": "already_sent_verified",
            "target_date": target_date,
            "external_link": receipt["external_link"],
            "weighted_lengths": [x_weighted_length(text) for text in posts],
        }
        write_job_summary(result)
        print(json.dumps(result, ensure_ascii=False))
        return

    client = BufferClient()
    channel = client.find_channel(TARGET_NAME)
    buffer_post, outcome = client.publish_verified(
        channel=channel,
        root_text=posts[0],
        posts=posts,
    )
    receipt = make_evening_receipt(
        target_date=target_date,
        posts=posts,
        selected_halls=halls,
        buffer_post=buffer_post,
    )
    atomic_write_json(evening_receipt_path(target_date), receipt)

    published.append(
        {
            "target_date": target_date,
            "status": "sent",
            "sent_at": buffer_post.get("sentAt"),
            "external_link": buffer_post.get("externalLink"),
            "buffer_post_id": buffer_post.get("id"),
            "content_sha256": expected_hash,
        }
    )
    atomic_write_json(PUBLISHED_PATH, published)
    result = {
        "ok": True,
        "status": outcome,
        "target_date": target_date,
        "external_link": receipt["external_link"],
        "buffer_post_id": receipt["buffer_post_id"],
        "weighted_lengths": [x_weighted_length(text) for text in posts],
    }
    write_job_summary(result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
