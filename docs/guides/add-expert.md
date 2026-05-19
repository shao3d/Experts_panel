# 🚀 Добавление нового эксперта (Полный алгоритм)

**Версия:** 7.3 (Admission-first + Single Config + Staged Fly DB Deploy)
**Дата:** 2026-05-20
**Статус:** Актуально

---

## 📋 Краткий алгоритм (TL;DR)

```
0. Admission: паспорт + knowledge matrix + accept/reject verdict
1. Экспорт JSON из Telegram Desktop
2. ./scripts/add_new_expert.sh <id> "<name>" <username> <json>
3. UI интеграция + roster doc (`expertConfig.ts`, `current-expert-roster.md`)
4. (Опционально) Ручной запуск Drift Analysis
5. Деплой: ./scripts/update_production_db.sh + targeted git commit/push
```

Этот runbook начинается после продуктового решения `accept`. Для оценки
кандидата до импорта используй `docs/architecture/expert-admission-control.md`
и artifacts under `output/expert_admission/*`.

---

## 📋 Требования

1. **JSON Экспорт канала:**
   - Telegram Desktop → Канал → ⋮ → Export chat history → **JSON**

2. **Доступ к Telegram API** (в `backend/.env`):
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
   - `TELEGRAM_SESSION_NAME`

3. **Vertex AI runtime** (в `backend/.env`) для эмбеддингов и дрифта:
   - `VERTEX_AI_PROJECT_ID`
   - `VERTEX_AI_LOCATION`
   - `VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH` локально
     или `VERTEX_AI_SERVICE_ACCOUNT_JSON` в managed runtime

---

## 🚀 Полная инструкция

### Step 1: Подготовьте данные

| Поле | Пример | Правила |
|------|--------|---------|
| `expert_id` | `doronin` | Только `a-z`, `0-9`, `_` |
| `display_name` | `"Doronin"` | В кавычках, для UI |
| `username` | `kdoronin_blog` | Telegram username без `@` |
| `json_path` | `data/exports/result.json` | Путь к экспорту |

### Step 2: Запустите скрипт регистрации

```bash
./scripts/add_new_expert.sh <expert_id> "<Display Name>" <username> <json_path>
```

**Пример (из корня проекта):**
```bash
./scripts/add_new_expert.sh polyakov "Polyakov" countwithsasha data/exports/polyakov.json
```

**Что произойдёт автоматически:**
- ✅ Метаданные в `expert_metadata`
- ✅ Посты из JSON
- ✅ Комментарии из Telegram API
- ✅ `pending` задачи для Drift Analysis

> **Важно:** Скрипт предложит запустить `update_production_db.sh` для анализа дрифта.
> **ОТВЕТЬ 'N' (Нет)**. Мы запустим этот процесс отдельно, когда будем готовы.

⏱️ **Длительность:** 5-15 минут

### Step 3: UI интеграция (Single Config)

Добавьте эксперта в **единственный файл конфигурации**: `frontend/src/config/expertConfig.ts`.

> **Note:** Файл `ExpertSelectionBar.tsx` редактировать **НЕ НУЖНО**, он подтянет настройки автоматически.
> Актуальный roster и группы фиксируются в `docs/architecture/current-expert-roster.md`.

```typescript
// 1. Добавить в EXPERT_GROUPS (выбрать нужную категорию):
{ label: 'Tech', expertIds: [..., '<expert_id>'] },

// 2. Добавить в displayNames:
'<expert_id>': '<Display Name>',

// 3. Добавить в order (определяет порядок сортировки):
order: [..., '<expert_id>']
```

### Step 4: Drift Analysis (Ручной или Автоматический)

На этом этапе эксперт добавлен в систему, но его комментарии ещё не проанализированы на предмет дрифта тем.

**Вариант А: Автоматический (при деплое)**
Если вы планируете сразу деплоить (`Step 5`), скрипт `./scripts/update_production_db.sh` **сам запустит** анализ дрифта для всех pending групп.
*   **Плюс:** Полная автоматизация.
*   **Минус:** Расходует Vertex AI квоту.

