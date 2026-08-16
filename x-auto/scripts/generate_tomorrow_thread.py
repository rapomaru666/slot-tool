import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError as exc:
    raise RuntimeError("beautifulsoup4 is required") from exc

JST = timezone(timedelta(hours=9))
RAINBOW_MIN = 16.0
TROPHY_MIN = 14.0
MAX_RAINBOW = 3
MAX_TROPHY = 2
PREFECTURES = ("東京都", "神奈川県", "埼玉県", "千葉県", "茨城県", "栃木県", "群馬県")
AUDIT_DIR = Path("x-auto/audit")


def target_date():
    override = os.getenv("TARGET_DATE", "").strip()
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return datetime.now(JST).date() + timedelta(days=1)


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RAPOMARU-X-Auto/1.0)",
            "Accept-Language": "ja,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_hall_navi(html: str, target) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    text = compact(soup.get_text(" ", strip=True))
    target_label = target.strftime("%Y/%m/%d")
    pattern = re.compile(
        r"(?P<score>\d{1,2}\.\d)点\s+"
        r"(?P<date>\d{4}/\d{2}/\d{2}\([^)]+\))\s+"
        r"(?P<body>.*?)"
        r"(?=(?:\d{1,2}\.\d点\s+\d{4}/\d{2}/\d{2}\()|全\d+件|※一部|$)"
    )
    candidates = []
    seen = set()
    for match in pattern.finditer(text):
        if not match.group("date").startswith(target_label):
            continue
        score = float(match.group("score"))
        body = compact(match.group("body"))
        parsed = re.match(r"(?P<hall>.+?)\s+(?P<rank>S|A|B|C)\s+(?P<details>.+)", body)
        if not parsed:
            continue
        hall = compact(parsed.group("hall"))
        if hall in PREFECTURES or hall.endswith("県") or hall == "東京都":
            continue
        if hall.startswith("Image "):
            hall = re.sub(r"^Image\s+\d+\s+", "", hall)
        if not hall or hall in seen:
            continue
        details = compact(parsed.group("details"))
        for pref in PREFECTURES:
            pos = details.find(pref)
            if pos > 0:
                details = details[:pos].strip()
                break
        details = re.sub(r"\s+評価\s+\+.*$", "", details).strip()
        if not details:
            details = "公開スケジュール・過去傾向を総合評価"
        candidates.append({
            "hall": hall,
            "score": score,
            "rank": parsed.group("rank"),
            "details": details,
            "source": "hall-navi",
        })
        seen.add(hall)
    candidates.sort(key=lambda x: (-x["score"], x["hall"]))
    return candidates


def short_detail(text: str, limit: int = 28) -> str:
    text = compact(text)
    replacements = {
        "ナビ子AI予想〖機種仕掛け〗": "AI機種仕掛け予想",
        "ナビ子AI予想〖差枚プラス〗": "AI差枚プラス予想",
        "スロパチステーション来店取材": "スロパチ来店取材",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_thread(target, candidates: list[dict]) -> dict | None:
    rainbow = [c for c in candidates if c["score"] >= RAINBOW_MIN][:MAX_RAINBOW]
    trophy = [c for c in candidates if TROPHY_MIN <= c["score"] < RAINBOW_MIN][:MAX_TROPHY]
    selected = rainbow + trophy
    if not selected:
        return None

    weekday = "月火水木金土日"[target.weekday()]
    header = [f"🎰{target.month}/{target.day}({weekday}) 関東近郊", "らぽまる太郎狙い目"]
    tail = ["#スロット #パチスロ"]
    lines = header[:]
    if rainbow:
        lines.append("🌈")
        for c in rainbow:
            lines.append(f"{c['hall']}｜{short_detail(c['details'])}")
    if trophy:
        lines.append("🏆")
        for c in trophy:
            lines.append(f"{c['hall']}｜{short_detail(c['details'])}")

    root = "\n".join(lines + tail)
    while len(root) > 280 and selected:
        last = selected.pop()
        if last in trophy:
            trophy.remove(last)
        elif last in rainbow:
            rainbow.remove(last)
        lines = header[:]
        if rainbow:
            lines.append("🌈")
            lines.extend(f"{c['hall']}｜{short_detail(c['details'])}" for c in rainbow)
        if trophy:
            lines.append("🏆")
            lines.extend(f"{c['hall']}｜{short_detail(c['details'])}" for c in trophy)
        root = "\n".join(lines + tail)
    if not selected or len(root) > 280:
        return None

    replies = []
    for index, c in enumerate(selected[:3], start=1):
        mark = "🌈" if c["score"] >= RAINBOW_MIN else "🏆"
        detail = compact(c["details"])
        reply = f"{mark}{index} {c['hall']}\n公開評価{c['score']:.1f}点。{detail}\n※公開スケジュール・過去傾向を基に自動抽出。"
        if len(reply) > 280:
            reply = reply[:279] + "…"
        replies.append(reply)
    return {"root": root, "replies": replies}


def main():
    target = target_date()
    thread_path = Path(f"x-auto/thread-{target.isoformat()}.json")
    if thread_path.exists():
        print(json.dumps({"ok": True, "skipped": True, "reason": "thread_already_exists", "target_date": target.isoformat()}, ensure_ascii=False))
        return

    url = f"https://hall-navi.com/osusume_list?kbn=sche_yosou&ken=all&ymd={target.isoformat()}"
    try:
        html = fetch_html(url)
        candidates = parse_hall_navi(html, target)
    except Exception as exc:
        print(json.dumps({"ok": False, "reason": "source_fetch_or_parse_failed", "target_date": target.isoformat(), "error": str(exc)}, ensure_ascii=False))
        raise

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit = {
        "target_date": target.isoformat(),
        "generated_at_jst": datetime.now(JST).isoformat(),
        "source_url": url,
        "thresholds": {"rainbow_min": RAINBOW_MIN, "trophy_min": TROPHY_MIN},
        "candidates": candidates[:30],
    }
    audit_path = AUDIT_DIR / f"candidates-{target.isoformat()}.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    thread = build_thread(target, candidates)
    if thread is None:
        print(json.dumps({"ok": True, "skipped": True, "reason": "no_absolute_threshold_candidates", "target_date": target.isoformat(), "candidate_count": len(candidates)}, ensure_ascii=False))
        return

    for i, post in enumerate([thread["root"]] + thread.get("replies", []), start=1):
        if len(post) > 280:
            raise RuntimeError(f"generated post {i} exceeds 280 characters: {len(post)}")

    thread_path.write_text(json.dumps(thread, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "target_date": target.isoformat(), "thread_path": str(thread_path), "candidate_count": len(candidates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
