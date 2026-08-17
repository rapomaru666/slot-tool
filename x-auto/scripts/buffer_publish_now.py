import json
import os
import urllib.request
from pathlib import Path

API_URL = "https://api.buffer.com"
TOKEN = os.environ["BUFFER_API_KEY"]
TARGET_NAME = "rapomaru777"
QUOTE_PATH = Path("x-auto/quote-now.json")
QUEUE_PATH = "x-auto/queue.json"
TARGET_ID = "2026-08-17-kanto-pick"
MAX_CHARS = 280


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


def get_channel():
    orgs = graphql("""
    query GetOrganizations {
      account { organizations { id name } }
    }
    """)["account"]["organizations"]
    if not orgs:
        raise RuntimeError("No Buffer organization found")

    for org in orgs:
        q = f'''query GetChannels {{
          channels(input: {{ organizationId: "{org['id']}" }}) {{
            id name displayName service
          }}
        }}'''
        channels = graphql(q)["channels"]
        for c in channels:
            names = {
                str(c.get("name", "")).lower(),
                str(c.get("displayName", "")).lower(),
            }
            if c.get("service") == "twitter" and TARGET_NAME.lower() in names:
                return c
    raise RuntimeError("X channel rapomaru777 not found in Buffer")


def publish_quote(config, channel):
    text = str(config["text"]).strip()
    tweet_id = str(config["quote_tweet_id"]).strip()
    if not tweet_id.isdigit():
        raise RuntimeError("quote_tweet_id must be numeric")
    if len(text) > MAX_CHARS:
        raise RuntimeError(f"Refusing to publish {len(text)} characters")

    escaped_text = json.dumps(text, ensure_ascii=False)
    escaped_id = json.dumps(tweet_id)
    mutation = f'''mutation PublishQuoteNow {{
      createPost(input: {{
        text: {escaped_text},
        channelId: "{channel['id']}",
        schedulingType: automatic,
        mode: shareNow,
        saveToDraft: false,
        metadata: {{
          twitter: {{
            retweet: {{ id: {escaped_id}, comment: {escaped_text} }}
          }}
        }}
      }}) {{
        ... on PostActionSuccess {{
          post {{ id text status sentAt sharedNow shareMode externalLink metadata {{ ... on TwitterPostMetadata {{ retweet {{ id url text }} }} }} }}
        }}
        ... on MutationError {{ message }}
      }}
    }}'''
    result = graphql(mutation)["createPost"]
    if result.get("message"):
        raise RuntimeError(result["message"])
    return result


def publish_plain(channel):
    with open(QUEUE_PATH, encoding="utf-8") as f:
        queue = json.load(f)
    item = next((x for x in queue if x.get("id") == TARGET_ID), None)
    if not item:
        raise RuntimeError("Target queue item not found")
    text = item["text"]
    if len(text) > MAX_CHARS:
        raise RuntimeError(f"Refusing to publish {len(text)} characters")

    escaped = json.dumps(text, ensure_ascii=False)
    mutation = f'''mutation PublishNow {{
      createPost(input: {{
        text: {escaped},
        channelId: "{channel['id']}",
        schedulingType: automatic,
        mode: shareNow,
        saveToDraft: false
      }}) {{
        ... on PostActionSuccess {{
          post {{ id text status sentAt sharedNow shareMode externalLink }}
        }}
        ... on MutationError {{ message }}
      }}
    }}'''
    result = graphql(mutation)["createPost"]
    if result.get("message"):
        raise RuntimeError(result["message"])
    return result


channel = get_channel()

if QUOTE_PATH.exists():
    config = json.loads(QUOTE_PATH.read_text(encoding="utf-8"))
    if config.get("enabled"):
        result = publish_quote(config, channel)
        print(json.dumps({"ok": True, "mode": "quote", "channel": channel, "result": result}, ensure_ascii=False))
        raise SystemExit(0)

result = publish_plain(channel)
print(json.dumps({"ok": True, "mode": "plain", "channel": channel, "result": result}, ensure_ascii=False))
