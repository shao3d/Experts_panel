# Video Hub: Scaling Roadmap & Architecture Audit

**Created:** 2026-03-28
**Status:** Active Roadmap (implement when video library exceeds ~100 segments)
**Current State:** 53 segments, 4 videos, 40 topics. Pipeline stable.
**Trigger:** Start implementing when approaching 100-150 segments or 10+ videos.

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
`scripts/deploy_video.sh` — 5 фаз с backup, SSH wait, SFTP, WAL cleanup и rollback. Production-grade.

---

## Проблемы масштабирования (что ломается при росте)

### P1. Brute-force загрузка всех сегментов

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

**Риск 2 (Эмбеддинги при деплое):** `deploy_video.sh` НЕ запускает `embed_posts.py` после импорта! Эмбеддинги создаются только при запуске `update_production_db.sh` (шаг 4: Vectorization). Это значит: свежие сегменты не имеют эмбеддингов до следующего цикла обновления. При включении Hybrid Search для видео **обязательно** добавить шаг эмбеддинга в `deploy_video.sh` (между шагами 2 и 3):
```bash
log "🧬 [2.5/5] Generating embeddings for new segments..."
$PYTHON_CMD backend/scripts/embed_posts.py --continuous
```

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

**Проблема:** `import_video_json.py:140`:
```python
datetime.utcnow().isoformat(),  # created_at
```
Если импортировать старое видео (2024 года), его сегменты получат `created_at = today`. Последствия:
- Фильтр `use_recent_only` (последние 3 месяца) неправильно включает/исключает сегменты
- Сортировка "newest first" в UI некорректна

**Решение:** Добавить опциональное поле `published_at` в `video_metadata` JSON-схему:
```json
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

### N3. Модель `gemini-3-pro-preview` для синтеза

Video Hub использует Pro (самую дорогую модель) для синтеза. Основной пайплайн использует `gemini-3-flash-preview`. Стоит протестировать Flash для видео — возможно, разница в качестве минимальна при существенной экономии.

**Конфигурация:** `MODEL_VIDEO_PRO` в `.env` — можно просто переключить без изменения кода.

### N4. Нет Medium Scoring для видео

Основной пайплайн имеет отдельную фазу Medium Scoring (score 0-1, threshold 0.7, top 5). Video Hub пропускает ALL MEDIUM сегменты. При росте библиотеки может появиться "шум" от нерелевантных MEDIUM.

**Решение:** Добавить аналог `MediumScoringService` или хотя бы простой threshold на количество MEDIUM сегментов (например, top-10).

### N5. PostCard отображает сырой формат

Для видео-сегментов `PostCard` рендерит `message_text` как есть: `TITLE: ...\nSUMMARY: ...\n---\nCONTENT:...`. Разделитель `---` рендерится как `<hr>`, но метки TITLE/SUMMARY/CONTENT видны пользователю.

**Решение:** В `PostCard.tsx` для `isVideoSegment` парсить формат и рендерить title как заголовок, summary как блок, content как основной текст.

---

## Порядок реализации (приоритеты)

| Приоритет | Задача | Когда | Сложность |
|-----------|--------|-------|-----------|
| **1** | P3: Retry-логика (Map + Synthesis) | Сейчас (баг) | Низкая |
| **2** | P5: Валидация ID после Map | Сейчас (баг) | Тривиальная |
| **3** | P4: `published_at` в импорт | При следующем импорте видео | Низкая |
| **4** | N2: Динамическая дата в промпте | При любом изменении сервиса | Тривиальная |
| **5** | P2: Chunking в Video Map | При ~100 сегментах | Средняя |
| **6** | P1: Включить Hybrid Search + эмбеддинги в deploy | При ~100-150 сегментах | Средняя |
| **7** | N1: Использовать `context_bridge` | При рефакторинге синтеза | Низкая |
| **8** | N3: Тест Flash vs Pro для синтеза | При оптимизации стоимости | Тривиальная |
| **9** | N4: Medium Scoring | При ~200 сегментах | Средняя |
| **10** | N5: PostCard парсинг | При UX-рефакторинге | Низкая |

---

## Файловая карта Video Hub (полный инвентарь)

### Backend
| Файл | Роль |
|------|------|
| `src/services/video_hub_service.py` | 4-фазный pipeline (Map, Resolve, Synthesis, Validation) |
| `src/api/simplified_query_endpoint.py` | Оркестратор (строки 212-315 — video_hub ветка) |
| `src/services/sync_orchestrator.py` | Исключает video_hub из Telegram-синхронизации (строка 45) |
| `src/config.py` | `MODEL_VIDEO_PRO`, `MODEL_VIDEO_FLASH` (строки 54-56) |
| `scripts/import_video_json.py` | JSON -> SQLite импорт с virtual ID |
| `scripts/embed_posts.py` | Эмбеддинги (покрывает video_hub — нет фильтра по expert_id) |
| `prompts/video_segmentation_prompt.md` | Golden Prompt для AI Studio сегментации |

### Frontend
| Файл | Роль |
|------|------|
| `src/config/expertConfig.ts` | Knowledge Hub группа, display name "Video_Hub" |
| `src/components/ExpertAccordion.tsx` | Иконка, "Video Archive" лейбл |
| `src/components/PostCard.tsx` | YouTube deep-links с `&t=XXXs` |

### Scripts & Deploy
| Файл | Роль |
|------|------|
| `scripts/deploy_video.sh` | 5-фазный deploy: backup -> import -> compress -> SFTP -> restart |

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

4. **Весь video_hub — один "эксперт"** — все видео разных авторов (Gleb, MKarpov) хранятся под одним `expert_id="video_hub"`. Это упрощает архитектуру (один sidecar), но смешивает авторов. При необходимости разделить: создать `video_hub_gleb`, `video_hub_mkarpov` и т.д. в `expert_metadata`.

---

## Документационный долг

Следующие файлы **не содержат** упоминаний `MODEL_VIDEO_PRO` / `MODEL_VIDEO_FLASH`, хотя по правилам проекта (см. `docs/DOCUMENTATION_MAP.md`, секция "Изменения в моделях") должны:

| Файл | Что отсутствует |
|------|----------------|
| `.env.example` | Нет `MODEL_VIDEO_PRO` и `MODEL_VIDEO_FLASH` (env vars без документации) |
| `CLAUDE.md` (корень) | Секция "Current Production Models" не включает Video модели |
| `backend/CLAUDE.md` | Секция "Models" (Configuration) не включает Video модели |
| `docs/architecture/pipeline.md` | Таблица "Model Configuration (Env Vars)" не включает Video модели |

**Примечание:** Модели описаны только в `docs/architecture/video-hub-service.md` (специализированный SSOT) и в `backend/CLAUDE.md` в таблице сервисов (как часть описания `video_hub_service.py`). При обновлении этих моделей — добавить недостающие записи во все 4 файла выше.

---

## Метрики для мониторинга

При добавлении новых видео отслеживать:
- **Количество сегментов**: `SELECT COUNT(*) FROM posts WHERE expert_id='video_hub'`
- **Количество видео**: `SELECT COUNT(DISTINCT json_extract(media_metadata, '$.video_url')) FROM posts WHERE expert_id='video_hub'`
- **Наличие эмбеддингов**: `SELECT COUNT(*) FROM post_embeddings WHERE post_id IN (SELECT post_id FROM posts WHERE expert_id='video_hub')`
- **Время Map-фазы**: В логах `[video_hub]` — должно быть <10s
