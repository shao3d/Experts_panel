# VideoHub: полный онбординг `LOUEH3DzLro` (JOEY, Claude skills v2) — отчёт для приёмки

**Status:** Completed (staging-only; независимая повторная приёмка вторым агентом, ремонт кадров 1016 — §12 и вычистка систематического артефакта кадров Stage 1 — §13; формальная приёмка владельцем не проводилась; прод не тронут)
**Last updated:** 2026-10-18
**Исполнитель:** агент Experts Panel (сессия из корня `/home/ubuntu/apps/experts-panel/dev`; чат-сессия 2026-10-17)

Этот документ — операторский отчёт для передачи, не SSOT. SSOT процедуры онбординга:
`docs/guides/video-hub-operator.md`; контракт данных: `docs/architecture/video-hub-service.md`;
гейт: `docs/architecture/expert-admission-control.md` §16. Назначение документа —
полная передача контекста внешнему анализирующему агенту: что именно сделано,
какими командами, на каких свидетельствах, что перепроверено, что не проверено.

---

## 1. Задача и полномочия

Полный ingest ролика **LOUEH3DzLro — JOEY «How We Make AI Videos In A Day
(4 free Claude skills & how to use them)»** (опубликован 2026-10-14, ~22:05 (1324.57s), en,
жанр: production-разбор конвейера из четырёх бесплатных Claude skills).

- Вердикт **`ingest`, приоритет 1/5** — из октябрьской волны пробации
  (`output/video_admission/PROBE_REPORT_2026-10-17.md`; запись в
  `output/video_admission/admission_log.json` от 2026-10-16: транскрипт-проба +
  Scout-пробы RU+EN). Уникальный gap, подтверждённый Scout-пробами: **поименованная
  16-слотовая shotcaller-архитектура промпта с правилом «один факт — один слот»** — в
  корпусе 0 совпадений; канон-шит на 18% серого и story-bible покрыты частично другими
  авторами (Youri, JOEY-старые, acidcrunch).
- Phase-0 считался выполненным до этой сессии (дубль-чек FREE, транскрипт-проба).
- Одобрение владельца получено в чате 2026-10-17 и зафиксировано в журнале:
  `decided_by: "owner_directed_2026-10-17"` (`decided_at` остался 2026-10-16 — дата
  агентского предложения; формат как у IAl240xpSGM/UQDM-ZigvGo).

## 2. Хронология и команды

| Время (UTC) | Шаг | Действие | Результат |
|---|---|---|---|
| 12:56 | 0.1a префлайт | `warp-cli status`; `curl` через `socks5h://127.0.0.1:40000` | Connected; YouTube `204` |
| 12:56–12:57 | 0.1a скачивание | `yt-dlp --proxy socks5h://127.0.0.1:40000 --js-runtimes node:/usr/bin/node -r 5M -c -f "299/303/399/312/18/best" -o video.mp4 …` и `-f "140/251/249/bestaudio" -o audio.m4a` | video 132 MB (1920x1080, 1324.57s), audio 21 MB (1324.63s); в `/tmp/LOUEH3DzLro_ingest/` |
| 12:57–13:18 | 0.2 Stage 1 | `backend/.venv/bin/python backend/scripts/ingest_video.py --video … --audio … --video-id LOUEH3DzLro --out /tmp/LOUEH3DzLro_ingest --chunk-minutes 5` | ASR faster-whisper large-v3-turbo (int8, CPU): 297 реплик / 3839 слов, en p=0.9997, 907s; **5 чанков** (0–300, 275–575, 550–850, 825–1125, 1100–1324.57; overlap 25s); 285 coarse-кадров / 14 шитов, 38 окон, 219 dense |
| 13:20–14:00 | 0.3 Stage 2 | Ручная разметка агентом: чтение ASR-срезов, coarse/dense шитов, native-кадров; запись `chunks/chunk_NN/segments.json` | **27 сегментов (1001–1027)**, сквозные ID |
| 14:0x | перенос | `cp -r chunks …` + `chunks_index.json`, `meta.json`, `transcript.json` → `output/video_ingest/LOUEH3DzLro/` (76 MB) | Постоянный артефакт создан ДО combine |
| 14:02 | 0.4 | `ingest_video.py --combine --out output/video_ingest/LOUEH3DzLro` | 27 сегментов; дубликатов нет |
| 14:03:06 | 0.4 | `import_video_json.py … --dry-run` | ok: 27 segments, 37 frames |
| 14:03:17 | 0.4 | `import_video_json.py output/video_ingest/LOUEH3DzLro/segments.json` | импорт в staging `backend/data/experts.db`: 27 сегментов, 37 кадров, 0 замен; receipt создан |
| 14:03:29–44 | 0.4 | `embed_posts.py --continuous --receipt …/segments.import-receipt.json` | 27/27 эмбеддингов, 0 ошибок, **status=searchable** |
| 14:0x | 0.4 | `expert_scout.py videos --json` | **scope=full, coverage=declared_scope**, 27 сегментов (keyframes 18–1224) |
| 14:0x | 0.4 | `build_video_matrix.py` (дважды — см. §8.1) | 30 видео / 727 сегментов / 13 клеток / 0 gaps |
| 14:0x | 0.4 | `video_hub_index.py --write` | `docs/video-hub-index.md` регенерирован; `--check` теперь честно = DUPLICATE |
| 19:31–19:33 | ремонт (§12) | переизвлечены кадры 1016 (676/681/687), правка `chunk_03/segments.json` → combine → import → embed | receipt `e9402bda…`, 27/27 searchable; Матрица 30/727/13/0 |

