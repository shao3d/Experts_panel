# Video Hub: Scaling Roadmap & Architecture Audit

**Created:** 2026-03-28
**Status:** Active Roadmap (query-time side; P2/P3/P5/P4/N2 closed — see the
priority table and "Review fixes")
**Last updated:** 2026-10-04
**Current State (2026-10-04):** **24 видео / 595 сегментов** после ремонта
тройки MiMo; scoped visual data release завершён, production healthy.
Приёмка, границы проверки и выпуск — в [отчёте](../quality/2026-10-04-mimo-trio-repair.md).

История предыдущего выпуска (2026-10-02):
Yapper `mbEo8tn2BZA` принят: 26 сегментов, 49 ссылок на кадры,
семь подтверждённых ячеек, receipt `searchable` (26/26), каталог и Матрица
пересобраны. Четыре проверки Скаута пройдены; scoped visual data release
завершён 2026-10-02 в 12:40 UTC с healthy production. Подробности — в
[отчёте онбординга](../quality/2026-10-02-yapper-music-video-onboarding.md).
Исправленная разметка новой тройки промоутирована через scoped visual data release
2026-10-02; проверка целостности БД и production `/health` прошли.
Current inventory: [generated index](../video-hub-index.md). Введены 2026-10-02:
`AgUATWAOaKY` (24), `cCDn0Z6AdmM` (21), `FJfMTvZvX7w` (12) — все с receipts
`searchable`, матрица 20 видео / 458 сегментов / 13 клеток / 0 gaps; материалы и
REVIEW — `output/video_review/2026-10-02/REVIEW.md`. Независимая приёмка выявила
ошибки экранной разметки, таймкодов и неполное отражение ячеек Матрицы;
ремонт и проверки staging завершены:
[находки, исправления и затраты](../quality/2026-10-02-mimo-video-onboarding-review.md).
Успешный импорт не означает приёмку точности содержания. Ранее: Dan Kieft
`qwGIwxZFc2I` was imported with 35 reviewed segments and 85 frame references.
Its generated receipt confirms `searchable` (35/35 indexed, zero embedding
errors). The Matrix is rebuilt with six source-backed cells for this video.
Three targeted Sol Scout runs passed integrity and semantic review: set website
preview limits, KIEFT match-cut/provenance, AE editable outlines/Adobe control
limits. Scoped visual data release completed on 2026-10-01 with healthy production.
Verification and release evidence: [quality report](../quality/2026-09-30-videohub-scout-fixes.md).
Downloads now run directly on the VM via Cloudflare WARP SOCKS-proxy (recipe in
`docs/guides/video-hub-operator.md` §0.1a) — Mac/G15 no longer required.
Ingest is automated (chunked ASR + adaptive frames + LLM pass),
the structured `visual` block and per-segment frames are stored, and Scout
returns YouTube deep-links with timestamps. The 2026-09-24 review pass closed
the scaling blockers that had already tripped their triggers: Map is chunked
(P2, was live at 172 segments), retries + honest failures (P3), timestamp
normalization (P4 gap). The remaining items below stay valid for the
query-time side.
**Trigger:** was "100-150 segments or 10+ videos" — reached and handled
2026-09-24; next scale step is N4 (~200+ segments) — **trigger reached
2026-09-29 (250 segments), N4 остаётся открытым; после ingest 2026-09-29 —
358 сегментов (16 видео); текущий каталог — по ссылке выше, N4 всё ещё открыт**.
Актуальное подтверждённое покрытие — в сгенерированной Матрице; новый ролик
Dan включён после подтверждения `searchable`.

---

## Кандидаты на ingest (watchlist, 2026-09-29)

Решение по каждому — владелец; порядок — по ценности для матрицы
(`output/video_admission/video_matrix/video_matrix.md`). Полные пробы
(транскрипты, scout-прогоны, аргументация, `decision`-поля) —
`output/video_admission/candidate_probe_journal.json`. Это SSOT по «какие
видео рассматривать дальше»: если здесь чего-то нет — кандидата нет.

### Что рассматривать дальше (приоритетный порядок, 2026-10-03)

Скан 2026-10-03 (инкремент к окну 2026-10-02, 10 каналов, через WARP на VM)
нашёл 4 новых загрузки: `xZx5940qoKE`, `kOoC3yhUyDQ`, `OQdyw2vVXq4`
(2026-10-02) и `gVPZU1btFA8` (2026-10-03). Одновременно закрыты 11 видео
окна 2026-10-02, остававшихся без вердикта (транскрипт-пробы ASR на VM +
scout-чеки read-only хелпером; полный журнал проб —
`output/video_admission/candidate_probe_journal.json`, скан-артефакты —
`output/video_admission/channel_scan_2026-10-03/`). Тройка ниже уже онбордирована,
отремонтирована и промоутирована в production 2026-10-04. Повторный онбординг не нужен:

