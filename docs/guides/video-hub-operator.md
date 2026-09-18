# 🎥 Video Hub Operator Playbook

**Role:** Expert Digital Twin Creator
**Status:** Active Workflow (automated ingest preferred)
**Owner:** System Architect (opencode agent)

---

## 🎯 Objective
Transform raw video content (YouTube/MP4) into a structured Knowledge Graph (Segments & Topics) for the Expert Panel.

---

## 🤖 Phase 0: Automated Ingest (preferred)

The pipeline replaces the manual AI Studio pass. Full details:
`docs/architecture/video-hub-service.md` → "Automated Ingest Pipeline".

### 0.0 Duplicate check (MANDATORY)

Before any work on a new video, check its canonical YouTube URL against the
staging DB (`backend/data/experts.db`) — the same DB that is promoted to
production, so the check covers prod too. All URL shapes normalize to one
identity (`watch?v=…&t=…`, `youtu.be/…?si=…`, `/shorts/…`).

```bash
backend/.venv/bin/python - <<'PY'
import sqlite3, sys
sys.path.insert(0, "backend")
from scripts.import_video_json import canonical_video_url, find_video_post_ids
conn = sqlite3.connect("file:backend/data/experts.db?mode=ro", uri=True)
canonical = canonical_video_url("https://youtu.be/<youtube_id>")
ids = find_video_post_ids(conn.cursor(), canonical)
print(canonical, "->", len(ids), "segments")
PY
```

If the count is **0** — proceed to 0.1. If the count is **> 0** — **stop and
notify the owner**: video title, segment count, import/release date. Re-process
an already imported video only with the owner's explicit consent, and then only
with `--replace-video` at import time (0.4).

### 0.1 Get the media onto the VM
YouTube blocks the VM datacenter IP, so downloads happen on the Mac over the
reverse SSH tunnel (the `fetch_audio.sh` pattern) and the files are copied to
the VM (video-only 1080p + audio m4a; the Mac has no ffmpeg).

### 0.2 Stage 1 — deterministic extraction (no LLM, no DB)

```bash
backend/.venv/bin/python backend/scripts/ingest_video.py \
  --video /path/video.mp4 --audio /path/audio.m4a \
  --video-id <youtube_id> --out /tmp/<id>_ingest \
  --chunk-minutes 5
```

- ASR: `backend/scripts/asr_whisper.py` (faster-whisper int8, CPU, glossary-biased, auto language).
- Chunks: `chunks/chunk_NN/` with coarse frames, contact sheets, change curve, cue windows, dense frames.
- Caps per chunk: `--max-windows-per-chunk`, `--max-dense-frames-per-chunk`; artifacts are review-only.
- Reuse `--transcript <json>` / `--skip-asr` for re-runs.

### 0.3 Stage 2 — LLM pass per chunk
Read one chunk (transcript slice + sheets + native frames), write
`chunks/chunk_NN/segments.json` with the extended schema (`visual`, `frames`),
then forget the frames. Disk is the memory.

Number `segment_id` **continuously across chunks** (do not restart from 1001 in
each chunk): `--combine` fails on duplicates, and duplicate virtual IDs would
otherwise overwrite segments at import time.

### 0.4 Combine, import, embed

```bash
backend/.venv/bin/python backend/scripts/ingest_video.py --combine --out /tmp/<id>_ingest
backend/.venv/bin/python backend/scripts/import_video_json.py /tmp/<id>_ingest/segments.json --dry-run
backend/.venv/bin/python backend/scripts/import_video_json.py /tmp/<id>_ingest/segments.json
backend/.venv/bin/python backend/scripts/embed_posts.py
```

Re-importing the same video after re-segmentation: add `--replace-video` so the
old segments (matched by canonical video URL) and their embeddings are deleted
before the new ones are imported.

Production promotion of the updated DB is a separate owner command (`обнови базу`).

---

## 🧠 Phase 1 (legacy): Manual Segmentation in Google AI Studio

Use **Google AI Studio** or another Gemini UI to generate the source JSON.

> **Важно:** Это резервный ручной путь. Основной — Phase 0 выше.

### 📝 The Golden Prompt (System Instructions)
*Copy this into AI Studio System Instructions:*

```text
Ты — Senior AI Knowledge Architect. Твоя задача — провести глубокий мультимодальный анализ видео и превратить его в структурированную базу знаний (Knowledge Nodes).

ПРАВИЛА АНАЛИЗА:
1. ВИЗУАЛЬНЫЙ КОНТЕКСТ (MULTIMODAL): Всё видимое — в квадратных скобках [НА ЭКРАНЕ: ...] внутри поля 'content'. Разделяй два случая: служебный фон (говорящий, браузер, обои слайда) — кратко; ценная нагрузка (промт, настройки/параметры генерации, код, формулы, точные цифры, заголовок) — ДОСЛОВНО, промт в кавычках, настройки коротким списком. Нечитаемое — пиши [НА ЭКРАНЕ: текст нечитаем], не выдумывай.
2. СЕМАНТИЧЕСКИЕ ГРАНИЦЫ: Один сегмент = одна законченная мысль. Не режь на полуслове.
3. ПРАВИЛО "КЛЕЯ": Конец сегмента N дублируется в начале сегмента N+1 (1-2 предложения).
4. ТЕМАТИЧЕСКИЕ НИТИ (TOPIC_ID): 
   - Группируй сегменты одной темы под одним ID.
   - ВАЖНО: Меняй topic_id при смене логического блока (главы) или каждые 10-15 минут.
   - ИЗБЕГАЙ гигантских тем на все видео. Используй гранулярные ID: "rag_intro", "rag_architecture".
5. ДОСЛОВНОСТЬ: Речь автора сохраняй дословно.
6. КЛЮЧЕВЫЕ КАДРЫ (ON-SCREEN MOMENTS): значимые моменты фиксируй меткой [НА ЭКРАНЕ: ...] в 'content', а в timestamp_seconds ставь СЕКУНДУ ПОЯВЛЕНИЯ кадра, не начало сегмента. Ключевой = читаемый текст (промт/заголовок/метрика), интерфейс/настройки/модалка, таблица/график/код/формула, результат генерации, «до/после», клик или уведомление. Каденция ~1 кадр/15 сек, но без насилия. При сомнении — фиксируй. Частично нечитаемое помечай [НА ЭКРАНЕ (неуверенно): ...].

ФОРМАТ ВЫХОДА (JSON):
{
  "video_metadata": { "title": "...", "author": "Gleb Kudryavtcev", "url": "...", "duration_seconds": 0 },
  "segments": [
    {
      "segment_id": 1001,
      "topic_id": "slug",
      "title": "Заголовок",
      "summary": "Резюме",
      "content": "[НА ЭКРАНЕ: ...] Текст...",
      "timestamp_seconds": 123
    }
  ]
}
```