Дубль-чек перед импортом повторно давал **FREE** (exit 0) — совпадает с пробацией.

## 3. Инвентарь артефактов

- **Постоянный ingest-набор:** `output/video_ingest/LOUEH3DzLro/`
  - `chunks/chunk_01..05/` — `chunk_meta.json`, `segments.json`, `sheets_coarse/`, `sheets_dense/`, `frames_coarse/`, `frames_dense/`, а также извлечённые вручную native-кадры `native_c*.jpg` (для экранных вставок, пропущенных кривой изменений);
  - `chunks_index.json`, `meta.json`, `transcript.json`;
  - итоговый **`segments.json`** — SHA256 `e9402bdab728cd80eba255d8257789c59e24b1392ffe6bcd989895e01b309cd4` (после ремонта §12; прежний `917f5eb2…` — до правки кадров 1016);
  - **`segments.import-receipt.json`**: 27 source_keys (`video_hub:858713004` …), `cell_sources` по 8 клеткам, `indexed_segments: 27`, `index_checked_at: 2026-10-17T19:32:08` (после ремонта §12).
- **Кадры-копии для БД:** `backend/data/video_frames/adc4b91ac8fe/` — **38 файлов** после ремонта (§12): 35 актуальных по ссылкам разметки (объяснение переиспользований — §7, п.4) + 3 неизменяемые копии заменённых кадров 1016 (не удаляются по дизайну).
- **Журнал:** `output/video_admission/admission_log.json` — запись LOUEH3DzLro дополнена полями приёмки (см. §6.1); шапка `updated_at: 2026-10-17`.
- **Матрица:** `output/video_admission/video_matrix/video_matrix.{md,json}` — LOUEH3DzLro: `state=searchable`, `in_corpus=true`, scope заполнен текстом, **8 verified_cells**.
- **Индекс:** `docs/video-hub-index.md` — шаг 0.4, регенерирован командой (output/ и backend/data/ в .gitignore, поэтому эпоха модификаций в git это не видит).
- **Git-состояние:** изменены отслеживаемые `docs/video-hub-index.md` и `docs/DOCUMENTATION_MAP.md` (регистрация отчёта); новый файл — сам отчёт (`docs/quality/2026-10-17-loueh3dzlro-onboarding-report.md`, вне индекса до коммита). Остальные M-файлы git-статуса (`.gitignore`, `scout-web/*`, `scripts/update_production_db.sh`) были изменены ДО этой сессии.
- **Оригиналы медиа:** `/tmp/LOUEH3DzLro_ingest/video.mp4`, `audio.m4a`, логи скачивания и Stage 1 (`stage1.log`).
- **Probe-артефакты (не тронуты):** `output/video_admission/LOUEH3DzLro/` — `LOUEH3DzLro.en.vtt`, `LOUEH3DzLro.en-orig.vtt`, `transcript.json`, `transcript_ts.txt`, `meta.txt`, `probe_notes.md`, `scout_probe.md`, `scout_probe_en.md`.

Секреты, `.env`, токены не читались и не печатались; `/home/ubuntu/apps/experts-panel/app` (production checkout) не открывался.

## 4. Решения разметки (Stage 2)

