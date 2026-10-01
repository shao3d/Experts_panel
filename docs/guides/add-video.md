# Adding New Videos (The "Video Hub" Pipeline)

**Status:** Active
**Last updated:** 2026-10-01
**Scope:** VideoHub onboarding; query-time behavior is documented in `docs/architecture/video-hub-service.md`.
**Деплой: Oracle VM (Fly.io-процесс удалён 24.08.2026)**

## 🤖 Automated Ingest (preferred)

The preferred workflow combines scripted extraction with agent annotation and
source review. Start with duplicate and admission checks, then obtain owner
approval before ingest. Full playbook and source of truth for commands:
[operator guide](video-hub-operator.md) (Phase 0). Manual export follows the same
contract and review requirements.

```bash
# 1. media: follow operator step 0.1 (VM WARP preferred; Mac/G15 are fallbacks)

# 2. deterministic extraction (transcript, chunked frames, windows)
backend/.venv/bin/python backend/scripts/ingest_video.py \
  --video /path/video.mp4 --audio /path/audio.m4a \
  --video-id <youtube_id> --out /tmp/<id>_ingest --chunk-minutes 5

# 3. LLM pass: write chunks/chunk_NN/segments.json per chunk
#    (segment_id — сквозной по всему видео: combine падает на дублях)
#    Ведущий принимает разметку по речи и кадрам до импорта.

# 4. combine, validate, import, embed
backend/.venv/bin/python backend/scripts/ingest_video.py --combine --out /tmp/<id>_ingest
backend/.venv/bin/python backend/scripts/import_video_json.py /tmp/<id>_ingest/segments.json --dry-run
backend/.venv/bin/python backend/scripts/import_video_json.py /tmp/<id>_ingest/segments.json
backend/.venv/bin/python backend/scripts/embed_posts.py --continuous --receipt /tmp/<id>_ingest/segments.import-receipt.json
```

После подтверждения `searchable` пересобери Матрицу по шагу 0.4 руководства
оператора и обнови индекс видео по шагу 0.0. Импорт и индексация здесь относятся
к staging; выпуск в production — отдельная операция по
[operations](../operations.md).

При повторном заходе по тому же видео (пересегментация) добавь к импорту
`--replace-video`: старые сегменты, найденные по каноническому URL, и их
эмбеддинги удаляются перед импортом новой разметки.

## Legacy wrapper (production data release)

`deploy_video.sh` теперь работает как production DB release через проверенный
путь `update_production_db.sh`. Это не обычный шаг онбординга. Запускай только
при явном разрешении владельца на production data release и только из VM dev:

```bash
ssh -t ubuntu@82.70.251.73
cd ~/apps/experts-panel/dev
./scripts/deploy_video.sh path/to/video.json
```

> **Важно:** это production data release. Как и обычный `обнови базу`
> (`docs/operations.md`), он затрагивает production DB, поэтому запускается
> только на VM, из dev checkout, никогда — из `app`-checkout или с Mac.

> **Важно:** `deploy_video.sh` сам по себе **не вызывает LLM** для разметки.
> Он импортирует готовый JSON в staging SQLite и выкатывает обновлённую БД.
> Query-time Video Hub отвечает через OpenRouter-модели уже позже, во время
> реального runtime.

## 📋 Prerequisite: JSON Format

Ensure your JSON file follows the **Segmented Topic Structure**:

- `topic_id`: Must change every 10-15 mins or at logical chapters.
- `segments`: Must be granular (one thought per segment).

**Example (legacy minimum; the automated pipeline also adds `visual` and `frames`):**
```json
{
  "video_metadata": {
    "title": "My Video",
    "author": "Gleb Kudryavtcev",
    "url": "youtube_id",
    "published_at": "2026-08-21"
  },
  "segments": [
    {
      "segment_id": 1001,
      "topic_id": "chapter_1_intro",
      "title": "Intro",
      "summary": "... (RU: used by map phase and lexical search)",
      "content": "... (original speech)",
      "timestamp_seconds": 0,
      "visual": {
        "kind": "prompt_panel",
        "model": "Seedance 2.5",
        "showcase_prompt_verbatim": "..."
      },
      "frames": [{"time_s": 0, "path": "/abs/path/frame.jpg"}]
    }
  ]
}
```

`visual` is stored in `media_metadata` and appended to `message_text` as a
`VISUAL:` block (searchable by FTS5/vector and visible to synthesis); frame files
are copied to `backend/data/video_frames/<video_hash>/`. `published_at` drives
`created_at`, so recency filters use the video date. Write it as `YYYY-MM-DD`
(the Stage-2 prompt requires it); the importer normalizes any accepted shape to
canonical `YYYY-MM-DD HH:MM:SS`. Missing or unparsable `published_at` aborts
the import; import time is never a substitute for the video publication date.

## 🛠️ What the script does

1.  **Guards**: проверяет, что запущен на Oracle VM в dev checkout.
2.  **Import**: runs `backend/scripts/import_video_json.py` to add segments to
    the **staging** SQLite (`backend/data/experts.db`). Успешный импорт фиксирует
    изменения в staging. Ошибка импорта откатывает транзакцию и останавливает
    wrapper до production promotion.
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

- `deploy_video.sh` offers an optional embedding run; skipping it or an embedding
  failure does not stop its production promotion. It does not perform the
  receipt-based readiness check. Use the reviewed workflow above to confirm
  `searchable` before a separate owner-authorized data release:

```bash
backend/.venv/bin/python backend/scripts/embed_posts.py --continuous --receipt /path/segments.import-receipt.json
```

- This embedding step uses the same OpenRouter credentials from `backend/.env` (the legacy Vertex name in older docs is historical).

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
