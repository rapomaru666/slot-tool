import json
import os
import urllib.request

API_URL = "https://api.buffer.com"
TOKEN = os.environ["BUFFER_API_KEY"]
TARGET_NAME = "rapomaru777"
THREAD_PATH = "x-auto/thread-2026-08-17.json"


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


with open(THREAD_PATH, encoding="utf-8") as f:
    thread_data = json.load(f)

root = thread_data["root"]
posts = [root] + thread_data.get("replies", [])

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
      post {{ id status sentAt sharedNow shareMode externalLink threadCount }}
    }}
    ... on MutationError {{ message }}
  }}
}}'''

result = graphql(mutation)["createPost"]
if result.get("message"):
    raise RuntimeError(result["message"])
print(json.dumps({"ok": True, "channel": channel, "result": result}, ensure_ascii=False))