| # | Видео | Автор | Ценность для матрицы | Статус |
|---|-------|-------|----------------------|--------|
| 1 | `CAWnlOJbSX4` I Turned My Boring Hometown Into A Movie With AI VFX (2026-08-12) | River Cody | durable-крафт: 5 слоёв продакшена (композиция→свет→цвет→фон→динамика), elements → Claude-переводчик → storyboard-кадр → Seedance → композитинг оригинала назад; риск дубля с levels-фреймворком `5y20tE7zo40` снят (структуры разные) | **production**, 35 сегментов; ремонт 2026-10-04 |
| 2 | `xZx5940qoKE` How to Storyboard Realistic AI Videos with Google Flow (2026-10-02) | Youri van Hofwegen | last-frame chaining (скриншот последнего кадра → старт следующей сцены), сторибординг-план в чате до генерации, one-at-a-time; scout-чеки 2026-10-03: пусто в корпусе (RU+EN); та же техника независимо у `9sMkvSIgq7s` | **production**, 38 сегментов; ремонт 2026-10-04 |
| 3 | `0d8pqU8JRrY` How to Make 3D Animations With GPT 6 Astra (2026-09-19) | Youri van Hofwegen | named parts → раздельный тайминг + assembly deadline + hold; рендер по scene camera vs viewport; одна анимация → 3 стиля; принцип «камера отдельно от актёра» уже покрыт `neyrograph:4667`, конкретика 3D Jutso — нет | **production**, 38 сегментов; ремонт 2026-10-04 |

Следом: `kOoC3yhUyDQ` GPT-6 Astra Finally Solves AI Video Editing (Higgsfield
AI, 2026-10-02) — **recommend ingest_scoped** ~4:50–9:00 (style-context
«прошлые проекты+шрифты+skill-файл», батч-нарезка шортсов, AE-скрипт с
альфа-экспортом; ядро монтажа покрыто `AgUATWAOaKY`). Остатки waitlist:

| # | Видео | Автор | Ценность для матрицы | Статус |
|---|-------|-------|----------------------|--------|
| 1 | `3LekYT1rKoc` Can AI Color Grade Better Than A Human? (2026-09-16) | River Cody | film-reference prompting для грейдинга, cost breakdown; ядро Astra+Resolve покрыто `qwGIwxZFc2I` | **waitlist** (проба 2026-10-02) |
| 2 | `gr9fEEKrO5Y` Video Editors Are Dead? Opus Edited This (2026-09-29) | AI Samson | word-by-word animation, selects-labels; code-animation покрыта (Remotion/Three.js/Python) | waitlist |
| 3 | `OQdyw2vVXq4` Kling 4 Flash vs Seedance 2.5 (2026-10-02, RU) | Bla Bla about AI | свежие RU-факты: русский липсинк 20с, цена с итерациями в рублях, цензура; микробиты уже у `neyrograph:4669`, compare-клетка с 3 видео; возможен ingest_scoped (цена 2:13–2:50, липсинк 7:31–9:10, мульт 17:16–18:30) | waitlist (проба 2026-10-03) |

`qwGIwxZFc2I` больше не кандидат: онбординг в dev и проверка поиска завершены;
scoped visual data release выполнен 2026-10-01.

Вне очереди (waitlist / отсевы — не брать без нового повода):

| Видео | Автор | Почему |
|-------|-------|--------|
| `W3-RIZ-Ps64` GPT-6 Astra + After Effects Motion Graphics (11м) | Adil (Higgsfield) | угол «агент собирает AE-композиции» узкий, `montage_language` уже 10 видео (вердикт матрицы 2026-09-29) |
| `FW_tIpEBJ0U` Hybrid Production With Higgsfield Genjutsu (0:56) | Higgsfield AI | тизер без техники; тема `hybrid_ai_vfx_pipeline` покрыта `3I2jj6HA3p0` — ждать полноценный breakdown |
| `RaJ0cywS7Hw` / `SWhYbZxRZCA` (липсинк Kling / lock face+voice) | Tao Prompts / AI Video Studio | липсинк-голос: плотный overlap (neyrograph:4650/4732/4728, cgevent:16412 и др.) — отсеяны пробами |
| `StX3eflYq_o` 10+ Seedance 2.5 Prompts | Dan Kieft | промт-листикл, `prompt_architecture` перегружен (12 видео) |
| `UQDM-ZigvGo` Anerneq, `IAl240xpSGM` The Trigger | Higgsfield AI/Originals | шоукейс-фильмы без техники |
| `M73BrFnVPA8`, `9Pbg-_ptBcE`, `rwVeovA805k` | разные | продуктовые тизеры без техники (reject_low_value по пробам) |
| `eUFdtZLDOo8` 50+ Ways to Use GPT-6, `_cbq1SJ_vP0` Opus 5.5 use cases | AI Samson | рейтинги/хайп и юзкейсы LLM вне видео-крафта |
| `gVPZU1btFA8` GPT-6 Astra Changed Meta Ads Forever! (2026-10-03) | Higgsfield AI | маркетинг/реклама (PROOF/QUEST, лидген, CPL) — не видео-крафт (транскрипт-проба 2026-10-03) |
| `2OwMjg5As2g` Claude Fable 5.1 + Higgsfield Motion Graphics | Higgsfield AI | locked-text моушн и one-to-one recreation узкие; AE/моушн-угол перегружен, денежная подача (проба 2026-10-03) |
| `lCly-zH6A78` CapCut AI Tools, `eoSCoD--npk` UGC Ads with AI | Youri van Hofwegen | sheet-техника уже покрыта (cCDn0Z6AdmM/xZx5940qoKE); уникальное узкое: порядок captions-после-склеек, 10-панельный turn-around продукта (пробы 2026-10-03) |
| `chNPqmJx0fY` GPT 6 Astra Come to Life, `QwzVmGov9ec` Astra Editing (Tao) | Youri / Tao Prompts | третий-четвёртый workflow «монтаж/оркестрация агентом» — территория AgUATWAOaKY + kOoC3yhUyDQ (пробы 2026-10-03) |
| `9sMkvSIgq7s` Flow Plant Growth Workflow | AI Video Studio | тот же last-frame chaining, что в xZx5940qoKE — дублирует механику кандидата №2 (проба 2026-10-03) |
| `7SZ76s-nqpQ`, `wJc0jnX49R0`, `dZBAJNdFxzo`, `I9EvujHJm3o`, `yRM1df108G0` | разные | правило-отсевы 2026-10-03: деньги/бизнес, тур фичи, API-сетап, free-generators, identity+voice overlap (детали в journal) |

