from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path("x-auto/scripts").resolve()))

from common.buffer_client import BufferClient, BufferError


POST_PATH = Path("x-auto/wai/post.json")
HISTORY_PATH = Path("x-auto/wai/published.json")

TARGETS = {
    "twitter": os.environ.get("WAI_X_NAME", "wai_wai_69"),
    "threads": os.environ.get("WAI_THREADS_NAME", "wai_wai_69"),
}


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def norm(value: str) -> str:
    return value.strip().lstrip("@").lower()


def find_channel(client: BufferClient, service: str, target_name: str) -> dict:
    wanted = norm(target_name)
    organizations = client.graphql(
        "query GetOrganizations { account { organizations { id name } } }",
        safe_to_retry=True,
    )["account"]["organizations"]

    candidates = []
    for organization in organizations:
        organization_id = organization["id"]
        channels = client.graphql(
            f"""query GetChannels {{
              channels(input: {{ organizationId: "{organization_id}" }}) {{
                id name displayName service
              }}
            }}""",
            safe_to_retry=True,
        )["channels"]
        for channel in channels:
            if str(channel.get("service", "")).lower() != service:
                continue
            names = {
                norm(str(channel.get("name", ""))),
                norm(str(channel.get("displayName", ""))),
            }
            if wanted in names:
                return {**channel, "organization_id": organization_id}
            candidates.append(
                f'{service}:{channel.get("name") or channel.get("displayName")}'
            )

    raise BufferError(
        f"Buffer channel not found: service={service}, name={target_name}. "
        f"Connected candidates={candidates}"
    )


def wait_until_sent(client: BufferClient, post: dict, max_wait_seconds: int = 180) -> dict:
    deadline = time.monotonic() + max_wait_seconds
    current = post
    while True:
        status = current.get("status")
        if status == "sent":
            return current
        if status == "error":
            raise BufferError(
                "Buffer post failed: " + json.dumps(current, ensure_ascii=False)
            )
        if time.monotonic() >= deadline:
            raise BufferError(f"Buffer did not reach sent status: {status}")
        time.sleep(10)
        current = client.get_post(current["id"])


def publish_one(client: BufferClient, channel: dict, text: str) -> dict:
    existing = client.find_existing(
        organization_id=channel["organization_id"],
        channel_id=channel["id"],
        root_text=text,
    )
    if existing:
        return wait_until_sent(client, existing)

    created = client.create_post(
        channel_id=channel["id"],
        root_text=text,
        posts=[text],
    )
    return wait_until_sent(client, created)


def main() -> None:
    payload = read_json(POST_PATH, {})
    if not payload.get("enabled", False):
        print(json.dumps({"ok": True, "status": "disabled"}, ensure_ascii=False))
        return

    post_id = str(payload.get("id", "")).strip()
    text = str(payload.get("text", "")).strip()
    if not post_id:
        raise RuntimeError("post.json: id is required")
    if not text:
        raise RuntimeError("post.json: text is required")

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    history = read_json(HISTORY_PATH, [])
    entry = next((x for x in history if x.get("id") == post_id), None)

    if entry and entry.get("text_sha256") != text_hash:
        raise RuntimeError("Existing post id has different text")

    if not entry:
        entry = {
            "id": post_id,
            "text_sha256": text_hash,
            "text": text,
            "targets": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        history.append(entry)

    client = BufferClient()
    results = {}

    for service, target_name in TARGETS.items():
        prior = entry["targets"].get(service, {})
        if prior.get("status") == "sent":
            results[service] = prior
            continue

        channel = find_channel(client, service, target_name)
        post = publish_one(client, channel, text)
        result = {
            "status": "sent",
            "channel_id": channel["id"],
            "channel_name": channel.get("name") or channel.get("displayName"),
            "buffer_post_id": post.get("id"),
            "sent_at": post.get("sentAt"),
            "external_link": post.get("externalLink"),
        }
        entry["targets"][service] = result
        write_json(HISTORY_PATH, history)
        results[service] = result

    entry["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_json(HISTORY_PATH, history)

    print(
        json.dumps(
            {
                "ok": True,
                "status": "sent_to_x_and_threads",
                "id": post_id,
                "targets": results,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
