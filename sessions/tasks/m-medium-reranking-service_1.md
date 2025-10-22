# Task: Medium Posts Re-ranking Service Implementation

## 🎯 Цель
Создать дополнительный этап ре-ранкинга MEDIUM постов через GPT-4o-mini для повышения качества ответов без изменения существующей Map-фазы.

## 📋 Описание проблемы
Текущая система включает все MEDIUM посты в pipeline, что может:
- Увеличивать шум в контексте
- Снижать точность ответов
- Увеличивать стоимость токенов в Reduce фазе

## 💡 Предлагаемое решение
Гибридная архитектура с отдельным ре-ранкингом MEDIUM постов:

```
Map → Filter → [MEDIUM Re-ranking] → Resolve → Reduce
```

**Ключевая идея:** Отфильтровать все MEDIUM посты, прогнать через GPT-4o-mini как ре-ранкер, взять TOP-5 лучших для каждого эксперта.

## 🏗️ Архитектура

### Новые компоненты:
1. **`MediumReRankingService`** - новый сервис для ре-ранкинга
2. **Промпт для ре-ранкинга** - специализированный промпт для GPT-4o-mini
3. **Интеграция в pipeline** - модификация `simplified_query_endpoint.py`

### Порядок работы:
1. **Map фаза** (без изменений) → HIGH/MEDIUM/LOW классификация
2. **Filter фаза** → разделение на HIGH и MEDIUM посты
3. **Re-ranking фаза** (новая) → GPT-4o-mini ре-ранкинг MEDIUM постов
4. **Resolve фаза** → поиск связанных постов для HIGH + TOP-5 MEDIUM
5. **Reduce фаза** → финальный синтез

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

### 1. MediumReRankingService
**Файл:** `backend/src/services/medium_reranking_service.py`

```python
class MediumReRankingService:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini")
    self.client = create_openrouter_client(api_key=api_key)
    self.model = convert_model_name(model)

    async def rerank_medium_posts(
        self,
        medium_posts: List[Dict],
        high_posts_context: str,
        query: str,
        expert_id: str,
        top_k: int = 5
    ) -> List[Dict]:
        """Re-rank medium posts using GPT-4o-mini"""
```

### 2. Промпт для ре-ранкинга
**Файл:** `backend/prompts/medium_reranking_prompt.txt`

```
You are analyzing MEDIUM-relevant posts to complement HIGH-relevant posts.

User query: {query}
HIGH posts summary: {high_posts_context}

MEDIUM posts to evaluate:
{medium_posts}

Select TOP {top_k} posts that would be most valuable to complement HIGH posts.

Consider:
1. Information gaps in HIGH posts
2. Additional examples or case studies
3. Alternative perspectives
4. Technical details missing from HIGH posts
5. Related topics not covered in HIGH posts

Return JSON with selected posts.
```

### 3. Интеграция в pipeline
**Место:** `backend/src/api/simplified_query_endpoint.py`

```python
# После Map фазы:
high_posts = [p for p in relevant_posts if p.get("relevance") == "HIGH"]
medium_posts = [p for p in relevant_posts if p.get("relevance") == "MEDIUM"]

# Новый этап: Re-ranking MEDIUM постов
if medium_posts:
    reranking_service = MediumReRankingService(api_key)

    # Создаем контекст из HIGH постов
    high_context = format_high_posts_context(high_posts)

    # Re-ranking
    top_medium_posts = await reranking_service.rerank_medium_posts(
        medium_posts=medium_posts,
        high_posts_context=high_context,
        query=request.query,
        expert_id=expert_id
    )

    # Объединяем HIGH + TOP-MEDIUM
    filtered_posts = high_posts + top_medium_posts
else:
    filtered_posts = high_posts
```

## 📋 План реализации

### Фаза 1: Создание MediumReRankingService
- [ ] Создать файл `backend/src/services/medium_reranking_service.py`
- [ ] Реализовать базовый класс с GPT-4o-mini
- [ ] Добавить обработку ошибок и retry логику
- [ ] Написать unit тесты

### Фаза 2: Промпт и тестирование
- [ ] Создать `backend/prompts/medium_reranking_prompt.txt`
- [ ] Тестировать промпт на реальных данных
- [ ] Оптимизировать для качества ре-ранкинга
- [ ] Валидировать JSON ответы

### Фаза 3: Интеграция в pipeline
- [ ] Модифицировать `simplified_query_endpoint.py`
- [ ] Добавить ре-ранкинг после Map фазы
- [ ] Обновить логирование и метрики
- [ ] Тестировать полный pipeline

### Фаза 4: Тестирование и оптимизация
- [ ] Провести A/B тестирование со старой версией
- [ ] Сравнить качество ответов
- [ ] Измерить стоимость и время
- [ ] Оптимизировать top_k параметр

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
- Graceful degradation при ошибках ре-ранкинга

## 🚨 Риски и митигация

### Риск 1: API ошибки GPT-4o-mini
**Митигация:** Retry логика, fallback к использованию всех MEDIUM постов

### Риск 2: Плохое качество ре-ранкинга
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

- [ ] Фаза 1: MediumReRankingService (0/3)
- [ ] Фаза 2: Промпт и тестирование (0/3)
- [ ] Фаза 3: Интеграция (0/3)
- [ ] Фаза 4: Тестирование (0/4)

**Общий прогресс:** 0/13 задач выполнено

---

**Приоритет:** Средний (улучшение качества без критических изменений)
**Сложность:** Средняя (новый сервис, но изолированная реализация)
**Влияние:** Высокое (значительное улучшение качества ответов)