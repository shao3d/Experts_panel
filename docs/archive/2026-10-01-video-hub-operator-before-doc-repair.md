# VideoHub Operator Playbook: historical snapshot before documentation repair

**Status:** Archived / historical only
**Last updated:** 2026-10-01

Снимок прежнего руководства перед устранением противоречий. Приведённые ниже
сценарии, команды и утверждения могут быть устаревшими; не выполнять их как
текущий регламент. В частности, старый «Merge & Deploy» не даёт разрешения
на production release, а `deploy_video.sh` действительно продвигает БД в prod.
Текущий SSOT: [руководство оператора](../guides/video-hub-operator.md).

---

# 🎥 Video Hub Operator Playbook

**Role:** Expert Digital Twin Creator
**Original status:** Active Workflow (automated ingest preferred)
**Last updated:** 2026-10-01
**Owner:** System Architect (opencode agent)

---

## 🎯 Objective
Transform raw video content (YouTube/MP4) into a structured Knowledge Graph (Segments & Topics) for the Expert Panel.

---

## 🤖 Phase 0: Automated Ingest (preferred)

The pipeline replaces the manual AI Studio pass. Full details:
`docs/architecture/video-hub-service.md` → "Automated Ingest Pipeline".

### Модель для ведения онбординга

Распределение ролей согласовано владельцем 2026-09-30:

| Роль | Модель и reasoning | Ответственность |
|---|---|---|
| Ведущий агент | Astra Medium | Ценность видео, решение по overlap и scope, постановка задач, сверка полноты по исходникам, приёмка разметки Матрицы и итоговых ответов |
| Технический исполнитель | Sol 6.1 low | Метаданные и подготовка материалов, черновой список тем с указателями на исходник, запуск разрешённых технических шагов и проверка их результатов |
| Исполнитель фазы 6 | Sol 6.1 high | Подробный разбор назначенного чанка: речь и кадры, самостоятельные приёмы, точные экранные инструкции, `segments.json`, предложения `matrix_cells` и список неопределённостей |

Фаза 6 в обсуждении с владельцем соответствует **Stage 2 / шагу 0.3** ниже.
Это организация работы агентов, а не новый автоматический LLM-runner.
Ведущий создаёт двух исполнителей с явно заданными моделью и reasoning;
не считать модель новой сессии автоматически выбранной Astra. Успех Sol в
экзамене поиска не доказывает качество разметки видео. Первые результаты
Sol high проверяются ведущим по исходному тексту и кадрам до расширения работы.

Для следующей работы рассматривается Sol 6.1 high как ведущий, с xhigh для
сложных разборов. Это рекомендация, а не проверенная эквивалентность Astra
Medium: сравнение ведущих на одной задаче ещё не проведено. Модель текущего
чата выбирает владелец; таблица выше описывает команду завершённого онбординга.

Технический исполнитель не решает, какие полезные фрагменты отбросить.
Исполнитель фазы 6 сохраняет самостоятельные инструкции даже внутри знакомой
темы; спорные повторы и противоречия передаёт ведущему. Для задания ему нужны
chunk, текст, sheets/native frames, offset исходного видео и выделенный диапазон
`segment_id`. Нечитаемый экранный текст и отсутствие свидетельств отмечаются,
а не восполняются по памяти. Разметка ячеек требует конкретных сегментов.

Параллельная запись в один артефакт запрещена: исполнитель фазы 6 владеет только
назначенным chunk JSON; технический исполнитель запускает combine/import лишь
после приёмки ведущим. Каждый исполнитель учитывает чужие изменения и не
откатывает их. При спорном качестве ведущий углубляет проверку по исходникам;
сводка исполнителя не заменяет такую проверку. Делегирование не отменяет
согласование владельцем вердикта ingest и отдельные правила релиза.

Probe по существующему корпусу идёт через штатный Скаут; его текущая модель и
режим описаны в [руководстве Скаута](../guides/expert-scout.md). Скачивание, нарезка,
combine/import и пересборка Матрицы остаются скриптовыми шагами. ASR использует
локальный faster-whisper (по умолчанию large-v3-turbo); это отдельная задача.
MiMo из [анализа дрифта](../guides/drift-analysis.md) к онбордингу не подключена.

