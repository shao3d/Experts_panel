# ⚠️ DEPRECATED ⚠️

**NOTE:** This playbook describes the legacy manual process for adding experts.
The system has evolved to use a centralized `expert_metadata` table (Migration 009) and automated sync/deployment scripts.

**Current Workflow:**
1.  **Add Expert:** Use `backend/tools/add_expert.py` (if available) or manually insert into `expert_metadata` table.
2.  **Sync & Drift:** Use `scripts/update_production_db.sh` which handles sync, drift analysis, and deployment automatically.
3.  **Frontend:** Experts are loaded dynamically from the API (`/api/v1/experts`), no need to edit `App.tsx`.

---

# Добавление нового эксперта - Интерактивный Playbook с Claude Code

**Версия:** 3.0 (с полным учётом всех особенностей системы)
**Дата:** 2025-10-14
**Тип процесса:** Интерактивный с Claude Code

---

## 🔴 КРИТИЧЕСКИ ВАЖНО ПОНЯТЬ ПЕРЕД НАЧАЛОМ

### Проблема channel_id vs telegram_message_id

**ГЛАВНАЯ ОПАСНОСТЬ:** Разные Telegram каналы имеют ПЕРЕСЕКАЮЩИЕСЯ диапазоны telegram_message_id!

**Реальный пример из системы:**
```
refat (channel_id: 2273349814):     посты #5, #6, #7, #8, #9...
ai_architect (channel_id: 2293112404): посты #2, #3, #4, #5, #6...
                                                         ↑
                                              КОНФЛИКТ: оба имеют пост #5!
```

**Что происходит БЕЗ фильтра по channel_id:**
1. Загружаем комментарии для ai_architect пост #5
2. SQL запрос: `SELECT * FROM posts WHERE telegram_message_id = 5`
3. Находит ПЕРВЫЙ пост с ID=5 (это refat!)
4. Комментарии ai_architect сохраняются к посту refat
5. **ОШИБКА МОЛЧАЛИВАЯ** - никаких warnings, всё выглядит нормально!

**ПРАВИЛО:** Любой запрос с telegram_message_id ОБЯЗАН включать channel_id фильтр!

---

## 📋 Описание процесса

Это пошаговое руководство для совместной работы с Claude Code по добавлению нового эксперта в систему. Claude Code будет:
- Создавать todo список для отслеживания прогресса
- Выполнять команды и проверки
- Запрашивать у вас необходимые данные
- Проверять результаты каждого шага
- Выявлять молчаливые ошибки через специальные проверки

**Время выполнения:** 2-4 часа (включая drift analysis)
**Требуется от пользователя:** JSON файл экспорта, Telegram API credentials, подтверждения на критических шагах

---

## 🎯 Что будет делать Claude Code

1. Создаст todo список со всеми шагами
2. Будет последовательно выполнять каждый шаг
3. Запросит у вас данные когда необходимо
4. Проверит корректность после каждого шага
5. **Выполнит проверки на молчаливые ошибки** (cross-expert pollution, orphaned records)
6. Откатит изменения если что-то пойдёт не так

---

## 📝 Данные, которые Claude Code запросит у вас

### На старте процесса:
1. **Путь к JSON файлу** экспорта канала (например: `data/exports/channel_export.json`)
2. **expert_id** - короткий идентификатор (например: `crypto_guru`)
3. **expert_name** - отображаемое имя (например: "Crypto Guru 🚀")
4. **channel_username** - username канала БЕЗ @ (например: `crypto_talks`)

### Во время импорта комментариев (Шаг 4):
1. **TELEGRAM_API_ID** - из https://my.telegram.org
2. **TELEGRAM_API_HASH** - из https://my.telegram.org
3. **Номер телефона** - для авторизации в Telegram
4. **Код из SMS** - при первом подключении

### На критических шагах:
- Подтверждение перед импортом
- Подтверждение перед коммитом
- Решения при возникновении конфликтов

---

## 🚀 ПОШАГОВЫЙ ПРОЦЕСС

### ✅ ШАГ 0: Инициализация и проверка prerequisites

