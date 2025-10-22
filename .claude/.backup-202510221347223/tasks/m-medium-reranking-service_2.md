# Task: Medium Posts Scoring Service (Hybrid LLM + Code)

## 🎯 Цель
Создать гибридную систему ре-ранкинга MEDIUM постов через GPT-4o-mini, где LLM оценивает, а код принимает финальное решение.

## 💡 Гибридный подход: LLM оценивает + код решает

**✅ Лучший из двух миров:** Используем сильные стороны LLM (семантическая оценка) и детерминированного кода (предсказуемые решения).

```
Map → Filter → [MEDIUM Scoring] → Code Selection → Resolve → Reduce
```

**Ключевая идея:** LLM ставит оценки всем MEDIUM постам, а код принимает финальное решение на основе этих оценок.

### Как работает гибридный подход:

1. **LLM задача (оценка):** "Оцени каждый Medium пост по шкале 1-10, насколько он полезен для дополнения HIGH постов"
2. **LLM результат:** Возвращает полный список с оценками в JSON формате
3. **Код задача (фильтрация):** Применяет предсказуемую логику к оценкам

### Пример LLM ответа:
```json
{
  "ranked_posts": [
    {"post_id": 123, "score": 9, "reason": "Добавляет конкретный пример..."},
    {"post_id": 456, "score": 8, "reason": "Предлагает альтернативную методику..."},
    {"post_id": 789, "score": 4, "reason": "Лишь косвенно касается темы..."},
    ...
  ]
}
```

### Варианты логики отбора в коде:
- **Простой порог:** Взять все посты с `score >= 7`
- **Порог с ограничением:** Взять посты с `score >= 7`, но не более 10 штук
- **Динамический порог:** Брать до тех пор, пока оценка не упадет резко
- **Топ-K (MVP):** Взять лучшие K постов

### Почему гибридный подход — лучший:
- ✅ **Надежность:** LLM решает простую задачу оценки, результат стабильнее
- ✅ **Контроль:** Код контролирует максимальное количество постов
- ✅ **Гибкость:** Можно менять логику отбора без изменения промпта
- ✅ **Интеллект:** Используем семантические возможности LLM для оценки
- ✅ **Предсказуемость:** Детерминированная логика в коде

## 📋 Описание проблемы
Текущая система включает все MEDIUM посты в pipeline, что может:
- Увеличивать шум в контексте
- Снижать точность ответов
- Увеличивать стоимость токенов в Reduce фазе

## 🏗️ Архитектура

### Новые компоненты:
1. **`MediumScoringService`** - сервис для оценки MEDIUM постов
2. **Промпт для оценки** - специализированный промпт для GPT-4o-mini
3. **Логика отбора** - детерминированная фильтрация в коде
4. **Интеграция в pipeline** - модификация `simplified_query_endpoint.py`

### Порядок работы:
1. **Map фаза** (без изменений) → HIGH/MEDIUM/LOW классификация
2. **Filter фаза** → разделение на HIGH и MEDIUM посты
3. **Scoring фаза** (новая) → GPT-4o-mini оценка всех MEDIUM постов
4. **Selection фаза** → код выбирает лучшие посты по оценкам
5. **Resolve фаза** → поиск связанных постов для HIGH + выбранные MEDIUM
6. **Reduce фаза** → финальный синтез

## 📊 Анализ стоимости и производительности

### Стоимость GPT-4o-mini:
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens

### Пример расчета на 1 эксперта:
```
MEDIUM постов: 15
Токенов на пост: ~300
Input: 4,500 токенов → $0.0007
Output: 200 токенов → $0.0001
Итого: ~$0.001 за эксперта
```

**Общая стоимость:** ~$0.003 за 3 экспертов (копейки!)

### Время выполнения:
- +5-10 секунд к общему времени
- Параллельная обработка для всех экспертов
- Незамедлительное увеличение времени обработки

## 🔧 Техническая реализация

### 1. MediumScoringService
**Файл:** `backend/src/services/medium_scoring_service.py`

```python
class MediumScoringService:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini")
    self.client = create_openrouter_client(api_key=api_key)
    self.model = convert_model_name(model)

    async def score_medium_posts(
        self,
        medium_posts: List[Dict],
        high_posts_context: str,
        query: str,
        expert_id: str
    ) -> List[Dict]:
        """Score all medium posts using GPT-4o-mini"""
```

### 2. Промпт для оценки
**Файл:** `backend/prompts/medium_scoring_prompt.txt`

