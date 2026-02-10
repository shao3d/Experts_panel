# Reddit Integration (Enhanced)

**Статус:** Production (Stable)
**Архитектура:** Sidecar Proxy Pattern
**Логика:** AI Scout (Gemini 3 Flash) + Code Preservation
**Дата обновления:** 09.02.2026

---

## 🏗️ Архитектура (Sidecar Proxy)

Система использует интеллектуальный микросервис-прокси для глубокого анализа Reddit с сохранением технического контекста.

```mermaid
graph LR
    User[User Query] --> Backend[FastAPI Backend]
    Backend -- "1. Translate (RU->EN)" --> Translation[Translation Service]
    Translation --> Scout[🤖 AI Scout (Gemini 3 Flash)]
    
    Scout -- "Dynamic Targets" --> Proxy[Reddit Proxy Service]
    
    Proxy -- "MCP Tool (Depth 3)" --> Reddit[Reddit API]
    Reddit --> Proxy
    Proxy -- "Sanitized JSON (Code Preserved)" --> Backend
    Backend -- "Fact-Maxing Synthesis" --> Gemini[Gemini 3 Flash]
```

### Компоненты

1.  **Backend (`RedditEnhancedService`)**:
    *   **🤖 AI Scout:** Вместо жестких словарей используется `Gemini 3 Flash Preview` для динамического подбора сабреддитов (например, понимает, что "RAG" это `LocalLLaMA` + `DataEngineering`).
    *   **Query Expansion:** Расширяет запросы техническими терминами (`vram`, `gguf`, `latency`, `margin`).
    *   **Parallel Search:** Запускает стратегии `Relevance`, `Top Year`, `Freshness`, `Comparison` и `High Signal`.
2.  **Proxy (`services/reddit-proxy`)**:
    *   Node.js + Fastify микросервис.
    *   **Code Preservation:** Специальный алгоритм санитизации, который **не трогает** блоки кода (` ``` `), сохраняя отступы в Python/YAML конфигах.
    *   **Deep Fetch:** Качает дерево комментариев (Depth 3, Limit 50).
3.  **Synthesis (`RedditSynthesisService`)**:
    *   **Fact-Maxing:** Промпт жестко фильтрует эмоции ("Amazing!") и ищет цифры/бенчмарки.
    *   **Link Priority:** Выделяет ссылки на GitHub/HuggingFace как **[PRIMARY SOURCE]**.
    *   **Inverted Pyramid:** Ответ строится по схеме "Решение -> Детали -> Споры".

---

## 🧠 Логика "Smart Scout" (Dynamic Targeting)

Вместо хардкодных списков (`SUBREDDIT_BY_TOPIC`) внедрен AI-агент.

### Как это работает:
1.  **Запрос:** "Как скейлить RAG?"
2.  **Scout (Gemini 3):** Анализирует интеншн и возвращает JSON: `["LocalLLaMA", "DataEngineering", "SystemDesign", "DevOps"]`.
3.  **Поиск:** Ищет только в этих сообществах через оператор `OR` (`subreddit:LocalLLaMA OR ...`).

**Преимущества:**
*   Покрывает **любые** темы (Кулинария, Биотех, Бизнес), а не только IT.
*   Находит нишевые сообщества (`r/selfhosted`, `r/homelab`), о которых мы могли не знать.
*   Исключает шум из `r/all`.

---

## 🛡️ Code Preservation (Спасение кода)

Критическое улучшение для технических запросов.

*   **Было:** Функция очистки текста схлопывала все пробелы (`replace(/\s+/, ' ')`), уничтожая структуру Python и YAML.
*   **Стало:** Алгоритм разбивает текст по разделителю ` ``` `, чистит обычный текст, но оставляет блоки кода **в первозданном виде**.

---

## 🛠️ Технические детали

### Файлы
- **Backend Service:** `backend/src/services/reddit_enhanced_service.py` (Scout Logic)
- **Proxy Service:** `services/reddit-proxy/src/index.ts` (Sanitization Logic)
- **Synthesis:** `backend/src/services/reddit_synthesis_service.py` (Prompts)

### Proxy API
```http
POST https://experts-reddit-proxy.fly.dev/search
Content-Type: application/json

{
  "query": "How to fight hallucinations?",
  "subreddits": ["LocalLLaMA", "MachineLearning"], 
  "limit": 25,
  "sort": "relevance"
}
```

*Примечание: Если `subreddits` не передан, бэкенд вызовет Scout и заполнит этот список перед отправкой.*

---

## 🚀 Deployment

- **Backend:** Деплоится автоматически при изменениях в `backend/`.
- **Proxy:** Деплоится автоматически при изменениях в `services/reddit-proxy/`.

---

## 🔍 Troubleshooting

1.  **Scout Errors:** Если Gemini 3 Scout недоступен, система падает в **Global Search** (`r/all`) с warning'ом в логах.
2.  **Proxy Errors:** Если Proxy недоступен (Circuit Breaker Open), возвращается пустой результат Reddit, основной ответ эксперта не страдает.