**Claude Code сделает:**
```bash
# Проверить что backend и frontend остановлены
lsof -ti:8000 && echo "❌ Backend работает, останови его!" || echo "✅ Backend остановлен"
lsof -ti:5173 && echo "❌ Frontend работает, останови его!" || echo "✅ Frontend остановлен"

# Проверить ВСЕ критические миграции (не только 008!)
echo "Проверка миграций..."

# Migration 007: Composite unique на posts
sqlite3 data/experts.db "
SELECT COUNT(*) as has_migration_007
FROM sqlite_master
WHERE type='index'
    AND sql LIKE '%telegram_message_id%channel_id%';"

# Migration 008: Composite unique на comments
sqlite3 data/experts.db "
SELECT COUNT(*) as has_migration_008
FROM sqlite_master
WHERE type='index'
    AND name='idx_telegram_comment_post_unique';"

# Проверить foreign keys включены
sqlite3 data/experts.db "PRAGMA foreign_keys;"
# Должно вернуть: 1

# Проверить load_dotenv() в main.py
grep -q "load_dotenv()" backend/src/api/main.py && echo "✅ load_dotenv найден" || echo "❌ КРИТИЧНО: Добавь load_dotenv() в main.py!"

# Показать текущих экспертов и их channel_id
echo -e "\n📊 Текущие эксперты в системе:"
sqlite3 data/experts.db "
SELECT
    expert_id,
    channel_id,
    COUNT(*) as posts,
    MIN(telegram_message_id) as first_msg,
    MAX(telegram_message_id) as last_msg
FROM posts
GROUP BY expert_id, channel_id
ORDER BY expert_id;"
```

**Если миграции не применены:**
```bash
# Применить миграцию 007 если нужно
[ -f backend/migrations/007_fix_unique_telegram_message_id.sql ] && \
    sqlite3 data/experts.db < backend/migrations/007_fix_unique_telegram_message_id.sql

# Применить миграцию 008 (критично!)
sqlite3 data/experts.db < backend/migrations/008_fix_comment_unique_constraint.sql
```

**❓ Claude Code спросит:** "Все проверки пройдены. Продолжаем?"

---

### ✅ ШАГ 1: Backup базы данных

**⚠️ КРИТИЧНО! Обязательный шаг перед любыми изменениями!**

**Claude Code сделает:**
```bash
# Создать папку для backup если её нет
mkdir -p data/backups

# Создать backup с датой и временем
BACKUP_NAME="experts_backup_$(date +%Y%m%d_%H%M%S).db"
sqlite3 data/experts.db ".backup data/backups/$BACKUP_NAME"

# Проверить backup
ls -lh "data/backups/$BACKUP_NAME"
sqlite3 "data/backups/$BACKUP_NAME" "SELECT COUNT(*) FROM posts;" && echo "✅ Backup создан и проверен"

# Сохранить имя backup для возможного отката
echo "$BACKUP_NAME" > /tmp/last_backup.txt

# Дополнительно: сохранить drift analysis если есть
sqlite3 data/experts.db ".dump comment_group_drift" > "data/backups/drift_${BACKUP_NAME%.db}.sql"
echo "✅ Drift analysis сохранён отдельно"
```

**Verification:**
- ✅ Backup файл создан
- ✅ Размер совпадает с оригиналом
- ✅ Backup открывается без ошибок
- ✅ Drift backup создан (если были drift записи)

---

### ✅ ШАГ 2: Импорт постов из JSON

**❓ Claude Code запросит у вас:**
- Путь к JSON файлу (например: `data/exports/crypto_guru_history.json`)
- expert_id для нового эксперта
- expert_name для отображения
- channel_username для Telegram ссылок

**Claude Code сделает:**
```bash
cd backend

# Проверить что файл существует
[ -f "../[JSON_FILE]" ] && echo "✅ Файл найден" || echo "❌ Файл не найден!"

# Показать информацию о файле
echo "Анализ JSON файла:"
head -100 "../[JSON_FILE]" | grep -E '"id"|"name"|"type"' | head -5

# Импорт с указанием expert_id
uv run python -m src.data.json_parser \
  ../[JSON_FILE] \
  --expert-id [EXPERT_ID]

# Сохранить channel_id для последующих шагов (КРИТИЧНО!)
CHANNEL_ID=$(sqlite3 ../data/experts.db "SELECT DISTINCT channel_id FROM posts WHERE expert_id='[EXPERT_ID]' LIMIT 1;")
echo "Channel ID: $CHANNEL_ID"
echo "$CHANNEL_ID" > /tmp/new_expert_channel_id.txt

# КРИТИЧНО: Проверить уникальность channel_id
sqlite3 ../data/experts.db "
SELECT expert_id, channel_id, COUNT(*) as conflicts
FROM posts
WHERE channel_id = '$CHANNEL_ID'
GROUP BY expert_id, channel_id;"
```

