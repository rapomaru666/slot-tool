import argparse
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from buffer_client import publish_post

JST = ZoneInfo("Asia/Tokyo")
STATE_PATH = Path(__file__).with_name("morning-state.json")

# 09:50 JST に起動し、日ごとに 0〜20 分待って投稿する。
MAX_DELAY_MINUTES = 20
SKIP_DIVISOR = 8  # 約8日に1回。連続休みは禁止。
MIN_PUBLISHED_BEFORE_SKIP = 5  # 開始直後は休まない。

MORNING_TEXTS = [
    "おはよう〜☺️\n今日もよろしくね！",
    "おはよ〜🙌\n今日もよろしく☺️",
    "おはよう🌷\n今日も一日よろしくね〜",
    "おはよ☺️\n今日もがんばろ〜！",
    "おはよう〜！\n今日もいい日にしよ☺️",
    "おはよ〜🫶\n今日もよろしくね！",
    "おはよう☺️\n今日もがんばってこ〜",
    "おはよ〜！\n今日も一日よろしく🙌",
    "おはよう〜🌷\n今日もよろしく☺️",
    "おはよ☺️\n今日もいい日にしよ〜！",
    "おはよう〜🙌\n今日もがんばろ☺️",
    "おはよ〜☺️\n今日もよろしくね🌷",
    "おはよう！\n今日もよろしく〜☺️",
    "おはよ〜🌷\n今日も一日がんばろ〜",
    "おはよう☺️\n今日もよろしくね🙌",
    "おはよ〜！\n今日もいい日にしよ🫶",
]


def stable_int(key: str) -> int:
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"days": {}}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"days": {}}
    if not isinstance(data, dict):
        return {"days": {}}
    data.setdefault("days", {})
    return data


def save_state(state: dict) -> None:
    # 状態は直近60日だけ保持。
    days = state.setdefault("days", {})
    keys = sorted(days.keys())
    for old_key in keys[:-60]:
        days.pop(old_key, None)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def raw_skip(day) -> bool:
    return stable_int(f"rena-morning-skip|{day.isoformat()}") % SKIP_DIVISOR == 0


def published_count(state: dict) -> int:
    return sum(
        1
        for item in state.get("days", {}).values()
        if isinstance(item, dict) and item.get("status") == "published"
    )


def should_skip(day, state: dict) -> bool:
    # 最初の5回は必ず投稿。その後「たまに休む」。ただし2日連続では休まない。
    if published_count(state) < MIN_PUBLISHED_BEFORE_SKIP:
        return False
    return raw_skip(day) and not raw_skip(day - timedelta(days=1))


def delay_minutes(day) -> int:
    return stable_int(f"rena-morning-delay|{day.isoformat()}") % (MAX_DELAY_MINUTES + 1)


def choose_text(day, state: dict) -> str:
    start = stable_int(f"rena-morning-text|{day.isoformat()}") % len(MORNING_TEXTS)

    # 直近7件と同じ文面を避ける。
    recent = []
    for key in sorted(state.get("days", {}).keys(), reverse=True):
        item = state["days"].get(key) or {}
        if item.get("status") == "published" and item.get("text"):
            recent.append(item["text"])
        if len(recent) >= 7:
            break

    for offset in range(len(MORNING_TEXTS)):
        candidate = MORNING_TEXTS[(start + offset) % len(MORNING_TEXTS)]
        if candidate not in recent:
            return candidate
    return MORNING_TEXTS[start]


def extract_post(payload: dict) -> dict:
    post = ((payload or {}).get("result") or {}).get("post") or {}
    if post.get("status") != "sent":
        raise RuntimeError(f"Morning post was not confirmed sent: {post}")
    if not post.get("externalLink"):
        raise RuntimeError(f"Morning post has no externalLink: {post}")
    return post


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = datetime.now(JST)
    day = now.date()
    day_key = day.isoformat()
    state = load_state()
    existing = state.get("days", {}).get(day_key)

    if existing and existing.get("status") in {"published", "skipped"}:
        print(json.dumps({"ok": True, "action": "already_done", "state": existing}, ensure_ascii=False, indent=2))
        return

    skip = should_skip(day, state)
    delay = delay_minutes(day)
    text = choose_text(day, state)
    planned_time = f"{9 + ((50 + delay) // 60):02d}:{(50 + delay) % 60:02d}"

    plan = {
        "date_jst": day_key,
        "planned_time_jst": planned_time,
        "delay_minutes": delay,
        "skip": skip,
        "text": text,
        "target": "renatotaikun",
    }

    if args.dry_run:
        print(json.dumps({"ok": True, "action": "dry_run", "plan": plan}, ensure_ascii=False, indent=2))
        return

    if skip:
        state.setdefault("days", {})[day_key] = {
            "status": "skipped",
            "reason": "occasional_rest_day",
            "planned_time_jst": planned_time,
        }
        save_state(state)
        print(json.dumps({"ok": True, "action": "skipped", "plan": plan}, ensure_ascii=False, indent=2))
        return

    if delay:
        time.sleep(delay * 60)

    payload = publish_post(text)
    post = extract_post(payload)

    state.setdefault("days", {})[day_key] = {
        "status": "published",
        "planned_time_jst": planned_time,
        "text": text,
        "buffer_post_id": post.get("id"),
        "sent_at": post.get("sentAt"),
        "external_link": post.get("externalLink"),
    }
    save_state(state)

    print(
        json.dumps(
            {
                "ok": True,
                "action": "published",
                "channel": payload.get("channel"),
                "post": post,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