- **27 сегментов, IDs 1001–1027**, непрерывно по чанкам: ч01→1001–1004, ч02→1005–1012, ч03→1013–1019, ч04→1020–1026, ч05→1027. Один сегмент = одна законченная мысль; связи — `context_bridge`.
- **`timestamp_seconds`** = сек появления keyframe, где маркер есть; иначе старт мысли (навигационная точка). Диапазон 18.5–1224s. `start_seconds/end_seconds` не заполнялись (full-приём, границы не проверялись покадрово).
- **Речь — дословный английский ASR.** Выверены ТОЛЬКО имена собственные, каждое по независимому свидетельству:
  - "shot color" / "C-dense" → **Shot Caller / Seedance** (экранные карточки 18.5s + чип 884.5s);
  - "Hicksfield" → **Higgsfield** (оверлеи портретов 567/573s, панель генератора 904.5s, UI Cinema Studio 1224s);
  - "quad skills" → **Claude skills** (YouTube-субтитры проба-артефакта: "the four Claude skills");
  - "Fresh In/Freshly" (скетч-реклама в сюжете) оставлено как в ASR — сегмент исключён.
- **26 маркеров `[НА ЭКРАНЕ: …]`** (1 помечен `(неуверенно)`), **12 `visual`-блоков**, **37 ссылок на кадры.** `visual.kind`: ui_settings, skill_file_screen, character_reference_screen, character_sheet, prompt_screen, generation_pair, cost_caption, ui_workspace, definition_card.
- **Golden-prompt правило 8 (отбор):** промо-блоки без техник исключены из сегментов: cold-open+спонсор+голосование Don't Poison Ivy (0:00–2:55), анонс мини-сериала (~18:41–19:06), плаг Nadine (19:06–20:08), финальный призыв голосовать+аутро (20:59–конец). Исключения зафиксированы в журнале в `scope`.
- **Клетки (фаза 1, по факту сегментов; 8):**
  - `creative_multimodal/prompt_architecture/build_human_ai_workflow` — SKILL.md story-bible и 7 проходов + вопросы Step 0 (1006), рамки порядка запуска (1003, 1004, 1005, 1007), кейс автотропов библай (1008), канон-трюк панелей (1017), ядро Shot Caller: 16 слотов и «один факт — один слот» (1020, 1021, 1025);
  - `creative_multimodal/character_consistency/build_human_ai_workflow` — locked face (1009), порядок лицо→наряды→триптих (1010), текстовый бриф (1011), Soul vs Nano Banana Pro для лица (1012, совместная клетка), canon-хедшот (1013), 18% фон (1014, совместно с color_and_light), лукбуки (1015), триптих (1016), канон-трюк третьей панели (1017, совместная с prompt_architecture), автотропы библай (1008, совместная с prompt_architecture);
  - `creative_multimodal/ai_video_direction/build_human_ai_workflow` — порядок запуска (1001, 1002), master project (1027);
  - `creative_multimodal/multimodal_generation/build_human_ai_workflow` — 1080p-stretch без апскейла (1023), лимиты референсов (1024), budget/draft (1026);
  - `creative_multimodal/multimodal_generation/compare_models_for_task` — Seedance 2.0/2.5 (1022), Soul 2.0 vs Nano Banana Pro (1012);
  - `creative_multimodal/color_and_light/build_human_ai_workflow` — 18% серый/без key light (1014), атмосферная глубина (1020);
  - `creative_multimodal/scene_blocking/build_human_ai_workflow` + `creative_multimodal/hybrid_ai_vfx_pipeline/build_human_ai_workflow` — scene plate = VFX clean plate (1018, 1019).

## 5. Дословные экранные свидетельства (кадр → что прочитано)

Все 37 ссылок указывают на существующие файлы; **содержимое каждого кадра визуально сверено** (полный просмотр или montage-тайл с точечной дочиткой). Ключевое:

