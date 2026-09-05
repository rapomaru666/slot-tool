import json
from pathlib import Path

from buffer_client import TARGET_HANDLE, publish_post

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
    if not text:
        raise RuntimeError("Rena post text is empty")
    return text, image_url


text, image_url = load_config()
output = publish_post(text, image_url=image_url)
print(json.dumps({"ok": True, **output}, ensure_ascii=False, indent=2))