**⚠️ Важно:** При импорте автоматически происходит:
- Конвертация Telegram entities в markdown формат через `entities_to_markdown_from_json()`
- Создание Link записей для REPLY/FORWARD/MENTION связей
- Сохранение channel_id из JSON файла

**Verification (расширенная):**
```bash
# Количество импортированных постов
sqlite3 data/experts.db "SELECT COUNT(*) as posts FROM posts WHERE expert_id='[EXPERT_ID]';"

# Проверить channel_id уникальность (КРИТИЧНО!)
sqlite3 data/experts.db "
SELECT
    channel_id,
    COUNT(DISTINCT expert_id) as expert_count,
    GROUP_CONCAT(DISTINCT expert_id) as experts
FROM posts
WHERE channel_id = '$CHANNEL_ID'
GROUP BY channel_id
HAVING expert_count > 1;"
# ДОЛЖНО БЫТЬ ПУСТО! Если нет - channel_id конфликт!

# Проверить диапазон telegram_message_id
sqlite3 data/experts.db "
SELECT
    MIN(telegram_message_id) as min_id,
    MAX(telegram_message_id) as max_id,
    COUNT(DISTINCT telegram_message_id) as unique_ids
FROM posts
WHERE expert_id='[EXPERT_ID]';"

# Проверить отсутствие дубликатов внутри эксперта
sqlite3 data/experts.db "
SELECT telegram_message_id, COUNT(*) as cnt
FROM posts
WHERE expert_id='[EXPERT_ID]'
GROUP BY telegram_message_id, channel_id
HAVING cnt > 1;"
# Должно быть пусто!

# Проверить примеры постов с markdown
sqlite3 data/experts.db "
SELECT
    telegram_message_id,
    SUBSTR(message_text, 1, 100) as preview,
    CASE
        WHEN message_text LIKE '%[%](%)%' THEN '✅ Has markdown links'
        WHEN message_text LIKE '%**%**%' THEN '✅ Has bold'
        WHEN message_text LIKE '%`%`%' THEN '✅ Has code'
        ELSE '⚪ Plain text'
    END as markdown_status
FROM posts
WHERE expert_id='[EXPERT_ID]'
ORDER BY created_at DESC
LIMIT 5;"
```

**⚠️ Claude Code запомнит channel_id для следующих шагов!**

---

### ✅ ШАГ 3: Обновить конфигурацию моделей

**Claude Code автоматически обновит** `backend/src/api/models.py`:

1. В функцию `get_expert_name()` (около строки 480) добавит:
```python
'[EXPERT_ID]': '[EXPERT_NAME]'
```

2. В функцию `get_channel_username()` (около строки 489) добавит:
```python
'[EXPERT_ID]': '[CHANNEL_USERNAME]'
```

**Verification:**
```bash
cd backend

# Проверить синтаксис Python
python -c "
from src.api.models import get_expert_name, get_channel_username
print(f'Expert: {get_expert_name(\"[EXPERT_ID]\")}')
print(f'Channel: @{get_channel_username(\"[EXPERT_ID]\")}')
" && echo "✅ Helper функции работают"

# Проверить что функции возвращают правильные значения
uv run python -c "
from src.api.models import get_expert_name, get_channel_username
assert get_expert_name('[EXPERT_ID]') == '[EXPERT_NAME]', 'Wrong expert name!'
assert get_channel_username('[EXPERT_ID]') == '[CHANNEL_USERNAME]', 'Wrong channel username!'
print('✅ Все значения корректны')
"
```

---

### ✅ ШАГ 4: Импорт комментариев из Telegram API (опционально)

**❓ Claude Code спросит:** "Импортировать комментарии сейчас? (можно сделать позже)"

Если ДА:

**Claude Code подготовит скрипт:**

```bash
cd backend

# 1. Загрузить channel_id из ШАГ 2
CHANNEL_ID=$(cat /tmp/new_expert_channel_id.txt)
echo "Channel ID для импорта: $CHANNEL_ID"

# 2. Обновить channel_id в скрипте (строки 186, 209)
sed -i.bak "186s/'[0-9]*'/'$CHANNEL_ID'/; 209s/'[0-9]*'/'$CHANNEL_ID'/" src/data/telegram_comments_fetcher.py

# 3. Обновить комментарии в скрипте для ясности
sed -i "184s/neuraldeep/[EXPERT_ID]/; 186s/Neuraldeep/[EXPERT_NAME]/; 209s/Neuraldeep/[EXPERT_NAME]/" src/data/telegram_comments_fetcher.py

# 4. Обновить .env (TELEGRAM_CHANNEL)
sed -i "s/TELEGRAM_CHANNEL=.*/TELEGRAM_CHANNEL=[CHANNEL_USERNAME]/" .env

# 5. Проверить изменения
echo "Проверка channel_id в скрипте:"
grep "channel_id == '$CHANNEL_ID'" src/data/telegram_comments_fetcher.py | wc -l
# Должно показать: 2 (строки 186 и 209)

echo "Проверка .env:"
grep "TELEGRAM_CHANNEL" .env
# Должно показать: TELEGRAM_CHANNEL=[CHANNEL_USERNAME]

echo "✅ Скрипт подготовлен для [EXPERT_ID]"
```

