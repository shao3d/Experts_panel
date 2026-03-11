# AI Scout Upgrade Plan (Level 1: Fast Wins)

**Цель:** Повысить Recall (полноту поиска) FTS5 и предотвратить "тихие падения" (Syntax Errors) при поиске технических терминов со спецсимволами, не перестраивая текущие индексы базы данных.

**Статус:** Утверждено. (Финальная версия после v2 CTO Code Review. Устранены баги в регулярках, добавлено структурированное логирование).

## Проблема текущей реализации
1. **Слепота FTS5 к спецсимволам:** Токенизатор `unicode61` в SQLite FTS5 игнорирует символы `+` и `#`. Запрос `C++` превращается в поиск одиночной буквы `c`, выдавая сотни мусорных результатов (или падая с Syntax Error, если к спецсимволу приклеен `*`).
2. **Gap Санитайзера:** AI Scout может сгенерировать правильный запрос с кавычками (например, `"си плюс плюс"`), но `FTS5RetrievalService` жестко вырезает все кавычки перед отправкой в БД. Это ломает фразовый поиск.
3. **Рассинхрон LLM и словаря:** LLM не знает о словаре `KNOWN_SLANG` (он используется только в Fallback). Поэтому LLM пытается угадывать и генерирует невалидный синтаксис (вроде `C++*`). Fallback, в свою очередь, слепо приклеивает `*` к оригинальным словам, что убивает FTS5 на спецсимволах.

---

## 🛠️ Прагматичный План Внедрения (Без Over-Engineering)

Мы решаем проблему на уровне умного маппинга, точечной инструкции для LLM и безопасной очистки.
*Примечание к архитектуре:* Правила перевода спецсимволов дублируются в Промпте (для AI Path) и в Словаре (для Fallback Path), чтобы обе ветки работали надежно.

### ШАГ 1: Обучить LLM и обновить словарь `KNOWN_SLANG`
Мы переводим нечитаемые для FTS5 спецсимволы в буквенные аналоги, которые есть в тексте постов, и защищаем фразы кавычками. 

**Файл:** `backend/src/services/ai_scout_service.py`

**1.1 Добавить правила в хардкод-промпт метода `_generate_with_ai`:**
```text
RULES:
...
7. CRITICAL: SQLite FTS5 tokenizer ignores special characters (+, #). 
   NEVER output raw special chars. ALWAYS replace them with safe equivalents:
   - C++ → cpp, cplusplus, "си плюс плюс"
   - C# → csharp, "си шарп"
   - F# → fsharp, "эф шарп"
   - .NET → dotnet, "дотнет"
   - Node.js → nodejs, "нода"
   NEVER attach wildcards (*) to special characters.
```

**1.2 Дополнить словарь `KNOWN_SLANG` безопасными токенами (для Fallback):**
```python
    KNOWN_SLANG = {
        # ... существующий сленг ...
        "c++": "cpp OR cplusplus OR \"си плюс плюс\"",
        "с++": "cpp OR cplusplus OR \"си плюс плюс\"", # русская буква 'с'
        "c#": "csharp OR \"си шарп\"",
        "f#": "fsharp OR \"эф шарп\"",
        ".net": "dotnet OR \"дотнет\"",
        "node.js": "nodejs OR \"нода\""
    }
```

### ШАГ 2: Починить генератор Fallback'a (Защита от суицида)
В методе `_generate_fallback` нужно перестать лепить `*` к оригинальному слову, если это слово — спецсимвол. Иначе мы отправляем в FTS5 невалидный токен `c++*`.

**Файл:** `backend/src/services/ai_scout_service.py` (в методе `_generate_fallback`)
```python
            for ru, en in self.KNOWN_SLANG.items():
                if ru in word or word in ru:
                    # Проверяем само слово пользователя на спецсимволы, чтобы не добавить C++*
                    if any(c in word for c in '+#.'):
                        expanded_terms.append(f"({en})")
                    else:
                        expanded_terms.append(f"({word}* OR {en})")
                    found_slang = True
                    break
```

