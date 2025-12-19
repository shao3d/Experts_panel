# 🚀 Добавление нового эксперта (Полный алгоритм)

**Версия:** 5.0 (UI интеграция + Gemini CLI)
**Дата:** 2025-12-19
**Статус:** Актуально

---

## 📋 Краткий алгоритм (TL;DR)

```
1. Экспорт JSON из Telegram Desktop
2. ./scripts/add_new_expert.sh <id> "<name>" <username> <json>
3. Drift Analysis через Gemini CLI (бесплатно!)
4. UI интеграция (2 файла)
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

3. **Gemini CLI** (для бесплатного Drift Analysis):
   ```bash
   npm install -g @google/gemini-cli
   ```

---

## 🚀 Полная инструкция

### Step 1: Подготовьте данные

| Поле | Пример | Правила |
|------|--------|---------|
| `expert_id` | `crypto_guru` | Только `a-z`, `0-9`, `_` |
| `display_name` | `"Crypto Guru"` | В кавычках, для UI |
| `username` | `crypto_insider` | Telegram username без `@` |
| `json_path` | `data/exports/result.json` | Путь к экспорту |

### Step 2: Запустите скрипт регистрации

```bash
./scripts/add_new_expert.sh <expert_id> "<Display Name>" <username> <json_path>
```

**Пример (из корня проекта):**
```bash
./scripts/add_new_expert.sh llm_under_hood "Rinat" llm_under_hood path/to/result.json
```

**Что произойдёт автоматически:**
- ✅ Метаданные в `expert_metadata`
- ✅ Посты из JSON
- ✅ Комментарии из Telegram API
- ✅ `pending` задачи для Drift Analysis

⏱️ **Длительность:** 5-15 минут

### Step 3: Drift Analysis (бесплатно через Gemini CLI)

> Скрипт предложит запустить `update_production_db.sh` — **откажись** (N).
> Вместо этого используй бесплатный Gemini CLI (1000 запросов/день!).
>
> *Альтернатива:* Если у тебя Tier 1 API ключ — можно ответить Y и Drift пройдёт автоматически.

1. Запусти Gemini CLI:
   ```bash
   cd /path/to/Experts_panel
   gemini
   # Если первый раз: выбери "Login with Google" для 1000 RPD лимита
   ```

2. Вставь промпт из `prompts/gemini_cli_drift_prompt.md`

3. Gemini обработает 20 групп за раз. Повторяй пока pending > 0.

4. Проверь статус:
   ```bash
   sqlite3 backend/data/experts.db "SELECT analyzed_by, COUNT(*) FROM comment_group_drift GROUP BY analyzed_by;"
   ```

### Step 4: UI интеграция (ОБЯЗАТЕЛЬНО!)

Добавьте эксперта в **2 файла**:

#### 4.1 `frontend/src/components/ExpertSelectionBar.tsx`

```typescript
// Добавить в DISPLAY_NAME_MAP:
'<expert_id>': '<Display Name>',

// Добавить в нужную группу EXPERT_GROUPS:
// TechExperts или Tech&BizExperts
{ label: 'Tech&BizExperts', expertIds: [..., '<expert_id>'] },
```

#### 4.2 `frontend/src/config/expertConfig.ts`

```typescript
// Добавить в displayNames:
'<expert_id>': '<Display Name>',

// Добавить в order (определяет порядок аккордеонов):
order: [..., '<expert_id>']
```

### Step 5: Деплой

```bash
# 1. БД на Fly.io (Drift уже готов, пропустит анализ)
./scripts/update_production_db.sh

# 2. Код на GitHub → автодеплой frontend
git add .
git commit -m "feat: add new expert <expert_id>"
git push
```

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

### Проверка эксперта в БД
```bash
sqlite3 backend/data/experts.db "SELECT * FROM expert_metadata;"
```

---

## ❓ FAQ

**Q: Почему не автоматизировать UI-интеграцию в скрипте?**
A: Слишком хрупко (sed для TypeScript). Ручная правка 2 файлов занимает 1 минуту.

**Q: Сколько времени на Drift Analysis?**
A: С Gemini CLI (1000 RPD): ~10-15 минут на 200 групп.
   Через API Free Tier (20 RPD): ~10 дней 😱

**Q: Как определить группу эксперта (Tech vs Biz)?**
A: Субъективно. Tech = чисто технический контент. Biz = бизнес/продукты.

