# VideoHub Starter (handoff)

**Дата:** 2026-09-16
**Тема:** автоматический ingest видео + поиск по видео через Expert Scout
**Статус:** ingest работает, 1 видео в dev-корпусе, scoped data release готов

> Это handoff-промт для нового чата. Сначала прочитай `AGENTS.md`, затем
> `docs/DOCUMENTATION_MAP.md`, затем профильные доки из §0 ниже.

---

## 0. Что читать дальше

1. `AGENTS.md` — правила проекта (язык, операции владельца, запреты).
2. `docs/architecture/video-hub-service.md` — SSOT: схема сегмента, `visual`,
   `frames`, «Automated Ingest Pipeline», query-time 4-фазный пайплайн.
3. `docs/guides/video-hub-operator.md` — playbook: Phase 0 (автоматический
   ingest), Phase 1 (legacy AI Studio), troubleshooting.
4. `docs/operations.md` — code/data release, включая scoped `--scope visual`.
5. `docs/guides/expert-scout.md` — как Скаут ищет и какие поля отдаёт.

---

## 1. Контекст задачи

VideoHub — synthetic-эксперт (`expert_id="video_hub"`) для видео-материалов.
Раньше видео размечали руками в Google AI Studio. Теперь ingest автоматический:
ASR + адаптивные кадры + LLM-пасс по чанкам, затем импорт в `posts` с
эмбеддингами. Поиск по видео идёт **через Expert Scout** (у него собственный
гибридный движок FTS5 + sqlite-vec + RRF по `posts`).

---

## 2. Текущее состояние (проверено)

- **Коммиты:** `69c5efa` (ingest + Scout deep links), `65fbc53` (scoped release
  `--scope visual`). Оба запушены и выкачены, прод `/health` зелёный.
