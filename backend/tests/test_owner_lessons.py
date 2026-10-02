"""Private lesson storage stays separate and keeps stable source keys."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_search_and_show_preserve_lesson_identity(tmp_path):
    importer = _module("owner_import", ROOT / "scripts" / "import_owner_lessons.py")
    lessons = _module("owner_lessons", ROOT / "backend" / "scripts" / "owner_lessons.py")
    store = tmp_path / "private"
    (store / ".git").mkdir(parents=True)
    (store / "manifest.json").write_text("[]", encoding="utf-8")
    document = "# Lessons\n\n## L01. Geometry control\n\nRefine геометрию scene.\n\n## L02. Audio\n\nCheck audio.\n"
    assert importer.import_lessons("scene", document, updated="2026-10-02", store=store) == 2
    assert [item["source_key"] for item in lessons.search("геометрия", store=store)["posts"]] == ["lesson:1"]
    assert lessons.show(["lesson:1"], store=store)[0]["content"].startswith("## L01.")
    assert lessons.show(["lesson:2"], store=store)[0]["content"] == "## L02. Audio\n\nCheck audio."
    updated = document.replace("Check audio.", "Check audio and fps.") + "\n## L03. Frames\n\nVerify fps.\n"
    assert importer.import_lessons("scene", updated, updated="2026-10-03", store=store) == 1
    manifest = json.loads((store / "manifest.json").read_text(encoding="utf-8"))
    assert [(item["id"], item["lesson"]) for item in manifest] == [(1, "L01"), (2, "L02"), (3, "L03")]
    first = lessons.search("fps", limit=1, store=store)
    second = lessons.search("fps", limit=1, cursor=first["next_cursor"], store=store)
    assert first["total"] == 2
    assert first["next_cursor"] == 1
    assert second["next_cursor"] is None
    assert first["posts"][0]["source_key"] != second["posts"][0]["source_key"]


def test_import_refuses_removing_published_lesson(tmp_path):
    importer = _module("owner_import_remove", ROOT / "scripts" / "import_owner_lessons.py")
    store = tmp_path / "private"
    (store / ".git").mkdir(parents=True)
    (store / "manifest.json").write_text('[{"id": 4, "project": "scene", "lesson": "L01", "date": "2026-10-02"}]')
    try:
        importer.import_lessons("scene", "## L02. New\n\nText", updated="2026-10-02", store=store)
    except ValueError as exc:
        assert "refusing to remove" in str(exc)
    else:
        raise AssertionError("published source key was removed")
