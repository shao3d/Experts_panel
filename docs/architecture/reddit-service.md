# Reddit Integration (Enhanced)

**Статус:** Production (Stable)
**Архитектура:** Sidecar Proxy Pattern
**Логика:** AI Scout v2 (Intent Plans) + Context-Aware Ranking
**Дата обновления:** 28.03.2026

---

## 🏗️ Архитектура (Sidecar Proxy)

Система использует интеллектуальный микросервис-прокси для глубокого анализа Reddit с сохранением технического контекста.

```mermaid
graph LR
    User[User Query] --> Backend[FastAPI Backend]
    Backend -- "1. Translate (Entity-Preserving)" --> Translation[Translation Service]
    Translation -- "2. Generate Plan" --> Scout[🤖 AI Scout v2 (Gemini 3 Flash)]
    
    Scout -- "Intent Queries + Keywords" --> Proxy[Reddit Proxy Service]
    
    Proxy -- "MCP Tool (Depth 3)" --> Reddit[Reddit API]
    Reddit --> Proxy
    Proxy -- "Sanitized JSON" --> Backend
    Backend -- "3. Semantic Ranking" --> Ranker[Context-Aware Ranker]
    Ranker -- "Top 15 Posts" --> Gemini[Synthesis Model]
```

### Компоненты

1.  **Backend (`RedditEnhancedService`)**:
    *   **🤖 AI Scout v2:** Вместо простого подбора сабреддитов, Gemini 3 создает **План Поиска** (Search Plan):
        *   `Subreddits`: Целевые сообщества (например, `LocalLLaMA`).
        *   `Intent Queries`: 3-5 конкретных поисковых фраз (например, `"Claude Code" config.json setup`).
        *   `Keywords`: Ключевые слова для ранжирования (например, `Skills`, `CLI`).
    *   **Context-Aware Ranking:**
        *   **No Time Decay:** Технические гайды (флаг `is_technical_guide`) не теряют рейтинг со временем.
        *   **Semantic Boost:** Посты, содержащие ключевые слова в заголовке, получают множитель Score до **x3.0**.
    *   **Deep Fetch:** Для топ-постов выполняется отдельный запрос к `/details` эндпоинту прокси. Загружается полный текст поста и глубокое дерево комментариев (**Depth 5, Limit 100**) для "Staff Engineer" синтеза.
    *   **🛡️ Authority Signals:**
        *   **Flair Detection:** Система видит плашки пользователей (`Maintainer`, `Dev`) и повышает доверие к ним.
        *   **OP Verification:** Если автор поста (OP) подтверждает решение ("Thanks, it worked!"), это решение получает статус `[✅ OP VERIFIED SOLUTION]`.
        *   **Score Skepticism:** LLM инструктирована скептически относиться к высокому рейтингу без технического обоснования (фильтр шуток).

