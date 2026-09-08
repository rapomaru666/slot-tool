from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))


def determine_target_date() -> str:
    now_jst = datetime.now(JST)
    if os.environ.get("GITHUB_EVENT_NAME") == "push":
        override = Path("x-auto/publish-target.txt")
        if override.exists() and override.read_text(encoding="utf-8").strip():
            return override.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        return now_jst.date().isoformat()
    override = os.environ.get("TARGET_DATE", "").strip()
    return override or (now_jst.date() + timedelta(days=1)).isoformat()


def sanitize_public_text(text: str) -> str:
    # Internal RAPOMARU scores must never appear in public posts.
    text = re.sub(r"\s+\d{1,2}\.\d(?=\n|$)", "", text)
    text = re.sub(r"公開評価\s*\d{1,2}\.\d\s*点[、,]?\s*", "", text)
    text = re.sub(r"数値は公開情報を基にした事前評価で、?", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def rainbow_reply(target_date: str, hall: dict) -> str:
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    name = str(hall.get("name", "")).strip()
    details = re.sub(r"\s+", " ", str(hall.get("details", "")).strip())
    if len(details) > 120:
        details = details[:119] + "…"
    lines = [
        f"🌈{name}",
        f"{target.month}/{target.day}の個別メモ。",
    ]
    if details:
        lines.append(f"公開スケジュール・過去傾向で「{details}」を確認。")
    lines.extend([
        "確認できた公開情報だけで選定。根拠のない機種推奨はしません。",
        "#スロット #パチスロ",
    ])
    return "\n".join(lines)


def main() -> None:
    target_date = determine_target_date()
    path = Path(f"x-auto/thread-{target_date}.json")
    if not path.exists():
        raise RuntimeError(f"Required thread file is missing: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    data["root"] = sanitize_public_text(str(data.get("root", "")))

    selected = data.get("selected_halls") or []
    rainbow = [h for h in selected if str(h.get("category", "")).strip() == "rainbow"]
    data["replies"] = [rainbow_reply(target_date, hall) for hall in rainbow]

    public_posts = [data["root"]] + data["replies"]
    joined = "\n".join(public_posts)
    if re.search(r"公開評価\s*\d{1,2}\.\d\s*点", joined):
        raise RuntimeError("Internal score leaked into public post text")
    for hall in rainbow:
        name = str(hall.get("name", "")).strip()
        count = sum(1 for reply in data["replies"] if name and name in reply)
        if count != 1:
            raise RuntimeError(f"Rainbow hall must have exactly one individual reply: {name}")

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "target_date": target_date,
        "rainbow_replies": len(data["replies"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
