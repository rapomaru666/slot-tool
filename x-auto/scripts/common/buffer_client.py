from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from .publication_state import extract_x_post_id


API_URL = "https://api.buffer.com"


class BufferError(RuntimeError):
    pass


class BufferAmbiguousResult(BufferError):
    pass


class BufferClient:
    def __init__(self, token: str | None = None, timeout: int = 30):
        self.token = token or os.environ["BUFFER_API_KEY"]
        self.timeout = timeout

    def graphql(self, query: str, *, safe_to_retry: bool = False) -> dict:
        attempts = 3 if safe_to_retry else 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                request = urllib.request.Request(
                    API_URL,
                    data=json.dumps({"query": query}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.token}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if payload.get("errors"):
                    raise BufferError(json.dumps(payload["errors"], ensure_ascii=False))
                return payload["data"]
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    raise BufferError(f"Buffer authentication failed: HTTP {exc.code}") from exc
                last_error = exc
                if not safe_to_retry or exc.code not in (429, 500, 502, 503, 504):
                    raise
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if not safe_to_retry:
                    raise
            if attempt < attempts - 1:
                time.sleep((attempt + 1) * 5)
        raise BufferError(f"Buffer request failed after retries: {last_error}")

    def find_channel(self, target_name: str) -> dict:
        organizations = self.graphql(
            "query GetOrganizations { account { organizations { id name } } }",
            safe_to_retry=True,
        )["account"]["organizations"]
        for organization in organizations:
            organization_id = organization["id"]
            channels = self.graphql(
                f'''query GetChannels {{
                  channels(input: {{ organizationId: "{organization_id}" }}) {{
                    id name displayName service
                  }}
                }}''',
                safe_to_retry=True,
            )["channels"]
            for channel in channels:
                names = {
                    str(channel.get("name", "")).lower(),
                    str(channel.get("displayName", "")).lower(),
                }
                if channel.get("service") == "twitter" and target_name.lower() in names:
                    return {**channel, "organization_id": organization_id}
        raise BufferError(f"X channel {target_name} not found in Buffer")

    def get_post(self, post_id: str) -> dict:
        return self.graphql(
            f'''query GetPost {{
              post(input: {{ id: {json.dumps(post_id)} }}) {{
                id text status sentAt externalLink createdAt updatedAt
              }}
            }}''',
            safe_to_retry=True,
        )["post"]

    def recent_posts(self, *, organization_id: str, channel_id: str) -> list[dict]:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
        end = (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        query = f'''query RecentPosts {{
          posts(first: 50, input: {{
            organizationId: {json.dumps(organization_id)},
            filter: {{
              channelIds: [{json.dumps(channel_id)}],
              startDate: {json.dumps(start)},
              endDate: {json.dumps(end)}
            }}
          }}) {{
            edges {{
              node {{ id text status sentAt externalLink createdAt updatedAt }}
            }}
          }}
        }}'''
        result = self.graphql(query, safe_to_retry=True)["posts"]
        return [edge["node"] for edge in result.get("edges", [])]

    def find_existing(
        self,
        *,
        organization_id: str,
        channel_id: str,
        root_text: str,
    ) -> dict | None:
        candidates = [
            post
            for post in self.recent_posts(
                organization_id=organization_id,
                channel_id=channel_id,
            )
            if post.get("text") == root_text and post.get("status") != "error"
        ]
        candidates.sort(key=lambda post: post.get("createdAt") or "", reverse=True)
        return candidates[0] if candidates else None

    def create_post(self, *, channel_id: str, root_text: str, posts: list[str]) -> dict:
        thread_items = ",\n".join(
            "{ text: " + json.dumps(text, ensure_ascii=False) + " }" for text in posts
        )
        metadata_block = ""
        if len(posts) > 1:
            metadata_block = f''',
            metadata: {{
              twitter: {{
                thread: [
                  {thread_items}
                ]
              }}
            }}'''
        mutation = f'''mutation PublishNow {{
          createPost(input: {{
            text: {json.dumps(root_text, ensure_ascii=False)},
            channelId: {json.dumps(channel_id)},
            schedulingType: automatic,
            mode: shareNow,
            saveToDraft: false
            {metadata_block}
          }}) {{
            ... on PostActionSuccess {{
              post {{ id text status sentAt externalLink createdAt updatedAt }}
            }}
            ... on MutationError {{ message }}
          }}
        }}'''
        result = self.graphql(mutation)["createPost"]
        if result.get("message"):
            raise BufferError(result["message"])
        post = result.get("post")
        if not post or not post.get("id"):
            raise BufferError(f"Buffer did not return a post: {json.dumps(result, ensure_ascii=False)}")
        return post

    def wait_until_sent(self, post: dict, *, max_wait_seconds: int = 180) -> dict:
        deadline = time.monotonic() + max_wait_seconds
        current = post
        while True:
            status = current.get("status")
            if status == "sent":
                if not current.get("sentAt"):
                    raise BufferError("Buffer sent status has no sentAt")
                if extract_x_post_id(current.get("externalLink")):
                    return current
                if time.monotonic() >= deadline:
                    raise BufferError("Buffer sent status has no valid X externalLink")
            elif status == "error":
                raise BufferError(f"Buffer post failed: {json.dumps(current, ensure_ascii=False)}")
            elif time.monotonic() >= deadline:
                raise BufferError(f"Buffer did not reach sent status: {status}")
            time.sleep(10)
            current = self.get_post(current["id"])

    def publish_verified(
        self,
        *,
        channel: dict,
        root_text: str,
        posts: list[str],
    ) -> tuple[dict, str]:
        existing = self.find_existing(
            organization_id=channel["organization_id"],
            channel_id=channel["id"],
            root_text=root_text,
        )
        if existing:
            return self.wait_until_sent(existing), "already_sent_verified"

        try:
            created = self.create_post(
                channel_id=channel["id"],
                root_text=root_text,
                posts=posts,
            )
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            for delay in (5, 15, 30):
                time.sleep(delay)
                existing = self.find_existing(
                    organization_id=channel["organization_id"],
                    channel_id=channel["id"],
                    root_text=root_text,
                )
                if existing:
                    return self.wait_until_sent(existing), "sent"
            raise BufferAmbiguousResult(
                "Buffer create result is unknown; no duplicate retry was attempted"
            ) from exc
        return self.wait_until_sent(created), "sent"