### Каналы на радаре (free-roam 2026-09-29; дополнения 2026-10-02, 2026-10-03)

**Дополнение 2026-10-03:** все 10 радар/корпусных каналов отсканированы повторно
(инкремент к окну 2026-10-02; артефакты —
`output/video_admission/channel_scan_2026-10-03/`). Новые загрузки только у
Higgsfield AI (2), Youri (1) и Bla Bla about AI (1) — все пробработаны, см.
«Что рассматривать дальше». Полный breakdown Passport Rush (Higgsfield
Animation) по-прежнему не вышел — проверено 2026-10-03.

**Добавлены владельцем 2026-10-02 и отсканированы (окно 30 дней):**
- **Yapper AI** (`@yapper_so`) — введены `cCDn0Z6AdmM` и `mbEo8tn2BZA`
  (music video: 26 принятых сегментов, `searchable`, production; проверка выпуска —
  в [отчёте](../quality/2026-10-02-yapper-music-video-onboarding.md)).
- **Bla Bla about AI** (`@BlaBlaProAi`, RU) — `TgCp6SuVnJw` (Blender dummy) отсеян пробой: overlap с `3d_previz_pipeline` + реклама; ждать новые ролики.
- **Tao Prompts** (`@taoprompts`) — ранее помечен «не пробовать» за липсинк; отсканирован по указанию владельца: `TggVh3WCwxg` (4-Step Workflow, 2026-09-30) и `EcxvHRccXnc` (Level Up с Opus 5.5) — в окне, не пробованы (слоты заняты сильнейшими); липсинк-ролики остаются в отсеве.



- **В корпусе (сканировать новые видео наравне с остальными):** River Cody
  (hybrid «практика + ИИ», рекомендация Matti Haapoja; `3I2jj6HA3p0` введён),
  Max Novak (AI+3D/VFX композитинг; `yUiTmO8AjJc` введён), AI Video Studio
  (Veo/Flow/Omni/Runway, «hypothesis → test → result», промты в описании;
  `6dNnvhoR3YY` введён).
- **Ещё не пробованы** (списки рекомендаций: LinkedIn «9 AI Filmmaking
  Channels», Haapoja, интернет): Curious Refuge (тренды + туториалы
  Seedance/Kling/Runway), AI Filmmaking Academy (AI VFX), Roboverse
  (аватары/UGC), Planet AI, Nour Art, Creating with Conor, Theoretically Media
(production breakdown с цифрами), GenAI+ (Flow prompt-document), Beriky
  Studios (постмортемы короткометражек). Tao Prompts — липсинк/музыкальные
  клипы, тема перекрыта корпусом (не пробовать).
- Источники discovery: reddit-search (1 релевантный тред r/comfyui, в основном
  abstained), HN (Show HN шум), веб-списки рекомендаций.

