# Adding New Videos (The "Video Hub" Pipeline)

**Pipeline:** `Map -> Resolve (Summary Bridging) -> Reduce (Digital Twin)`
**Деплой: Oracle VM (Fly.io-процесс удалён 24.08.2026)**

## 🚀 Quick Command

`deploy_video.sh` теперь работает как production DB release через проверенный
путь `update_production_db.sh`. Запускай **только на Oracle VM из dev checkout**:

```bash
ssh -t ubuntu@82.70.251.73
cd ~/apps/experts-panel/dev
./scripts/deploy_video.sh path/to/video.json
```

> **Важно:** это production data release. Как и обычный `обнови базу`
> (`docs/operations.md`), он затрагивает production DB, поэтому запускается
> только на VM, из dev checkout, никогда — из `app`-checkout или с Mac.

> **Важно:** `deploy_video.sh` сам по себе **не вызывает Gemini / Vertex AI**
> для разметки. Он импортирует готовый JSON в staging SQLite и выкатывает
> обновлённую БД. Сам Video Hub отвечает через Vertex AI уже позже, во время
> реального query runtime.

## 📋 Prerequisite: JSON Format

Ensure your JSON file follows the **Segmented Topic Structure**:

- `topic_id`: Must change every 10-15 mins or at logical chapters.
- `segments`: Must be granular (one thought per segment).

**Example:**
```json
{
  "video_metadata": {
    "title": "My Video",
    "author": "Gleb Kudryavtcev",
    "url": "youtube_id"
  },
  "segments": [
    {
      "segment_id": 1001,
      "topic_id": "chapter_1_intro",
      "title": "Intro",
      "summary": "...",
      "content": "...",
      "timestamp_seconds": 0
    }
  ]
}
```

## 🛠️ What the script does

1.  **Guards**: проверяет, что запущен на Oracle VM в dev checkout.
2.  **Import**: runs `backend/scripts/import_video_json.py` to add segments to
    the **staging** SQLite (`backend/data/experts.db`). Staging DB не меняется
    только там, где импорт прошёл успешно (иначе abort до деплоя).
3.  **Integrity**: `PRAGMA integrity_check` на staging DB перед продвижением.
4.  **Embeddings (optional)**: спрашивает, векторизовать ли свежие сегменты
    сразу (`embed_posts.py --continuous`); `N` — пропустить и сделать позже.
5.  **Promote**: вызывает `DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh`,
    который: делает production backup, stage + verify (размер/SHA/gzip/integrity),
    атомарно заменяет production DB, перезапускает `panel` и ждёт `/health`.

### Что с этого убрали

- Процесс SFTP-загрузки на Fly.io (`/app/data/experts.db.gz`) + `fly ssh`
  + `fly apps restart` удалён как неактуальный.
- Rollback теперь через штатный `./scripts/update_production_db.sh --rollback`
  (из dev checkout на VM).

## 🔎 Important Runtime Note

- `deploy_video.sh` **does not** generate embeddings for fresh video segments
  (it only asks optionally). If you need new video segments to participate in
  Hybrid Search immediately, run:

```bash
python3 backend/scripts/embed_posts.py --continuous
```

- This embedding step uses the same Vertex AI credentials from `backend/.env`.

## 🐛 Troubleshooting

### "This script must run ON the Oracle VM"
Скрипт не запускается с другой машины или из неверной директории. Зайди на VM
и запусти из `~/apps/experts-panel/dev`.

### Health-проверка после деплоя падает
`deploy_video.sh` упадёт, если `update_production_db.sh` не получит здоровый
`/health`. Подожди и проверь логи контейнера:

```bash
sudo docker logs --tail 100 $(sudo docker ps -qf name=panel-1)
```

Если application greenlit и нужно вернуть прошлую БД:

```bash
cd ~/apps/experts-panel/dev
./scripts/update_production_db.sh --rollback
```

### "No staging DB found"
Первый полный деплой БД ещё не делался (`backend/data/experts.db` отсутствует).
Сначала выполни полноценный sync/pipeline по `docs/operations.md`.

---
**Note:** This process promotes the **entire** production database from your
staging copy, so keep the staging DB up to date (run the normal sync) before
deploying video if other data changed since the last DB release.