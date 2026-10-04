# VideoHub: онбординг тройки CAWnlOJbSX4 + xZx5940qoKE + 0d8pqU8JRrY

**Status:** Archived — staging onboarding and repair completed
**Last updated:** 2026-10-04

Current acceptance and release status: `docs/quality/2026-10-04-mimo-trio-repair.md`.
Original handoff below is history; its duration/audio assumptions were corrected during onboarding.
**Created:** 2026-10-03
**Owner:** Андрей
**SSOT процедуры:** `docs/guides/video-hub-operator.md` (шаги 0.0–0.4)
**Гейт приёмки:** `docs/architecture/expert-admission-control.md` §16
**Пробы и вердикты:** `output/video_admission/candidate_probe_journal.json` (записи 2026-10-03)

---

## Приказ владельца (2026-10-03)

Провести **staging-онбординг трёх видео** (полный список ниже). Verdict'ы пробы
`recommend ingest` утверждены передачей этого приказа. Production data release
(«обнови базу») в задачу **не входит** и требует отдельной явной команды
владельца. Commit/push — только по отдельной команде владельца.

## Что уже сделано (не переделывать)

Гейт 0.0b Phase 0 закрыт агентом 2026-10-03:

- duplicate check: все три видео **FREE** (`video_hub_index.py --check`, exit 0);
- транскрипт-пробы: локальный ASR faster-whisper large-v3-turbo, артефакты в
  `output/video_admission/<id>/transcript.json` и `transcript_ts.txt`;
  аудио уже лежит в `output/video_admission/<id>/audio.m4a`;
- scout probe-чеки read-only хелпером (`backend/scripts/expert_scout.py`):
  ключевые дыры подтверждены пустыми успешными поисками RU+EN, overlap-источники
  прочитаны полностью — детали в `probe`-блоке журнала;
- watchlist обновлён: `docs/roadmap/video-hub-scaling.md` (раздел «Что
  рассматривать дальше, 2026-10-03»).

**Важно про качество пробных транскриптов:** они без глоссария, имена моделей
испорчены («Sedans/Cedance/Seederns» = Seedance, «Kixel/Hixel/Higsfield» =
Higgsfield, «GPT-Sex Astra» = GPT-6 Astra). Для онбординга годятся только как
карта тем. Для Stage 1 перегони ASR заново **с глоссарием** (`asr_whisper.py
--initial-prompt "Seedance, Higgsfield, GPT-6 Astra, Kling, Nano Banana Pro"`)
— аудио уже на диске, ~8 минут на ролик. Сверь интервалы ASR с длительностью
медиа (правило шага 0.2).

## Среда VM (проверено 2026-10-03)

- WARP SOCKS-прокси поднят: `socks5h://127.0.0.1:40000` (рецепт скачивания —
  операторский гайд §0.1a; YouTube-сабы отдают 429 — не рассчитывай на них,
  качай видео `299/303/399/312/18` + аудио уже есть).
- faster-whisper живёт в **`/usr/bin/python3.11`** (в backend-venv модуля НЕТ):
  `python3.11 backend/scripts/asr_whisper.py ...`.
- Работа только в `/home/ubuntu/apps/experts-panel/dev` (VM dev checkout).
- Staging-БД: `backend/data/experts.db`; трогать production запрещено.

## Тройка: вердикты и что сохранить (must_preserve)

### 1. `CAWnlOJbSX4` — River Cody, «I Turned My Boring Hometown Into A Movie With AI VFX» (2026-08-12, 623s) — ingest (full)

- 5 уровней продакшена, каждый «сначала практически, потом AI»: композиция →
  свет → цвет → окружение/фон → фоновая динамика (extras);
- elements в Higgsfield (мульти-ракурсные ассеты персонажа/пропса/локации) +
  Claude Fable как «переводчик» → промпт в Seedance 2.5;
- storyboard-кадр сначала (Higgsfield cinematic cameras), скриншот hero-кадра
  как референс; неснятые ракурсы генерируются через storyboard-reference →
  sequence (3 шота);
- selective change: Seedance 2.5 меняет только указанное (цвет маски, фон),
  остальное держит → композитинг оригинального субъекта поверх видео
  («masked out the mask»);
- впрыск динамики: extras/машина в кадр из того же сгенерированного видео.
- Draft cells: `scene_blocking`, `hybrid_ai_vfx_pipeline`, `color_and_light`,
  `image_model_workflow` (уточнить по фактическим сегментам).
- Caveat: вставки «check out this course / link in description» — CTA, в
  сегменты не тащить.

### 2. `xZx5940qoKE` — Youri van Hofwegen, «How to Storyboard Realistic AI Videos with Google Flow» (2026-10-02, 649s) — ingest (full)

- настройки Flow-агента: confirm-before-generate Always, Nano Banana Pro
  (изображения) + OmniFlash 1.1 (видео), фикс AR/числа выходов; цена 15
  кредитов/10s, план $4.99 = 200 кредитов;
- стиль-лок: реализм описывается один раз в первом сообщении и переносится на
  все генерации;
