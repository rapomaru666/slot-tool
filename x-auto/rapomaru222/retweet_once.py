import json
import os
import re
import urllib.request
from pathlib import Path

API_URL = "https://api.buffer.com"
TARGET_HANDLE = "rapomaru222"
TRIGGER_FILE = Path("x-auto/rapomaru222/retweet-trigger.txt")


def graphql(query: str):
    token = os.environ["BUFFER_API_KEY"]
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]


def source_tweet_id():
    text = TRIGGER_FILE.read_text(encoding="utf-8").strip()
    match = re.search(r"(?:status/)?(\d{10,25})", text)
    if not match:
        raise RuntimeError(f"No X status ID found in {TRIGGER_FILE}: {text!r}")
    return match.group(1)


def get_channel():
    orgs = graphql("query { account { organizations { id name } } }")["account"]["organizations"]
    matches = []
    twitter_channels = []
    for org in orgs:
        q = f'''query {{ channels(input: {{ organizationId: "{org['id']}" }}) {{ id name displayName service }} }}'''
        for channel in graphql(q)["channels"]:
            if channel.get("service") != "twitter":
                continue
            twitter_channels.append(channel)
            names = {
                str(channel.get("name", "")).lstrip("@").lower(),
                str(channel.get("displayName", "")).lstrip("@").lower(),
            }
            if TARGET_HANDLE in names:
                matches.append(channel)
    print("BUFFER_X_CHANNELS=" + json.dumps(twitter_channels, ensure_ascii=False))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one @{TARGET_HANDLE} Buffer channel, found {len(matches)}")
    return matches[0]


def main():
    source_id = source_tweet_id()
    channel = get_channel()
    tweet_id = json.dumps(source_id)
    mutation = f'''mutation RetweetRapomaru222 {{
      createPost(input: {{
        text: ""
        channelId: "{channel['id']}"
        schedulingType: automatic
        mode: shareNow
        saveToDraft: false
        metadata: {{ twitter: {{ retweet: {{ id: {tweet_id}, comment: "" }} }} }}
      }}) {{
        ... on PostActionSuccess {{ post {{ id text status sentAt sharedNow externalLink }} }}
        ... on MutationError {{ message }}
      }}
    }}'''
    result = graphql(mutation)["createPost"]
    if result.get("message"):
        raise RuntimeError(result["message"])
    print(json.dumps({"ok": True, "channel": channel, "source_tweet_id": source_id, "result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
