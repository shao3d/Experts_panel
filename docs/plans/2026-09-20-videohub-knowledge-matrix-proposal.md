# VideoHub Knowledge Matrix — предложение (proposal)

**Дата:** 2026-09-20
**Статус:** Draft / Proposal. Не SSOT и не утверждённая архитектура.
**Автор:** агент (по запросу владельца), после ingest двух видео Higgsfield AI.
**Ссылки:** `docs/architecture/expert-admission-control.md` (SSOT матрицы Панели),
`backend/scripts/build_knowledge_matrix.py`, `docs/architecture/video-hub-service.md`,
`docs/roadmap/video-hub-scaling.md`, `docs/guides/video-hub-operator.md`.

---

## 0. Назначение документа и стартовый контекст

**Что это:** предложение по механике «матрицы знаний» для VideoHub и критериям
приёмки новых видео. **На момент написания ничего из описанного не реализовано**
— ни `admission_log`, ни чек-листа 0.0b, ни скрипта `build_video_matrix.py`;
это проект решения, ожидающий утверждения владельца (вопросы — §8).

**Для кого:** (а) владелец — утвердить или изменить принцип; (б) будущий
ИИ-агент — внедрить после утверждения. Пока принцип не утверждён, документ —
только контекст: ничего не внедрять. SSOT остаются `expert-admission-control.md`
(матрица Панели) и `video-hub-service.md` (VideoHub runtime); при утверждении
содержимое переезжает туда (см. финал файла).

**Карта документа (что/зачем):**

| Раздел | Что вносит | Почему внесено |
|---|---|---|
| §1 | Механика матрицы Панели | База переноса: без понимания механики нельзя оценивать переносимость |
| §2 | Структурные отличия VideoHub | Почему прямое копирование вредно: цена ошибки до/после ingest несимметрична |
| §3 | Переносимость по компонентам | Что берём из Панели, что нет; что держит две матрицы сравнимыми |
| §4 | Принцип «ценность на операторо-час» + двухфазный гейт | Ядро предложения: фильтр ДО ingest, инверсия эксперт-центричности |
| §5 | Чек-лист приёмки и вердикты | Операционализация: по каким критериям ingest/waitlist/reject |
| §6 | Реализация + схемы артефактов, примеры, права решений | Чтобы внедряющий агент не изобретал форматы заново |
| §7 | Самопроверка рациональности | Честные поправки к первому варианту; известные слабости и риски |
| §8 | Открытые вопросы | Что владелец должен решить до внедрения |

**Стартовый контекст (снимок на 2026-09-20):**

- VideoHub (staging, промоутнут в прод scoped-релизом 2026-09-19): **3 видео,
  111 сегментов** — `QfylrxtQSSs` (Higgsfield AI, 62), `vUYq38wC_xI`
  (Higgsfield AI, 38), `2b3Z4rW5VJc` (Youri van Hofwegen, 11).
- Панель: **27 экспертов в матрице** (v0.3, 81 клетка). Визуальная группа
  (`strangedalle`, `acidcrunch`, `cgevent`, `neyrograph`, `iideyalogiya`)
  принята в сентябре как `limited_scope` — именно её клетки пересекаются с
  контентом VideoHub.
- Owner decision #1 (2026-09-16, `docs/plans/2026-09-16-video-hub-starter.md` §4):
  VideoHub **не входит в панель и Панэкс**; поиск — только Expert Scout.
  Поэтому «ценность» видео определяется как улучшение ответов Скаута.
- Ingest-пайплайн: Stage 1 (ASR + кадры) → Stage 2 (LLM-сегментация) →
  import → embeddings; playbook `docs/guides/video-hub-operator.md`, шаг 0.0
  (duplicate-check) уже обязателен. Стоимость одного ingest: ~0.5–1.5 ч
  оператора + пайплайн.

---

## 1. Как устроена матрица Панели (baseline)

Цепочка: **LLM-паспорт над корпусом → `matrix_export.cells` → детерминированная
матрица → preflight кандидата → арбитраж по первоисточникам → вердикт**.

