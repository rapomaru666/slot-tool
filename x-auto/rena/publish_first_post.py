import json
import os
import urllib.request

API_URL = "https://api.buffer.com"
TOKEN = os.environ["BUFFER_API_KEY"]
TARGET_HANDLE = "renatotaikun"
IMAGE_URL = "https://static.metricool.com/planner/202609/6760386-file-11754633307708686853.jpeg"
TEXT = """X始めました〜！🙌✨

いろんな人とたくさん話せたらうれしいです☺️
気軽に話しかけてください🫶

よろしくお願いします！"""


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
    orgs = graphql("query { account { organizations { id name } } }")["account"]["organizations"]
    for org in orgs:
        q = f'''query {{ channels(input: {{ organizationId: "{org['id']}" }}) {{ id name displayName service }} }}'''
        for channel in graphql(q)["channels"]:
            if channel.get("service") != "twitter":
                continue
            name = str(channel.get("name", "")).lstrip("@").lower()
            display = str(channel.get("displayName", "")).lstrip("@").lower()
            if TARGET_HANDLE in {name, display}:
                return channel
    raise RuntimeError("Rena X channel @renatotaikun is not connected to Buffer")


def publish(channel):
    text = json.dumps(TEXT, ensure_ascii=False)
    image = json.dumps(IMAGE_URL)
    mutation = f'''mutation PublishRenaFirstPost {{
      createPost(input: {{
        text: {text}
        channelId: "{channel['id']}"
        schedulingType: automatic
        mode: shareNow
        saveToDraft: false
        assets: [{{ image: {{ url: {image} }} }}]
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
    return result


channel = get_channel()
result = publish(channel)
print(json.dumps({"ok": True, "channel": channel, "result": result}, ensure_ascii=False, indent=2))
