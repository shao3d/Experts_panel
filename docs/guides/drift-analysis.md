# Анализ Дрифта (headless OpenCode)

Status: Active
Last updated: 2026-10-08

Руководство по анализу «дрейфа тем» в комментариях Telegram-постов.

**Текущий рантайм:** drift выполняется только через headless opencode
(`DRIFT_BACKEND=opencode`) на **MiMo-V2.6-Pro**, провайдер **Xiaomi Token Plan (Singapore)**.
Точный ID: `xiaomi-token-plan-sgp/mimo-v2.6-pro`. Выбор хранится в
`backend/src/services/opencode_drift_client.py` (`OPENCODE_MODEL`) и применяется
к пакетному и одиночному анализу. Старый `OPENCODE_DRIFT_MODEL` из окружения
больше не переопределяет выбор: это предотвращает возврат на Muse после релиза. Генерация дрифта через
Gemini/Vertex/OpenRouter **отключена**: если opencode serve недоступен, группы
остаются `pending`, а не уходят в Gemini.

Разовая ручная проверка по явному поручению владельца 2026-10-08 через Sol 6.1
medium описана в [отчёте](../quality/2026-10-08-visual-drift-repair.md). Она не
меняет модель автоматического рантайма и не создаёт неявный fallback.

**ВАЖНО:**
1. **НИКАКИХ МОКОВ И ЗАГЛУШЕК.** Анализ должен реально читать текст поста и
   комментариев.
2. Рантайм-скрипты (`backend/run_drift_service.py`,
   `backend/analyze_specific_drift.py`) подхватывают `backend/.env` и ходят в
   opencode serve (`OPENCODE_URL`, по умолчанию `http://127.0.0.1:4096`).
   Убедись, что serve поднят.
3. Прямые чтение/изменение БД агентом запрещены правилами проекта. Примеры
   ручного SQL ниже предназначены оператору; агент использует штатный pipeline.

---

Сервер и клиент OpenCode должны поддерживать выбранного провайдера. При переключении
30.09.2026 установленный клиент был 1.18.33, а сервер оставался на 1.18.31:
attach-вызов возвращал `Unexpected server error`. После проверки отсутствия активных
сессий сервис `opencode-serve.service` перезапущен на установленной версии 1.18.33.
Ключи и авторизация остаются в OpenCode; в репозитории хранится только ID модели.

## Рантайм-путь (рекомендуется)

```bash
backend/.venv/bin/python backend/run_drift_service.py
```

Он обрабатывает все группы `analyzed_by = 'pending'`, пишет результат и
эмбеддинг темы (`drift_embedding`, модель `gemini-embedding-001` через
OpenRouter). Метка результата — `drift_checked_opencode`.

Проверка прогресса:

```bash
sqlite3 backend/data/experts.db "SELECT analyzed_by, COUNT(*) FROM comment_group_drift GROUP BY analyzed_by;"
```

---

## Ручной алгоритм (если нужно разобрать отдельную группу)

### 1. Найти pending-группы

```bash
sqlite3 backend/data/experts.db "SELECT post_id FROM comment_group_drift WHERE analyzed_by = 'pending' LIMIT 10;"
```

### 2. Прочитать данные (Source of Truth)

```bash
sqlite3 backend/data/experts.db "SELECT message_text FROM posts WHERE post_id = <ID>;" && echo "---COMMENTS---" && sqlite3 backend/data/experts.db "SELECT author_name, comment_text FROM comments WHERE post_id = <ID>;"
```

### 3. Смысловой анализ

1. О чем пост? (Основная мысль)
2. О чем комментарии?
3. Есть ли ветки, которые **существенно** отклоняются от темы поста?
   - *Дрейф:* пост про софт-скиллы менеджера → спор про цену H100.
   - *Не дрейф:* пост про софт-склиллы → «Согласен, это важно».

### 4. JSON результата

```json
{
  "has_drift": true,
  "drift_topics": [
    {
      "topic": "Короткое название темы дрейфа",
      "keywords": ["ключевое", "слово"],
      "key_phrases": ["цитата из комментария"],
      "context": "Почему это дрейф (1 предложение)"
    }
  ]
}
```

Если дрейфа нет: `has_drift = 0`, `drift_topics = NULL`.

### 5. Запись в базу (SQL)

**Важно:** при ручной записи используй метку `muse-manual` (не `gemini-*`).

Пример (дрейф есть):

```bash
sqlite3 backend/data/experts.db "UPDATE comment_group_drift SET has_drift = 1, drift_topics = '<JSON_СТРОКОЙ>', analyzed_by = 'muse-manual', analyzed_at = datetime('now') WHERE post_id = <ID>;"
```

Пример (дрейфа нет):

```bash
sqlite3 backend/data/experts.db "UPDATE comment_group_drift SET has_drift = 0, drift_topics = NULL, analyzed_by = 'muse-manual', analyzed_at = datetime('now') WHERE post_id = <ID>;"
```

---

## Критерии дрейфа

✅ **Считается дрейфом:**
- Обсуждение технических деталей, не упомянутых в посте (железо, библиотеки).
- Организационные вопросы (где купить, почём билеты), если пост не об этом.
- Философские споры, уходящие в абстракцию.
- Личные истории, меняющие фокус обсуждения.

❌ **Не считается дрейфом:**
- Уточняющие вопросы по тексту поста.
- Согласие/несогласие.
- Благодарности.
- Шутки «в тему».
