"""Read-only search and exact source lookup for the private owner lesson store."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


STORE = Path(__file__).resolve().parents[2] / "data" / "personal_lessons"
SECTION = re.compile(r"(?m)^## (L\d+)\. (.+)$")
MAX_FILE_BYTES = 1_000_000


def load_lessons(store: Path = STORE) -> list[dict]:
    manifest = store / "manifest.json"
    if not manifest.is_file():
        raise FileNotFoundError("private lesson store is unavailable")
    if manifest.is_symlink():
        raise ValueError("invalid lesson manifest")
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("invalid lesson manifest")
    lessons: list[dict] = []
    seen: set[int] = set()
    for entry in entries:
        number = entry["id"]
        project = entry["project"]
        lesson = entry["lesson"]
        if not isinstance(number, int) or number < 1 or number in seen:
            raise ValueError("invalid or duplicate lesson id")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", project) or not re.fullmatch(r"L\d+", lesson):
            raise ValueError("invalid lesson project or label")
        seen.add(number)
        path = (store / "projects" / project / "LESSONS.md").resolve()
        if store.resolve() not in path.parents or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("invalid lesson file")
        document = path.read_text(encoding="utf-8")
        sections = list(SECTION.finditer(document))
        matches = [(i, m) for i, m in enumerate(sections) if m.group(1) == lesson]
        if len(matches) != 1:
            raise ValueError("lesson label missing or duplicated")
        index, match = matches[0]
        content = document[match.start(): sections[index + 1].start() if index + 1 < len(sections) else len(document)].strip()
        content = re.sub(r'\s*<a id="l\d+"></a>\s*\Z', '', content)
        lessons.append({
            "source_key": f"lesson:{number}", "project": project,
            "lesson": lesson, "title": match.group(2), "content": content,
            "created_at": entry["date"], "source_path": f"projects/{project}/LESSONS.md#{lesson.lower()}",
            "kind": "owner_lesson", "author_name": "Андрей",
        })
    return lessons


def search(query: str, *, limit: int = 20, cursor: int = 0, store: Path = STORE) -> dict:
    lessons = load_lessons(store)
    tokens = re.findall(r"[^\W_]{2,}", query.lower(), re.UNICODE)
    if not tokens:
        return {"status": "completed", "posts": [], "total": 0, "next_cursor": None}
    if cursor < 0:
        raise ValueError("cursor must be nonnegative")
    window = min(max(limit, 1), 40)
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE VIRTUAL TABLE lesson_fts USING fts5(title, content, tokenize='unicode61')")
        for lesson in lessons:
            conn.execute("INSERT INTO lesson_fts(rowid,title,content) VALUES (?,?,?)",
                         (int(lesson["source_key"].split(":")[1]), lesson["title"], lesson["content"]))
        # OR gives the agent useful candidates when a natural-language question
        # has many words. The title receives extra weight during ranking.
        expression = " OR ".join(f'"{token[:5]}"*' if len(token) >= 6 else f'"{token}"'
                                 for token in tokens[:16])
        total = conn.execute("SELECT count(*) FROM lesson_fts WHERE lesson_fts MATCH ?", (expression,)).fetchone()[0]
        rows = conn.execute("SELECT rowid FROM lesson_fts WHERE lesson_fts MATCH ? "
                            "ORDER BY bm25(lesson_fts, 4.0, 1.0), rowid LIMIT ? OFFSET ?",
                            (expression, window, cursor)).fetchall()
    by_id = {int(item["source_key"].split(":")[1]): item for item in lessons}
    posts = [{k: item[k] for k in ("source_key", "project", "lesson", "title", "created_at", "source_path", "kind")}
             | {"snippet": item["content"][:400]}
             for (number,) in rows if (item := by_id[number])]
    next_cursor = cursor + len(posts) if cursor + len(posts) < total else None
    return {"status": "completed", "posts": posts, "total": total,
            "next_cursor": next_cursor, "search_mode": "text"}


def show(keys: list[str], *, store: Path = STORE) -> list[dict]:
    by_key = {lesson["source_key"]: lesson for lesson in load_lessons(store)}
    return [by_key[key].copy() if key in by_key else {"source_key": key, "error": "not_found"} for key in keys]