### 0.0 Duplicate check (MANDATORY)

Before any work on a new video, run the read-only index checker against the
staging DB (`backend/data/experts.db`) — the same DB that is promoted to
production, so the check covers prod too. All URL shapes normalize to one
identity (`watch?v=…&t=…`, `youtu.be/…?si=…`, `/shorts/…`).

```bash
backend/.venv/bin/python backend/scripts/video_hub_index.py --check <youtube_url|youtube_id>
# exit 0  -> FREE: нет в VideoHub, можно брать в работу
# exit 10 -> DUPLICATE: уже есть (автор, название, сегменты, дата)
```

The full inventory lives in `docs/video-hub-index.md`, grouped by author
(`Higgsfield AI`, …). Regenerate it after every import with:

```bash
backend/.venv/bin/python backend/scripts/video_hub_index.py --write
```

If `--check` reports DUPLICATE — **stop and notify the owner**: author, video
title, segment count, publication date. Re-process an already imported video
only with the owner's explicit consent, and then only with `--replace-video`
at import time (0.4).

### 0.0b Knowledge-matrix gate (MANDATORY, механика: `docs/architecture/expert-admission-control.md` §16)

Перед любым ingest нового видео — гейт ценности ДО скачивания медиа.
Полный цикл: траскрипт-проба → probe Скаутом → вердикт → `admission_log`.

1. **Транскрипт-проба:** забрать YouTube auto-captions (механика доступа — шаг 0.1
   ниже; гигиена транскрипта — `expert-admission-control.md` §16.3), один LLM-вызов:
   3–5 реальных тем + черновые `prompt_density` / `version_lock` / `durable_share`.
   Транскрипт — артефакт в `output/video_admission/<id>/`, в БД не импортировать.
2. **Probe-чек Скаутом:** 3–5 вопросов по конкретным приёмам транскрипта (RU и EN) через
   `scripts/expert_scout.sh`. Overlap подтверждается прочитанным источником с тем же
   действием, условием и существенными деталями. Совпадение общей темы или ячейки
   матрицы недостаточно: общий совет о правках клиента не заменяет инструкцию
   про чёрную заглушку для жидкости или speed ramp. Исключая блок, проверь каждый
   полезный приём внутри него; частичное совпадение не исключает весь блок.
   Пустой успешный поиск — кандидат на gap, а ошибка/partial — незавершённая проверка.
   Артефакты — `output/video_admission/<id>/scout_probe*.md`.
3. **Вердикт** в `output/video_admission/admission_log.json`: `ingest` /
   `ingest_scoped` / `waitlist` / `reject_*` + `decision_basis` (маппинг gap-тем
   на source_key) и `caveat` (version_lock / durable_share). Владелец
   утверждает вердикт до старта ingest.
4. **Если `ingest_scoped`:** gap-диапазоны локализовать по vtt-таймкодам,
   срезать один сплошной диапазон ffmpeg-ом на VM (overlap-вставка дешевле
   второго offset), Stage 1/2 только на срезе. **Грабля:** таймкоды ASR —
   относительно среза; при разметке сегментов прибавлять offset, иначе
   deep-links будут вести не туда (`expert-admission-control.md` §16.3).

Пример полного прогона: `OiULPvTJ-0E` (2026-09-20) — ядро overlap, вердикт
`ingest_scoped`, импортировано 8 сегментов хвоста 10:25–19:42, gap-темы
(robo-arm, hypermotion, two-layer prompt) ищутся Скаутом.