- сторибординг всего 40-сек фильма (4×10s) в чате ДО генерации; твист выбирается
  так, чтобы модель могла показать его без сложного движения;
- 3-панельный character sheet до генераций: front БЕЗ головы, back, крупный
  портрет; серый фон и плоский свет; контрольные детали (родинка, шрам);
- непрерывность сцен: последний кадр предыдущего клипа → скриншот → референс
  начала следующей; сцены генерируются строго по одной;
- честный фейл: сцена 4 не подхватила последний кадр; сборка в CapCut, музыка
  поверх нативного аудио OmniFlash.
- Draft cells: `character_consistency`, `multimodal_generation`,
  `ai_video_direction` или `scene_blocking` (сторибординг-план; уточнить по
  сегментам).
- Caveat: no-head front panel уже покрыт `cCDn0Z6AdmM` — не выдавать за новое;
  уникальность именно в last-frame chaining и плане-до-генерации.

### 3. `0d8pqU8JRrY` — Youri van Hofwegen, «How to Make 3D Animations With GPT 6 Astra (No Blender Needed)» (2026-09-19, 610s) — ingest (full)

- 3D Jutso (Higgsfield): Astra строит полную 3D-сцену из описания —
  props/layout/lighting отдельными объектами, реальная камера; правка
  перетаскиванием вместо перепромпта;
- named parts: каждый деталь называется отдельно (8 частей) → независимо
  анимируемые объекты; дедлайн сборки «snap together by 6s + hold 2s»;
  спецификация камеры (orbit 20°, medium → close-up), 30fps;
- обязательная инструкция рендера: «используй scene camera и её реальный путь,
  не viewport preview»; фикс длительности/AR/разрешения в том же сообщении;
- relight/reshoot: движение собирается в сером viewport, затем Seedance 2.5
  переливает и переснимает как «ultra high-budget commercial»;
- одна сцена → три рендера стиля (anime/photoreal/feature film) при фиксированных
  камере и движении;
- персонаж: путь раннера и путь камеры — отдельные и редактируемые; 3-панельный
  sheet (GPT image 2.5 Sunburst, 4K max quality); финальный рендер =
  sheet + сцена + «natural weighted body movement вместо копирования превью».
- Draft cells: `3d_previz_pipeline`, `scene_blocking`, `multimodal_generation`,
  `character_consistency` (уточнить по сегментам).
- Caveat: спонсор-блок 0:30–1:08 (бонусный пакет за подписку) — пометить при
  разметке, в полезные сегменты не включать; принцип «камера отдельно от актёра»
  уже покрыт `neyrograph:4667` — не дублировать как «уникальное».

## Порядок работы

1. Прочитай `AGENTS.md`, `docs/DOCUMENTATION_MAP.md`, этот файл; SSOT процедуры —
   `docs/guides/video-hub-operator.md` (шаги 0.0–0.4 и правила разметки чанков).
   Модель ведущего выбирает владелец; если создаёшь исполнителей — роли по
   таблице «Модель для ведения онбординга» гайда. Параллельная запись в один
   артефакт запрещена.
2. На каждое видео: скачать mp4 через WARP (§0.1a; аудио уже на диске) →
   Stage 1 `ingest_video.py` (`--chunk-minutes 5`, ASR с глоссарием) → Stage 2
   разметка чанков по Golden Prompt (сквозные `segment_id`, `published_at`
   обязателен, `[НА ЭКРАНЕ: ...]` по кадрам, промты/цифры сверять с native
   кадрами; OCR русских надписей ненадёжен) → приёмка ведущим по исходникам.
3. Шаг 0.4: `--combine` → `import_video_json.py --dry-run` → импорт →
   `embed_posts.py --continuous --receipt ...` → дождаться `searchable` →
   `build_video_matrix.py` (матрицу руками не править).
4. Phase 1 (лёгкая разметка): проставить `matrix_cells` сегментам; внести в
   `output/video_admission/admission_log.json` записи ingest (verdict, cells,
   scope=full, decided_at 2026-10-03, receipt) и пометить в
   `candidate_probe_journal.json` `approval: owner_approved_by_handoff_2026-10-03`.
5. Проверка поиска: 3–4 вопроса Скаутом (`backend/scripts/expert_scout.py
   search`, read-only) по must_preserve каждого видео — приёмы должны
   находиться с deep-link на это видео.
6. Не трогать: waitlist/резервы, `kOoC3yhUyDQ` (ждёт отдельного решения), чужие
   изменения в git, production.

## Границы

Языки — только RU/EN. Секреты, `.env`, токены, production DB — не читать/не
печатать. Тяжёлые тест-сьюты не гонять. Commit/push/production release — только
по явной команде владельца.

## Готовность и отчёт

Готово = все три видео `searchable` + матрица пересобрана + spot-check Скаута
находит приёмы. В финале — простыми словами: что сделано, что проверено, что НЕ
проверено (в т.ч. честные ограничения: успешный импорт ≠ приёмка точности
содержания), сколько сегментов/ячеек дал каждый ролик, и нужен ли владельцу
следующий шаг (`обнови базу` — отдельно и только по его команде).
