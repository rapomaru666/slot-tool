import json
import os
import urllib.request

API_URL = "https://api.buffer.com"
TARGET_CHANNEL_ID = "6a9b8207065799be468fa585"
TARGET_HANDLE = "renatotaikun"
PROTECTED_OTHER_CHANNEL_IDS = {"6a818a27ccaf649a67b736f1": "rapomaru777"}


def _norm(value):
    return str(value or "").lstrip("@").strip().lower()


def graphql(query: str):
    token = os.environ["BUFFER_API_KEY"]
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]


def get_rena_channel():
    if TARGET_CHANNEL_ID in PROTECTED_OTHER_CHANNEL_IDS:
        raise RuntimeError("Rena target channel ID collides with a protected non-Rena channel")

    orgs = graphql("query { account { organizations { id name } } }")["account"]["organizations"]
    matches = []
    for org in orgs:
        q = f'''query {{ channels(input: {{ organizationId: "{org['id']}" }}) {{ id name displayName service }} }}'''
        for channel in graphql(q)["channels"]:
            if str(channel.get("id")) == TARGET_CHANNEL_ID:
                matches.append(channel)

    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one Rena channel id={TARGET_CHANNEL_ID}, found {len(matches)}")

    channel = matches[0]
    if channel.get("service") != "twitter":
        raise RuntimeError("Rena target channel is not X/Twitter")

    names = {_norm(channel.get("name")), _norm(channel.get("displayName"))}
    if TARGET_HANDLE not in names:
        raise RuntimeError(f"Rena channel identity mismatch: expected @{TARGET_HANDLE}, got {channel}")

    if str(channel.get("id")) in PROTECTED_OTHER_CHANNEL_IDS:
        raise RuntimeError("Refusing to use protected non-Rena channel")

    return channel


def publish_post(text: str, image_url: str | None = None):
    channel = get_rena_channel()
    text = str(text).strip()
    if not text:
        raise RuntimeError("Post text is empty")

    escaped_text = json.dumps(text, ensure_ascii=False)
    assets = ""
    if image_url:
        escaped_image = json.dumps(str(image_url).strip())
        assets = f"assets: [{{ image: {{ url: {escaped_image} }} }}]"

    mutation = f'''mutation PublishRenaNow {{
      createPost(input: {{
        text: {escaped_text}
        channelId: "{TARGET_CHANNEL_ID}"
        schedulingType: automatic
        mode: shareNow
        saveToDraft: false
        {assets}
      }}) {{
        ... on PostActionSuccess {{
          post {{ id text status sentAt sharedNow externalLink assets {{ id mimeType source }} }}
        }}
        ... on MutationError {{ message }}
      }}
    }}'''
    result = graphql(mutation)["createPost"]
    if result.get("message"):
        raise RuntimeError(result["message"])
    return {"channel": channel, "result": result}


def quote_post(tweet_id: str, comment: str):
    channel = get_rena_channel()
    tweet_id = str(tweet_id).strip()
    comment = str(comment).strip()
    if not tweet_id.isdigit():
        raise RuntimeError("Quote target tweet ID must be numeric")
    if not comment:
        raise RuntimeError("Quote comment is empty")

    escaped_comment = json.dumps(comment, ensure_ascii=False)
    mutation = f'''mutation QuoteRenaPost {{
      createPost(input: {{
        text: {escaped_comment}
        channelId: "{TARGET_CHANNEL_ID}"
        schedulingType: automatic
        mode: shareNow
        saveToDraft: false
        metadata: {{
          twitter: {{
            retweet: {{
              id: "{tweet_id}"
              comment: {escaped_comment}
            }}
          }}
        }}
      }}) {{
        ... on PostActionSuccess {{
          post {{ id text status sentAt sharedNow externalLink }}
        }}
        ... on MutationError {{ message }}
      }}
    }}'''
    result = graphql(mutation)["createPost"]
    if result.get("message"):
        raise RuntimeError(result["message"])
    return {"channel": channel, "result": result}
