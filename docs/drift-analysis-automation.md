# Drift Analysis Automation Guide

Руководство по автоматизации анализа drift topics через drift-extraction агента.

---

## Вариант 1: Параллельная обработка (5 терминалов)

Быстрый способ - запустить 5 терминалов одновременно.

### Терминал 1 (посты 3-17):
```
Выполни SQL запрос чтобы получить post_id для постов ai_architect с 3-го по 17-й: "SELECT cgd.post_id, p.telegram_message_id FROM comment_group_drift cgd JOIN posts p ON cgd.post_id = p.post_id WHERE p.expert_id = 'ai_architect' ORDER BY cgd.post_id LIMIT 15 OFFSET 2". Создай TodoWrite список по этим post_id. Каждый шаг = запуск drift-extraction агента. После каждого - отмечай completed.
```

### Терминал 2 (посты 18-32):
```
Выполни SQL запрос чтобы получить post_id для постов ai_architect с 18-го по 32-й: "SELECT cgd.post_id, p.telegram_message_id FROM comment_group_drift cgd JOIN posts p ON cgd.post_id = p.post_id WHERE p.expert_id = 'ai_architect' ORDER BY cgd.post_id LIMIT 15 OFFSET 17". Создай TodoWrite список по этим post_id. Каждый шаг = запуск drift-extraction агента. После каждого - отмечай completed.
```

### Терминал 3 (посты 33-47):
```
Выполни SQL запрос чтобы получить post_id для постов ai_architect с 33-го по 47-й: "SELECT cgd.post_id, p.telegram_message_id FROM comment_group_drift cgd JOIN posts p ON cgd.post_id = p.post_id WHERE p.expert_id = 'ai_architect' ORDER BY cgd.post_id LIMIT 15 OFFSET 32". Создай TodoWrite список по этим post_id. Каждый шаг = запуск drift-extraction агента. После каждого - отмечай completed.
```

### Терминал 4 (посты 48-62):
```
Выполни SQL запрос чтобы получить post_id для постов ai_architect с 48-го по 62-й: "SELECT cgd.post_id, p.telegram_message_id FROM comment_group_drift cgd JOIN posts p ON cgd.post_id = p.post_id WHERE p.expert_id = 'ai_architect' ORDER BY cgd.post_id LIMIT 15 OFFSET 47". Создай TodoWrite список по этим post_id. Каждый шаг = запуск drift-extraction агента. После каждого - отмечай completed.
```

### Терминал 5 (посты 63-79):
```
Выполни SQL запрос чтобы получить post_id для постов ai_architect с 63-го по 79-й: "SELECT cgd.post_id, p.telegram_message_id FROM comment_group_drift cgd JOIN posts p ON cgd.post_id = p.post_id WHERE p.expert_id = 'ai_architect' ORDER BY cgd.post_id LIMIT 17 OFFSET 62". Создай TodoWrite список по этим post_id. Каждый шаг = запуск drift-extraction агента. После каждого - отмечай completed.
```

**Преимущества:**
- ⚡ Очень быстро (параллельная обработка)
- ✅ Обрабатывает 77 постов одновременно

**Недостатки:**
- 🔧 Требует ручного запуска 5 терминалов
- 📊 Нужно следить за всеми терминалами

---

## Вариант 2: Самовоспроизводящийся цикл (1 терминал)

Автоматический способ - один терминал обработает все посты последовательно.

### Команда для запуска:

```
Создай самовоспроизводящийся TodoWrite список для drift-анализа постов ai_architect.

Инструкции:
1. Выполни SQL запрос: "SELECT cgd.post_id, p.telegram_message_id FROM comment_group_drift cgd JOIN posts p ON cgd.post_id = p.post_id WHERE p.expert_id = 'ai_architect' AND cgd.analyzed_by = 'pending' ORDER BY cgd.post_id LIMIT 10"

2. Создай todo список на эти посты (максимум 10 шагов):
   - Шаги 1-9: "Analyze drift for post_id=X via drift-extraction agent"
   - Шаг 10: "Check remaining posts and create next batch"

3. Для каждого поста (шаги 1-9):
   - Запусти drift-extraction агента через Task tool
   - Отметь задачу как completed
   - Переходи к следующей

4. На шаге 10:
   - Выполни SQL: "SELECT COUNT(*) FROM comment_group_drift cgd JOIN posts p ON cgd.post_id = p.post_id WHERE p.expert_id = 'ai_architect' AND cgd.analyzed_by = 'pending'"
   - Если count > 0: создай НОВЫЙ список с шагами 1-10 (рекурсия)
   - Если count = 0: завершись с сообщением "✅ All posts processed!"

Начни прямо сейчас.
```