### ШАГ 3: Усилить валидатор на выходе Скаута
Даже если LLM сгаллюцинирует и попытается прилепить wildcard к спецсимволу, мы должны это поймать *до* санитайзера, чтобы корректно отработал Fallback.

**Файл:** `backend/src/services/ai_scout_service.py` (в методе `validate_match_query`)
```python
    def validate_match_query(self, match_query: str) -> bool:
        # ... существующие проверки (баланс скобок и кавычек) ...

        # Защита от FTS5 Syntax Error на спецсимволах (ловит C++*, C#*, C+ * и т.д.)
        if re.search(r'[+#][+#\s]*\*', match_query):
            logger.warning(f"[AI Scout] Invalid wildcard after special char: {match_query}")
            return False

        return True
```

### ШАГ 4: Починить Санитайзер (Разрешить парные кавычки)
Чтобы фразы типа `"си плюс плюс"` доходили до FTS5, нужно убрать агрессивное удаление двойных кавычек, оставив только проверку на их баланс.

**Файл:** `backend/src/services/fts5_retrieval_service.py`
```python
def sanitize_fts5_query(query: str) -> str:
    # ...
    # ИЗМЕНЕНИЕ: Оставляем только удаление ; ' \
    # Двойные кавычки (") убраны из списка удаления, чтобы работал фразовый поиск
    query = re.sub(r'[;\'\\]', '', query)
    
    # ... проверка баланса скобок остается ...

    # Проверка баланса кавычек теперь реально работает
    if query.count('"') % 2 != 0:
        logger.warning(f"[FTS5 Sanitize] Unbalanced quotes, removing: {original[:50]}")
        query = query.replace('"', '')
```

### ШАГ 5: Внедрить метрики успеха (FTS5 Hit Rate - JSON)
Мы должны понимать, как часто поиск реально использует быстрый индекс FTS5. Используем JSON для легкого парсинга логов.

**Файл:** `backend/src/services/fts5_retrieval_service.py` (в методе `search_posts`, перед return)
```python
            import json # Убедиться, что импортирован
            
            if post_ids:
                # ... existing code ...
                logger.info(f"[FTS5 Metrics] " + json.dumps({
                    "event": "hit", 
                    "posts": len(sorted_posts), 
                    "query": match_query[:50]
                }, ensure_ascii=False))
                return sorted_posts, True
            else:
                logger.info(f"[FTS5 Metrics] " + json.dumps({
                    "event": "miss", 
                    "query": match_query[:50]
                }, ensure_ascii=False))
                return [], False
        except Exception as e:
            logger.error(f"[FTS5 Metrics] " + json.dumps({
                "event": "error", 
                "error_msg": str(e), 
                "query": match_query
            }, ensure_ascii=False))
            return [], False
```

---

## 🧪 ШАГ 6: Тестирование (Unit & Integration)
Для гарантии стабильности необходимо добавить тесты.

**Unit-тест для спецсимволов (`tests/test_ai_scout.py`):**
```python
def test_special_chars_validation():
    service = AIScoutService()
    query, success = service.generate_match_query("как работать с C++")
    assert "C++*" not in query  # Не должно быть wildcard после плюсов
    assert "cpp" in query or "cplusplus" in query
```

**Integration-тест для FTS5 (`tests/test_fts5_retrieval.py`):**
```python
def test_fts5_phrase_search():
    # Проверка, что санитайзер пропускает фразы в кавычках
    posts, used_fts5 = service.search_posts(expert_id, '"си плюс плюс"')
    assert used_fts5  # Должен использовать FTS5, не fallback
```

---

## 📈 Ожидаемый результат
1. **Safety:** Пользователи смогут искать `C++`, `C#` и `F#`. Система не упадет с Syntax Error (ни в AI Scout, ни в Fallback).
2. **Recall:** За счет сохранения кавычек заработает фразовый поиск, отсекая мусор.
3. **Observability:** Структурированные JSON логи `[FTS5 Metrics]` позволят легко считать Hit Rate в Kibana/Datadog. Latency останется на прежнем уровне (~100ms для FTS5).
