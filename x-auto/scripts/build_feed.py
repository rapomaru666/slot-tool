import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(__file__).resolve().parents[1]
QUEUE = BASE / "queue.json"
FEED = BASE / "feed.xml"
JST = timezone(timedelta(hours=9))


def parse_jst(value: str):
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=JST)


def main():
    posts = json.loads(QUEUE.read_text(encoding="utf-8"))
    now = datetime.now(JST)
    ready = []

    for post in posts:
        if post.get("status") != "ready":
            continue
        at = parse_jst(post.get("publish_at_jst", ""))
        if at and at <= now:
            ready.append((at, post))

    ready.sort(key=lambda x: x[0], reverse=True)

    items = []
    for at, post in ready[:20]:
        text = post["text"]
        guid = post["id"]
        pub = at.strftime("%a, %d %b %Y %H:%M:%S +0900")
        items.append(f"""    <item>\n      <title>{escape(guid)}</title>\n      <description>{escape(text)}</description>\n      <guid isPermaLink=\"false\">{escape(guid)}</guid>\n      <pubDate>{pub}</pubDate>\n    </item>""")

    xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\">\n  <channel>\n    <title>RAPOMARU X Auto Post</title>\n    <link>https://rapomaru666.github.io/slot-tool/x-auto/</link>\n    <description>Auto-post feed for @rapomaru777</description>\n{chr(10).join(items)}\n  </channel>\n</rss>\n"""
    FEED.write_text(xml, encoding="utf-8")


if __name__ == "__main__":
    main()
