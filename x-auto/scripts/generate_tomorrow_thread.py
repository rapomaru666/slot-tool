import json
import os
import re
import time
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
MIN_POST_COUNT = 1
MIN_POST_CHARS = 200
MAX_POST_CHARS = 250
PREFECTURES = ("東京都", "神奈川県", "埼玉県", "千葉県", "茨城県", "栃木県", "群馬県")
AUDIT_DIR = Path("x-auto/audit")


def target_date():
    override = os.getenv("TARGET_DATE", "").strip()
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return datetime.now(JST).date() + timedelta(days=1)


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; RAPOMARU-X-Auto/1.1)",
                    "Accept-Language": "ja,en;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                return res.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 5)
    raise RuntimeError(f"fetch failed after {attempts} attempts: {last_error}")


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
    if not candidates:
        return None

    rainbow = [c for c in candidates if c["score"] >= RAINBOW_MIN][:MAX_RAINBOW]
    trophy = [c for c in candidates if TROPHY_MIN <= c["score"] < RAINBOW_MIN][:MAX_TROPHY]
    selected = rainbow + trophy
    fallback = []

    # 絶対評価基準に届く店が0件でも、その日の最上位候補を最低1店舗は掲載する。
    if len(selected) < MIN_POST_COUNT:
        already = {c["hall"] for c in selected}
        for c in candidates:
            if c["hall"] not in already:
                fallback.append(c)
                selected.append(c)
                already.add(c["hall"])
            if len(selected) >= MIN_POST_COUNT:
                break

    weekday = "月火水木金土日"[target.weekday()]
    header = [f"🎰{target.month}/{target.day}({weekday}) 関東注目", "らぽまる太郎狙い目"]
    tail = ["公開スケジュール・過去傾向を総合評価。取材重複・旧イベ日・過去レポートを重視。", "#スロット #パチスロ"]

    def mark_for(c):
        if c["score"] >= RAINBOW_MIN:
            return "🌈"
        if c["score"] >= TROPHY_MIN:
            return "🏆"
        return "🎯"

    def render_root(items, detail_limit=26):
        lines = header[:]
        for c in items:
            lines.append(
                f"{mark_for(c)}{c['hall']}｜{short_detail(c['details'], detail_limit)} {c['score']:.1f}"
            )
        lines.extend(tail)
        return "\n".join(lines)

    root = render_root(selected)

    # 250文字を超える場合は低評価側から減らし、それでも長い場合は説明を短くする。
    while len(root) > MAX_POST_CHARS and len(selected) > MIN_POST_COUNT:
        selected.pop()
        root = render_root(selected)

    if len(root) > MAX_POST_CHARS:
        root = render_root(selected, detail_limit=12)

    if len(root) > MAX_POST_CHARS:
        c = selected[0]
        root = "\n".join(
            header
            + [f"{mark_for(c)}{c['hall']}｜公開評価{c['score']:.1f}点"]
            + tail
        )

    # 200文字未満なら上位候補の根拠を追加。意味のある公開情報だけで埋める。
    if len(root) < MIN_POST_CHARS:
        notes = []
        for c in selected[:3]:
            notes.append(
                f"{c['hall']}は公開評価{c['score']:.1f}点、{short_detail(c['details'], 44)}を確認。"
            )
        notes.extend([
            "当日の取材強度だけでなく、過去の営業傾向と重複要素も合わせて見る。",
            "数値は公開情報を基にした事前評価で、当日の状況は入場前にも確認したい。",
        ])

        lines = root.split("\n")
        hashtags = lines.pop() if lines and lines[-1].startswith("#") else "#スロット #パチスロ"
        base = "\n".join(lines)
        for note in notes:
            candidate = base + "\n" + note + "\n" + hashtags
            if len(candidate) <= MAX_POST_CHARS:
                base = base + "\n" + note
                root = base + "\n" + hashtags
            elif len(root) < MIN_POST_CHARS:
                room = MAX_POST_CHARS - len(base) - len(hashtags) - 2
                if room > 12:
                    clipped = note[:room]
                    base = base + "\n" + clipped
                    root = base + "\n" + hashtags
            if len(root) >= MIN_POST_CHARS:
                break

    if not MIN_POST_CHARS <= len(root) <= MAX_POST_CHARS:
        raise RuntimeError(
            f"generated root must be {MIN_POST_CHARS}-{MAX_POST_CHARS} characters: {len(root)}"
        )

    # 自動生成は本文1本に絞る。手動確定threadでは200〜250文字のリプ追加可。
    return {"root": root, "replies": []}


def main():
    target = target_date()
    thread_path = Path(f"x-auto/thread-{target.isoformat()}.json")
    if thread_path.exists():
        print(json.dumps({"ok": True, "skipped": True, "reason": "thread_already_exists", "target_date": target.isoformat()}, ensure_ascii=False))
        return

    url = f"https://hall-navi.com/osusume_list?kbn=sche_yosou&ken=all&ymd={target.isoformat()}"
    html = fetch_html(url, attempts=3)
    candidates = parse_hall_navi(html, target)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit = {
        "target_date": target.isoformat(),
        "generated_at_jst": datetime.now(JST).isoformat(),
        "source_url": url,
        "thresholds": {"rainbow_min": RAINBOW_MIN, "trophy_min": TROPHY_MIN},
        "minimum_post_count": MIN_POST_COUNT,
        "post_chars": {"min": MIN_POST_CHARS, "max": MAX_POST_CHARS},
        "candidate_count": len(candidates),
        "candidates": candidates[:30],
    }
    audit_path = AUDIT_DIR / f"candidates-{target.isoformat()}.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    thread = build_thread(target, candidates)
    if thread is None:
        raise RuntimeError(f"No candidates found for {target.isoformat()}; do not silently skip. Investigation required.")

    for i, post in enumerate([thread["root"]] + thread.get("replies", []), start=1):
        if not MIN_POST_CHARS <= len(post) <= MAX_POST_CHARS:
            raise RuntimeError(
                f"generated post {i} must be {MIN_POST_CHARS}-{MAX_POST_CHARS} characters: {len(post)}"
            )

    thread_path.write_text(json.dumps(thread, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "target_date": target.isoformat(), "thread_path": str(thread_path), "candidate_count": len(candidates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
