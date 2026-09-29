# Starter: ввод тройки free-roam в VideoHub + матрицу (3I2jj6HA3p0, yUiTmO8AjJc, 6dNnvhoR3YY)

**Status:** Done (архив: задача закрыта 2026-09-29 — все три видео введены в
staging, матрица пересобрана (13 клеток / 0 gaps), watchlist и индекс обновлены;
data release «обнови базу по визуалам» и выкатка — по отдельной команде владельца)
**Last updated:** 2026-09-29
**Задача:** без лишних вопросов обработать три видео из free-roam-тройки через
полный цикл ввода в VideoHub + матрицу (по одному, от полного цикла к
следующему), затем обновить доки и отчитаться. По завершении — `git mv`
этого файла в `docs/archive/` и обновить статусы в
`docs/roadmap/video-hub-scaling.md` (watchlist).

Это handoff-промт активной задачи: он актуальнее общей навигации. Начни с него,
затем открой указанные SSOT-доки.

---

## 0. Команда владельца (дана 2026-09-29)

Владелец провёл free-roam поиск новых каналов и утвердил работу по этой тройке:
«новая сессия должна сразу найти этот стартер и начать по нему работать» —
то есть провести тройку через полный цикл ввода. Вердикт `ingest` для тройки
считается одобренным этой командой (`decided_by:
agent_proposed_owner_approved`). Спрашивать подтверждения не нужно; если что-то
технически невыполнимо — честно написать в отчёте, а не замалчивать.

Финальные owner-операции («обнови базу по визуалам», «выкатывай», commit/push)
выполняются только по явной команде владельца в той же сессии — как обычно.
Если команды не было — завершить отчётом с готовностью к ним.

## 1. Видео (работать по одному, от полного цикла к следующему)

Порядок — по ценности для матрицы (сверка с gap/overlap сделана, см. §2).

1. **`3I2jj6HA3p0`** — «I Mixed AI With Real Footage… and I'm Kinda Scared
   (3 VFX Tricks)», River Cody, 512s (2026-01-27). **Закрывает единственную
   дыру матрицы `hybrid_ai_vfx_pipeline`**: clean plate + достройка разрушений
   (дерево падает на крышу) поверх реального кадра (Скаут: у разрушений поверх
   плейта 0 хитов; clean plate/гибрид-композ — точечный overlap: `cgevent:16218`,
   `cgevent:16417`, `iideyalogiya:1963`, `video_hub:12983652`), DaVinci
   magic mask / композитинг ИИ-слоя, «generations = takes», второй воркфлоу
   (снять свет → base grade → Nano Banana Pro → remove subject → Cinema Studio
   → анимированный фон). Черновик `cells` для admission_log (полные ID):
   `creative_multimodal/hybrid_ai_vfx_pipeline/build_human_ai_workflow`
   (primary), `creative_multimodal/cg_craft_to_ai/build_human_ai_workflow`,
   `creative_multimodal/color_and_light/build_human_ai_workflow`; черновые
   атрибуты — `draft_attributes` в журнале проб.
2. **`yUiTmO8AjJc`** — «The Easiest Way for Filmmakers to Start Using Blender
   (with Switchlight AI!)», Max Novak, 752s (2025-03-03). **Первое покрытие
   темы light maps / relighting** (Скаут: 0 хитов, «Switchlight» — 0
   совпадений): карты освещения из съёмного плейта, согласование света
   3D-объекта с реальной съёмкой, кейс «серая стена → хоррор-кадр с
   3D-персонажем». Черновик `cells` (полные ID):
   `creative_multimodal/color_and_light/build_human_ai_workflow` (primary),
   `creative_multimodal/cg_craft_to_ai/build_human_ai_workflow`,
   `creative_multimodal/hybrid_ai_vfx_pipeline/build_human_ai_workflow`.
   Caveat: version_lock (Switchlight open beta 2025-03) — зафиксировать в
   `caveat`; техника световых карт durable.
