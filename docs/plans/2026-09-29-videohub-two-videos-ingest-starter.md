# Starter: ввод двух видео в VideoHub + матрицу (H8WDehuVams, reFzEtCG_m8)

**Status:** Active starter (handoff из сессии 2026-09-29)
**Last updated:** 2026-09-29
**Задача:** без вопросов обработать два видео из watchlist через полный цикл
ввода в VideoHub + матрицу, затем data release, коммит и деплой.
По завершении — `git mv` этого файла в `docs/archive/` и обновить статусы в
`docs/roadmap/video-hub-scaling.md` (watchlist).

Это handoff-промт активной задачи: он актуальнее общей навигации. Начни с него,
затем открой указанные SSOT-доки.

---

## 0. Команда владельца (дана 2026-09-29, действуй без уточнений)

Владелец уже принял решение — вердикт `ingest` для обоих видео утверждён.
Ниже разрешён полный цикл, включая финальные операции «обнови базу по
визуалам» и «выкатывай». Спрашивать подтверждения не нужно; если что-то
технически невыполнимо — честно написать в отчёте, а не замалчивать.

## 1. Видео (работать по одному, от полного цикла к следующему)

1. **`H8WDehuVams`** — «How to Create Realistic AI Avatars (Full Guide)»,
   Youri van Hofwegen, 926s. Ценность: закрывает дыру матрицы
   `lipsync_dubbing` (голос + липсинк аватара); gap по пробам: audio-промт
   «речь на камеру против нарратива», правило ~75 слов/30с, мульти-ref
   переходы одним вызовом.
2. **`reFzEtCG_m8`** — «How To Animate a Short Film with Blender + Higgsfield
   (Full Breakdown)», Higgsfield Animation (аниматор Amina), 1685s.
   Ценность: `3d_previz_pipeline` / `scene_blocking`, squash & stretch
   (0 хитов в корпусе), постмортемы провалов, акварельный пайплайн, новый
   автор. **ВАЖНО:** субтитры при пробе упёрлись в YouTube 429 — докачать
   auto-captions перед Stage 2 (WARP-прокси на VM работает; паузы между
   запросами); запасной материал (описание + таймкоды) уже лежит в
   `output/video_admission/reFzEtCG_m8/description.txt`.

Запасной кандидат (если один из двух отвалится): `qwGIwxZFc2I` (Dan Kieft,
20м) — см. watchlist.

## 2. Что уже сделано (не переоткрывать)

- **Watchlist с аргументацией:** `docs/roadmap/video-hub-scaling.md`, раздел
  «Кандидаты на ingest (watchlist)».
- **Доктрина гейта:** `docs/architecture/expert-admission-control.md` §16.
- **Операторская процедура:** `docs/guides/video-hub-operator.md` (0.0b —
  гейт, 0.1a — WARP-скачивание, 0.2–0.4 — Stage 1/2 + импорт + матрица).
- **Пробы уже сделаны** (транскрипты, 2 scout-прогона на видео, разбор gap/
  overlap) — артефакты в `output/video_admission/<id>/`, журнал вердиктов —
  `output/video_admission/candidate_probe_journal.json` (дописать `decision:
  ingest` и `decision_note`).
- **Образец прошлого цикла:** видео `y8PJ3B38S2o` (17 сегментов, 2026-09-29) —
  запись в `admission_log.json`, сегменты в
  `output/video_ingest/y8PJ3B38S2o/ingest/segments.json`, стиль коммита в
  `git log`.

## 3. Цикл на каждое видео

1. **Вердикт** `ingest` в `output/video_admission/admission_log.json`
   (`decision_basis` — из проб журнала; `decided_by:
   agent_proposed_owner_approved`, `decided_at` — сегодня).
2. **Медиа через WARP:** `yt-dlp --proxy socks5h://127.0.0.1:40000
   --js-runtimes node:/usr/bin/node -r 5M -c` (видео `299/303/399/312/18/best`,
   аудио `140/251/249/bestaudio`) в `output/video_ingest/<id>/media/`.
3. **Stage 1:** `backend/.venv/bin/python backend/scripts/ingest_video.py
   --video ... --audio ... --video-id <id> --out
   output/video_ingest/<id>/ingest --chunk-minutes 5`.
4. **Stage 2 (ты — LLM-пасс):** по каждому чанку читай `transcript` из
   `chunk_meta.json` + контактные листы/кадры, пиши
   `chunks/chunk_NN/segments.json`. Правила:
   - `segment_id` сквозной внутри видео (от 1001, не сбрасывать между чанками);
   - «клей»: 1–2 предложения конца сегмента N — в начало N+1;
   - речь дословно (ASR-опечатки имён моделей нормализовать: Seedense→Seedance);
   - `title`/`summary` на русском, `content` — дословная речь + `[НА ЭКРАНЕ:
     ...]` с промтами/настройками с экрана (нечитаемое не выдумывать);
   - `timestamp_seconds` — секунда появления ключевого кадра;
   - `frames: [{time_s, path}]` — ссылки на плотные кадры.
5. **Combine + импорт (грабли, проверено 2026-09-29!):**
   - после `--combine` пути кадров в `segments.json` обязаны быть полными
     относительными: `chunks/chunk_NN/frames_dense/<file>` (combine НЕ
     переписывает пути — переписать самому по префиксу `cNN` имени файла);
   - в `segments.json` должен быть `video_metadata` (`title`, `author`, `url`,
     `duration_seconds`, `published_at` — обязательно, иначе импорт скажет
     «Untitled Video»);
   - затем `import_video_json.py --dry-run` → реальный импорт →
     `embed_posts.py` (дождаться N/N без ошибок).
6. **Фаза 1:** уточнить `cells` по `topic_id` сегментов в `admission_log.json`,
   пересобрать матрицу `backend/.venv/bin/python
   backend/scripts/build_video_matrix.py` (руками не править!), обновить индекс
   `backend/.venv/bin/python backend/scripts/video_hub_index.py --write`.
7. **После обоих видео:** обновить watchlist и Current State в
   `docs/roadmap/video-hub-scaling.md` (цифры, статусы кандидатов, оставшиеся
   дыры матрицы) и `candidate_probe_journal.json` (`decision`/`decision_note`).

## 4. Финал (разрешено этим стартером, без вопросов)

1. **«обнови базу по визуалам»:** `./scripts/update_production_db.sh --check`,
   затем `./scripts/update_production_db.sh --scope visual` в tmux, мониторить
   до `SUCCESS` (VideoHub-промоушен глобальный — сегменты уходят в прод).
2. **Коммит** в стиле репо (см. `git log`): ingest-сообщение с числом
   сегментов и обновлённым индексом; доки — туда же или отдельным
   docs-коммитом. Не коммитить `backend/scripts/benchmark_reddit_synthesis_models.py`
   (чужая незаконченная работа) и `output/` (в .gitignore).
3. **«выкатывай»:** `git push origin main` → `gh run watch` за
   `deploy-oracle.yml` → проверить `https://expa.beyondhorizon.dev/health`.
4. **Отчёт:** что сделано, что проверено, что не проверено, статус матрицы
   (дыры), что осталось в watchlist.

## 5. Правила проекта (кратко)

- Общение только RU/EN (`AGENTS.md`); работать только в
  `/home/ubuntu/apps/experts-panel/dev`.
- Не читать/печатать секреты, `.env`, БД напрямую (исключение — read-only
  Скаут), не трогать production checkout `app`.
- Не делать ничего сверх перечисленного. Медиа не качать для новых кандидатов
  сверх двух видео — watchlist решает владелец.
