import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from buffer_client import quote_post

JST = ZoneInfo("Asia/Tokyo")
CONFIG_PATH = Path(__file__).with_name("buzz-candidate.json")
STATE_PATH = Path(__file__).with_name("buzz-state.json")
MAX_DAILY = 2
COOLDOWN_HOURS = 4
MAX_AGE_HOURS = 3
MIN_VIEWS = 1_000_000
TARGET = "renatotaikun"


def parse_dt(value: str) -> datetime:
    value = str(value or "").strip()
    if not value:
        raise RuntimeError("source_created_at is required")
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def operational_day(now: datetime):
    # 24:00チェック（実際は翌日00:00）は前日の運用日として扱う。
    return (now - timedelta(days=1)).date() if now.hour == 0 else now.date()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return data


def save_state(state: dict):
    posts = state.setdefault("posts", [])
    posts.sort(key=lambda x: x.get("sent_at_jst") or "")
    state["posts"] = posts[-200:]
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_candidate(cfg: dict, now: datetime):
    if not cfg.get("enabled"):
        raise RuntimeError("Buzz candidate is disabled")
    if str(cfg.get("target") or "").strip().lstrip("@").lower() != TARGET:
        raise RuntimeError("Buzz target must be renatotaikun")

    tweet_id = str(cfg.get("quote_tweet_id") or "").strip()
    if not tweet_id.isdigit():
        raise RuntimeError("quote_tweet_id must be numeric")

    text = str(cfg.get("text") or "").strip()
    if not text:
        raise RuntimeError("Buzz quote text is empty")
    if len(text) > 80:
        raise RuntimeError("Buzz quote text is too long")
    if "#" in text:
        raise RuntimeError("Buzz quote text must not contain hashtags")

    try:
        views = int(cfg.get("source_views"))
    except (TypeError, ValueError):
        raise RuntimeError("source_views must be an integer")
    if views < MIN_VIEWS:
        raise RuntimeError(f"Source views below threshold: {views}")

    created = parse_dt(cfg.get("source_created_at"))
    age = now - created
    if age < timedelta(minutes=-5):
        raise RuntimeError("Source created time is in the future")
    if age > timedelta(hours=MAX_AGE_HOURS):
        raise RuntimeError(f"Source is older than {MAX_AGE_HOURS} hours")

    return tweet_id, text, views, created


def main():
    now = datetime.now(JST)
    cfg = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {"posts": []})
    posts = state.setdefault("posts", [])

    tweet_id, text, views, created = validate_candidate(cfg, now)
    op_day = operational_day(now).isoformat()

    if any(str(p.get("quote_tweet_id")) == tweet_id for p in posts):
        raise RuntimeError("This source tweet has already been quoted")

    today_posts = [p for p in posts if p.get("operational_day") == op_day and p.get("status") == "sent"]
    if len(today_posts) >= MAX_DAILY:
        raise RuntimeError("Daily Rena buzz quote limit reached")

    sent_times = []
    for p in posts:
        if p.get("status") != "sent" or not p.get("sent_at_jst"):
            continue
        try:
            sent_times.append(parse_dt(p["sent_at_jst"]))
        except Exception:
            pass
    if sent_times:
        last = max(sent_times)
        if now - last < timedelta(hours=COOLDOWN_HOURS):
            raise RuntimeError("Rena buzz quote cooldown is still active")

    payload = quote_post(tweet_id, text)
    post = ((payload or {}).get("result") or {}).get("post") or {}
    if post.get("status") != "sent" or not post.get("externalLink"):
        raise RuntimeError(f"Buzz quote was not confirmed sent: {post}")

    posts.append({
        "operational_day": op_day,
        "quote_tweet_id": tweet_id,
        "text": text,
        "source_url": cfg.get("source_url"),
        "source_views": views,
        "source_created_at": created.isoformat(),
        "checked_at_jst": cfg.get("checked_at_jst"),
        "status": "sent",
        "buffer_post_id": post.get("id"),
        "sent_at_jst": now.isoformat(),
        "external_link": post.get("externalLink"),
    })
    save_state(state)

    print(json.dumps({"ok": True, "channel": payload.get("channel"), "post": post}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
