import json
from pathlib import Path

from buffer_client import TARGET_HANDLE, publish_post, quote_post

CONFIG_PATH = Path("x-auto/rena/post-now.json")


def load_config():
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Missing config: {CONFIG_PATH}")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    if config.get("enabled") is not True:
        raise RuntimeError("Rena post config is not enabled")
    if str(config.get("target", "")).lstrip("@").lower() != TARGET_HANDLE:
        raise RuntimeError(f"Refusing target other than @{TARGET_HANDLE}")

    text = str(config.get("text", "")).strip()
    image_url = config.get("image_url")
    quote_tweet_id = config.get("quote_tweet_id")
    if not text:
        raise RuntimeError("Rena post text is empty")
    if image_url and quote_tweet_id:
        raise RuntimeError("Use either image_url or quote_tweet_id, not both")
    return text, image_url, quote_tweet_id


text, image_url, quote_tweet_id = load_config()
if quote_tweet_id:
    output = quote_post(quote_tweet_id, text)
else:
    output = publish_post(text, image_url=image_url)
print(json.dumps({"ok": True, **output}, ensure_ascii=False, indent=2))