```
You are analyzing MEDIUM-relevant posts to complement HIGH-relevant posts.

User query: {query}
HIGH posts summary: {high_posts_context}

MEDIUM posts to evaluate:
{medium_posts}

Rate each post on a scale of 1-10 based on how valuable it would be to complement HIGH posts.

Consider:
1. Information gaps in HIGH posts
2. Additional examples or case studies
3. Alternative perspectives
4. Technical details missing from HIGH posts
5. Related topics not covered in HIGH posts

Return JSON with all posts and their scores.
```

### 3. Логика отбора в коде
**Место:** `backend/src/api/simplified_query_endpoint.py`

```python
# После Map фазы:
high_posts = [p for p in relevant_posts if p.get("relevance") == "HIGH"]
medium_posts = [p for p in relevant_posts if p.get("relevance") == "MEDIUM"]

# MVP: Top-K выборка
TOP_MEDIUM_POSTS = 5

# Будущая реализация: гибридный подход
if medium_posts:
    scoring_service = MediumScoringService(api_key)

    # Создаем контекст из HIGH постов
    high_context = format_high_posts_context(high_posts)

    # Scoring
    scored_posts = await scoring_service.score_medium_posts(
        medium_posts=medium_posts,
        high_posts_context=high_context,
        query=request.query,
        expert_id=expert_id
    )

    # MVP: Просто берем топ-K
    selected_medium_posts = scored_posts[:TOP_MEDIUM_POSTS]

    # Future: Гибридная логика
    # selected_medium_posts = select_posts_by_threshold(
    #     scored_posts,
    #     min_score=7,
    #     max_count=10
    # )

    # Объединяем HIGH + выбранные MEDIUM
    filtered_posts = high_posts + selected_medium_posts
else:
    filtered_posts = high_posts
```

### 4. Гибридная логика отбора (Future)
```python
def select_posts_by_threshold(posts: List[Dict], min_score: int = 7, max_count: int = 10) -> List[Dict]:
    """Select posts based on score threshold and maximum count"""
    selected = []

    for post in posts:
        if post.get("score", 0) >= min_score:
            selected.append(post)
            if len(selected) >= max_count:
                break

    return selected
```

## 📋 План реализации

### MVP (Текущий спринт): Жесткий лимит Top-K
- [ ] Создать `MediumScoringService` с GPT-4o-mini
- [ ] Создать промпт для оценки всех MEDIUM постов
- [ ] Реализовать простую Top-K выборку (K=5)
- [ ] Интегрировать в pipeline
- [ ] Тестировать полный pipeline

### Future: Гибридный подход
- [ ] Обновить логику отбора для работы с оценками
- [ ] Добавить пороговый выбор (`score >= 7`)
- [ ] Добавить максимальное количество (`max=10`)
- [ ] Реализовать динамические пороги
- [ ] A/B тестирование разных стратегий

## 🎯 Успешные критерии

### Качественные метрики:
- Ответы становятся более полными и контекстно богатыми
- Система находит неочевидные связи через MEDIUM посты
- Выше точность на сложных многогранных вопросах

### Количественные метрики:
- +10-20% полезных постов в main_sources
- Cost increase < $0.01 за запрос
- Time increase < 15 секунд
- Ошибка API < 5%

### Технические метрики:
- Все unit тесты проходят
- Интеграция не ломает существующий pipeline
- Graceful degradation при ошибках оценки

## 🚨 Риски и митигация

### Риск 1: API ошибки GPT-4o-mini
**Митигация:** Retry логика, fallback к использованию всех MEDIUM постов

### Риск 2: Плохое качество оценки
**Митигация:** Тщательное тестирование промпта, A/B тестирование

### Риск 3: Увеличение времени обработки
**Митигация:** Параллельная обработка, мониторинг времени

### Риск 4: JSON парсинг ошибки
**Митигация:** Валидация схемы, обработка исключений

## 📚 Дополнительные ресурсы

- [OpenRouter API docs](https://openrouter.ai/docs)
- [GPT-4o-mini documentation](https://platform.openai.com/docs/models/gpt-4o-mini)
- [RAG re-ranking best practices](https://arxiv.org/abs/2401.18087)

## 📊 Отслеживание прогресса

### MVP Phase:
- [ ] MediumScoringService implementation (0/3)
- [ ] Промпт и тестирование (0/2)
- [ ] Интеграция в pipeline (0/2)
- [ ] Тестирование (0/1)

### Future Phase:
- [ ] Гибридная логика отбора (0/3)
- [ ] A/B тестирование стратегий (0/2)

**Общий прогресс:** 0/13 задач выполнено

---

**Приоритет:** Средний (улучшение качества без критических изменений)
**Сложность:** Средняя (новый сервис, но изолированная реализация)
**Влияние:** Высокое (значительное улучшение качества ответов)