**Недавно введены (больше не кандидаты):** Ведены 2026-10-02 (скан окна 30 дней,
10 каналов, гейт 0.0b, workers: MiMo-V2.6-Pro max): `AgUATWAOaKY` (Dan Kieft, 24 сегмента —
6 методов AI-монтажа: universal prompt, B-cam из фото комнаты, VFX по кадровым маркерам,
sound design), `cCDn0Z6AdmM` (Yapper AI, 21 сегмент — copyright-workaround, element sheet
без головы на front view, 6-beat бой, cost breakdown), `FJfMTvZvX7w` (Dan Kieft, 12 сегментов —
two-role overlay swap, multi-tag гардероб/объекты, сшивка шотов в одну генерацию).
Полные материалы: `output/video_ingest/<id>/`, `output/video_review/2026-10-02/REVIEW.md`.
Ранее: `H8WDehuVams` (Youri van Hofwegen, `H8WDehuVams` (Youri van Hofwegen,
25 сегментов — закрыл `lipsync_dubbing`) и `reFzEtCG_m8` (Higgsfield Animation /
Amina, 33 сегмента — squash&stretch, постмортемы, акварельный пайплайн) — оба
2026-09-29, см. `docs/video-hub-index.md` и
`docs/archive/2026-09-29-videohub-two-videos-ingest-starter.md`; free-roam
тройка 2026-09-29 — `3I2jj6HA3p0` (River Cody, 14 сегментов — закрыл
`hybrid_ai_vfx_pipeline`), `yUiTmO8AjJc` (Max Novak, 20 сегментов — первое
покрытие light maps/relighting), `6dNnvhoR3YY` (AI Video Studio, 16 сегментов —
первый side-by-side тест Seedance 2.0 / Kling 3.0 / Veo 3.1) — см.
`docs/archive/2026-09-29-videohub-free-roam-trio-starter.md`.

### Следить (дыры без готовых кандидатов)

- `hybrid_ai_vfx_pipeline` — **закрыта 2026-09-29** (`3I2jj6HA3p0` River Cody +
`yUiTmO8AjJc` Max Novak; матрица: 13 клеток / 0 gaps, все поддомены
`creative_multimodal` покрыты). Продолжать следить за полноценными
VFX/Genjutsu breakdown'ами, а не тизерами (`FW_tIpEBJ0U`, `rwVeovA805k`) —
но как за дополнением покрытой клетки, не за закрывателем дыры.
- **Higgsfield Animation** — новый автор с трек-рекордом; анонсирован полный
  breakdown Passport Rush с production numbers (число генераций, бюджет,
  сроки) — брать первым, как только выйдет.
- Регулярный скан каналов корпуса (см. «Механика отбора» ниже) — новые кандидаты
  появляются только через него или по запросу владельца.

### Не рассматривать (действующие отсевы)

Конкретные ID — в таблице «Вне очереди» выше; здесь — правила отсева:

- Промт-листиклы (`prompt_architecture` — **12 видео**, перенасыщение).
- Шоукейс-фильмы без техники; рейтинги и «50+ способов»; юзкейсы LLM вне
  видео-крафта; продуктовые тизеры без техники.
- Авторов с трек-рекордом не резать по заголовку — вскрывать транскрипт-пробой
  (урок `qwGIwxZFc2I`, 2026-09-29).

Механика отбора: гейт 0.0b (`docs/guides/video-hub-operator.md`) +
`docs/architecture/expert-admission-control.md` §16. Скан каналов: RSS/flat
по авторам корпуса за окно 3 недель → транскрипт-проба → probe Скаутом →
вердикт владельцу.

---

## Текущая архитектура (что работает хорошо)

### Сильные стороны (не трогать при рефакторинге)

**1. Summary Bridging (Differential Retrieval)**
Главная архитектурная находка. HIGH сегменты получают FULL TRANSCRIPT, MEDIUM сегменты получают SUMMARY. В промпте синтеза это явно размечено:
- `[FULL TRANSCRIPT]` — для технических деталей и цитат
- `[SUMMARY (NARRATIVE BRIDGE)]` — для связности нарратива

Это решает проблему Lost Middle: LLM видит детали только там, где нужно, а не тонет в 53 полных транскриптах.

**Файл:** `backend/src/services/video_hub_service.py` — `_synthesize_response()`, строки 183-231.

**2. Topic-based Thread Expansion (Winning Topics)**
Когда хотя бы один сегмент в теме (topic_id) оценён как HIGH, все его "соседи" по topic_id подтягиваются как MEDIUM. Это реконструирует полный ход мысли эксперта, даже если она разбросана по видео.

**Файл:** `backend/src/services/video_hub_service.py` — `_resolve_threads()`, строки 130-181.

**3. Composite `topic_id` = `hash(url)[:12] + slug`**
Изоляция тем между видео. "rag_intro" из видео A и "rag_intro" из видео B никогда не смешаются.

**Файл:** `backend/scripts/import_video_json.py`, строки 109-112.

**4. Визуальные маркеры `[НА ЭКРАНЕ: ...]`**
Промпт синтеза запрещает механическое цитирование ("На слайде написано..."), требуя органично вплетать визуальный контекст в нарратив эксперта.

**5. Deploy Pipeline**
Production data release follows [operations](../operations.md). The legacy
`scripts/deploy_video.sh` wrapper imports JSON into staging and promotes the
whole DB through the Oracle VM upload-only path; the old Fly.io SFTP flow is
obsolete. It requires explicit owner authorization for a data release.

---

## Проблемы масштабирования (что ломается при росте)

### P1. Brute-force загрузка всех сегментов

> **Решение владельца (2026-09-16):** Video Hub намеренно **не** включается в
> hybrid-поиск панели и в Панэкс (Agent Context API отклоняет `video_hub`).
> Поиск по видео идёт через Expert Scout, у которого свой гибридный движок
> (FTS5 + sqlite-vec + RRF) прямо по `posts`. Пункт ниже остаётся планом на
> случай, если панель всё же получит видео.

**Проблема:** Оркестратор явно обходит Hybrid Search для video_hub:
```python
# simplified_query_endpoint.py:212
if scout_query and expert_id != "video_hub":  # <-- Video Hub МИМО
```
Все сегменты грузятся из БД и отправляются в Map. При 53 сегментах — ок. При 200+ — лишние API-вызовы и токены.

**Факт:** Все 53 сегмента уже имеют эмбеддинги в `post_embeddings` (проверено 2026-03-28). Hybrid Search (Vector KNN + FTS5 + RRF) может работать "из коробки".

**Решение:** Убрать исключение `expert_id != "video_hub"` в оркестраторе. Hybrid Search отфильтрует нерелевантные сегменты ДО Map-фазы.

**Файлы для изменения:**
- `backend/src/api/simplified_query_endpoint.py` — убрать 4 проверки `expert_id != "video_hub"` (строки 212, 247, 258, 264)
- `backend/scripts/embed_posts.py` — уже покрывает video_hub (SQL без фильтра по `expert_id`, проверено 2026-03-28)
- `backend/src/services/video_hub_service.py` — `process()` должен принимать уже предфильтрованные сегменты (интерфейс не меняется)

**Риск 1 (Topic Thread Expansion):** `_resolve_threads()` подтягивает "соседей" по topic_id. Если Hybrid Search отфильтровал часть соседей, нужно будет дозагрузить их из БД. Решение: в `_resolve_threads()` добавить SQL-запрос для подтягивания недостающих сегментов из winning topics.

**Риск 2 (Эмбеддинги при деплое):** старое предложение добавить embedding-шаг
устарело: `deploy_video.sh` уже предлагает его, но пропуск или ошибка не
останавливают promotion. Поэтому успешный wrapper не доказывает готовность
поиска. Основной онбординг подтверждает receipt как `searchable` до пересборки
Матрицы и отдельного data release; процедура — в
[руководстве оператора, шаг 0.4](../guides/video-hub-operator.md#04-combine-import-embed).

**Ориентировочный порог:** При 100+ сегментах выигрыш от предфильтрации превысит overhead на дозагрузку.

---

### P2. Нет chunking в Video Map

**Проблема:** `_map_segments()` (строки 80-130) отправляет ВСЕ сегменты в одном промпте:
```python
prompt = f"""...Segments:\n{json.dumps(map_input, ensure_ascii=False)}..."""
```
Основной `MapService` разбивает на чанки по 50 (`MAP_CHUNK_SIZE`). Video Map — нет.

**Текущий input:** ~53 сегмента = ~15-20K input tokens (title + summary каждого). Укладывается в лимиты `gemini-2.5-flash-lite`.

**Порог проблемы:** При ~150-200 сегментах промпт превысит 60K tokens — начнутся обрезки и деградация качества.

**Решение:** Добавить chunking по аналогии с `MapService`:
```python
# Пример:
chunks = [map_input[i:i+MAP_CHUNK_SIZE] for i in range(0, len(map_input), MAP_CHUNK_SIZE)]
results = await asyncio.gather(*[self._map_chunk(query, chunk) for chunk in chunks])
scored = [item for chunk_result in results for item in chunk_result]
```

**Файлы для изменения:**
- `backend/src/services/video_hub_service.py` — `_map_segments()`, переписать на chunked + parallel

---

### P3. Нет retry-логики (отказоустойчивость)

**Проблема:** Основной пайплайн имеет 3-уровневую защиту (Client Retry, Service Retry, Global Chunk Retry). Video Hub — ни одного retry:

```python
# _map_segments() — единственный try/except, без retry
except Exception as e:
    logger.error(f"Video Map failed: {e}")
    return []  # Молча пустой список → пользователь видит "Не найдено сегментов"

# _synthesize_response() — НЕТ try/except вообще
response = await self.llm_client.chat_completions_create(...)  # Exception пробрасывается наверх
```

**Цепочка при сбое Synthesis:**
1. `_synthesize_response()` бросает exception (429, timeout, safety filter)
2. Exception проходит через `process()` (нет try/except)
3. Exception проходит через `process_expert_pipeline()` (нет try/except для video-ветки)
4. Exception ЛОВИТСЯ оркестратором на **строке 1396** (`event_generator_parallel`)
5. `error_handler.process_api_error()` формирует user-friendly SSE error event
6. Фронтенд показывает ошибку в UI (НЕ HTTP 500, но и НЕ частичный результат)

**Важно:** `LanguageValidationService.process()` имеет свой try/except (строка 181) и при ошибке возвращает оригинальный ответ. Т.е. Phase 4 (Validation) не может "уронить" пайплайн.

**Итог:** При сбое Map — молчаливая деградация ("нет сегментов"). При сбое Synthesis — полная потеря ответа (error event в UI). Нет retry ни на одном из уровней.

**Решение:**
1. Map: Добавить `@retry` декоратор (tenacity) с exponential backoff, как в `map_service.py`
2. Synthesis: Обернуть в try/except с retry и fallback-сообщением (как в `error_handler.py`)

**Файлы для изменения:**
- `backend/src/services/video_hub_service.py` — `_map_segments()` и `_synthesize_response()`
- Импортировать `tenacity` (уже есть в зависимостях проекта)

---

### P4. `created_at` = момент импорта, не дата видео

**История закрытого пункта:** проблема ниже устранена. Прежнее предложение
с опциональной датой и fallback на время импорта не является текущим контрактом.
Сейчас `published_at` обязательна; актуальная семантика — в
[архитектурном SSOT](../architecture/video-hub-service.md).

**Проблема:** `import_video_json.py:140`:
```python
datetime.utcnow().isoformat(),  # created_at
```
Если импортировать старое видео (2024 года), его сегменты получат `created_at = today`. Последствия:
- Фильтр `use_recent_only` (последние 3 месяца) неправильно включает/исключает сегменты
- Сортировка "newest first" в UI некорректна

**Решение:** Добавить опциональное поле `published_at` в `video_metadata` JSON-схему:
```jsonc
{
  "video_metadata": {
    "title": "...",
    "url": "...",
    "published_at": "2024-11-15"  // <-- новое поле
  }
}
```
И использовать его в `import_video_json.py`:
```python
created_at = meta.get("published_at", datetime.utcnow().isoformat())
```

**Файлы для изменения:**
- `backend/scripts/import_video_json.py` — использовать `published_at`
- `docs/guides/video-hub-operator.md` — обновить JSON-схему
- `docs/architecture/video-hub-service.md` — обновить Data Schema

---

### P5. Нет валидации ID после Map-фазы

**Проблема:** `_map_segments()` отправляет реальные `telegram_message_id` в промпт и ожидает, что LLM вернёт те же ID. Но валидации нет:

```python
# _map_segments() возвращает данные из LLM:
return data.get("scores", [])  # [{id: ???, relevance: "HIGH"}, ...]

# _resolve_threads() пытается сопоставить с реальными постами:
scores_by_id = {str(s["id"]): s["relevance"] for s in scored_segments}
# Если LLM вернул несуществующий ID → он молча пропускается (default="LOW")
```

Если LLM галлюцинирует или округляет ID (виртуальные ID могут быть до 10^9), `_resolve_threads()` не найдёт совпадений. При этом проверка `if not high_segments and not medium_segments` (строка 45) пройдёт (она проверяет сырой LLM-ответ, а не сопоставленные сегменты), и `_synthesize_response()` получит пустой контекст.

**Решение:** Добавить валидацию после Map:
```python
valid_ids = {str(s.telegram_message_id) for s in video_segments}
scored_segments = [s for s in raw_scores if str(s["id"]) in valid_ids]
```

**Файл:** `backend/src/services/video_hub_service.py` — между строками 38 (вызов `_map_segments()`) и 41 (фильтрация `high_segments`).

---

### P6. Video Hub пропускает фазы Comment Groups (6) и Comment Synthesis (7)

**Текущее поведение:** Оркестратор возвращает результат на строке 315, ДО фаз комментариев (строки 498-559). Возвращает пустые:
```python
relevant_comment_groups=[],
comment_groups_synthesis=None,
```

**Почему это правильно сейчас:** Видео-сегменты не имеют комментариев в Telegram. Нет данных для анализа.

**Когда может измениться:** Если в будущем добавить YouTube-комментарии к видео-сегментам (import из YouTube API), потребуется интеграция с Comment phases. Пока это не планируется — просто зафиксировано как design decision.

---

## Менее критичные улучшения (nice-to-have)

### N1. `context_bridge` — мёртвая метадата

Поле хранится в `media_metadata`, но `video_hub_service.py` его не читает. Можно передавать в промпт синтеза для улучшения связности:
```
--- SEGMENT [123] [...] ---
[BRIDGE: This segment continues the discussion of RAG architecture from the previous one]
Content here...
```

**Файл:** `video_hub_service.py` — `_synthesize_response()`, формирование `formatted_parts`.

### N2. Hardcoded дата "2026" в промпте синтеза

```python
# video_hub_service.py:199
<date>TODAY is 2026.</date>
```
Заменить на:
```python
f"<date>TODAY is {datetime.now().strftime('%Y-%m-%d')}.</date>"
```

### N3. Модель `gemini-3.1-pro-preview` для синтеза

Video Hub использует текущую Pro-модель `gemini-3.1-pro-preview` для синтеза. Основной пайплайн использует `gemini-3-flash-preview`. Стоит протестировать Flash для видео — возможно, разница в качестве минимальна при существенной экономии.

**Конфигурация:** `MODEL_VIDEO_PRO` в `.env` — можно просто переключить без изменения кода.

### N4. Нет Medium Scoring для видео

Основной пайплайн имеет отдельную фазу Medium Scoring (score 0-1, threshold 0.7, top 5). Video Hub пропускает ALL MEDIUM сегменты. При росте библиотеки может появиться "шум" от нерелевантных MEDIUM.

**Решение:** Добавить аналог `MediumScoringService` или хотя бы простой threshold на количество MEDIUM сегментов (например, top-10).

### N5. PostCard отображает сырой формат

Для видео-сегментов `PostCard` рендерит `message_text` как есть: `TITLE: ...\nSUMMARY: ...\n---\nCONTENT:...`. Разделитель `---` рендерится как `<hr>`, но метки TITLE/SUMMARY/CONTENT видны пользователю.

**Решение:** В `PostCard.tsx` для `isVideoSegment` парсить формат и рендерить title как заголовок, summary как блок, content как основной текст.

### N6. Видео-ответ не проходит citation verification

**Проблема:** Видео-ветка оркестратора возвращает `ExpertResponse` напрямую
(ветка video_hub в `simplified_query_endpoint.py`), минуя
`_run_citation_verification` (вызывается только для обычных экспертов после
Reduce). При этом промпт синтеза ОБЯЗЫВАЕТ ставить `[post:ID]` —
галлюцинированная или битая ссылка в видео-ответе не проверится никогда.

**Решение:** При возврате видео в панель — прогнать видео-ответ через
`_run_citation_verification` так же, как обычный Reduce, с `posts_by_id`,
собранным из видео-сегментов (маппинг по `telegram_message_id`).

**Файл:** `backend/src/api/simplified_query_endpoint.py` — видео-ветка.

---

## Порядок реализации (приоритеты)

| Приоритет | Задача | Когда | Сложность | Статус |
|-----------|--------|-------|-----------|--------|
| **1** | P3: Retry-логика (Map + Synthesis) | Сейчас (баг) | Низкая | ✅ 2026-09-24: retry ×3 (tenacity) на Map и Synthesis; Map-сбой больше не маскируется под «не найдено» |
| **2** | P5: Валидация ID после Map | Сейчас (баг) | Тривиальная | ✅ 2026-09-17 (`_normalize_scores`) |
| **3** | P4: `published_at` в импорт | При следующем импорте видео | Низкая | ✅ 2026-09-16 |
| **4** | N2: Динамическая дата в промпте | При любом изменении сервиса | Тривиальная | ✅ 2026-09-17 |
| **5** | P2: Chunking в Video Map | При ~100 сегментах | Средняя | ✅ 2026-09-24: порции по 50, параллельно с капом `MAP_MAX_PARALLEL`; сбой порции = честный отказ Map |
| **6** | P1: Включить Hybrid Search + эмбеддинги в deploy | При ~100-150 сегментах | Средняя | Снято решением владельца: поиск по видео — только Scout |
| **7** | N1: Использовать `context_bridge` | При рефакторинге синтеза | Низкая | Открыто |
| **8** | N3: Тест Flash vs Pro для синтеза | При оптимизации стоимости | Тривиальная | Открыто |
| **9** | N4: Medium Scoring | При ~200 сегментах | Средняя | Открыто |
| **10** | N5: PostCard парсинг | При UX-рефакторинге | Низкая | Открыто (deep-link `?t=`/`&t=` починен 2026-09-17) |
| **11** | N6: Citation verification в видео-ветке | При возврате видео в панель | Низкая | Открыто |

### Review fixes (2026-09-17)

- Канонизация YouTube-URL: все формы (`youtu.be`, `shorts`, `embed`, `watch?v=`) дают одну
  идентичность — дубли видео и расхождение topic-хэшей исключены.
- Guard'ы целостности: `--combine` и импорт падают на дублях `segment_id`; transcript
  валидируется по ASR-схеме; неизвестные скалярные ключи `visual` попадают в поисковый текст.
- `import_video_json.py --replace-video` — чистая переиндексация видео после ресегментации;
  при изменении `message_text` старые эмбеддинги инвалидируются.
- PostCard: deep-link собирается с `?` или `&` в зависимости от формы URL (был битый `&t=`).
- Тесты: `backend/tests/test_video_ingest_guards.py` — guard'ы combine/import/transcript/scores.

### Review fixes (2026-09-24, Map chunking)

- `_map_segments()` больше не шлёт все сегменты одним промптом: порции по
  `MAP_CHUNK_SIZE` (50), параллельно с капом `MAP_MAX_PARALLEL`, merge scores
  после. Снимает потолок ~300 сегментов (обрезка JSON со скорами → молчаливое
  «не найдено»). Сбой любой порции после её retry роняет Map целиком
  (`VideoMapUnavailable`) — без частичной оценки, которая молча потеряла бы
  сегменты упавшей порции. Закрывает P2 из таблицы выше.

### Review fixes (2026-09-24, honest failures & retry)

- Map-сбой (LLM упал, битый JSON, ответ без валидных scores) после 3 попыток
  больше не превращается в молчаливое «не найдено сегментов»: возвращается
  локализованное «видеоархив временно недоступен» (`VideoMapUnavailable`,
  пустые `main_sources`, LOW). Честный «не найдено» остался только для реального
  вердикта «всё LOW». Synthesis получил retry ×3 и после финального сбоя
  честно кидает ошибку наверх (SSE error event). Закрывает P3 из таблицы выше.

### Review fixes (2026-09-24, timestamps)

- Нормализация дат: `published_at` при импорте приводится к каноническому
  `YYYY-MM-DD HH:MM:SS` (date-only/ISO-T/offsets — любой вход), дублируется в
  `media_metadata.published_at`; кривая дата роняет импорт, а молча не
  подменяется. Парсеры свежести (Scout, `HybridRetrievalService`) принимают и
  date-only. Гэп P4: строки с bare-date `created_at` считались «очень старыми»
  и свежие видео (Dan Kieft) занижались в поиске. Швабра для старых строк:
  `backend/scripts/maintenance/normalize_video_timestamps.py`.
- `embed_posts.py` пишет `vec_posts.created_at` в том же каноническом формате.

### Review fixes (2026-09-17, повторный проход)

- Фолбэк «не найдено сегментов» локализован: RU/EN по языку запроса (синтез уже был
  language-aware, фолбэк — нет).
- `_normalize_scores` дедуплицирует Map-scores до сильнейшей релевантности на сегмент —
  HIGH/MEDIUM-счётчики не раздуются дублями.
- `import_video_json.py`: единая column→value карта для INSERT и UPDATE вместо
  позиционных срезов (`values[:7]`/`values[8:]`) — добавление колонки не рассинхронизирует
  два запроса молча.
- `datetime.now(UTC).replace(tzinfo=None)` вместо deprecated `utcnow()`; формат хранения
  `created_at` не менялся (naive ISO) — aware-значения смешались бы с naive-арифметикой
  в `_calculate_age_days` retrieval-сервисов.
- Открыто (находка ревью): видео-ответ не проходит citation verification — см. N6.

---

## Файловая карта Video Hub (полный инвентарь)

### Backend
| Файл | Роль |
|------|------|
| `src/services/video_hub_service.py` | 4-фазный pipeline (Map, Resolve, Synthesis, Validation) |
| `src/api/simplified_query_endpoint.py` | Оркестратор (строки 212-315 — video_hub ветка) |
| `src/services/sync_orchestrator.py` | Исключает video_hub из Telegram-синхронизации (строка 45) |
| `backend/src/config.py` | `MODEL_VIDEO_PRO`, `MODEL_VIDEO_FLASH` в секции Video Hub Models |
| `scripts/import_video_json.py` | JSON -> SQLite: virtual ID, structured `visual`, кадры, `published_at`; upsert по `telegram_message_id` (не сиротит эмбеддинги) |
| `scripts/ingest_video.py` | Stage 1 ingest: ASR, чанки, кадры, окна; `--combine` для склейки чанков |
| `scripts/asr_whisper.py` | ASR-хелпер (faster-whisper int8, CPU, глоссарий, авто-язык) |
| `scripts/embed_posts.py` | Эмбеддинги (покрывает video_hub — нет фильтра по expert_id) |
| `prompts/video_segmentation_prompt.md` | Golden Prompt сегментации (ключевые кадры, дословные промты/настройки); используется и ручным путём, и LLM-пассом |

### Frontend
| Файл | Роль |
|------|------|
| `src/config/expertConfig.ts` | Knowledge Hub группа, display name "Video_Hub" |
| `src/components/ExpertAccordion.tsx` | Иконка, "Video Archive" лейбл |
| `src/components/PostCard.tsx` | YouTube deep-links с `?t=`/`&t=` параметрами |

### Scripts & Deploy
| Файл | Роль |
|------|------|
| `scripts/deploy_video.sh` | Legacy manual path: promotion готового JSON через DB release. Основной путь — автоматический ingest + обычный `обнови базу` |

### Documentation
| Файл | Роль |
|------|------|
| `docs/architecture/video-hub-service.md` | Architecture SSOT |
| `docs/guides/video-hub-operator.md` | Operator Playbook (AI Studio segmentation) |
| `docs/guides/add-video.md` | Quick-start guide |
| `docs/roadmap/video-hub-scaling.md` | **Этот файл** — план масштабирования |

### Database
- Таблица `posts`: `expert_id="video_hub"`, `channel_id="video_hub_internal"`
- Таблица `post_embeddings`: все 53 сегмента имеют эмбеддинги
- `media_metadata` JSON: `type`, `video_url`, `topic_id`, `timestamp_seconds`, `context_bridge`, `original_author`
- Virtual `telegram_message_id`: `MD5(url + segment_id) % 10^9`

---

## Design Decisions (осознанные решения, не баги)

Эти решения зафиксированы как осознанные. Не "чинить", если нет явной необходимости:

1. **Video Hub изолирован от Telegram-синхронизации** — `sync_orchestrator.py` исключает `video_hub` из cron-sync (`WHERE expert_id != 'video_hub'`). Правильно: у видео нет Telegram-канала для синхронизации.

2. **Comment phases (6, 7) пропущены** — оркестратор возвращает результат ДО фаз комментариев. Правильно: видео-сегменты не имеют комментариев.

3. **`INSERT OR REPLACE` в импорте** — при повторном импорте того же видео сегменты перезаписываются (virtual ID детерминирован: `MD5(url + segment_id)`). Это обеспечивает идемпотентность. Риск: если segment_id изменился между импортами (другая сегментация), старые записи останутся как "мусор". Решение при необходимости: добавить `DELETE FROM posts WHERE expert_id='video_hub' AND json_extract(media_metadata, '$.video_url') = ?` перед импортом.

4. **Весь video_hub — один "эксперт"** — все видео разных авторов хранятся под одним `expert_id="video_hub"`, а настоящий автор остаётся в `media_metadata.original_author`. Это упрощает архитектуру (один sidecar), но смешивает авторов. При необходимости разделить: создать отдельные synthetic IDs вида `video_hub_<author_slug>` в `expert_metadata`, не переиспользуя удалённых Telegram-экспертов как живые сущности.

---

## Документационный статус

Ранее здесь был долг: `MODEL_VIDEO_PRO` / `MODEL_VIDEO_FLASH` были описаны не во всех SSOT-документах. На 2026-04-27 этот долг закрыт.

| Файл | Статус |
|------|--------|
| `.env.example` | Содержит `MODEL_VIDEO_PRO=gemini-3.1-pro-preview` и `MODEL_VIDEO_FLASH=gemini-3-flash-preview` |
| `backend/CLAUDE.md` | Сервисная таблица и Configuration включают Video модели |
| `docs/architecture/pipeline.md` | Vertex notes фиксируют замену `gemini-3-pro-preview` на `gemini-3.1-pro-preview` |
| `docs/architecture/video-hub-service.md` | Architecture SSOT содержит Video Hub model table |

При следующей смене Video Hub моделей обновить все строки выше вместе с `backend/src/config.py`.

---

## Метрики для мониторинга

При добавлении новых видео отслеживать:
- **Количество сегментов**: `SELECT COUNT(*) FROM posts WHERE expert_id='video_hub'`
- **Количество видео**: `SELECT COUNT(DISTINCT json_extract(media_metadata, '$.video_url')) FROM posts WHERE expert_id='video_hub'`
- **Наличие эмбеддингов**: `SELECT COUNT(*) FROM post_embeddings WHERE post_id IN (SELECT post_id FROM posts WHERE expert_id='video_hub')`
- **Время Map-фазы**: В логах `[video_hub]` — должно быть <10s