3. **`6dNnvhoR3YY`** — «I Tested 3 AI Video Generators: Which One Has the Best
   Character Consistency?», AI Video Studio, 556s (2026-05-26).
   Воспроизводимый side-by-side тест «один персонаж, одни промты, 3 модели»
   (Seedance / Kling / Veo 3.1 в Runway) + contact sheet + стоимость/скорость
   (Скаут: системных тестов в корпусе нет). Черновик `cells` (полные ID):
   `creative_multimodal/multimodal_generation/compare_models_for_task`
   (primary),
   `creative_multimodal/character_consistency/build_human_ai_workflow`;
   Veo 3.1 в протестированном наборе — разнообразие к нашему
   Seedance/Higgsfield-ядру. Caveat: version_lock (модели крутятся).

Запасные кандидаты (если один из тройки отвалится): `CAWnlOJbSX4` (River Cody,
5 уровней «скучная локация → кино», резерв №1 — проверить дубль с
levels-фреймворком AI Samson `5y20tE7zo40`), затем `qwGIwxZFc2I` (Dan Kieft,
проба готова). Отсеяны пробами и НЕ брать: `RaJ0cywS7Hw`, `SWhYbZxRZCA`
(липсинк/голос — плотный overlap с корпусом).

## 2. Что уже сделано (не переоткрывать)

- **Free-roam discovery:** Reddit (`reddit-search`, в основном abstained), HN
  (шум), веб-списки (LinkedIn «9 AI Filmmaking Channels», Matti Haapoja) —
  каналы и аргументация в `docs/roadmap/video-hub-scaling.md`, раздел
  «Кандидаты на ingest (watchlist)» → «Каналы на радаре».
- **Ранние пробы готовы:** транскрипты (auto-captions) и `scout_probe1.md` —
  `output/video_admission/{3I2jj6HA3p0,yUiTmO8AjJc,6dNnvhoR3YY}/`; вердикты,
  gap/overlap по Скауту и `draft_attributes` —
  `output/video_admission/candidate_probe_journal.json`. Duplicate-check:
  все три FREE (`video_hub_index.py --check`).
- **Сверка с матрицей сделана:** `output/video_admission/video_matrix/`
  (13 видео / 308 сегментов / 12 клеток / 1 gap `hybrid_ai_vfx_pipeline`);
  тройка выбрана по gap/тонким клеткам, overlap-кандидаты отсеяны.
- **Операторская процедура и грабли:** `docs/guides/video-hub-operator.md`
  (0.0b — гейт, 0.1a — WARP-скачивание, 0.2–0.4 — Stage 1/2 + combine +
  импорт; в 0.3–0.4 — проверенные грабли combine и OCR для `[НА ЭКРАНЕ]`).
- **Доктрина гейта:** `docs/architecture/expert-admission-control.md` §16.
- **Образец прошлых циклов:** `H8WDehuVams` (25 сегментов) и `reFzEtCG_m8`
  (33 сегмента) — оба 2026-09-29; записи в `admission_log.json`, сегменты в
  `output/video_ingest/<id>/ingest/segments.json`, стиль коммита в `git log`.

## 3. Цикл на каждое видео

1. **Вердикт** `ingest` в `output/video_admission/admission_log.json`
   (`decision_basis` — из проб журнала + scout-цитаты; `cells` — черновики из
   §1, уточнить по `topic_id` после Stage 2; `decided_by:
   agent_proposed_owner_approved`, `decided_at` — сегодня).
2. **Медиа через WARP:** `yt-dlp --proxy socks5h://127.0.0.1:40000
   --js-runtimes node:/usr/bin/node -r 5M -c` (видео `299/303/399/312/18/best`,
   аудио `140/251/249/bestaudio`) в `output/video_ingest/<id>/media/`.
   При 403 — повтор с `--sleep-requests 3 --retries 5` (проверено).
3. **Stage 1:** `backend/.venv/bin/python backend/scripts/ingest_video.py
   --video ... --audio ... --video-id <id> --out
   output/video_ingest/<id>/ingest --chunk-minutes 5`.