| Сегмент | Кадр(ы) | Дословное содержание (перенесено в content/visual) |
|---|---|---|
| 1001 | native_c01_0000185 (18.5s) | карточки `STORY-BIBLE-BUILDER.MD / CASTKIT-V1.MD / SCENECRAFT-V1.MD / SHOTCALLER-V1.MD` |
| 1003 | c01_w06_00002018 / _00002058, native_c01_00002095 | Claude Settings→Skills; список: motiondojo-v1, castkit-v1 («character builder»), shotcaller-v1 («full cinema director for Seedance 2.0 and 2.5»), scenecraft-v1, story-bible-builder, ctrl-universe + Anthropic-набор |
| 1006 | native_c02_0003460/3500/3540 | инвок "walk me through the /story-bible-builder if we're building a completely new world nothing CTRL world related" + "Loaded skill"; «What you end up with: one SKILL.md file — your world's canon…»; «The flow, seven passes» (Scope check / The spine / Factions, locations, world rules / Characters / Ensemble dynamics / Structural engines / Production rules + assembly — тексты 1–7 полностью); [TBD]-правило («I never invent canon») + «Step 0 — scope check. Five questions» (вопросы 1–4 полностью; 5-й обрезан нижним краем кадра — помечен неуверенным, не выдуман) |
| 1008 | frames_coarse/c02f_00003850 (385s) | кадр MV «невеста» — пример сборки за день |
| 1009 | native_c02_0004650 (465s) | «locked face»: портрет на ровном сером фоне, глаза закрыты красной плашкой |
| 1012 | native_c02_0005675 / native_c02_0005720 / c02_w08_00005730 | оверлеи: «Model: Higgsfield Soul 2.0 / Moodboard: General / Quality: 2k / Size: 1538×2048»; «Model: Nano Banana Pro / Quality: 2k / Size: 1856×2304» |
| 1013–1014 | frames_dense/c03_w01_00005840 (584s) | canon-хедшот на ровном светло-сером фоне (кадр переиспользован двумя сегментами) |
| 1015 | native_c03_0006520 / native_c03_0006660 | пример-источник (метро); KY за рабочим столом |
| 1016 | native_c03_0006760/6810/6870/6910 | референс наряда (тело без головы); трёхпанельный шит фронт/спина/крупный фейс; спина в полный рост; шит: спина + груд-плечевой портрет (кадры переизвлечены после приёмки, §12) |
| 1017 | frames_dense/c03_w06_00007382 / _00007442 / _00007462, native_c03_0007590 | промпт "using /castkit-v1 I need to generate a 3 panel sheet, use the second image reference as the canon locked face and bone structure only for the third panel in the sheet" + "Deciding whether to run a pre-prompt check for this station 27s"; ответ: «LEFT PANEL — full body front view, headless…», «CENTER PANEL — full body rear, head attached; RIGHT PANEL — tight chest-up face lock…», «Skin renders at its true natural tone…», «The background is a single flat 18% neutral gray field…»; превью промпта шита в генераторе (Nano Banana Pro, 16:9, 4K, Unlimited) |
| 1018–1019 | native_c03_0007750 / _0008110 / _0008140 | чип SCENECRAFT-V1.MD; карточка Definition Plate/Clean Plate (источник SHADE.INC, дословно); «AVENGERS: INFINITY WAR, BTS» |
| 1020 | native_c04_0008680 / native_c04_0008720 | «BLADE RUNNER 2049»: зелёный затуманенный коридор; оранжевый силуэт (кадр 872 перепроверен при ревизии) |
| 1021/1025 | native_c04_0008850 / _0009045 / native_c04_0010210 / native_c04_00105600 / _0009315 | чип SHOTCALLER-V1.MD; панель Seedance 2.5: «skipped. No extra words before or after any line / 1. @char_easy_sol: "...we're fine." / 2. @char_easy_zara: "We are not fine." / ONE MOUTH SPEAKS AT A TIME — CRITICAL: each numbered line belongs to exactly one person, and only that person's mouth forms those words. Both lines fall in the last four seconds of the take.» (1080p / 14.0s / 16:9); Story Beats-промпт «THE STORY BEATS LOCKED — CRITICAL: continuous moving 85mm lens…» с токенами <<<uuid>>> и BACKGROUND COOKING CHATTER; dialogue block «PRIMARY LAYER — the conversation on the couch» (7 реплик + ремарки о паузах); готовая сцена на диване (931.5) |
| 1026 | native_c04_0011030 | подпись «750 CREDITS = ROUGHLY $30 USD» |
| 1027 | native_c05_00012240 | Cinema Studio: проект «CTRL WORLD», Project brief/Settings/Elements/Tools/Canvas/Chat/AI Director, «All assets 680», «MASTER CHARACTER SHEET…», стена ассетов, prompt bar «Describe the scene you imagine.» |

