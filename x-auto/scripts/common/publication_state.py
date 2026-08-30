from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


JST = timezone(timedelta(hours=9))
STATE_DIR = Path("x-auto/state")
X_LINK_RE = re.compile(
    r"^https://(?:x|twitter)\.com/rapomaru777/status/(?P<id>\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)


def content_sha256(posts: list[str]) -> str:
    return hashlib.sha256("\0".join(posts).encode("utf-8")).hexdigest()


def hall_id(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def evening_receipt_path(target_date: str) -> Path:
    return STATE_DIR / f"evening-{target_date}.json"


def morning_receipt_path(target_date: str) -> Path:
    return STATE_DIR / f"morning-{target_date}.json"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def extract_x_post_id(external_link: str | None) -> str | None:
    if not external_link:
        return None
    match = X_LINK_RE.match(external_link)
    return match.group("id") if match else None


def is_verified_sent_receipt(receipt: dict | None, expected_hash: str | None = None) -> bool:
    if not receipt or receipt.get("status") != "sent":
        return False
    if expected_hash and receipt.get("content_sha256") != expected_hash:
        return False
    return bool(
        receipt.get("buffer_post_id")
        and receipt.get("sent_at")
        and extract_x_post_id(receipt.get("external_link"))
    )


def make_evening_receipt(
    *,
    target_date: str,
    posts: list[str],
    selected_halls: list[dict],
    buffer_post: dict,
) -> dict:
    external_link = buffer_post.get("externalLink")
    x_post_id = extract_x_post_id(external_link)
    if not x_post_id:
        raise RuntimeError(f"Buffer returned an invalid X link: {external_link!r}")
    return {
        "publication_key": f"evening:{target_date}",
        "target_date": target_date,
        "status": "sent",
        "content_sha256": content_sha256(posts),
        "selected_halls": selected_halls,
        "expected_thread_count": len(posts),
        "buffer_post_id": buffer_post.get("id"),
        "external_link": external_link,
        "x_root_post_id": x_post_id,
        "sent_at": buffer_post.get("sentAt"),
        "verified_at": datetime.now(JST).isoformat(),
    }


def make_morning_entry(
    *,
    target_date: str,
    hall: dict,
    text: str,
    buffer_post: dict,
    source: str | None,
) -> dict:
    external_link = buffer_post.get("externalLink")
    x_post_id = extract_x_post_id(external_link)
    if not x_post_id:
        raise RuntimeError(f"Buffer returned an invalid X link: {external_link!r}")
    return {
        "publication_key": f"morning:{target_date}:{hall['hall_id']}",
        "target_date": target_date,
        "hall": hall,
        "status": "sent",
        "content_sha256": content_sha256([text]),
        "text": text,
        "buffer_post_id": buffer_post.get("id"),
        "external_link": external_link,
        "x_post_id": x_post_id,
        "sent_at": buffer_post.get("sentAt"),
        "verified_at": datetime.now(JST).isoformat(),
        "source": source,
    }
