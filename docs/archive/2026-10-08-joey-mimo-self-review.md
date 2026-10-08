# ReviewMimo — финальный репорт: ingest fMU7Ku8ma4A (канал JOEY / @noisygroup)

Status: Archived historical self-review
Last updated: 2026-10-08

> Исторический снимок до независимой приёмки 2026-10-08. Текущий статус ремонта: `docs/quality/2026-10-08-joey-video-repair.md` (44 сегмента, все searchable в staging).

Дата: 2026-10-08. VM: /home/ubuntu/apps/experts-panel/dev, ветка main.
Объём: полный ingest одного видео от ручного разбора до Матрицы Знаний + исправление журнала вердиктов канала.

---

## 1. Что ингестилось

Видео `fMU7Ku8ma4A` — «the AI video explainer you were looking for (claude skills for better prompting in description)», автор JOEY (@noisygroup), опубликовано 2026-08-02, длительность 1753 с. Приоритет 1 из вердиктов v2 (owner approved 2026-10-08).

## 2. Куда что положено

### Артефакты ingest (главный результат)
`output/video_ingest/fMU7Ku8ma4A/` (81M):
- `segments.json` — 76 сегментов, сквозные id **1001–1604**, 168 кадров. Каждый сегмент: title/summary (ru), content (en ASR + блок `[НА ЭКРАНЕ]`), timestamp_seconds (= секунда ключевого кадра), start/end_seconds, context_bridge, visual{kind, app, observed}, frames (пути относительно чанка), matrix_cells.
- `chunks/chunk_01..07/` — по чанкам: chunk_meta.json, frames_coarse (381), frames_dense (274), sheets (19 contact sheets + 52 window sheets), segments.json. Распределение сегментов: c01 = 10 сегм. (1001–1010), c02 = 11 (1101–1111), c03 = 14 (1201–1214), c04 = 14 (1301–1314), c05 = 11 (1401–1411), c06 = 12 (1501–1512), c07 = 4 (1601–1604).
- `chunks_index.json` — индекс чанков Stage 1.
- `segments.import-receipt.json` — receipt: `status: searchable`, `source_sha256` совпадает с segments.json, source_path указывает на финальное расположение.

Эталон формата, за которым шёл: `output/video_ingest/mbEo8tn2BZA/chunks/chunk_01/segments.json`.

### Stage 1 (осталось в /tmp, не переносилось по назначению)
`/tmp/fMU7Ku8ma4A_ingest/`: video.mp4 (119M), audio.m4a (28M), transcript.json (323 сегмента ASR, lang=en, prob 0.9997), stage1.log (итог: 381 coarse + 274 dense, 19 sheets, 52 windows). Зеркало chunks+segments также скопировано в /tmp для сверки.

### База данных (dev, НЕ production)
`backend/data/experts.db`:
- 76 строк в `posts` (expert_id=video_hub, виртуальные telegram_message_id из url+segment_id);
- 76 эмбеддингов в `post_embeddings` (модель google/gemini-embedding-001);
- FTS: 76 строк; векторный индекс `vec_posts`: 76 строк. Статус receipt: **76/76 indexed, searchable**.

### Матрица Знаний
- `output/video_admission/video_matrix/video_matrix.{md,json}` — пересобраны; запись fMU7Ku8ma4A: `state: searchable`, `in_corpus: True`, `searchable: True`, `receipt_error: None`, `segment_count: 76`, `published_at: 2026-08-02`.
- **7 клеток (все verified, 0 флагов)** с числом сегментов:
  - `creative_multimodal/ai_video_direction/build_human_ai_workflow` — 20
  - `creative_multimodal/character_consistency/build_human_ai_workflow` — 13
  - `creative_multimodal/prompt_architecture/build_human_ai_workflow` — 11
  - `creative_multimodal/image_model_workflow/build_human_ai_workflow` — 7
  - `creative_multimodal/montage_language/build_human_ai_workflow` — 4
  - `creative_multimodal/scene_blocking/build_human_ai_workflow` — 2
  - `creative_multimodal/multimodal_generation/build_human_ai_workflow` — 1
- `docs/video-hub-index.md` — пересобран (--write), видео присутствует.
- Сводка корпуса после пересборки: 35 видео в логе, 25 ingested/searchable, 671 сегмент, 13 покрытых клеток, 0 gaps.

### Журналы канала (в рамках этой сессии)
- `output/video_admission/candidate_probe_journal.json` — дописаны 6 reject-вердиктов (`reject_off_topic`: VGDHR_U3r5k, kIxZJL4snE0, g7bxqNNMYVk, v3jtZYGOrWw, lAA1O4TLD7A, OnmAebVWMy8); стало 49 записей (12 noisy + 6 reject + прочие). Бэкап: `/tmp/cpj_backup_20261008.json`.
- `output/video_admission/admission_log.json` — у fMU7Ku8ma4A заполнены `cells` (7 клеток, агрегат из receipt) и `published_at: 2026-08-02` (из upload_date 20260802). Бэкапы: `/tmp/al_backup_20261008.json`, `/tmp/al_backup_cells_20261008.json`.
- `output/video_admission/noisy_probe_2026-10-08/report.md` — обновлён: ingest помечен завершённым, пути/итоги/исправления.

