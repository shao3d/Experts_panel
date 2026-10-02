#!/usr/bin/env python3
"""Publish one project's reviewed LESSONS.md into the private Scout store.

The operator reviews the source and commits/pushes the private repository
separately. This script never opens project media or an expert database.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path


STORE = Path(__file__).resolve().parents[1] / "data" / "personal_lessons"
SECTION = re.compile(r"(?m)^## (L\d+)\. .+$")


def import_lessons(project: str, document: str, *, updated: str, store: Path = STORE) -> int:
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", project):
        raise ValueError("project must be a lowercase slug")
    date.fromisoformat(updated)
    if len(document.encode("utf-8")) > 1_000_000:
        raise ValueError("lesson document is too large")
    labels = SECTION.findall(document)
    if not labels or len(labels) != len(set(labels)):
        raise ValueError("document needs unique '## L01. Title' sections")
    manifest_path = store / "manifest.json"
    if not manifest_path.is_file() or not (store / ".git").exists():
        raise FileNotFoundError("private lesson repository is unavailable")
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    known = {(entry["project"], entry["lesson"]): entry for entry in entries}
    removed = sorted(label for (slug, label) in known if slug == project and label not in labels)
    if removed:
        raise ValueError("refusing to remove published lesson labels: " + ", ".join(removed))
    next_id = max((entry["id"] for entry in entries), default=0) + 1
    added = 0
    for label in labels:
        if (project, label) not in known:
            entries.append({"id": next_id, "project": project, "lesson": label, "date": updated})
            next_id += 1
            added += 1
    target = store / "projects" / project / "LESSONS.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document.rstrip() + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--source", type=Path, help="local LESSONS.md; omit to read stdin")
    parser.add_argument("--date", default=date.today().isoformat(), help="publication date YYYY-MM-DD")
    args = parser.parse_args()
    text = args.source.read_text(encoding="utf-8") if args.source else sys.stdin.read()
    try:
        added = import_lessons(args.project, text, updated=args.date)
    except (ValueError, FileNotFoundError) as exc:
        print(f"import failed: {exc}", file=sys.stderr)
        return 2
    print(f"published project={args.project} new_lessons={added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
