# Онбординг JOEY higgsfield-ролика и ремонт scope-метаданных корпуса

Status: Accepted in staging; production promotion pending
Last updated: 2026-10-11

## Вердикт

Ролик `sVib0X-PvsY` («i burned 7,000 higgsfield credits so you don't have to») заонборден
в staging, receipt и матрица согласованы, 6/6 сегментов searchable. Внешняя перепроверка
подтвердила артефакты, но нашла дефект метаданных: в `video_metadata` не объявлялся
`scope`, поэтому корпус отдавал `coverage = unknown`. Дефект исправлен для этого ролика
и ещё трёх (`AgUATWAOaKY`, `cCDn0Z6AdmM`, `FJfMTvZvX7w`) штатным путём — combine,
ре-импорт, `verify_receipt_index`, пересборка матрицы. Production promotion не выполнялся.

## Что проверено и подтверждено

- `segments.json` SHA256 = `receipt.source_sha256` (для `sVib0X-PvsY` после ремонта —
  `237e58441a3c109c…`); `load_receipt` проходит полностью (уникальные `source_keys`,
  `indexed_segments = len(keys)`).
- Combine честный: сегменты чанков побайтово (поэлементно) равны итоговым, 3+3 сегмента.
- 13/13 кадров из `segments.json` существуют на диске; имена файлов совпадают с таймкодами.
- Перекрытия сегментов = 0 (соседи 1002→1003 делят только границу 276.66 с).
- ASR-пометки сегментов 1003/1004 подтверждены транскриптом: 1003 кончается на 300.12 с,
  1004 начинается на 305.42 с (зазор 5.30 с), вводная фраза «Okay, so, here's the thing
  nobody tells you» (305.42–308.0 с) сохранена в тексте.
- Матрица: `state = searchable`, обе заявленные клетки на месте; admission:
  `verdict = ingest`, `scope = full`, `ingested_at = 2026-10-11`.
- Пересборка матрицы и индекса во временные пути даёт идентичные `cells/videos/summary`;
  в корпусе ролик присутствует с 6 сегментами, поиск Скаута его находит
  (`video_hub:950695224`).
- Профильные тесты (6 файлов): 99 passed.

## Что исправлено в отчётной части предыдущего прохода

Подробности прежней версии отчёта — в истории этого прохода; здесь только факты:

- числа кадров по чанкам заменены на фактические: chunk_01 — 102 кадра
  (60 coarse + 42 dense) + 11 контактных листов, chunk_02 — 84 кадра
  (24 + 60) + 6 листов; прежние «113/90 кадров» считали вместе с листами;
- добавлен undisclosed хвост 359.54–394.33 с (34.8 с) без сегментов: речь до 382.48 с,
  дальше антураж и блупер-перебранка без практического содержания;
- отмечен стейл-файл кадра `c02_w02_00003300-*.jpg` (330 с) в
  `backend/data/video_frames/b0cc42847e1a/` — на поиск и receipt не влияет.

## Ремонт scope-метаданных

Дефект: `video_metadata.scope` отсутствовал в чанках, поэтому в корпусе `scope = null`
и `coverage = unknown`, хотя admission объявлял `ingest / full`. Скаут не получал
декларацию объёма приёма (`coverage = declared_scope` появляется только при объявленном
`scope`).

Порядок (одинаков для всех четырёх роликов):

1. Бэкап `segments.json`, `segments.import-receipt.json` и всех `chunks/*/segments.json`.
2. В `video_metadata` каждого чанка добавлено `"scope": "full"` (`scope_range_s` остаётся
   `null` — приём полный, диапазон не режется).
3. `ingest_video.py --combine --video-id <id>`: сегменты, кадры и метаданные, кроме
   `scope`, не изменились (сверял поэлементно).
4. Ре-импорт `import_video_json.py <id>/segments.json` — обновляет `media_metadata`
   в staging и штатно перегенерирует receipt; эмбеддинги и FTS не инвалидированы,
   потому что `message_text` и `created_at` не менялись.
5. `verify_receipt_index` — статус снова `searchable`, `indexed_segments = N/N`.
6. `build_video_matrix.py` + `video_hub_index.py --write`, профильные тесты.

| Видео | Сегментов | SHA256 `segments.json` после ремонта |
|---|---:|---|
| `AgUATWAOaKY` | 24 | `faf4a6555a5d643a…` (был `a262a353f686…`) |
| `cCDn0Z6AdmM` | 21 | `d42aedcc4fb6e250…` (был `b6832e1cda3e…`) |
| `FJfMTvZvX7w` | 12 | `452802c06dd9b29e…` (был `68ed4ccbffa1…`) |
| `sVib0X-PvsY` | 6 | `237e58441a3c109c…` (был `ee95ac41626a…`) |

Итог по корпусу: 29 видео, 699 сегментов, 29/29 searchable, `receipt_error` ни у одного,
видео без `scope` не осталось. Счётчики сегментов в staging не изменились, дублей нет.

Предотвращение рецидива — в SSOT: правило объявлять `scope` для каждого ingest и
проверять `videos`-вывод Скаута добавлены в `docs/guides/video-hub-operator.md`,
`docs/guides/add-video.md` и `docs/architecture/video-hub-service.md`.

## Ограничения

- Визуальное содержимое необработанного интервала 8–261 с по кадрам не пересматривалось —
  только разметка.
- `post-import-verification.json` у трёх отремонтированных роликов фиксирует доремонтный
  SHA (проверка 2026-10-02, отчёт
  `docs/quality/2026-10-02-mimo-video-onboarding-review.md`) — это evidence прошлой
  приёмки, файлы не переписывались.
- Production DB не менялась: последний data release — 2026-10-10 10:07, ремонт в staging —
  2026-10-11. Прод получает правки только при явном `обнови базу` / `обнови базу по
  визуалам`; scoped visual переносит всю staging-БД.

## Что не делалось

Ни commit, ни push, ни deploy, ни production data release в этом проходе не выполнялись.