---

## 🎬 Phase 2: Processing Scenarios

### Scenario A: Short Video (< 30 min)
1.  Generate **one JSON file** covering the entire video.
2.  Save as `video.json`.
3.  Deploy:
    ```bash
    ./scripts/deploy_video.sh video.json
    ```

### Scenario B: Long Video (> 30 min)
**Strategy:** "Overlap & Merge" (Нахлест и Склейка).

1.  **Generate Part 1:**
    *   Input: First 35 mins.
    *   User Prompt: "Analyze video content from 00:00 to 35:00. Finish at a logical pause."
    *   Save JSON (`part1.json`).

2.  **Generate Part 2:**
    *   Input: From 30:00 to End.
    *   User Prompt: "Analyze video content starting from timestamp 30:00 to the end. Ignore the intro, begin with the first complete thought after 30:00."
    *   *Note:* It is normal for `segment_id` to reset to 1001 here. Gemini CLI will renumber them.
    *   Save JSON (`part2.json`).

3.  **Merge & Deploy (Via Gemini CLI):**
    *   **Action:** Paste both JSON parts directly into the Gemini CLI chat.
    *   **Command:** *"Here are Part 1 and Part 2. Merge them, check the overlap, and deploy."*

### 🤖 Gemini Agent Protocol (For AI)
*When instructed to execute "Merge & Deploy", follow this precise workflow:*
1.  **Receive:** Wait for user to provide Part 1 and Part 2 JSON blocks.
2.  **Validate:** Check syntax (fix trailing commas, ensure `segments` array exists).
3.  **Smart Merge Logic:**
    *   Identify the last segment of Part 1.
    *   Find the corresponding/overlapping segment in Part 2 (match by `title` or `content` context).
    *   **Slice:** Keep Part 1 entirely. Remove overlapping segments from Part 2.
    *   **Re-index:** Update `segment_id` in Part 2 starting from `(Part 1 Max ID + 1)`.
    *   **Stitch Topics:** If `topic_id` at the seam is identical, keep it.
4.  **Execute:**
    *   Save merged content to `merged_video.json`.
    *   Run `./scripts/deploy_video.sh merged_video.json`.
    *   Delete `merged_video.json` upon success.

---

## 🐛 Troubleshooting

### Common Issues
1.  **"This script must run ON the Oracle VM"**:
    *   Video deploy — это production DB release. Запускай только на VM из dev
        checkout (`cd ~/apps/experts-panel/dev`), см. `docs/guides/add-video.md`.

2.  **"JSON Parse Error"**:
    *   AI Studio sometimes outputs invalid JSON (trailing commas, missing brackets).
    *   **Fix:** Paste the JSON into Gemini CLI and ask: *"Fix this JSON syntax"*.

3.  **"Lost Middle" (Missing Content)**:
    *   If a video is long (60m+) and you try to do it in one pass, the output will be truncated.
    *   **Fix:** Use **Scenario B** immediately.

4.  **Health-проверка падает после деплоя**:
    *   `deploy_video.sh` вернёт ошибку, если `/health` не пройден. Проверь логи
        контейнера (`sudo docker logs --tail 100 $(sudo docker ps -qf name=panel-1)`)
        и при необходимости откатись:
        `./scripts/update_production_db.sh --rollback` (из dev checkout).

---

## 🛠️ Maintenance
- **Ingest scripts:** `backend/scripts/ingest_video.py`, `backend/scripts/asr_whisper.py` (dev checkout).
- **Import:** `backend/scripts/import_video_json.py` (upsert by `telegram_message_id`; preserves embeddings across re-imports).
- **Embeddings:** `backend/scripts/embed_posts.py` (run after import so segments join vector search; FTS5 updates itself via triggers).
- **Database:** staging `backend/data/experts.db` → promoted to production via
  `DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh` (= Production data release,
  см. `docs/operations.md`). Legacy manual flow can still promote a ready JSON via
  `scripts/deploy_video.sh`. Устаревший Fly.io SFTP-путь удалён 24.08.2026.
- **Runtime Auth:** query-time Video Hub calls the configured OpenRouter models from `backend/.env` / managed secrets.
- **Important:** neither `deploy_video.sh` nor the ingest pipeline calls production; production DB changes only through the owner's `обнови базу`.
