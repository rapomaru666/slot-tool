import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_URL = "https://api.buffer.com"
TOKEN = os.environ["BUFFER_API_KEY"]
TARGET_NAME = "rapomaru777"
JST = timezone(timedelta(hours=9))
PUBLISHED_PATH = Path("x-auto/published.json")
MIN_POST_CHARS = 200
MAX_POST_CHARS = 250


def graphql(query: str):
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]


now_jst = datetime.now(JST)
event_name = os.environ.get("GITHUB_EVENT_NAME", "")
if event_name == "push":
    override_path = Path("x-auto/publish-target.txt")
    if override_path.exists() and override_path.read_text(encoding="utf-8").strip():
        target_date = override_path.read_text(encoding="utf-8").strip()
    else:
        target_date = now_jst.date().isoformat()
else:
    target_date = (now_jst.date() + timedelta(days=1)).isoformat()
thread_path = Path(f"x-auto/thread-{target_date}.json")

if not thread_path.exists():
    print(json.dumps({"ok": True, "skipped": True, "reason": "thread_file_not_found", "target_date": target_date}, ensure_ascii=False))
    raise SystemExit(0)

published = []
if PUBLISHED_PATH.exists():
    with PUBLISHED_PATH.open(encoding="utf-8") as f:
        published = json.load(f)

if any(item.get("target_date") == target_date and item.get("status") == "sent" for item in published):
    print(json.dumps({"ok": True, "skipped": True, "reason": "already_published", "target_date": target_date}, ensure_ascii=False))
    raise SystemExit(0)

with thread_path.open(encoding="utf-8") as f:
    thread_data = json.load(f)

root = thread_data["root"]
posts = [root] + thread_data.get("replies", [])
for index, text in enumerate(posts, start=1):
    if not MIN_POST_CHARS <= len(text) <= MAX_POST_CHARS:
        raise RuntimeError(
            f"Post {index} must be {MIN_POST_CHARS}-{MAX_POST_CHARS} characters: {len(text)}"
        )

orgs = graphql("""
query GetOrganizations {
  account { organizations { id name } }
}
""")["account"]["organizations"]
if not orgs:
    raise RuntimeError("No Buffer organization found")

channel = None
for org in orgs:
    q = f'''query GetChannels {{
      channels(input: {{ organizationId: "{org['id']}" }}) {{
        id name displayName service
      }}
    }}'''
    channels = graphql(q)["channels"]
    for c in channels:
        names = {str(c.get("name", "")).lower(), str(c.get("displayName", "")).lower()}
        if c.get("service") == "twitter" and TARGET_NAME.lower() in names:
            channel = c
            break
    if channel:
        break

if not channel:
    raise RuntimeError("X channel rapomaru777 not found in Buffer")

thread_items = ",\n".join(
    "{ text: " + json.dumps(text, ensure_ascii=False) + " }" for text in posts
)
root_escaped = json.dumps(root, ensure_ascii=False)
mutation = f'''mutation PublishThreadNow {{
  createPost(input: {{
    text: {root_escaped},
    channelId: "{channel['id']}",
    schedulingType: automatic,
    mode: shareNow,
    saveToDraft: false,
    metadata: {{
      twitter: {{
        thread: [
          {thread_items}
        ]
      }}
    }}
  }}) {{
    ... on PostActionSuccess {{
      post {{ id status sentAt sharedNow shareMode externalLink }}
    }}
    ... on MutationError {{ message }}
  }}
}}'''

result = graphql(mutation)["createPost"]
if result.get("message"):
    raise RuntimeError(result["message"])

post = result.get("post", {})
if post.get("status") != "sent":
    raise RuntimeError(f"Buffer did not confirm sent status: {json.dumps(result, ensure_ascii=False)}")

published.append({
    "target_date": target_date,
    "status": "sent",
    "sent_at": post.get("sentAt"),
    "external_link": post.get("externalLink"),
    "buffer_post_id": post.get("id"),
})
PUBLISHED_PATH.write_text(json.dumps(published, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(json.dumps({"ok": True, "target_date": target_date, "channel": channel, "result": result}, ensure_ascii=False))