**❗ВАЖНО: Claude Code попросит пользователя запустить В ОТДЕЛЬНОМ ТЕРМИНАЛЕ:**

```bash
cd /Users/.../Experts_panel/backend
uv run python -m src.data.telegram_comments_fetcher
```

**Что происходит:**
- Скрипт читает credentials из .env (TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL)
- Показывает найденные credentials и просит подтверждение (y/n)
- Подключается к Telegram, при первом запуске запросит код из SMS
- Импортирует комментарии для всех постов [EXPERT_ID] (~10-15 минут для 300-400 постов)
- Сохраняет комментарии батчами по 50 штук

**❓ Claude Code дождётся:** "Импорт завершён?" (пользователь сообщит)

**После завершения импорта Claude Code откатит изменения:**
```bash
cd backend
git checkout src/data/telegram_comments_fetcher.py .env
rm -f src/data/telegram_comments_fetcher.py.bak .env.bak
echo "✅ Скрипт и .env откачены к исходному состоянию"
```

**Verification (критические проверки):**
```bash
# Проверить импортированные комментарии
sqlite3 data/experts.db "
SELECT
    COUNT(DISTINCT c.comment_id) as total_comments,
    COUNT(DISTINCT c.post_id) as posts_with_comments
FROM comments c
JOIN posts p ON c.post_id = p.post_id
WHERE p.expert_id='[EXPERT_ID]';"

# КРИТИЧНО: Cross-expert pollution проверка #1
# Проверить что НЕТ комментариев, привязанных к неправильному эксперту
sqlite3 data/experts.db "
WITH recent_comments AS (
    SELECT
        c.comment_id,
        c.comment_text,
        c.author_name,
        p.expert_id as post_expert,
        p.telegram_message_id
    FROM comments c
    JOIN posts p ON c.post_id = p.post_id
    WHERE c.created_at > '$IMPORT_START'
)
SELECT
    COUNT(*) as wrong_assignments,
    GROUP_CONCAT(DISTINCT post_expert) as affected_experts
FROM recent_comments
WHERE post_expert != '[EXPERT_ID]';"
# MUST return: 0|NULL

# КРИТИЧНО: Cross-expert pollution проверка #2
# Детальная проверка если были найдены проблемы
sqlite3 data/experts.db "
SELECT
    c.telegram_comment_id,
    c.author_name,
    p.expert_id as assigned_to_expert,
    p.telegram_message_id as assigned_to_post,
    SUBSTR(c.comment_text, 1, 50) as comment_preview
FROM comments c
JOIN posts p ON c.post_id = p.post_id
WHERE c.created_at > '$IMPORT_START'
    AND p.expert_id != '[EXPERT_ID]'
LIMIT 10;"
# Должно быть ПУСТО!

# Проверить примеры комментариев с markdown
sqlite3 data/experts.db "
SELECT
    c.telegram_comment_id,
    c.author_name,
    SUBSTR(c.comment_text, 1, 60) as preview,
    CASE
        WHEN c.comment_text LIKE '%[%](%)%' THEN '✅ Has links'
        WHEN c.comment_text LIKE '%@%' THEN '✅ Has mentions'
        ELSE '⚪ Plain text'
    END as markdown
FROM comments c
JOIN posts p ON c.post_id = p.post_id
WHERE p.expert_id='[EXPERT_ID]'
ORDER BY c.created_at DESC
LIMIT 5;"
```

---

### ✅ ШАГ 5: Создать записи для drift analysis

