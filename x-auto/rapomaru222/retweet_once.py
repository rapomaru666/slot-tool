import json
import os
import urllib.request

API_URL = "https://api.buffer.com"
TARGET_HANDLE = "rapomaru222"
SOURCE_TWEET_ID = "2049382736163639501"


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


def get_channel():
    orgs = graphql("query { account { organizations { id name } } }")["account"]["organizations"]
    matches = []
    for org in orgs:
        q = f'''query {{ channels(input: {{ organizationId: "{org['id']}" }}) {{ id name displayName service }} }}'''
        for channel in graphql(q)["channels"]:
            names = {str(channel.get("name", "")).lstrip("@").lower(), str(channel.get("displayName", "")).lstrip("@").lower()}
            if channel.get("service") == "twitter" and TARGET_HANDLE in names:
                matches.append(channel)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one @{TARGET_HANDLE} Buffer channel, found {len(matches)}: {matches}")
    return matches[0]


def main():
    channel = get_channel()
    tweet_id = json.dumps(SOURCE_TWEET_ID)
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
    print(json.dumps({"ok": True, "channel": channel, "source_tweet_id": SOURCE_TWEET_ID, "result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