- **dev-корпус:** `video_hub` = **11 постов** — 1 видео
  «STOP Wasting Credits & Master Seedance 2.5» (Youri van Hofwegen,
  https://youtu.be/2b3Z4rW5VJc, published 2026-08-21). Старые 53 сегмента
  VideoHub удалены по решению владельца.
- **Scoped data release:** `./scripts/update_production_db.sh --scope visual`
  (владельческая фраза «обнови базу по визуалам»). Сам scoped-релиз пока НЕ
  запускался; обычный data release от 2026-09-16 ночью уже включал эти 11
  сегментов в production.
- В рабочем дереве есть **чужие незакоммиченные изменения**:
  `docs/DOCUMENTATION_MAP.md` (admission) и untracked
  `backend/scripts/benchmark_reddit_synthesis_models.py`. Их не трогать и не
  коммитить вместе со своими.

---

## 3. Что уже в коде

| Что | Где |
|---|---|
| Stage 1 ingest (чанки, ASR, окна, кадры, `--combine`) | `backend/scripts/ingest_video.py` |
| ASR-хелпер (faster-whisper int8, глоссарий, авто-язык) | `backend/scripts/asr_whisper.py` |
| Импорт (visual, frames, published_at, upsert) | `backend/scripts/import_video_json.py` |
| Скаут: deep-links `video_link`/`video_timestamp_s` | `backend/scripts/expert_scout.py` |
| Синтез: правило VISUAL ELEMENTS (ambient/informational/unreadable) | `backend/src/services/video_hub_service.py` |
| Golden Prompt сегментации | `backend/prompts/video_segmentation_prompt.md` |
| Scoped release (`--scope`) | `scripts/update_production_db.sh` + sync/drift сервисы |

### Команды пайплайна

```bash
# stage 1 (на VM; медиа уже скачано с Мака)
backend/.venv/bin/python backend/scripts/ingest_video.py \
  --video /path/video.mp4 --audio /path/audio.m4a \
  --video-id <youtube_id> --out /tmp/<id>_ingest --chunk-minutes 5
#   --audio обязателен, если в видеофайле нет аудиодорожки;
#   повторный прогон без ASR: --skip-asr --transcript <json>;
#   глоссарий под тематику: --glossary "Seedance, Higgsfield, ..."

# stage 2: LLM-пасс делаешь ТЫ САМ (ты и есть модель). Читаешь по чанку:
#   chunks/chunk_NN/chunk_meta.json        — срез транскрипта + окна
#   chunks/chunk_NN/sheets_coarse/         — листы для триажа
#   chunks/chunk_NN/sheets_dense/          — листы плотных окон
#   chunks/chunk_NN/frames_dense/c01_w01_00002600.jpg — нативные кадры
#     (имя = чанк_окно_секунды×10: 00002600 = 260.0s)
# и пишешь chunks/chunk_NN/segments.json по схеме из
# docs/architecture/video-hub-service.md, раздел «Extended Segment Schema».

# затем:
backend/.venv/bin/python backend/scripts/ingest_video.py --combine --out /tmp/<id>_ingest
backend/.venv/bin/python backend/scripts/import_video_json.py /tmp/<id>_ingest/segments.json --dry-run
backend/.venv/bin/python backend/scripts/import_video_json.py /tmp/<id>_ingest/segments.json
backend/.venv/bin/python backend/scripts/embed_posts.py
```

### Конвенции данных (соблюдать)

- `visual` пишется в `media_metadata.visual` **и** добавляется в `message_text`
  блоком `VISUAL:` — иначе промты не находятся поиском (индексируется только
  `message_text`).
- Кадры копируются в `backend/data/video_frames/<video_hash>/` (gitignored).
- `import_video_json.py` делает upsert по `telegram_message_id`; не заменять на
  `INSERT OR REPLACE` — он пересоздаёт строку и сиротит эмбеддинги
  (и `post_embeddings`, и `vec_posts`).

---

## 4. Решения владельца (не пересматривать без спроса)

1. **VideoHub НЕ включаем в панель и Панэкс.** В оркестраторе 4 исключения
   `expert_id != "video_hub"`, Agent Context API отклоняет video_hub. Поиск по
   видео — только Expert Scout.
2. **OCR не вводим.** Зрение модели хватает при нативных кадрах.
3. **Whisper всегда**, авто-субтитры YouTube не берём (грязные).
4. **Кадры только в нативном разрешении** — на уменьшенных текст не читается.

---

## 5. Ограничения среды (грабли)

- **IP VM заблокирован YouTube** (бот-чек). Медиа качается на Маке через
  обратный SSH-туннель, затем `scp` на VM. Туннель поднимает владелец с Мака
  (`ssh -N -R 2222:localhost:22 ubuntu@82.70.251.73`), на VM он виден как
  `127.0.0.1:2222`. На Маке **нет ffmpeg**, поэтому качать раздельно:
  video-only 1080p + audio m4a, склейка/обработка — уже на VM.
- **ASR** запускать через `/usr/bin/python3.11` (в `backend/.venv`
  faster-whisper нет). Модели в кэше HF, CPU int8, ~0.7–1.0 RT.
- **Не читать** прод-базу, `.env`, секреты, backups, логи. Production DB —
  только по команде владельца. dev-корпус читать только санкционированным
  путём: Expert Scout (`backend/scripts/expert_scout.py` / агент `expert-scout`).
- **Долгие операции** (ASR, data release) запускать в `tmux`/`setsid` —
  bash-таймауты убивают фоновые процессы, если не отделить сессию.

---

## 6. Артефакты последнего прогона

`/tmp/opencode/p0/ingest_final/`: `segments.json`, `transcript.json`,
`chunks/`, `chunks_index.json`, `meta.json`. Это **временные файлы** — `/tmp`
может очиститься. Пайплайн воспроизводим: медиа → stage 1 → LLM-пасс →
`--combine` → import → embed.

По умолчанию `ingest_video.py` пишет в `output/video_ingest/<video_id>/`
(gitignored) — для новых видео лучше использовать его, а не `/tmp`, чтобы
артефакты пережили перезагрузку.

---

## 7. Возможные следующие шаги

- Залить следующее видео по пайплайну (глоссарий под тематику — `--glossary`,
  туда же имена моделей/продуктов, которые Whisper коверкает).
- Запустить scoped-релиз: `./scripts/update_production_db.sh --scope visual`
  (по фразе владельца «обнови базу по визуалам»).
- Тюнинг ingest по реальным данным: `--max-windows-per-chunk`,
  `--max-dense-frames-per-chunk`, `--dense-max-gap`, порог дедупа.
- Из roadmap (`docs/roadmap/video-hub-scaling.md`): retry/backoff, chunking в
  Video Map, валидация ID, клипы как артефакт.

---

## 8. Первые шаги нового агента

1. `git status` — убедись, что не трогаешь чужие изменения (см. §2).
2. Проверь dev-корпус **санкционированным способом** — через Expert Scout
   (`backend/scripts/expert_scout.py experts` или агент `expert-scout`):
   у `video_hub` должно быть 11 постов. Прямые SQL-чтения базы не делать.
3. Спроси владельца, что делаем (варианты в §7).

---

## 9. Completion addendum (2026-09-17)

Сделано по итогам ревью VideoHub (см. `docs/roadmap/video-hub-scaling.md`,
раздел «Review fixes»):

- **Guards целостности ingest**: `--combine` падает на дублях `segment_id` и
  не-объектных сегментах, chunk-локальные метаданные не текут в финальный JSON;
  transcript валидируется по ASR-схеме; `--skip-asr` без `--transcript` запрещён.
- **`import_video_json.py`**: канонизация YouTube-URL (одна идентичность на
  видео, включая `youtu.be`/`shorts`/`embed`/`watch?v=`), флаг `--replace-video`
  (чистая пересегментация с удалением эмбеддингов), инвалидация эмбеддингов при
  изменении `message_text`, guard дублей virtual ID, `channel_username`.
- **`video_hub_service.py`**: `_normalize_scores` (валидация Map-ответа, включая
  фантомные ID и float-коэрцию), Map-контракт без `reason`, динамическая дата,
  мёртвые импорты.
- **`PostCard.tsx`**: deep-link собирается с `?`/`&` в зависимости от формы URL
  (был битый `&t=` для `youtu.be`-ссылок).
- **Тесты**: `backend/tests/test_video_ingest_guards.py` — 23 теста.
- **Staging**: 11 сегментов переимпортированы с каноническим URL
  (`--replace-video`), эмбеддинги пересозданы, старый
  `video_frames/2a038a73b55c` удалён; артефакты прогона сохранены в
  `output/video_ingest/2b3Z4rW5VJc/` (gitignored).

Проверки: `pytest test_video_ingest_guards.py test_expert_scout.py` — 42 passed;
`tsc --noEmit`; dry-run импорта с дублем и `--replace-video`; Scout: 11 постов,
deep-links вида `watch?v=...&t=40s`.

Не сделано сознательно: retry/backoff в query-time VideoHub (ветка dormant),
production data release (нужна команда владельца «обнови базу»), браузер-проверка
кнопки Watch Video (video_hub скрыт в UI).

Note: чужие незакоммиченные изменения (`docs/DOCUMENTATION_MAP.md` —
admission-строка, untracked `backend/scripts/benchmark_reddit_synthesis_models.py`)
остаются в рабочем дереве и в этот коммит не входят.