**Claude Code сделает:**
```bash
# Подсчитать сколько постов с комментариями
POSTS_WITH_COMMENTS=$(sqlite3 data/experts.db "
SELECT COUNT(DISTINCT c.post_id)
FROM comments c
JOIN posts p ON c.post_id = p.post_id
WHERE p.expert_id = '[EXPERT_ID]';")

echo "Найдено $POSTS_WITH_COMMENTS постов с комментариями"

# Создать записи drift analysis
sqlite3 data/experts.db "
INSERT INTO comment_group_drift (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
SELECT
    p.post_id,
    0 as has_drift,
    NULL as drift_topics,
    datetime('now') as analyzed_at,
    'pending' as analyzed_by,
    p.expert_id
FROM posts p
WHERE p.expert_id = '[EXPERT_ID]'
  AND p.post_id IN (
    SELECT DISTINCT c.post_id FROM comments c WHERE c.post_id = p.post_id
  )
  AND p.post_id NOT IN (
    SELECT post_id FROM comment_group_drift WHERE post_id = p.post_id
  );"

echo "✅ Drift записи созданы для $POSTS_WITH_COMMENTS групп"
```

**Verification:**
```bash
# Проверить созданные записи
sqlite3 data/experts.db "
SELECT
    COUNT(*) as total_drift_groups,
    SUM(CASE WHEN analyzed_by='pending' THEN 1 ELSE 0 END) as pending_analysis,
    p.expert_id
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
WHERE p.expert_id='[EXPERT_ID]'
GROUP BY p.expert_id;"

# Проверить что expert_id правильный во всех записях
sqlite3 data/experts.db "
SELECT COUNT(*) as wrong_expert_drift
FROM comment_group_drift cgd
WHERE cgd.expert_id != '[EXPERT_ID]'
  AND cgd.post_id IN (
    SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]'
  );"
# Должно быть: 0
```

---

### ✅ ШАГ 6: Запустить drift analysis (опционально)

**❓ Claude Code спросит:** "Запустить drift analysis сейчас? (займёт 20-60 минут)"

Если ДА:

**Claude Code проверит:**
```bash
# Убедиться что агент использует auto-detection (НЕ хардкод!)
grep "SELECT expert_id FROM posts WHERE post_id" .claude/agents/drift-extraction.md && \
    echo "✅ Drift agent настроен правильно (auto-detection)" || \
    echo "❌ ВНИМАНИЕ: Drift agent может иметь хардкод!"

# Показать сколько групп нужно проанализировать
sqlite3 data/experts.db "
SELECT
    COUNT(*) as groups_to_analyze
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
WHERE p.expert_id='[EXPERT_ID]'
    AND cgd.analyzed_by='pending';"
```

**Варианты:**

**A. Для <50 групп - автоматический скрипт:**
```bash
cd backend
python analyze_drift.py --batch-size 10 --expert-id [EXPERT_ID]
```

**B. Для >50 групп - параллельная обработка:**
Claude Code предложит запустить drift-extraction агентов в параллельных терминалах.

**Progress tracking:**
```bash
# Claude Code будет проверять прогресс каждые 5 минут
watch -n 300 'sqlite3 data/experts.db "
SELECT
    p.expert_id,
    COUNT(*) as total,
    SUM(CASE WHEN cgd.analyzed_by != \"pending\" THEN 1 ELSE 0 END) as done,
    SUM(CASE WHEN cgd.has_drift = 1 THEN 1 ELSE 0 END) as with_drift,
    ROUND(100.0 * SUM(CASE WHEN cgd.analyzed_by != \"pending\" THEN 1 ELSE 0 END) / COUNT(*), 1) || \"%\" as progress
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
WHERE p.expert_id=\"[EXPERT_ID]\"
GROUP BY p.expert_id;"'
```

---

### ✅ ШАГ 7: Финальная проверка данных (расширенная)

**Claude Code выполнит ПОЛНУЮ проверку целостности:**