Метод нахождения коротких (0.5–2s) экранных вставок: scene-change detection
`select='gt(scene,0.12)'` + точечная экстракция; таймкоды маркеров снимались с имён
файлов кадров (`cNNf_000TTTTT.jpg` = TTTTT/10 s; dense `*_000TTTT.jpg` = T/10 s).

**Поправка от 2026-10-18 (§13):** в строке 1012 цифра размера Soul 2.0 на экране —
**1536×2048** (в первой редакции таблицы стояло 1538×2048); кадры `c01_w06_*`,
`c02f_*`, `c02_w08_*`, `c03_w01_*`, `c03_w06_*` из этой таблицы заменены точными
native-кадрами (см. таблицу в §13) — сама таблица выше оставлена как снимок 2026-10-17.

## 6. Состояние после работы

### 6.1 Журнал (`admission_log.json`, запись LOUEH3DzLro)

- `decided_by: "owner_directed_2026-10-17"`, `decided_at: "2026-10-16"` (как у других owner-решений).
- `scope: "full instructional (~22:05); промо-блоки без техник исключены из сегментов: cold-open+спонсор+голосование Don't Poison Ivy (0:00-2:55), анонс мини-сериала (18:41-19:06), плаг Nadine (19:06-20:08), финальный призыв голосовать+аутро (20:59-конец)"` (цитата дословно; текст выровнен с §4 при ремонте §12).
- `cells` (8) и `attributes`: `language=en`, `prompt_density=high`, `version_lock=moderate-high`, `durable_share=0.8` (число).
- `caveat`: version_lock умеренно-высокий (Seedance 2.0/2.5, Claude skills v2, Soul 2.0, Nano Banana Pro, Cinema Studio); durable_share ~0.8 (слот-архитектура и канон-протокол переживают версии); пятый вопрос Step 0 обрезан.
- `segments_path: "output/video_ingest/LOUEH3DzLro/segments.json"`, `ingested_at: "2026-10-17T19:31:56+00:00"` (после ремонта §12), `receipt` {path, status searchable, segments 27, frames 37, source_sha256 e9402bda…}, `ingest_result` — сводка (27 сегментов, 37 кадров, 27/27 эмбеддингов, FREE→DUPLICATE, матрица 30/727, scope/coverage, расшифровка фазы 1 и списка дословных скринов; дополнена записями о ремонтах §12 и §13). После §13 источник и SHA другие: `9ca52055…` (см. §13).
- Целостность файла: 82 записи, без дублей video_id; соседние записи не изменены (спот-чек OiULPvTJ-0E, 6dNnvhoR3YY, 0d8pqU8JRrY).

### 6.2 БД/индекс/матрица/Скаут

- Импорт: 27 сегментов импортированы (по журналу импорта, receipt и Скауту — 27 source_keys, 27 в `videos --json`) по canonical URL; published-дата нормализована — Скаут показывает `published_at: "2026-10-14 00:00:00"`; media_metadata.frames → backend/data (в прод не деплоятся — штатно по архитектуре). Прямой SQL-чтения БД не было (корпус читается только санкционированными скриптами).
- Эмбеддинги: 27/27 в FTS и векторе; receipt `status: searchable`, `indexed_segments: 27`.
- Матрица: 30 видео / 727 сегментов / 13 клеток / 0 gaps; LOUEH3DzLro — searchable, 8 verified_cells.
- `video_hub_index.py --check` → DUPLICATE (автор JOEY (noisygroup), 27 сегм., 2026-10-14).

## 7. Повторная верификация (2026-10-17, по запросу владельца)

1. SHA256 `segments.json` = `receipt.source_sha256` — файл после последнего импорта не менялся (после ремонта §12 — `e9402bda…`).
2. Combined JSON: ID ровно 1001–1027 без повторов; таймкоды 18.5–1224 в длительности; метаданные согласованы; пустых `content` нет; поле `showcase_prompt_verbatim` в разметке не используется (опционально по схеме).
3. Сумма сегментов 5 чанков = 27 = combined; chunk JSON в `/tmp` и `output/` байт-идентичны (filecmp; синхронизировано и после ремонта §12).
4. Все пути кадров существуют; файлов в `video_frames/adc4b91ac8fe/` = 35 = 37 ссылок − 2 переиспользования (кадр 584s в 1013+1014; кадр 904.5s в 1021+1025).
5. `video_hub_index.py --check`, `expert_scout.py videos --json`, `build_video_matrix.py` и grep матрицы/индекса — все подтверждают состояние §6.2.
6. Git: коммитов нет; изменённые отслеживаемые файлы сессии — `docs/video-hub-index.md`, `docs/DOCUMENTATION_MAP.md` и новый отчёт `docs/quality/2026-10-17-loueh3dzlro-onboarding-report.md`; журнал и output вне git.
7. Кадр native_c04_0008720, остававшийся неподтверждённым после очистки, дочитан: BLADE RUNNER 2049 (оранжевый силуэт) — заявленное содержание верно.

