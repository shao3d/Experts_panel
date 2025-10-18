# Experts Panel 🔍

Интеллектуальная платформа для анализа дискуссий в Telegram-каналах с использованием инновационной архитектуры Map-Resolve-Reduce.

## 🚀 Особенности

- **Map-Resolve-Reduce архитектура** - эффективная обработка больших объемов сообщений
- **Умный поиск по контексту** - находит связанные посты через анализ ссылок и упоминаний
- **Real-time прогресс** - SSE для отслеживания состояния обработки запроса
- **Экспертные комментарии** - поддержка аннотаций от экспертов
- **Визуализация источников** - удобный просмотр найденных постов

## 📋 Требования

- Python 3.11+
- Node.js 18+
- SQLite 3
- OpenAI API ключ (для GPT-4o-mini)

## 🛠 Установка

### Backend

```bash
cd backend

# Установка зависимостей через uv (рекомендуется)
uv install

# Или через pip
pip install -r requirements.txt

# Создание .env файла
cp .env.example .env
# Добавьте ваш OPENAI_API_KEY в .env
```

### Frontend

```bash
cd frontend

# Установка зависимостей
npm install
```

## 🚦 Быстрый старт

### 1. Подготовка базы данных

```bash
cd backend

# Создание базы данных
sqlite3 ../data/experts.db < schema.sql

# Импорт данных из Telegram
python -m src.data.json_parser ../data/exports/your_export.json

# Добавление экспертных комментариев (опционально)
python -m src.data.comment_collector
```

### 2. Запуск Backend

```bash
cd backend

# Development режим
uv run python -m src.api.main

# Или через uvicorn напрямую
uvicorn src.api.main:app --reload --port 8000
```

Backend будет доступен на http://localhost:8000
- API документация: http://localhost:8000/api/docs
- Health check: http://localhost:8000/health

### 3. Запуск Frontend

```bash
cd frontend

# Development режим
npm run dev
```

Frontend будет доступен на http://localhost:5173

## 📚 API Endpoints

### Основные endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/api/query` | Выполнить поисковый запрос (SSE) |
| GET | `/api/v1/api/posts/{post_id}` | Получить детали поста |
| POST | `/api/v1/api/import` | Импортировать JSON файл |
| GET | `/api/v1/api/import/status/{job_id}` | Статус импорта |
| GET | `/health` | Проверка здоровья системы |
| GET | `/api/info` | Информация об API |

### Пример запроса

```bash
# Простой поисковый запрос
curl -X POST "http://localhost:8000/api/v1/api/query" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Какие основные темы обсуждаются в канале?",
       "max_posts": 100,
       "include_comments": true,
       "stream_progress": true
     }'

# Получение деталей поста
curl "http://localhost:8000/api/v1/api/posts/1"
```

## 📁 Структура проекта

```
Experts_panel/
├── backend/
│   ├── src/
│   │   ├── api/          # FastAPI endpoints
│   │   ├── models/       # SQLAlchemy модели
│   │   ├── services/     # Map-Resolve-Reduce сервисы
│   │   └── data/         # Импорт и обработка данных
│   ├── prompts/          # Промпты для LLM
│   └── tests/            # Тесты и валидация
├── frontend/
│   ├── src/
│   │   ├── components/   # React компоненты
│   │   ├── pages/        # Страницы приложения
│   │   ├── services/     # API клиент
│   │   └── types/        # TypeScript типы
│   └── public/
├── data/
│   ├── experts.db        # SQLite база данных
│   └── exports/          # Telegram JSON экспорты
└── tests/
    ├── test_queries.json # Тестовые запросы
    └── test_queries.py   # Скрипт валидации
```

## 🧪 Тестирование

### Запуск тестов валидации

```bash
# Из корня проекта
python tests/test_queries.py

# С кастомными настройками
python tests/test_queries.py --api-url http://localhost:8000 --timeout 60
```

### Валидация производительности

```bash
# Проверка времени обработки
python tests/test_queries.py --performance-check
```

## 🔧 Разработка

### Переменные окружения

Создайте файл `.env` в папке `backend/`:

```env
# OpenAI
OPENAI_API_KEY=your_api_key_here

# Database
DATABASE_URL=sqlite:///../data/experts.db

# API Settings
MAX_POSTS_LIMIT=500
CHUNK_SIZE=20
REQUEST_TIMEOUT=300

# CORS (для production)
PRODUCTION_ORIGIN=https://your-domain.com
```

### Архитектура Map-Resolve-Reduce

1. **Map фаза**: Параллельная обработка чанков постов (20-25 постов на чанк)
2. **Resolve фаза**: Обогащение результатов через анализ связей (depth=2)
3. **Reduce фаза**: Синтез финального ответа с источниками

### Логирование

Система использует комплексную систему логирования:
- Консольный вывод с цветовой кодировкой
- Файловые логи в `backend/logs/`
- SSE события для real-time мониторинга

## 📝 Лицензия

MIT

## 🤝 Контрибьюторы

- Проект создан с помощью Claude AI
- Основан на архитектуре Map-Resolve-Reduce

## 📞 Поддержка

Для вопросов и предложений:
- Создайте Issue в репозитории
- Обратитесь к документации в `PROJECT_BRIEF.md`
- Изучите примеры в `tests/test_queries.json`

---

🤖 Generated with [Claude Code](https://claude.ai/code)