```bash
echo "=== ФИНАЛЬНАЯ ПРОВЕРКА ДАННЫХ ==="

# 1. Общая статистика
sqlite3 data/experts.db "
SELECT
    '[EXPERT_ID]' as expert,
    (SELECT COUNT(*) FROM posts WHERE expert_id='[EXPERT_ID]') as posts,
    (SELECT COUNT(*) FROM comments c JOIN posts p ON c.post_id=p.post_id WHERE p.expert_id='[EXPERT_ID]') as comments,
    (SELECT COUNT(*) FROM links WHERE source_post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]')) as links,
    (SELECT COUNT(*) FROM comment_group_drift cgd JOIN posts p ON cgd.post_id=p.post_id WHERE p.expert_id='[EXPERT_ID]') as drift_groups,
    (SELECT COUNT(*) FROM comment_group_drift cgd JOIN posts p ON cgd.post_id=p.post_id WHERE p.expert_id='[EXPERT_ID]' AND cgd.has_drift=1) as with_drift;"

# 2. Проверить уникальность channel_id (КРИТИЧНО!)
echo -e "\n📊 Channel ID уникальность:"
sqlite3 data/experts.db "
SELECT
    expert_id,
    channel_id,
    COUNT(*) as posts
FROM posts
GROUP BY expert_id, channel_id
ORDER BY expert_id;"
# Каждый expert_id должен иметь УНИКАЛЬНЫЙ channel_id!

# 3. Проверка на orphaned записи (все должны быть 0!)
echo -e "\n🔍 Проверка orphaned записей:"
sqlite3 data/experts.db "
-- Orphaned comments
SELECT 'Orphaned comments' as check_type, COUNT(*) as count
FROM comments c
LEFT JOIN posts p ON c.post_id = p.post_id
WHERE p.post_id IS NULL

UNION ALL

-- Orphaned source links
SELECT 'Orphaned source links', COUNT(*)
FROM links l
LEFT JOIN posts p ON l.source_post_id = p.post_id
WHERE p.post_id IS NULL

UNION ALL

-- Orphaned target links
SELECT 'Orphaned target links', COUNT(*)
FROM links l
LEFT JOIN posts p ON l.target_post_id = p.post_id
WHERE p.post_id IS NULL

UNION ALL

-- Orphaned drift records
SELECT 'Orphaned drift records', COUNT(*)
FROM comment_group_drift cgd
LEFT JOIN posts p ON cgd.post_id = p.post_id
WHERE p.post_id IS NULL;"

# 4. Cross-expert pollution финальная проверка
echo -e "\n⚠️ Cross-expert pollution проверка:"
sqlite3 data/experts.db "
-- Comments assigned to wrong expert
SELECT
    'Comments to wrong expert' as issue,
    COUNT(*) as count
FROM comments c
JOIN posts p ON c.post_id = p.post_id
WHERE p.expert_id != '[EXPERT_ID]'
    AND c.post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]')

UNION ALL

-- Drift records with wrong expert
SELECT
    'Drift with wrong expert',
    COUNT(*)
FROM comment_group_drift cgd
WHERE cgd.expert_id != '[EXPERT_ID]'
    AND cgd.post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]');"
# ВСЕ должны показать 0!

# 5. Проверка foreign keys работают
echo -e "\n🔗 Foreign keys проверка:"
sqlite3 data/experts.db "PRAGMA foreign_key_check;"
# Должно быть пусто (нет нарушений)
```

**Checklist:**
- ✅ Все данные на месте
- ✅ channel_id уникальный для эксперта
- ✅ Нет orphaned записей (все показывают 0)
- ✅ Нет cross-expert pollution (все показывают 0)
- ✅ Foreign keys целостны
- ✅ Drift analysis завершён (если запускали)

---

### ✅ ШАГ 8: Тестовый запрос к API

**Claude Code запустит backend и проверит:**

```bash
# Запустить backend в фоне
cd backend && uv run uvicorn src.api.main:app --reload --port 8000 &
BACKEND_PID=$!
sleep 5

# Health check
curl -s http://localhost:8000/health | jq '{status, database, openai_configured}'
# openai_configured должен быть true!

# Тестовый запрос ТОЛЬКО к новому эксперту
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Расскажи о себе и своём канале",
    "expert_filter": ["[EXPERT_ID]"],
    "stream_progress": false
  }' -o /tmp/test_response.json

# Проверить ответ
echo -e "\n📊 Результат тестового запроса:"
cat /tmp/test_response.json | jq -r '
.expert_responses[] |
"Expert: \(.expert_id)
Channel: @\(.channel_username)
Posts analyzed: \(.posts_analyzed)
Sources found: \(.main_sources | length)
Confidence: \(.confidence)
Processing time: \(.processing_time_ms)ms"'

# Проверить что posts endpoint работает с expert_id
FIRST_POST=$(sqlite3 data/experts.db "SELECT telegram_message_id FROM posts WHERE expert_id='[EXPERT_ID]' LIMIT 1;")
curl -s "http://localhost:8000/api/v1/posts/$FIRST_POST?expert_id=[EXPERT_ID]" | \
    jq '{telegram_message_id, channel_name, author_name}'

# Остановить backend
kill $BACKEND_PID
echo "✅ Backend остановлен"
```