**Вариант Б: Ручной (бесплатный/Dev)**
Если хотите сэкономить квоту или проверить результат локально перед деплоем:
1.  Запустите Gemini CLI с промптом из `prompts/gemini_cli_drift_prompt.md`.
2.  Или используйте скрипт: `python3 backend/run_drift_service.py`

> **Важно:** `backend/run_drift_service.py` теперь сам подхватывает `backend/.env` и ожидает Vertex credentials из этого файла.

### Step 5: Деплой

```bash
# 1. БД на Fly.io (включает Drift Analysis, если остались pending группы)
./scripts/update_production_db.sh

# 2. Код на GitHub → автодеплой frontend
git add frontend/src/config/expertConfig.ts docs/architecture/current-expert-roster.md
git commit -m "feat: add new expert <expert_id>"
git push
```

`update_production_db.sh` сам грузит `backend/.env`, запускает `embed_posts.py --continuous` и `run_drift_service.py`, так что и embeddings, и drift идут через Vertex AI. Перед заменой production DB скрипт создаёт remote backup, проверяет свободное место на `/app/data`, сжимает локальную БД, загружает gzip маленькими SFTP-chunks, сверяет size/SHA/gzip, распаковывает во временный файл `/app/data/experts.db.tmp`, делает SQLite integrity check и только потом заменяет `/app/data/experts.db`.

> **Важно про Fly:** `git push` сам по себе не меняет SQLite на mounted volume `/app/data/experts.db`. Он обновляет код и собранный frontend. Если менялись данные эксперта, обязательно обновите production DB через штатный DB deploy или отдельный targeted cleanup с backup.

---

## 🗑️ Удаление эксперта

Удаление эксперта состоит из двух независимых частей: UI config и SQLite data. Нельзя считать задачу завершённой после одного `git push`.

### 1. Уберите эксперта из UI

В `frontend/src/config/expertConfig.ts` удалите `expert_id` из:

```typescript
EXPERT_GROUPS
EXPERT_UI_CONFIG.displayNames
EXPERT_UI_CONFIG.order
```

После этого обновите `docs/architecture/current-expert-roster.md`.

### 2. Уберите данные из локальной SQLite

Перед удалением сделайте backup `backend/data/experts.db`. Затем в одной транзакции очистите связанные строки:

- `expert_metadata`
- `posts`
- `comments`
- `links`
- `comment_group_drift`
- `post_embeddings`
- `posts_fts`
- `vec_posts`
- `sync_state`

`vec_posts` требует загруженный `sqlite-vec`. Если локальная версия `sqlite-vec` не удаляет строки из `vec0` direct `DELETE`, используйте проверенную пересборку virtual table или обновите `sqlite-vec`.

### 3. Обновите production DB отдельно

Для Fly production volume сначала создайте backup `/app/data/experts.db`, потом выполните targeted cleanup на `/app/data/experts.db` или загрузите свежую проверенную DB. Обычный deploy `vNNN` не удалит строки из mounted volume.

### 4. Проверка после удаления

```bash
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM expert_metadata WHERE expert_id='<expert_id>';"
sqlite3 backend/data/experts.db "PRAGMA foreign_key_check;"

curl -sS https://experts-panel.fly.dev/api/v1/experts
fly releases -a experts-panel
fly status -a experts-panel
```

Для frontend sanity check скачайте production bundle и проверьте, что удалённого `expert_id`/display name там нет.

---

## 🛠️ Ручное управление (Troubleshooting)

### Только регистрация эксперта
```bash
python3 backend/tools/add_expert.py expert_id "Name" username path/to.json
```

### Только выкачка комментариев
```bash
TELEGRAM_CHANNEL=username python3 backend/sync_channel.py --expert-id expert_id --depth 2000
```

### Проверка pending групп
```bash
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM comment_group_drift WHERE analyzed_by = 'pending';"
```