2.  **Proxy (`services/reddit-proxy`)**:
    *   Node.js + Fastify микросервис.
    *   **Endpoints:**
        *   `POST /search` - Поиск по сабреддитам.
        *   `POST /details` - Точечная загрузка поста с комментариями. Внутренняя реализация без зависимости от MCP для гарантии формата данных.
    *   **Code Preservation:** Специальный алгоритм санитизации, который **не трогает** блоки кода (` ``` `), сохраняя отступы в Python/YAML конфигах.
    *   **Data Integrity:** Рекурсивная санитизация всего дерева комментариев (удаление Zalgo, нормализация).

3.  **Synthesis (`RedditSynthesisService`)**:
    *   **Fact-Maxing:** Промпт жестко фильтрует эмоции ("Amazing!") и ищет цифры/бенчмарки.
    *   **Inverted Pyramid:** Ответ строится по схеме "Решение -> Детали -> Споры".

---

## 🎨 UX & Прогресс (Frontend Integration)
Чтобы пользователь не видел "зависшую" систему, пока Reddit ищет и анализирует 100 комментариев:
*   Внутренние фазы Reddit (`scout`, `search`, `reranking`, `synthesis`) мапятся на стандартные фазы пайплайна фронтенда (`map`, `resolve`, `reduce`).
*   События в прогресс-баре помечаются иконкой 🌐, чтобы четко отличать их от работы с локальными экспертами.

---

## 🌐 Query Translation (Entity-Preserving)

Russian queries are translated to English for Reddit search using an **entity-preserving** approach (not a simple translation):

1.  **Domain Context:** The translator knows this is an AI Experts Panel — it biases ambiguous queries toward AI ecosystem tools (Claude Code, Codex, RAG), not generic software engineering.
2.  **Named Entity Preservation:** Product names (Claude Code, Cursor), feature names (Skills, MCP, hooks), model names (Gemini, Llama), and tech terms (RAG, LoRA) pass through **verbatim** — they are not translated or generalized.
3.  **Reddit-Optimized Output:** Concise 4-8 word queries using Reddit community terminology ("setup" not "configuration").

**Example:** `"Как настроить Skills внутри Claude Code?"` → `"Claude Code skills setup workflow"`

### Language Detection (Russian-First)

Language detection uses a **Russian-first** rule: if the query contains **any Cyrillic word**, the response language is Russian. This handles the common case of Russian-speaking users mixing English tech terms with Russian syntax (e.g., `"Claude Code skills — что лучше для workflow"` → Russian).

## 🛡️ Synthesis Relevance Gate

The synthesis prompt includes a **relevance gate** (`priority="highest"`): before synthesizing, the LLM verifies that found posts actually answer the user's question. If posts are off-topic, the system honestly reports "No relevant Reddit discussions found" instead of confidently synthesizing irrelevant content.

## 🛡️ Resilience & Safety
*   **LLM Safety Filters:** Контент Reddit может быть токсичным или спорным, что иногда триггерит фильтры безопасности Gemini (`finish_reason: SAFETY`). Вместо падения и утечки сырых proto-объектов `AsyncGenerateContentResponse` в UI, система перехватывает пустой ответ и вежливо сообщает пользователю: *"Запрос был заблокирован фильтрами безопасности (Safety Settings)."*

---

## 🧠 Логика "AI Scout v2" (Intent Planning)

Вместо regex-расширения запроса (`OR`), мы используем LLM для генерации человеческих поисковых фраз.

### Пример работы:
**Запрос:** "как настроить скиллы в Claude Code?"

**Scout v2 Plan:**
1.  **Subreddits:** `ClaudeAI`, `Anthropic`, `coding`
2.  **Intent Queries:**
    *   `"Claude Code" skills workflow guide`
    *   `"Claude Code" MCP config.json`
    *   `"Claude Code" custom tools setup`
3.  **Keywords:** `["Skills", "Config", "MCP"]`

**Результат:**
Система находит конкретные гайды и конфиги, а не просто новости про Claude.

---

## 📊 Semantic Ranking Strategy

Как мы выбираем лучшее из найденного?

1.  **Base Score:** `(Upvotes + Comments * 2)`
2.  **Technical Guide Detection:** Если пост найден стратегией `ai_intent` или содержит маркеры "Guide/Tutorial" -> помечается как `is_technical_guide`.
3.  **Keyword Boost:** Если в заголовке есть слова из `Keywords` (Scout) -> Score умножается на **1.5 - 3.0**.
4.  **Time Decay (Умный):**
    *   Для **Новостей**: Применяется классическая "Гравитация" (Hacker News), штрафующая за возраст.
    *   Для **Гайдов**: Decay **ОТКЛЮЧЕН**. Старый, но полезный гайд с 2000 лайков будет выше свежей новости с 500 лайками.

---

## 🛠️ Технические детали

### Файлы
- **Backend Service:** `backend/src/services/reddit_enhanced_service.py` (Scout Logic & Ranking)
- **Proxy Service:** `services/reddit-proxy/src/index.ts` (Sanitization Logic)

### Proxy API
```http
POST https://experts-reddit-proxy.fly.dev/search
Content-Type: application/json

{
  "query": "Claude Code skills guide",
  "subreddits": ["ClaudeAI"], 
  "limit": 25,
  "sort": "relevance"
}
```

---

## 🚀 Deployment

- **Backend:** Деплоится автоматически при изменениях в `backend/`.
- **Proxy:** Деплоится автоматически при изменениях в `services/reddit-proxy/`.