- **Паспорт** (`output/expert_admission/semantic_passports/<expert>/...`):
  `matrix_cells` + `matrix_export.cells` с `cell_id = domain/subdomain/intent`,
  `coverage_level` (`strong`/`moderate`), `depth_level` (`deep_practitioner`),
  `source_role` (`primary`), `evidence_refs` (конкретные посты — аудитируемость).
- **7 оценок клетки:** depth, practicality, evidence_quality, source_utility,
  intrinsic_distinctiveness, anti_hype, community_signal.
- **Матрица** (`build_knowledge_matrix.py`) — детерминированная агрегация:
  покрытие клетки (`strong_single_source` / `strong_multi_source` / `moderate`),
  избыточность, лучшие эксперты клетки со скорами, rollups (domain+intent),
  related overlaps.
- **Таксономия:** 14 core domains, ~40 core subdomains, 13 query intents;
  расширения — только через владельца: `alias_to_*` / `promote_to_core`
  (так в 2026-09 появились `cg_craft_to_ai`, `3d_previz_pipeline` и др.).
- **Preflight** — детерминированное сравнение паспорта кандидата с матрицей:
  clean gap / overlap / duplicate-like / needs-probe / taxonomy extension.
- **Арбитраж** — только при плотном overlap: LLM/human по первоисточникам.
  «Матрица — карта, не судья» (`expert-admission-control.md:168–227`).
- **Вердикт:** accept / limited_scope / reject + `routing_caveat` +
  `decision_basis` → `admission_manifest.json`.
- **Принцип ценности:** «улучшает ли эксперт будущий отбор источников и ответы
  Панэкса настолько, чтобы оправдать admission» (`:174`), а не «сколько контента».

---

## 2. Чем VideoHub структурно другой (и что это меняет)