## 3. Методика (как делалось)

1. **Разметка сегментов вручную, с визуальной верификацией каждого кадра.** Для каждого чанка: текст ASR-транскрипта по интервалу → построение пронумерованных монтажей из dense/coarse кадров (PIL, лейблы с секундами) → чтение монтажей → привязка кадров к границам сегментов по реальному содержимому кадра. Это принципиально: в первых же монтажах вскрылось, что черновик chunk_01 ссылался на кадры с неверным временем (например, подпись про «character lock» вела на кадр 15-й секунды) — все подозрительные привязки перепроверены и исправлены.
2. Границы сегментов выставлялись по смысловым абзацам транскрипта; content = дословный ASR + правдивое описание того, что реально на кадре (никаких выдуманных [НА ЭКРАНЕ]).
3. Далее штатный конвейер: `ingest_video.py --combine` → `import_video_json.py --dry-run` → real import → `embed_posts.py --continuous --receipt` → `build_video_matrix.py` → `video_hub_index.py --write` → перенос в output → финальные сверки.

## 4. Найденные и исправленные дефекты (причины, а не симптомы)

1. **6 reject-вердиктов отсутствовали в journal** (были только в REPORT_MANUAL) — дописаны по конвенции журнала.
2. **Черновой chunk_01**: неверные привязки кадров — исправлено по монтажам (1002, 1003, 1004, 1006, 1008).
3. **5 сегментов с ключевым кадром вне интервала** `start<=ts<=end` (1001, 1006, 1302, 1503, 1512) — поймано dry-run импортом; поправлены ts/start в чанках, combine пересобран.
4. **2 битых path-референса кадров** в chunk_06 (несуществующие c06f_00015090/c06_w08_00016700) — заменены на существующие.
5. **Receipt отставал от реальности**: `source_path` указывал на /tmp, скрипт матрицы сверяет его с фактическим расположением → `receipt_error: ValueError`, видео не попадало в Матрицу как ingested. Исправлено переимпортом с финального пути `output/video_ingest/fMU7Ku8ma4A/segments.json` (импорт идемпотентен, дубликатов нет — проверено: ровно 76 строк по virtual id).
6. **`admission_log.json`**: у видео `cells: []`, `published_at: None`, а Матрица строит клетки именно из этого поля лога — заполнены агрегатом из receipt cell_sources.
7. **3 клетки вне таксономии**: `character_design`, `editing_workflow`, `production_pipeline` отсутствуют в `CORE_SUBDOMAIN_IDS` (флаг `unknown_subdomain`). Заменены на признанные семантические аналоги (46 замен в чанках и combined): character_design → `character_consistency` (Character consistency & reference grids), editing_workflow → `montage_language` (Montage language & shot sequencing), production_pipeline → `image_model_workflow` (AI image generation & style control). После пересборки: 0 флагов по видео.
8. **Чанки в output отставали от combined segments.json** (копия делалась до переназначения клеток; расхождения в 4 чанках) — пересинхронизировано, идентичность подтверждена.

## 5. Финальные проверки (все зелёные)

- receipt: `status searchable`, `source_sha256` == SHA(output segments.json) == SHA(/tmp segments.json);
- 76 сегментов: id уникальны, `start<=ts<=end` у всех, таймкоды ≤ 1753, 0 отсутствующих кадров;
- БД: posts 76, embeddings 76, FTS 76, vec_posts 76 (проверено через backend venv + sqlite_vec);
- Матрица: 7 cells == 7 verified_cells, 0 taxonomy_flags по видео; видео в video_matrix.md (8 упоминаний) и docs/video-hub-index.md;
- чанки output == чанки /tmp (0 расхождений); непризнанных клеток в output: 0.

## 6. Ограничения (честно)

- **Таксономия не менялась.** Заменой клеток я воспользовался, чтобы не выдумывать субдомены; если `character_design`/`editing_workflow`/`production_pipeline` нужны как отдельные — это отдельное решение владельца (правка knowledge_matrix.json / CORE_SUBDOMAIN_IDS), я его не принимал.
- **`published_at` = 2026-08-02** взят из video_metadata (upload_date 20260802), а не из логов скачивания (в сохранённых логах маркер не подтвердился) — пометить при ревью.
- `vec_posts` не читается из системного python (`no such module: vec0`) — проверялось только через backend venv; это ограничение окружения, не индекса.
- Production не трогал. `output/video_ingest/` в `.gitignore` — ingest-файлы в git не попадают (штатное поведение репо).
- Ручной разбор 12 видео канала (REPORT_MANUAL) — отдельная работа предыдущей сессии, здесь только перепроверен и дополнен журнал.

## 7. Что дальше (не делал, жду команды)

- Ingest остальных approved видео по приоритету: **yNMPr6oBozg (P2)**, затем 5dWgZDka3Ww (P3), 4TXaAnittHs (P4), r2UTG2ZyZTU (P5, scoped), ZkI0ffqr6-0 (P6), yb0RWQ0mbXg (P7), Sd1MpkDUNzo (P8), 5HQwoEZ41G8 (P9), sVib0X-PvsY (P10).
- `выкатывай` / `обнови базу` — только по явной команде владельца (docs/operations.md). Изменения лежат в dev-БД и output, в git не закоммичены.