**Verification:**
- ✅ API отвечает
- ✅ Health check показывает openai_configured: true
- ✅ Новый эксперт обрабатывает запросы
- ✅ posts_analyzed > 0
- ✅ Post endpoint возвращает правильный пост с учётом expert_id

---

### ✅ ШАГ 9: Обновить Frontend UI

**Claude Code обновит** `frontend/src/App.tsx`:

1. Добавит в начальное состояние expandedExperts (строка ~18):
```typescript
new Set(['refat', 'ai_architect', '[EXPERT_ID]'])
```

2. (Опционально) Изменит порядок сортировки если нужно (строки ~128-133)

**Важно:** Frontend передаёт expert_id при загрузке постов для избежания конфликтов telegram_message_id!

**Verification:**
```bash
cd frontend

# Проверить синтаксис TypeScript
npm run type-check && echo "✅ TypeScript проверка пройдена"

# Проверить что новый эксперт добавлен
grep "[EXPERT_ID]" src/App.tsx && echo "✅ Эксперт добавлен в UI"
```

---

### ✅ ШАГ 10: Полный E2E тест

**❓ Claude Code спросит:** "Запустить полный тест системы?"

**Claude Code запустит:**
```bash
# Terminal 1: Backend
cd backend && uv run uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: E2E тесты
sleep 10

# 1. Тест запроса ко ВСЕМ экспертам
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что ты думаешь об AI?", "stream_progress": false}' \
  -o /tmp/all_experts.json

# 2. Проверить что все эксперты ответили
echo "Эксперты в ответе:"
cat /tmp/all_experts.json | jq -r '.expert_responses[] | .expert_id'
# Должен включать [EXPERT_ID]!

# 3. Проверить изоляцию экспертов
cat /tmp/all_experts.json | jq -r '
.expert_responses[] |
"\(.expert_id): posts=\(.posts_analyzed), sources=\(.main_sources | length)"'
```

**❓ Claude Code попросит:** "Откройте http://localhost:5173 и проверьте:
1. Новый эксперт появляется в аккордеоне
2. При клике разворачивается
3. Ссылки на посты ведут в правильный канал (@[CHANNEL_USERNAME])
4. Нет пересечений с другими экспертами"

---

### ✅ ШАГ 11: Коммит изменений

**❓ Claude Code спросит:** "Все тесты пройдены. Закоммитить изменения?"

**Claude Code сделает:**
```bash
# Показать изменённые файлы
git status

# Добавить в stage
git add backend/src/api/models.py
git add frontend/src/App.tsx
git add docs/add-new-expert-playbook.md

# Создать коммит с деталями
git commit -m "feat: Add new expert '[EXPERT_NAME]' to multi-expert system

- Added expert_id '[EXPERT_ID]' with channel '@[CHANNEL_USERNAME]'
- Channel ID: [CHANNEL_ID] (verified unique)
- Imported [N] posts and [M] comments
- Created [X] drift analysis groups
- Updated models.py helper functions
- Updated frontend UI accordion
- All integrity checks passed (no cross-expert pollution)

Verification results:
- No orphaned records
- No channel_id conflicts
- Foreign keys intact
- Cross-expert isolation verified

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### ✅ ШАГ 12: Обновить документацию

**Claude Code обновит CLAUDE.md:**
- Добавит нового эксперта в секцию EXPERT_CHANNELS
- Обновит статистику
- Добавит channel_id mapping

**Финальная проверка:**
```bash
# Проверить что эксперт упомянут в документации
grep -q "[EXPERT_ID]" CLAUDE.md && echo "✅ CLAUDE.md обновлён"

# Финальная статистика системы
sqlite3 data/experts.db "
SELECT
    COUNT(DISTINCT expert_id) as total_experts,
    COUNT(*) as total_posts,
    (SELECT COUNT(*) FROM comments) as total_comments,
    (SELECT COUNT(*) FROM comment_group_drift WHERE has_drift=1) as drift_groups
FROM posts;"
```

---

## 🔄 Откат при ошибках (исправленный порядок)

**Если что-то пошло не так, Claude Code может откатить изменения:**

### Вариант 1: Полный откат к backup
```bash
BACKUP_NAME=$(cat /tmp/last_backup.txt)
cp "data/backups/$BACKUP_NAME" data/experts.db
echo "✅ База данных восстановлена из backup: $BACKUP_NAME"
```

### Вариант 2: Удалить только нового эксперта (правильный порядок!)
```bash
sqlite3 data/experts.db <<SQL
BEGIN TRANSACTION;

-- ВАЖНО: Строгий порядок удаления из-за foreign keys!