## 8. Проблемы, найденные и исправленные по ходу (честно)

1. **Тип атрибутов ломал матрицу.** Строковый `durable_share` ("0.8 — …") у probe-записей не попадает в decay, пока у записи пустые `cells`; заполнение cells у LOUEH3DzLro впервые включило его в decay-подсчёт и уронило `build_video_matrix.py` (naive `float()`). Исправлено приведением атрибутов этой записи к контрактным типам; детали перенесены в caveat/ingest_result. **Риск на будущее:** в журнале 46 probe-записей (считалось при ревизии; LOUEH3DzLro уже исправлен) со строковыми durable_share/`~`-форматами — при заполнении их `cells` матрица упадёт так же.
2. **Инструмент тайлинга (ffmpeg concat) показывал копии первого кадра** — несколько холостых итераций извлечения; на данные не повлияло (итоговые кадры извлекались поштучно и сверялись).
3. **Coarse-шиты не дают прямого маппинга «клетка→секунда»** — тайминги сняты из имён файлов кадров; короткие вспышки найдены scene-детектором.

## 9. Ограничения и риски (для анализирующего)

- **Приёмка одиночного агента:** Stage 2 и приёмка совмещены в одном исполнителе (прямо задано владельцем); второй пары глаз не было. Рекомендуемые для выборочной приёмки сегменты: **1006 (SKILL.md по шагам), 1016 (триптих), 1017 (canon-трюк + панели), 1025 (Story Beats + dialogue block)** — самые плотные дословные блоки.
- **Правило клея:** стыки 1004/1005 и 1012/1013 содержат по одному повторному предложению — контрактное поведение, дедуп combine их не убирает (сегменты разные).
- **Сегменты без keyframe** (1002, 1004, 1005, 1007, 1010, 1011, 1022, 1023, 1024 — 9 из 27): timestamp = начало мысли, кадры не прикладывались — навигационные точки.
- **Пятый вопрос Step 0** нечитаем в кадре: помечен `[НА ЭКРАНЕ (неуверенно)]`, не выдуман.
- **ASR-речь** может содержать остаточные ошибки распознавания вне выверенных имён собственных.
- Разметка клеток — лёгкая фаза 1 (не паспорт); спорные привязки — на усмотрение приёмки.

## 10. Что НЕ сделано (сознательные границы)

- Точечный Scout-проб по новым сегментам (для нового ролика не обязателен по правилам запуска проверок) и полные исторические поисковые замеры.
- Unit-тесты (код не менялся); тяжёлые автотест-наборы не запускались.
- Commit/push; data release «обнови базу по визуалам» — только по прямой команде владельца.

## 11. Точки входа для анализирующего агента

1. `output/video_ingest/LOUEH3DzLro/segments.json` — вся разметка (27 сегментов, маркеры, visuals, frames).
2. `output/video_ingest/LOUEH3DzLro/chunks/chunk_NN/` — исходный набор (chunk JSON байт-идентичны /tmp-версии) + кадры для сверки маркеров.
3. `output/video_admission/admission_log.json` — запись LOUEH3DzLro (сверить с §6.1).
4. `output/video_ingest/LOUEH3DzLro/segments.import-receipt.json` — source_keys и cell_sources по клеткам.
5. `docs/video-hub-index.md`, `output/video_admission/video_matrix/video_matrix.md` — карта после заливки.
6. Оригиналы видео/аудио: `/tmp/LOUEH3DzLro_ingest/` (могут исчезнуть при перезагрузке VM; кадры для сверки сохранены в `output/video_ingest/…/chunks/` и `backend/data/video_frames/adc4b91ac8fe/`).

---

## 12. Ремонт по итогам независимой повторной приёмки (2026-10-17)

Независимая read-only проверка вторым агентом (по запросу владельца) подтвердила всё
заявленное выше, кроме одного пункта; расхождения исправлены.

