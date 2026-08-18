import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
START_DATE = datetime(2026, 8, 18, tzinfo=JST).date()
API_URL = "https://api.buffer.com"
TARGET_NAME = "rapomaru777"
PUBLISHED_PATH = Path("x-auto/morning-published.json")
MAX_CHARS = 280

RANKING_PATTERNS = [
    r"\d+位",
    r"ランキング",
    r"順位",
    r"🌈[①②③④⑤⑥⑦⑧⑨⑩]",
]


def graphql(query: str):
    token = os.environ["BUFFER_API_KEY"]
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RAPOMARU-X-Auto/1.0)",
            "Accept-Language": "ja,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def rainbow_halls(thread):
    halls = []
    active = False
    for raw_line in thread.get("root", "").splitlines():
        line = raw_line.strip()
        if line == "🌈":
            active = True
            continue
        if line == "🏆":
            active = False
            continue
        if active and "｜" in line:
            halls.append(line.split("｜", 1)[0].strip())
            continue

        # Current scored format: "🌈1位 店名 20.0点"
        scored = re.match(
            r"^🌈\s*(?:\d+位\s+)?(.+?)\s+\d+(?:\.\d+)?点\s*$",
            line,
        )
        if scored:
            halls.append(scored.group(1).strip())

    # Preserve source order and prevent duplicate posts.
    return list(dict.fromkeys(halls))


def find_result_text(html, hall):
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
    p = text.find(hall)
    if p < 0:
        return None
    chunk = text[p : p + 900]
    nums = []
    for pat, label in [
        (r"平均[^+\-\d]{0,12}([+\-]?\d[\d,]*)\s*枚", "平均差枚"),
        (r"勝率[^\d]{0,8}(\d+(?:\.\d+)?)%", "勝率"),
        (r"平均[^\d]{0,12}(\d[\d,]*)\s*G", "平均G"),
    ]:
        m = re.search(pat, chunk)
        if m:
            nums.append(
                f"{label}{m.group(1)}"
                f"{'%' if label == '勝率' else ('G' if label == '平均G' else '枚')}"
            )
    return " / ".join(nums) if nums else "公開結果ページ掲載を確認"


def fit_280(text):
    if len(text) <= MAX_CHARS:
        return text
    suffix = "…\n#スロット"
    text = text[: MAX_CHARS - len(suffix)] + suffix
    if len(text) > MAX_CHARS:
        raise RuntimeError(f"Morning post exceeds {MAX_CHARS} characters")
    return text


def validate_post(text):
    if "答え合わせ" in text or "🌈Result" not in text:
        raise RuntimeError("Morning label must be 🌈Result; 答え合わせ is forbidden")
    if len(text) > MAX_CHARS:
        raise RuntimeError(f"Refusing to publish {len(text)} characters")
    for pattern in RANKING_PATTERNS:
        if re.search(pattern, text):
            raise RuntimeError(f"Ranking expression is forbidden: {pattern}")


def get_channel():
    orgs = graphql(
        "query GetOrganizations { account { organizations { id name } } }"
    )["account"]["organizations"]
    for org in orgs:
        channels = graphql(
            f'''query GetChannels {{ channels(input: {{ organizationId: "{org['id']}" }}) {{ id name displayName service }} }}'''
        )["channels"]
        for c in channels:
            if c.get("service") == "twitter" and TARGET_NAME.lower() in {
                str(c.get("name", "")).lower(),
                str(c.get("displayName", "")).lower(),
            }:
                return c
    raise RuntimeError("X channel not found")


def publish(text, channel):
    text = fit_280(text)
    validate_post(text)
    escaped = json.dumps(text, ensure_ascii=False)
    result = graphql(
        f'''mutation PublishNow {{ createPost(input: {{ text: {escaped}, channelId: "{channel['id']}", schedulingType: automatic, mode: shareNow, saveToDraft: false }}) {{ ... on PostActionSuccess {{ post {{ id status sentAt externalLink }} }} ... on MutationError {{ message }} }} }}'''
    )["createPost"]
    if result.get("message"):
        raise RuntimeError(result["message"])
    return result, text


def main():
    today = datetime.now(JST).date()
    if today < START_DATE:
        print("Morning reports have not started yet")
        return

    target = today - timedelta(days=1)
    thread_path = Path(f"x-auto/thread-{target.isoformat()}.json")
    if not thread_path.exists():
        raise RuntimeError(f"Prediction thread missing: {thread_path}")

    thread = json.loads(thread_path.read_text(encoding="utf-8"))
    halls = rainbow_halls(thread)
    if not halls:
        print("No rainbow halls; no morning report required")
        return

    history = (
        json.loads(PUBLISHED_PATH.read_text(encoding="utf-8"))
        if PUBLISHED_PATH.exists()
        else {}
    )
    if target.isoformat() in history:
        print("Morning report already published")
        return

    urls = [
        f"https://hall-navi.com/osusume_list?ymd={target.isoformat()}",
        f"https://hall-navi.com/?ymd={target.isoformat()}",
    ]
    pages = []
    for url in urls:
        for attempt in range(3):
            try:
                pages.append((url, fetch(url)))
                break
            except Exception:
                if attempt < 2:
                    time.sleep(5)

    channel = get_channel()
    posts = []
    all_sources = []

    for hall in halls:
        found = None
        source = None
        for url, html in pages:
            found = find_result_text(html, hall)
            if found:
                source = url
                break

        if not found:
            found = "8時時点で数値結果を確認できず（掲載確認継続）"

        text = (
            f"🌈Result {target.month}/{target.day}\n"
            f"🌈 {hall}\n"
            f"{found}\n"
            "#スロット #パチスロ"
        )
        result, posted_text = publish(text, channel)
        posts.append(
            {
                "hall": hall,
                "text": posted_text,
                "chars": len(posted_text),
                "buffer": result,
                "source": source,
            }
        )
        if source:
            all_sources.append(source)
        time.sleep(10)

    history[target.isoformat()] = {
        "reported_at_jst": datetime.now(JST).isoformat(),
        "halls": halls,
        "posts": posts,
        "sources": sorted(set(all_sources)),
    }
    PUBLISHED_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "target": target.isoformat(),
                "post_count": len(posts),
                "posts": [
                    {"hall": p["hall"], "chars": p["chars"]} for p in posts
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
