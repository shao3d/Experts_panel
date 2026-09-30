"""Canonical video identity shared by ingestion and read-only Scout."""
from urllib.parse import parse_qs, urlparse
import hashlib
import json
from pathlib import Path


def youtube_id(video_url: str) -> str | None:
    parsed = urlparse(video_url or "")
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0] or None
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}:
        if parsed.path == "/watch":
            return (parse_qs(parsed.query).get("v") or [None])[0]
        for prefix in ("/shorts/", "/embed/", "/live/", "/v/"):
            if parsed.path.startswith(prefix):
                return parsed.path[len(prefix):].split("/")[0] or None
    if video_url and len(video_url) < 15 and ":" not in video_url and "/" not in video_url:
        return video_url
    return None


def canonical_video_url(video_url: str) -> str:
    video_id = youtube_id(video_url)
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else video_url


def write_receipt(path: Path, receipt: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_receipt(path: Path) -> dict:
    """An import receipt is tied to the exact reviewed source artifact."""
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or not isinstance(receipt.get("source_path"), str):
        raise ValueError("Import receipt has invalid source identity")
    source = Path(receipt["source_path"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != receipt.get("source_sha256"):
        raise ValueError("Import receipt is stale: source artifact changed")
    keys = receipt.get("source_keys", [])
    if not isinstance(keys, list) or not keys or any(not isinstance(key, str) for key in keys):
        raise ValueError("Import receipt has invalid source keys")
    if len(set(keys)) != len(keys) or any(not key.startswith("video_hub:") or not key.partition(":")[2].isdigit() for key in keys):
        raise ValueError("Import receipt has invalid or duplicate source keys")
    if receipt.get("status") not in {"loaded", "searchable"}:
        raise ValueError("Import receipt does not confirm a completed import")
    if receipt["status"] == "searchable" and receipt.get("indexed_segments") != len(keys):
        raise ValueError("Import receipt does not confirm complete indexing")
    return receipt