1. **Кадры сегмента 1016.** `native_c03_0006740` и `native_c03_0006850` оказались планами
   говорящего, а не заявленными вставками; маркерные времена стояли на ~1–3 с раньше
   фактических окон (проверено точечными вырезками из исходника и яркостью кадров:
   вставки живут в окнах ~675–683 и ~686–691; PSNR подтвердил, что прежние файлы честно
   сняты со своих секунд — проблема была в привязке секунд к содержимому). Переизвлечены
   кадры на 676.0/681.0/687.0; `chunks/chunk_03/segments.json` обновлён (frames + текст
   маркера + опечатка «груду/фейс» → «грудь/фейс»), устаревшие файлы удалены из
   ingest-набора, /tmp-копия синхронизирована (байт-идентичность сохранена). Прогон:
   extract → `ingest_video.py --combine` (27 сегментов) → `import_video_json.py
   --dry-run` (27/37) → import (`loaded`) → `embed_posts.py --continuous --receipt`
   (searchable, 27/27; переэмбеддился 1 сегмент) → `build_video_matrix.py` (30/727/13/0).
2. **Журнал.** Текст `scope` выровнен с §4 (Don't Poison Ivy; анонс 18:41-19:06; Nadine
   19:06-20:08; финальный призыв+аутро 20:59-конец) вместо прежнего «(21:16-конец)»;
   исправлены опечатки («канон-шиит» → «канон-шит», «canон»/«перц» → «канон-протокол
   18% серого», «роверено» → «проверено»); `receipt.source_sha256` и `ingested_at`
   обновлены (`e9402bda…`, `19:31:56Z`), `ingest_result` дополнен записью о ремонте.
3. **Отчёт.** Уточнена формулировка про `showcase_prompt_verbatim` (§7, п.2), обновлены
   SHA/даты в §3, §5, §6.1, §7.

Состояние после ремонта: SHA `e9402bda…` = receipt; 37 ссылок / 35 уникальных кадров /
2 переиспользования; `expert_scout.py videos --json` — scope=full, coverage=declared_scope,
27 сегментов; `video_hub_index.py --check` = DUPLICATE (exit 10); матрица 30/727/13/0.
`backend/data/video_frames/adc4b91ac8fe/` — 38 файлов: 35 актуальных + 3 неизменяемые
копии заменённых кадров (по дизайну не удаляются). Содержимое сегментов 1001–1015 и
1017–1027, клетки и scope в БД не менялись.

(Это снимок состояния на 2026-10-17. Актуальное состояние после вычистки артефакта
кадров Stage 1 — §13: SHA `9ca52055…`, receipt searchable, матрица 32/804/13/0.)

---

## 13. Систематический артефакт кадров Stage 1 (найден 18.10, вычищен 2026-10-18)

Найден при независимой перепроверке следующего ролика (`5HYYXYYCrL4`): в
`backend/scripts/ingest_video.py` функция `extract_frames()` подписывала кадры как
`start_s + (index - 1)/fps`, тогда как фильтр `fps` отдаёт кадр из **середины** интервала —
имя опережало картинку примерно на +0.5 s у `frames_dense` и на +2.0–2.5 s у
`frames_coarse`. Баг починен в тот же день: кадры отбираются фильтром `select`, а время
берётся из `showinfo` (реальный PTS источника), поэтому имя, `time_s` и картинка всегда
описывают один и тот же кадр.

Разметка этого ролика содержала **9 таких ссылок** (8 dense + 1 coarse). Истинное время
картинки для каждой измерено MAD-сопоставлением сохранённого JPEG с исходным видео
(сетка 0.02 s; точное совпадение MAD ≤ 0.03 во всех случаях):

| сегмент | старая ссылка (имя → заявленное время) | истинное время картинки | замена |
|---|---|---|---|
| 1003 | `frames_dense/c01_w06_00002018` (201.8) | 202.28 | `native_c01_00002023` @ 202.3 |
| 1003 | `frames_dense/c01_w06_00002058` (205.8) | 206.29 | `native_c01_00002063` @ 206.3 |
| 1008 | `frames_coarse/c02f_00003850` (385.0) | 387.47 | `native_c02_00003875` @ 387.5 |
| 1012 | `frames_dense/c02_w08_00005730` (573.0) | 573.49 | `native_c02_00005735` @ 573.5 |
| 1013, 1014 | `frames_dense/c03_w01_00005840` (584.0) | 584.46 | `native_c03_00005845` @ 584.5 |
| 1017 | `frames_dense/c03_w06_00007382` (738.2) | 738.74 | `native_c03_00007387` @ 738.7 |
| 1017 | `frames_dense/c03_w06_00007442` (744.2) | 744.66 | `native_c03_00007447` @ 744.7 |
| 1017 | `frames_dense/c03_w06_00007462` (746.2) | 746.66 | `native_c03_00007467` @ 746.7 |

