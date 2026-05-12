from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "export_semantic_passport_packet_from_telegram_json.py"


def load_module():
    spec = importlib.util.spec_from_file_location("export_semantic_passport_packet_from_telegram_json", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_posts_skips_service_and_empty_messages():
    module = load_module()
    data = {
        "messages": [
            {
                "id": 1,
                "type": "service",
                "date": "2026-05-10T00:00:00",
                "text": "",
            },
            {
                "id": 2,
                "type": "message",
                "date": "2026-05-10T00:01:00",
                "text": "",
            },
            {
                "id": 3,
                "type": "message",
                "date": "2026-05-10T00:02:00",
                "views": 12,
                "forwards": 2,
                "text": [
                    "Read ",
                    {"type": "text_link", "text": "this", "href": "https://example.com"},
                ],
            },
        ],
    }

    posts = module.parse_posts(data, max_posts=None)

    assert len(posts) == 1
    assert posts[0].source_ref == "P0001"
    assert posts[0].telegram_message_id == 3
    assert posts[0].view_count == 12
    assert posts[0].forward_count == 2
    assert posts[0].text == "Read [this](https://example.com)"


def test_json_exporter_writes_read_only_packet(tmp_path, monkeypatch):
    module = load_module()
    export_path = tmp_path / "result.json"
    export_path.write_text(
        json.dumps(
            {
                "name": "Control Channel",
                "type": "public_channel",
                "id": 123,
                "messages": [
                    {
                        "id": 10,
                        "type": "message",
                        "date": "2026-05-10T00:00:00",
                        "text": "Practical AI workflow note",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "packet"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_semantic_passport_packet_from_telegram_json.py",
            "--json",
            str(export_path),
            "--expert-id",
            "control_channel",
            "--channel-username",
            "unknown_control",
            "--out-dir",
            str(out_dir),
        ],
    )

    assert module.main() == 0

    manifest = json.loads((out_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["script"] == "backend/scripts/export_semantic_passport_packet_from_telegram_json.py"
    assert manifest["corpus_stats"]["post_count"] == 1
    assert manifest["corpus_stats"]["comment_count"] == 0
    assert manifest["source_export"]["message_count_raw"] == 1
    assert (out_dir / "control_channel_telegram_export.json").exists()