### Как это работает:

1. **Шаги 1-9:** Обрабатывают посты через drift-extraction агента
2. **Шаг 10:** Проверяет остались ли необработанные посты:
   - Если **ДА** → создаёт новый список на следующие 10 постов
   - Если **НЕТ** → останавливается

### Пример SQL запроса для проверки:

```sql
-- Проверить сколько постов осталось обработать
SELECT COUNT(*)
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
WHERE p.expert_id = 'ai_architect'
AND cgd.analyzed_by = 'pending'
```

### Логика остановки:

```
if remaining_count > 0:
    batch_size = min(10, remaining_count)
    create_new_todo_list(batch_size)
else:
    print("✅ All posts processed!")
    stop()
```

**Преимущества:**
- 🤖 Полностью автоматический (запустил и забыл)
- 🔄 Обрабатывает любое количество постов
- 📝 Один терминал для всего

**Недостатки:**
- 🐌 Медленнее (последовательная обработка)
- ⚠️ Если упадёт - нужно перезапускать

---

## Проверка прогресса

### Проверить сколько постов обработано:

```sql
SELECT
    p.expert_id,
    COUNT(*) as total_posts,
    SUM(CASE WHEN cgd.analyzed_by != 'pending' THEN 1 ELSE 0 END) as processed,
    SUM(CASE WHEN cgd.analyzed_by = 'pending' THEN 1 ELSE 0 END) as remaining
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
WHERE p.expert_id = 'ai_architect'
GROUP BY p.expert_id;
```

### Проверить посты с дрифтом:

```sql
SELECT
    COUNT(*) as posts_with_drift
FROM comment_group_drift cgd
JOIN posts p ON cgd.post_id = p.post_id
WHERE p.expert_id = 'ai_architect'
AND cgd.has_drift = 1;
```

---

## Когда использовать каждый вариант

**Используйте Вариант 1 (5 терминалов) когда:**
- ⏰ Нужно быстро обработать известное количество постов
- 💪 Есть ресурсы для параллельной работы
- 👀 Можете следить за несколькими терминалами

**Используйте Вариант 2 (цикл) когда:**
- 🌙 Запускаете на ночь / на долгое время
- 🔢 Не знаете точно сколько постов нужно обработать
- 🧘 Хотите "запустил и забыл"
- 📱 Работаете удалённо и не хотите держать много терминалов

---

## Troubleshooting

### Агент не запускается:
Проверьте что исправлен файл `.claude/agents/drift-extraction.md` - строка с `expert_id` должна быть:
```sql
expert_id = (SELECT expert_id FROM posts WHERE post_id = <ID>)
```
А НЕ:
```sql
expert_id = 'refat'  -- ❌ Хардкод!
```

### Посты не находятся:
Убедитесь что созданы пустые записи в `comment_group_drift`:
```sql
INSERT INTO comment_group_drift (post_id, has_drift, drift_topics, analyzed_at, analyzed_by, expert_id)
SELECT
    p.post_id, 0, NULL, datetime('now'), 'pending', p.expert_id
FROM posts p
WHERE p.post_id IN (
    SELECT DISTINCT c.post_id FROM comments c
    JOIN posts p2 ON c.post_id = p2.post_id
    WHERE p2.expert_id = 'ai_architect'
)
AND p.post_id NOT IN (SELECT post_id FROM comment_group_drift);
```

### SQL ошибки:
Проверьте правильность путей:
- База данных: `/Users/andreysazonov/Documents/Projects/Experts_panel/data/experts.db`
- Промпт: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/prompts/extract_drift_topics.txt`