-- 1. comment_group_drift (NO CASCADE - удалить первым!)
DELETE FROM comment_group_drift
WHERE post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]');

-- 2. comments (CASCADE от posts, но лучше явно)
DELETE FROM comments
WHERE post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]');

-- 3. links (оба направления)
DELETE FROM links
WHERE source_post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]')
   OR target_post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]');

-- 4. posts (теперь безопасно удалить)
DELETE FROM posts WHERE expert_id='[EXPERT_ID]';

-- 5. Проверить что всё удалено
SELECT 'Posts remaining:' as check, COUNT(*) FROM posts WHERE expert_id='[EXPERT_ID]'
UNION ALL
SELECT 'Comments remaining:', COUNT(*) FROM comments WHERE post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]')
UNION ALL
SELECT 'Drift remaining:', COUNT(*) FROM comment_group_drift WHERE post_id IN (SELECT post_id FROM posts WHERE expert_id='[EXPERT_ID]');

-- 6. Освободить место
VACUUM;

COMMIT;
SQL

echo "✅ Эксперт [EXPERT_ID] полностью удалён"
```

### Вариант 3: Git откат
```bash
git checkout -- backend/src/api/models.py frontend/src/App.tsx
git status
```

---

## 📊 Финальный отчёт

После завершения Claude Code предоставит итоговый отчёт:

```
============================================================
✅ НОВЫЙ ЭКСПЕРТ УСПЕШНО ДОБАВЛЕН
============================================================
Expert ID: [EXPERT_ID]
Expert Name: [EXPERT_NAME]
Channel: @[CHANNEL_USERNAME]
Channel ID: [CHANNEL_ID] (verified unique)

Импортировано:
- Постов: [N]
- Комментариев: [M]
- Links: [L]
- Drift групп: [X] (из них [Y] с drift)

Проверки целостности:
- ✅ channel_id уникальный
- ✅ Нет orphaned записей
- ✅ Нет cross-expert pollution
- ✅ Foreign keys целостны

Обновлены файлы:
- backend/src/api/models.py
- frontend/src/App.tsx
- CLAUDE.md

Тесты:
- ✅ API работает
- ✅ Frontend отображает
- ✅ Запросы обрабатываются
- ✅ Изоляция экспертов подтверждена

Время выполнения: [TIME]
============================================================
```

---

## ❓ Частые проблемы и решения

### "MsgIdInvalidError" при импорте комментариев
**Причина:** Неправильный channel_id в фильтре
**Решение:** Временный скрипт автоматически использует правильный channel_id
**Проверка:** `grep "channel_id == '$CHANNEL_ID'" src/data/telegram_comments_fetcher_temp.py`

### Комментарии сохраняются к неправильному эксперту (МОЛЧАЛИВАЯ ОШИБКА!)
**Причина:** Отсутствует фильтр по channel_id при поиске parent post
**Симптом:** Cross-expert pollution проверка показывает > 0
**Решение:** Использовать временный скрипт с правильными фильтрами
**Проверка:** SQL запросы из Шага 4 Verification

### API не загружает ключи
**Причина:** Нет load_dotenv() в main.py
**Решение:** Claude Code проверяет это на Шаге 0
**Проверка:** `curl http://localhost:8000/health | jq '.openai_configured'`

### Дубликаты при импорте
**Причина:** Повторный импорт того же файла
**Решение:** UNIQUE constraints (telegram_message_id, channel_id) предотвращают
**Проверка:** SQL из Шага 2 проверяет дубликаты

### Frontend показывает посты другого эксперта
**Причина:** Не передан expert_id в API запросе к /posts endpoint
**Решение:** Frontend должен передавать expert_id параметр
**Проверка:** Network tab в браузере, запросы должны включать ?expert_id=

---

## 🎯 Критические моменты - НЕ ПРОПУСТИТЬ!

1. **channel_id MUST BE UNIQUE** - проверять после импорта!
2. **Миграция 008 ОБЯЗАТЕЛЬНА** - composite key для comments
3. **load_dotenv() ОБЯЗАТЕЛЕН** в main.py до других импортов
4. **Cross-expert pollution проверки** - после КАЖДОГО импорта
5. **Временный скрипт для комментариев** - НЕ использовать оригинальный!
6. **Порядок удаления при откате** - drift → comments → links → posts
7. **expert_id в Frontend запросах** - иначе конфликты telegram_message_id

---

**Версия 3.0 - Полностью готово к использованию с Claude Code!**