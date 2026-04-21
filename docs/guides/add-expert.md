# 🚀 Добавление нового эксперта (Полный алгоритм)

**Версия:** 7.0 (Single Config + Manual Drift)
**Дата:** 2026-02-17
**Статус:** Актуально

---

## 📋 Краткий алгоритм (TL;DR)

```
1. Экспорт JSON из Telegram Desktop
2. ./scripts/add_new_expert.sh <id> "<name>" <username> <json>
3. UI интеграция (1 файл: expertConfig.ts)
4. (Опционально) Ручной запуск Drift Analysis
5. Деплой: ./scripts/update_production_db.sh + git push
```

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
git add .
git commit -m "feat: add new expert <expert_id>"
git push
```

`update_production_db.sh` сам грузит `backend/.env`, запускает `embed_posts.py --continuous` и `run_drift_service.py`, так что и embeddings, и drift идут через Vertex AI.

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