4. **Stage 2 (ты — LLM-пасс):** по каждому чанку читай `transcript` из
   `chunk_meta.json` + OCR контактных листов/кадров (на VM есть
   `rapidocr-onnxruntime`, ~1.3с/кадр; паттерн — playbook 0.3; одноразовый
   OCR-скрипт прошлой сессии не сохранён — переписать ~30 строк), пиши
   `chunks/chunk_NN/segments.json`. Правила:
   - `segment_id` сквозной внутри видео (от 1001, не сбрасывать между чанками);
   - соседним сегментам в overlap-окне давать РАЗНЫЕ `topic_id` (иначе combine
     их схлопнет);
   - «клей»: 1–2 предложения конца сегмента N — в начало N+1;
   - речь дословно (ASR-опечатки имён моделей нормализовать);
   - `title`/`summary` на русском, `content` — дословная речь + `[НА ЭКРАНЕ:
     ...]` с промтами/настройками с экрана (по OCR, нечитаемое не выдумывать);
   - `timestamp_seconds` — секунда появления ключевого кадра;
   - `frames: [{time_s, path}]` — голые имена dense-кадров (combine).
5. **Combine + импорт (грабли — playbook 0.4):**
   - после `--combine` пути кадров переписать на полные
     `chunks/chunk_NN/frames_dense/<file>` (по префиксу `cNN` имени файла) и
     сверить, что все файлы существуют;
   - `video_metadata` (`title`, `author`, `url`, `duration_seconds`,
     `published_at` — даты из §1/журнала) должен быть в `segments.json`;
   - затем полный прогон: `import_video_json.py ... --dry-run` → тот же вызов
     без `--dry-run` → `backend/.venv/bin/python
     backend/scripts/embed_posts.py` (дождаться N/N без ошибок).
6. **Фаза 1:** уточнить `cells` по `topic_id` сегментов в `admission_log.json`,
   пересобрать матрицу `backend/.venv/bin/python
   backend/scripts/build_video_matrix.py` (руками не править!), обновить индекс
   `backend/.venv/bin/python backend/scripts/video_hub_index.py --write`.
7. **После всех трёх:** обновить watchlist и Current State в
   `docs/roadmap/video-hub-scaling.md` (тройку перевести в «недавно введены»,
   поднять резервы, цифры, оставшиеся дыры) и `candidate_probe_journal.json`
   (`decision`/`decision_note` по тройке).

## 4. Финал (команды владельца)

1. По явной команде «обнови базу по визуалам»: `./scripts/update_production_db.sh
   --check`, затем `./scripts/update_production_db.sh --scope visual` в tmux,
   мониторить до `SUCCESS` (VideoHub-промоушен глобальный).
2. По явной команде «зафиксируй»/«выкатывай»: коммит в стиле репо (см. `git
   log`; ingest-сообщение с числом сегментов и индексом; доки — туда же или
   отдельным docs-коммитом) → `git push origin main` → `gh run watch` за
   `deploy-oracle.yml` → `https://expa.beyondhorizon.dev/health`.
   Не коммитить `backend/scripts/benchmark_reddit_synthesis_models.py`
   (чужая незаконченная работа) и `output/` (в .gitignore).
3. **Отчёт:** что сделано, что проверено, что не проверено, статус матрицы
   (дыры), что осталось в watchlist.
4. `git mv` стартера в `docs/archive/`, маршрут в `docs/DOCUMENTATION_MAP.md`
   перевести в «Завершено».

## 5. Правила проекта (кратко)

- Общение только RU/EN (`AGENTS.md`); работать только в
  `/home/ubuntu/apps/experts-panel/dev`.
- Не читать/печатать секреты, `.env`, БД напрямую (исключение — read-only
  Скаут), не трогать production checkout `app`.
- Медиа качать только для тройки из §1 (и запасных — по ситуации); новых
  кандидатов не разрабатывать — watchlist решает владелец.