Каждый новый кадр просмотрен глазами и сверен с утверждением маркера. Заодно исправлено
то, что вылезло при этой сверке:

1. **1003.** Маркер утверждал, что список скиллов виден с ~201.8 s; на самом деле в
   202.0–205.0 s открыта вкладка Appearance, а страница Skills со списком появляется
   ~205.8 s. Маркер переписан на два честных экрана (Settings/Appearance ~202.3 s →
   Skills со списком ~206.3 s); покадровая проверка окна 202.0–210.0 s (шаг 0.5 s).
2. **1012.** Оверлей Soul 2.0 на экране читается **1536×2048**, в разметке стояло
   1538×2048 (исправлено в маркере и в `visual.settings`); времена уточнены до
   ~567.5 s и ~573.5 s.
3. **1013/1014** — ~584.5 s; **1017** — ~738.7 s и ~744.7–746.7 s (было «~742–746 s»).

Прогон после правок: `ingest_video.py --combine` (27 сегментов, повторный combine
байт-идентичен) → `import_video_json.py --dry-run` (27/37) → import `--replace-video`
(27 сегментов, 37 кадров скопировано) → `embed_posts.py --continuous --receipt`
(searchable, 27/27) → `build_video_matrix.py` (32/804/13/0).

Состояние после §13: SHA `9ca52055…` = receipt; 27 сегментов, 37 ссылок, 0 отсутствующих
файлов, 0 ссылок на dense/coarse; `expert_scout.py videos --json` — scope=full,
coverage=declared_scope, 27 сегментов; `video_hub_index.py --check` = DUPLICATE;
`backend/data/video_frames/adc4b91ac8fe/` — 46 файлов = 35 актуальных ссылок + 3 неизменяемые
копии кадров 1016 (§12) + 8 неизменяемых копий заменённых dense/coarse-кадров (по дизайну
не удаляются). Смещённых кадров в ссылках разметки нет.
Сами старые dense/coarse-файлы остались в `chunks/*/frames_dense|frames_coarse/` как
исходный скрэтч Stage 1 — ссылок на них больше нет; клетки, scope и тексты сегментов,
кроме перечисленных маркеров, не менялись.

**Открытый пункт (на решение владельца): тот же артефакт есть в 12 более старых
инджестах.** Полный скан `output/video_ingest/*/segments.json` (2026-10-18) нашёл ссылки
на `frames_dense`/`frames_coarse` ещё у 12 роликов: всего **604 ссылки** (274 dense +
330 coarse) — `0d8pqU8JRrY` (51), `2b3Z4rW5VJc` (11), `AgUATWAOaKY` (67), `CAWnlOJbSX4` (77),
`FJfMTvZvX7w` (23), `cCDn0Z6AdmM` (45), `fMU7Ku8ma4A` (101), `mbEo8tn2BZA` (28),
`qwGIwxZFc2I` (85), `sVib0X-PvsY` (18), `xZx5940qoKE` (77), `yNMPr6oBozg` (21).
Исходных видео этих роликов на диске нет, поэтому замену кадров нельзя ни измерить, ни
переизвлечь без повторной выкачки каждого ролика (WARP) и повторного
combine → import → embed с новым receipt. Смещение у них такое же (≈+0.5 s dense и
≈+2.0–2.5 s coarse), но последствие обычно мягче: маркер описывает экран, который
на 0.5 s позже почти не меняется (грубый пример обратного — сегмент 1003 этого ролика,
где смещение меняло экран). Решение о батчевом ремонте — за владельцем.

Артефакты измерений §13 (вне репозитория, скрэтч VM): `/home/ubuntu/tmp_ingest/frame_repair/`
— `shift_report.json` (замеры «имя → истинное время»), `match_shift.py` и `repair_frames.py`
(методика и применённые правки), `compare_sheet.png` / `overlay_zoom2.png` (визуальные
сверки), `backup/` (segments.json и receipt до ремонта).