### 0.1 Get the media onto the VM
YouTube blocks the VM datacenter IP directly ("Sign in to confirm you're not a
bot"). Three paths, in order of preference (0.1a verified 2026-09-26):

**0.1a. Cloudflare WARP in SOCKS-proxy mode on the VM (preferred, no other
machine needed).** Free, community-verified method for datacenter IPs. The
client runs in proxy mode only — a local SOCKS5 on `127.0.0.1:40000`, so the
panel/SSH traffic is untouched and only yt-dlp goes through WARP:

```bash
# one-time setup (arm64/jammy): apt repo pkg.cloudflareclient.com, package
# cloudflare-warp; then:
warp-cli --accept-tos registration new
warp-cli --accept-tos mode proxy
warp-cli --accept-tos connect          # SOCKS5 on 127.0.0.1:40000
# download (rate-limited per community advice; formats are often 50fps —
# request 299/303/399, not just 137):
yt-dlp --proxy socks5h://127.0.0.1:40000 --js-runtimes node:/usr/bin/node \
  -r 5M -c -f "299/303/399/312/18/best" -o video.mp4 URL
yt-dlp --proxy socks5h://127.0.0.1:40000 --js-runtimes node:/usr/bin/node \
  -r 5M -c -f "140/251/249/bestaudio" -o audio.m4a URL
```

Notes: `warp-cli` needs the global `--accept-tos` flag before the subcommand;
proxy mode does not hijack the default route. The `bgutil-ytdlp-pot-provider`
PO-token sidecar was tried and is NOT required with WARP (it even slows
requests when its container cannot reach the proxy) — keep it disabled unless
downloading without WARP. Old notes: keep `-r 5M` (faster rates trigger 403 on
new videos) and avoid hard `[ext=mp4]` constraints (they fall back to blocked
legacy clients).

Fallback paths when WARP is unavailable (detail and commands —
`docs/archive/2026-09-20-videohub-knowledge-matrix-proposal.md` §6.4a,
историческая деталь):

- **G15 (Windows laptop, preferred, 2026-09-20):** fresh `yt-dlp.exe` in
  `%USERPROFILE%\expp` opens formats up to 4K (video `-f 137`, EN-original
  audio `-f 140-20`); persistent reverse tunnel G15→VM on port 2223
  (Task Scheduler `expa-vm-tunnel`), then `scp -P 2223` pulls files to VM.
- **Mac (backup):** reverse tunnel `-R 2222` (the `fetch_audio.sh` pattern),
  SSH from VM with `~/.ssh/mac_remote`. Verified capable of FULL 1080p ingest
  on 2026-09-25 (G15 offline) when the download stack is fresh: standalone
  `yt-dlp` in `~/.local/bin` (the brew-pip copy is stale and dies with
  HTTP 403 / SABR) plus `deno` in `~/.deno/bin` for the n-sig challenge —
  put both on PATH. Video `-f 137`, audio `-f 140/251/bestaudio` (opus is
  fine for ASR). Run downloads under `nohup` so an SSH drop does not kill
  them. The Mac has no ffmpeg (Stage 1 runs on the VM) and overheats on
  long work.

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

Combine сохраняет разные инструкции даже при одинаковой теме и близких таймкодах. Удаляются только одинаковые свидетельства из соседних чанков. Искусственно менять `topic_id` ради обхода дедупликации больше не требуется.

- **[НА ЭКРАНЕ] по кадрам, OCR помогает чтению.** Промпты и настройки
  сверяй с native-кадрами: результат OCR сам по себе не подтверждает точность
  символов. На VM проверен `rapidocr-onnxruntime 1.4.4` в `/usr/bin/python3`
  (Python 3.10, пользовательский пакет `ubuntu`; не backend venv).
  У установленной модели `ch_PP-OCRv4_rec_infer.onnx` нет полного русского
  алфавита — распознавание русских надписей этой конфигурацией не считать
  надёжным. Проверено 2026-09-30 по словарю в metadata ONNX-модели.
  Нечитаемое не выдумывать; важные цифры и промпты проверять визуально.

### 0.4 Combine, import, embed

```bash
backend/.venv/bin/python backend/scripts/ingest_video.py --combine --out /tmp/<id>_ingest
backend/.venv/bin/python backend/scripts/import_video_json.py /tmp/<id>_ingest/segments.json --dry-run
backend/.venv/bin/python backend/scripts/import_video_json.py /tmp/<id>_ingest/segments.json
backend/.venv/bin/python backend/scripts/embed_posts.py --continuous --receipt /tmp/<id>_ingest/segments.import-receipt.json
```

До combine: каждый чанк должен содержать согласованные метаданные ролика, включая настоящую дату публикации. Проверяется весь ожидаемый набор чанков. Пути кадров автоматически перебазируются относительно каталога чанка; проверить существование файлов всё равно нужно. Import без даты, с пустым текстом, отрицательным таймкодом или конфликтующей идентичностью останавливается.

Для scoped ingest сохраняй `video_metadata.scope` и `scope_range_s` (границы на исходной шкале YouTube). `timestamp_seconds` — навигационный keyframe; `start_seconds`/`end_seconds` добавляй только при проверенных границах. Импорт эти поля сохраняет, но не выдумывает отсутствующее покрытие.

Phase 1: до импорта сопоставь реальные сегменты с ячейками таксономии: `matrix_cells: ["domain/subdomain/intent"]` у каждого подтверждающего сегмента. Это лёгкая разметка, не отдельный тяжёлый паспорт. В `admission_log.json` сохраняй выбранные cells и `segments_path`, если источник лежит вне стандартного ingest-каталога.

После commit импорт создаёт `segments.import-receipt.json` со статусом `loaded`, SHA256 источника и соответствием cell → source_key. Команда embedding выше должна закончиться успешно и подтвердить `searchable`. Только затем пересобирай матрицу:

```bash
backend/.venv/bin/python backend/scripts/build_video_matrix.py
```

Обновление матрицы — обязательный шаг чек-листа, а не отдельное обещание:
забыл пересобрать — карта устаревает (`video_matrix.md`/`.json` генерируются, руками
их не править).

Старые материалы без receipt считаются неподтверждёнными, а не отсутствующими в базе. Не создавай подтверждения вручную по одному verdict. Их проверка/повторный импорт — отдельная работа с данными по разрешению владельца. Изменение исходного JSON делает receipt устаревшим; после уточнения разметки повтори импорт и проверку индексов. Уже импортированные материалы эти правки кода не пересоздают.

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
6. ДАТА ВЫХОДА: в video_metadata.published_at всегда ставь дату публикации видео на YouTube (YYYY-MM-DD) — поле обязательно.
7. КЛЮЧЕВЫЕ КАДРЫ (ON-SCREEN MOMENTS): значимые моменты фиксируй меткой [НА ЭКРАНЕ: ...] в 'content', а в timestamp_seconds ставь СЕКУНДУ ПОЯВЛЕНИЯ кадра, не начало сегмента. Ключевой = читаемый текст (промт/заголовок/метрика), интерфейс/настройки/модалка, таблица/график/код/формула, результат генерации, «до/после», клик или уведомление. Каденция ~1 кадр/15 сек, но без насилия. При сомнении — фиксируй. Частично нечитаемое помечай [НА ЭКРАНЕ (неуверенно): ...].

ФОРМАТ ВЫХОДА (JSON):
{
  "video_metadata": { "title": "...", "author": "Gleb Kudryavtcev", "url": "...", "duration_seconds": 0, "published_at": "YYYY-MM-DD" },
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
- **Timestamps:** `video_metadata.published_at` (YYYY-MM-DD) is required by the
  Stage-2 prompt; the importer normalizes it to canonical `YYYY-MM-DD HH:MM:SS`.
  Rows imported before 2026-09-24 are healed by
  `backend/scripts/maintenance/normalize_video_timestamps.py` (staging DB;
  production goes with the owner's `обнови базу`).
- **Database:** staging `backend/data/experts.db` → promoted to production via
  `DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh` (= Production data release,
  см. `docs/operations.md`). Legacy manual flow can still promote a ready JSON via
  `scripts/deploy_video.sh`. Устаревший Fly.io SFTP-путь удалён 24.08.2026.
- **Runtime Auth:** query-time Video Hub calls the configured OpenRouter models from `backend/.env` / managed secrets.
- **Important:** neither `deploy_video.sh` nor the ingest pipeline calls production; production DB changes only through the owner's `обнови базу`.