| Аспект | Панель | VideoHub | Следствие |
|---|---|---|---|
| Субъект ценности | эксперт (поток постов) | видео (дискретный артефакт) | матрица должна быть **контент-центричной** |
| Цена ошибки | контент уже синхронизирован, смотреть дёшево | ingest = 0.5–1.5 ч оператора (download, ASR, Stage 2) | главный фильтр — **до ingest**, по дешёвым сигналам |
| Доказательства | посты + комменты | сегменты с дословными промтами и UI-скринами | «паспорт» почти рождается на Stage 2 |
| Устаревание | неравномерное | агрессивное: version-locked туториалы гниют за месяцы | распад — **первоклассная колонка** |
| Потребление | Панэкс/роутер | только Scout (sidecar; owner decision #1) | «ценность» = улучшение ответов Скаута |
| Масштаб | 27 экспертов, ~8k постов | 3 видео, 111 сегментов | тяжёлая матрица сейчас = бюрократия |

---

## 3. Переносимость по компонентам

- **Доктрина** (карта-не-судья, overlap ≠ приговор, финал — продуктовое
  суждение) — переносится ~100%.
- **Таксономия** — ~75%: визуальные клетки уже в core (`cg_craft_to_ai`,
  `3d_previz_pipeline`, `ai_video_direction`, `scene_blocking`,
  `montage_language`, `color_and_light`, `character_consistency`,
  `image_model_workflow`, `prompt_architecture`). Видео-специфичные оси
  (модель/тулчейн, уровень, язык, промт-плотность) добавлять **атрибутами
  клеток, не новыми клетками** — иначе две матрицы несравнимы.
- **7 оценок** — частично: depth/practicality/evidence_quality/source_utility/
  distinctiveness — да; **anti_hype — да (для ютуба критичнее)** — на Stage 2
  golden prompt уже реализует это разделение: дословные промты сохраняются,
  CTA-шум («hit subscribe») отбрасывается;
  community_signal — нет (комменты YouTube не собираем; просмотры — слабый
  сигнал). Взамен видео-специфичные: `prompt_density`, `verbatim_ui`,
  `version_lock`, `durable_share`.
- **Alias/promote_to_core** — переносится как есть (только владелец).
- **Preflight + вердикты + манифест** — по форме да, вердикты другие (см. §5).
- **Арбитраж по первоисточникам** — переносится; инструмент уже есть: Скаут.
- **НЕ переносится:** тяжёлый LLM-паспорт на кандидата (дублирует Stage 2),
  `routing_caveat` (роутинга нет), включение матрицы в панель/Панэкс.

---

## 4. Предлагаемый принцип: контент-центричная карта + «ценность на операторо-час»

Панель спрашивает: «улучшает ли эксперт отбор источников и ответы». Для
VideoHub предлагается инверсия:

> **Marginal value per operator-hour** =
> δпокрытия × (глубина + промт-плотность) × (1 − скорость распада)
> ÷ часы оператора на ingest.

Это **эвристика для ранжирования кандидатов, а не вычисление**. Вопрос не
«полезно ли видео», а «полезно ли оно настолько, чтобы потратить следующий час
ingest на него, а не на кандидата из пробела матрицы». Матрица — карта «что
качать», а не отчёт «что уже скачано».

**Двухфазный гейт:**

- **Фаза 0 (до скачивания, дёшево):** duplicate-check (0.0, уже есть) →
  тематический фильтр → **probe-чек Скаутом**: 3–5 вопросов, которые обещает
  видео (из названия/описания); корпус отвечает хорошо → overlap, пусто →
  gap → вердикт + rationale в журнал решений.
- **Фаза 1 (после ingest):** один LLM-вызов — маппинг `topic_id` сегментов на
  клетки таксономии (лёгкий «видео-паспорт», не тяжёлый) → обновить
  видео-матрицу. 80%+ сегментов в уже покрытых клетках → сигнал понижать
  приоритет канала на будущее.

**Overlap двухсторонний:** против других видео И против клеток панели. Пример:
Higgsfield-видео легло в клетки cgevent (`cg_craft_to_ai`) и neyrograph
(`3d_previz_pipeline`) — но это не дублирование: RU-практик и англоязычный
вендорский туториал — комплементарные углы одной клетки.

---

## 5. Критерии приёмки видео (чек-лист Фазы 0)

1. **Тема:** практический контент по генеративному видео/визуальному
   продакшну (не новости, не хайп-обзоры).
2. **Дубликат:** `video_hub_index.py --check` + сюжет уже покрыт каналом?
3. **Ценность:** probe-чек Скаутом; gap / новая версия тулчейна / новая
   техника против «корпус уже отвечает».
4. **Качество источника:** авторитет (вендор/практик с результатами),
   промт-плотность, доля пошагового vs воды.
5. **Распад:** version-locked (быстро гниёт — только при критичном gap) vs
   процессный (blocking, монтаж, экономика — приоритет).
6. **Стоимость:** длительность, язык (качество Whisper), доступность медиа.

**Вердикты:** `ingest` / `waitlist` / `reject_duplicate` / `reject_low_value` /
`reject_off_topic`, с `decision_basis` в журнале (маппинг на термины Панели:
accept / limited_scope / reject).

---

## 6. Минимальная реализация (без бюрократии)

- **Сейчас (3 видео)** — ручной режим:
  - чек-лист 0.0b в `docs/guides/video-hub-operator.md`;
  - `output/video_admission/admission_log.json` — по объекту на видео
    (verdict, basis, caveat, cells, date);
  - видео-матрица — маленькая md-таблица по клеткам creative_multimodal
    (какие видео какие клетки покрывают + decay-пометки).
- **Порог ~10 видео / когда руками больно** — `backend/scripts/build_video_matrix.py`:
  детерминированная агрегация из `admission_log` + сохранённых маппингов
  `topic_id→cell`; LLM зовётся один раз на видео (при добавлении), билд — без LLM.
  Общие таксономические константы — из `build_knowledge_matrix.py`.
- **Артефакты:** `output/video_admission/video_matrix/video_matrix.{md,json}`.
- **В прод/runtime не уходит** — матрица операторская.

### 6.1 Схема `admission_log.json` (пример записи)

Один файл-журнал, один объект на видео — лёгкий аналог
`admission_manifest.json` Панели. Обязательные поля: `verdict`,
`decision_basis`, `caveat`, `cells`, `attributes`, `decided_at`;
`probe_notes` — только если probe-чек делался.

```json
{
  "schema_version": "0.1",
  "updated_at": "2026-09-20T00:00:00",
  "videos": [
    {
      "video_id": "vUYq38wC_xI",
      "title": "GPT Astra 6 + Blender + Higgsfield Builds The Craziest Cinematic Scenes!",
      "channel": "Higgsfield AI",
      "published_at": "2026-09-12",
      "verdict": "ingest",
      "decision_basis": "gap: вендорский туториал Blender-previz → Seedance через MCP; no panel coverage (RU) по EN-углу; высокая промт-плотность",
      "probe_notes": "scout RU: blocking/playblast уже отвечает neyrograph; EN-вендорный угол отсутствует → комплемент, не дубль",
      "caveat": "version_lock высокий (Seedance 2.5 / GPT-6 Astra UI) — быстрый распад",
      "cells": [
        "creative_multimodal/3d_previz_pipeline/build_human_ai_workflow",
        "creative_multimodal/cg_craft_to_ai/build_human_ai_workflow",
        "creative_multimodal/scene_blocking/build_human_ai_workflow",
        "creative_multimodal/image_model_workflow/build_human_ai_workflow"
      ],
      "attributes": {
        "language": "en",
        "prompt_density": "high",
        "version_lock": "high",
        "durable_share": 0.5
      },
      "decided_at": "2026-09-19",
      "decided_by": "agent_proposed_owner_approved"
    }
  ]
}
```

### 6.2 Пример ручной видео-матрицы (md)

| Клетка | Видео (черновая разметка) | Эксперты Панели (RU) | Распад |
|---|---|---|---|
| `3d_previz_pipeline/build_human_ai_workflow` | vUYq38wC_xI | neyrograph (primary) | средний |
| `cg_craft_to_ai/build_human_ai_workflow` | vUYq38wC_xI | cgevent (primary) | высокий (version_lock) |
| `ai_video_direction/build_human_ai_workflow` | QfylrxtQSSs, vUYq38wC_xI | neyrograph | низкий |
| `multimodal_generation/compare_models_for_task` | 2b3Z4rW5VJc | acidcrunch, cgevent | высокий |

Правило обновления: таблица пересобирается/правится при **каждом** добавлении
видео (см. §7.7) — иначе карта врёт.

### 6.3 Черновик разметки текущих видео (иллюстрация, не финал)

Маппинг `topic_id` → клетка по уже существующим видео, чтобы будущий агент
видел, как выглядит «лёгкий видео-паспорт» (§7.1). Источник `topic_id` —
артефакты ingest: `output/video_ingest/<id>/ingest/segments.json`
(базу напрямую не читать — только Scout). Это **черновик для примера**, не
утверждённая разметка.

- `vUYq38wC_xI` (Astra + Blender + Higgsfield): `astra_builds_blocking`,
  `loop_hook_iteration`, `chase_blocking_ok`, `jutsu_*` →
  `3d_previz_pipeline` + `cg_craft_to_ai`; `plugin_install` и MCP-промты →
  `cg_craft_to_ai`; `nano_banana_layout` → `image_model_workflow`;
  `loop_concept`, `mirror_*` → `ai_video_direction` + `scene_blocking`;
  `concert_*` → `multimodal_generation`; `vacuum_generate` → `prompt_architecture`.
- `QfylrxtQSSs` (AI Love Story): `ai_video_direction`, `prompt_architecture`,
  `character_consistency`, `montage_language`.
- `2b3Z4rW5VJc` (Seedance 2.5): `multimodal_generation/compare_models_for_task`
  (промтинг, экономика кредитов) + `prompt_architecture`.

### 6.4 Механика probe-чека (Фаза 0)

1. Из названия/описания кандидата выписать 3–5 «обещанных» тем.
2. Задать их Скауту — через агента `expert-scout` (санкционированный read-only
   путь; прямой доступ к базе запрещён), формулировки RU и EN.
3. Оценить выдачу: релевантные топ-источники с цитатами = «покрыто»;
   пусто/нерелевантно = gap.
4. Результат — в `probe_notes`; для `waitlist`/`reject` он же основа
   `decision_basis`.
   Ограничения: корпус мал, «корпус отвечает» ненадёжен (§7.3); EN-видео
   против RU-корпуса даёт «gap» слишком легко — писать «no panel coverage (RU)».

### 6.5 Права решений

| Решение | Кто принимает |
|---|---|
| Вердикт ingest / waitlist / reject по кандидату | агент готовит, владелец утверждает |
| Новые клетки таксономии, `alias_to_*` / `promote_to_core` | только владелец |
| Включение video_hub в панель/Панэкс | запрещено (owner decision #1) без нового решения владельца |
| Коммит, push, прод-релизы | только по командам владельца («зафиксируй», «выкатывай», «обнови базу») |

**Что НЕ делать:** не плодить report-семейства (один admission_log, как
manifest в Панели); не заводить отдельную таксономию; не включать video_hub в
панель/Панэкс; не автоматизировать скрипт раньше, чем ручная таблица станет
болью.

---

## 7. Самопроверка рациональности (уточнения после перепроверки)

1. **«Отдельный паспорт не нужен» — неточность.** Нужен **лёгкий** паспорт:
   один LLM-вызов на видео (клетки + оценки), а не многостадийный паспорт
   Панели. Stage 2 даёт сегменты и `topic_id`, но не оценки клеток.
2. **Формула — эвристика.** Не выдавать за расчёт; годится только для
   сортировки кандидатов.
3. **Probe-чек не для каждого кандидата.** Только при overlap-сигнале; на
   малом корпусе вердикт «корпус отвечает» ненадёжен; язык запросов влияет
   (EN-видео против RU-корпуса). Скаут-проба стоит минуты против часа ingest —
   но и она не бесплатна.
4. **Атрибуты минимальны.** Часть видео-осей уже покрыта клетками
   (`model_comparison`, `compare_models_for_task`); новые атрибуты — только
   то, чего в таксономии реально нет (`prompt_density`, `version_lock`,
   `durable_share`, `verbatim_ui`).
5. **community_signal.** Сейчас нет, но YouTube-комменты технически
   доступны через yt-dlp — записать как future option, не сейчас.
6. **На 3 видео матрица почти бесполезна.** Реальная ценность сейчас —
   дисциплина pre-ingest чек-листа; карта окупается с ~10 видео.
7. **Риск загнивания.** Правило: регенерировать (или обновлять руками)
   видео-матрицу при каждом добавлении видео; иначе карта врёт.
8. **Риск бюрократии.** Один JSON-журнал, простые вердикты, никаких
   arbitration-отчётов на каждое видео (только для спорных overlap).
9. **Стоимость — не только операторо-часы.** Есть ещё LLM/ASR/диск; сейчас
   доминирует время оператора, после автоматизации формула сдвинется к
   машинным затратам.
10. **«Gap по панели» может быть языковым артефактом** (RU-панель vs EN-видео).
    В журнале писать «no panel coverage (RU)», а не «unique» безусловно.

---

## 8. Открытые вопросы к владельцу

1. Утверждаем ли принцип (контент-центричная карта + гейт до ingest)?
2. Порог автоматизации: ~10 видео или «когда руками больно»?
3. Кто ведёт `admission_log` — агент пишет, владелец подтверждает вердикты?
4. Нужен ли видео-матрице отдельный статус в `DOCUMENTATION_MAP.md` при
   утверждении (и переезд в `docs/architecture/`)?

---

*При утверждении: перенести принцип в `docs/architecture/video-hub-service.md`
или дополнить `expert-admission-control.md` разделом "VideoHub sidecar
admission"; этот файл оставить как историю решения.*
