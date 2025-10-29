# Experts Panel

[![CI/CD](https://github.com/andreysazonov/Experts_panel/workflows/CI%2FCD/badge.svg)](https://github.com/andreysazonov/Experts_panel/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org)

**Интеллектуальная система анализа Telegram каналов экспертов с использованием многомодельной AI-архитектуры**

Experts Panel — это мощный инструмент для семантического поиска и анализа контента из Telegram каналов экспертов. Система использует продвинутую **8-фазную архитектуру Map-Resolve-Reduce pipeline** с несколькими AI-моделями для предоставления точных и контекстуально релевантных ответов.

## 🏗️ Архитектура системы

### Высокоуровневая архитектура

```mermaid
graph TD
    subgraph "Пользовательская среда"
        User[Пользователь]
        Frontend[React Frontend Vite]
    end

    subgraph "Инфраструктура Experts Panel"
        Backend[FastAPI Backend]
        subgraph "База Знаний"
            DB[(SQLite PostgreSQL)]
        end
    end

    subgraph "Внешние AI сервисы"
        LLM_API[OpenRouter API]
    end

    User -- "Отправляет запрос" --> Frontend
    Frontend -- "API-запрос /api/v1/query SSE" --> Backend
    Backend -- "Обращается к LLM-моделям" --> LLM_API
    Backend -- "Извлекает посты, комментарии, связи" --> DB
    Backend -- "Потоком SSE отдаёт прогресс и ответ" --> Frontend
    Frontend -- "Отображает ответ и источники" --> User
```

### Интеллектуальный конвейер обработки запросов

```mermaid
graph TD
    A[Старт: Пользовательский запрос] --> B{Определение языка запроса}
    B --> C[1. Map-фаза: Qwen 2.5]
    C -- "Посты" --> D{Разделение на HIGH и MEDIUM}
    D -- "HIGH посты" --> E[3. Resolve-фаза: Поиск связанных постов в БД]
    D -- "MEDIUM посты" --> F[2. Scoring-фаза: Qwen 2.5]
    F -- "Top-5 постов score >= 0.7" --> G[4. Reduce-фаза: Gemini Flash]
    E -- "Обогащенные HIGH посты" --> G
    G -- "Синтезированный ответ" --> H[5. Language Validation: Qwen 2.5]
    H -- "Ответ на нужном языке" --> I{Сборка финального ответа}

    subgraph "Параллельный Pipeline B: Поиск в комментариях"
        J[6. Поиск по Drift Topics] --> K[7. Синтез инсайтов из комментариев]
    end

    A --> J
    K --> I[8. Response Building]

    I --> L[Финальный ответ]

    classDef llm_step fill:#f9f,stroke:#333,stroke-width:2px
    class C,F,G,H,J,K llm_step
```

### Жизненный цикл данных

```mermaid
graph TD
    subgraph "Этап 1: Ручной импорт Первичная загрузка"
        A[Администратор] --> B[json_parser.py]
        C[JSON экспорт из Telegram] --> B
        B --> D[Запись постов комментариев связей в БД]
    end

    subgraph "Этап 2: Автоматическая инкрементальная синхронизация"
        E[Cron Job Планировщик] --> F[sync_channel.py]
        F -- "Получает ID последнего поста" --> G[БД]
        G -- "Отдаёт ID" --> F
        F -- "Запрашивает новые данные" --> H[Telegram API]
        H -- "Отдаёт новые посты и комментарии" --> F
        F --> I[Обновляет добавляет данные в БД]
        F --> J[Помечает новые группы комментариев как pending]
    end

    D --> G
    I --> G
    J --> G
```

### Пользовательский путь

```mermaid
graph TD
    A[Пользователь открывает приложение] --> B{Видит форму ввода}
    B --> C[Вводит вопрос и нажимает Ask]
    C --> D[UI переходит в состояние Processing]
    D --> E[ProgressSection отображает прогресс в реальном времени]
    E --> F["Появляются статусы: Map - Resolve - Reduce ..."]
    F --> G[Бэкенд присылает финальный ответ]
    G --> H[Появляются аккордеоны для каждого эксперта]
    H -- "Клик на аккордеон" --> I{Раскрывается результат}
    I --> J[Видит ответ и список постов-источников]
    J -- "Клик на ссылку post ID в ответе" --> K[Нужный пост подсвечивается в списке]
    J -- "Клик на пост в списке" --> L[Пост раскрывается, показывая полный текст и комментарии]
    L --> J
    H --> B
```

### Архитектура развёртывания

```mermaid
graph TD
    subgraph "Интернет"
        User[Пользователь]
    end

    subgraph "Облачная платформа Fly.io Railway"
        LB[Load Balancer Proxy]

        subgraph "Frontend контейнер"
            Nginx[Nginx] --> Static[Статика React]
        end

        subgraph "Backend контейнер"
            Uvicorn[ASGI сервер Uvicorn] --> App[FastAPI приложение]
        end

        subgraph "Постоянное хранилище"
            Volume[Mounted Volume]
            DB[(experts.db)]
            Volume -- содержит --> DB
        end
    end

    User -- HTTPS --> LB
    LB -- "Запросы UI" --> Nginx
    Nginx --> Static
    LB -- "Проксирует /api/*" --> Uvicorn
    App -- "Читает пишет в БД" --> DB
    App -- "Обращается к AI" --> LLM_API[OpenRouter API]

    style Volume fill:#fdf,stroke:#333
```

## ✨ Ключевые возможности

- **🧠 8-фазная Map-Resolve-Reduce архитектура**: Продвинутый pipeline с дифференциальной обработкой HIGH/MEDIUM постов
- **🎯 Многомодельная AI-стратегия**: Qwen 2.5-72B (Map+Validation), Gemini 2.0 Flash (Reduce+Synthesis), GPT-4o-mini (Scoring+Matching)
- **🔍 Умный семантический поиск**: Находит релевантные посты по смыслу, а не по ключевым словам
- **📊 Medium Posts Hybrid Reranking**: Гибридная система с порогом ≥0.7 и топ-5 отбором
- **💬 Comment Drift Analysis**: Отдельный pipeline для анализа комментариев и обсуждений
- **🌐 Language Validation Phase**: Валидация языка ответа и перевод RU→EN при необходимости
- **⚡ Реальное время**: Отображение прогресса обработки через Server-Sent Events
- **👥 Мульти-экспертность**: Поддержка `expert_id` для изоляции данных и параллельной обработки
- **🔄 Автоматическая синхронизация**: Инкрементальное обновление данных из Telegram каналов

## 🚀 Быстрый старт

### Требования

- Python 3.11+
- Node.js 18+
- OpenRouter API ключ

### Установка и запуск

```bash
# 1. Клонирование репозитория
git clone https://github.com/andreysazonov/Experts_panel.git
cd Experts_panel

# 2. Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env, добавив OPENROUTER_API_KEY

# 3. Запуск бэкенда
cd backend
pip install -r requirements.txt
python3 -m uvicorn src.api.main:app --reload --port 8000

# 4. Запуск фроненда (в новом терминале)
cd frontend
npm install
npm run dev
```

Приложение будет доступно по адресу http://localhost:3001

## 🛠️ Управление данными

### Импорт данных из Telegram

```bash
# Импорт JSON файла с указанием expert_id
cd backend && python -m src.data.json_parser data/exports/channel.json --expert-id refat

# Интерактивное добавление комментариев
cd backend && python -m src.data.comment_collector

# Синхронизация Telegram канала
cd backend && python sync_channel.py --dry-run --expert-id refat
cd backend && python sync_channel.py --expert-id refat
```

### Анализ drift и база данных

```bash
# Анализ drift в комментариях (обязательно после реимпорта данных)
cd backend && python analyze_drift.py

# Управление базой данных
cd backend && python -m src.models.database  # Интерактивное управление (init/reset/drop)

# Создание и миграция SQLite базы
sqlite3 data/experts.db < schema.sql
sqlite3 data/experts.db < backend/migrations/001_create_comment_group_drift.sql
sqlite3 data/experts.db < backend/migrations/002_add_sync_state.sql
sqlite3 data/experts.db < backend/migrations/003_add_expert_id.sql
```

## 📚 Использование API

### Базовый запрос

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Ваш вопрос", "stream_progress": false}'
```

### Запрос к конкретному эксперту

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Ваш вопрос", "expert_filter": ["refat"], "stream_progress": false}'
```

### Переменные окружения

```bash
# Основные переменные
OPENROUTER_API_KEY=your-key-here
DATABASE_URL=sqlite:///data/experts.db

# Medium Posts Reranking
MEDIUM_SCORE_THRESHOLD=0.7
MEDIUM_MAX_SELECTED_POSTS=5
MEDIUM_MAX_POSTS=50

# Производительность
MAX_POSTS_LIMIT=500
CHUNK_SIZE=20
REQUEST_TIMEOUT=300
```

## 🏗️ Техническая архитектура

### Технологический стек

- **Backend**: FastAPI, SQLAlchemy 2.0, Pydantic v2
- **Frontend**: React 18, TypeScript, Vite
- **Database**: SQLite / PostgreSQL с полной `expert_id` изоляцией
- **AI Models**: OpenRouter API (Qwen 2.5-72B, Gemini 2.0 Flash, GPT-4o-mini)
- **Deployment**: Docker, Fly.io

### Структура проекта

```
backend/
├── src/
│   ├── models/       # SQLAlchemy модели с expert_id полями
│   ├── services/     # Map-Resolve-Reduce pipeline
│   │   ├── medium_scoring_service.py    # Medium Posts Reranking
│   │   ├── language_validation_service.py # Language Validation
│   │   └── drift_analysis_service.py    # Comment Drift Analysis
│   ├── api/          # FastAPI эндпоинты
│   ├── data/         # Импорт и парсинг Telegram данных
│   └── utils/        # Утилиты и конвертеры
├── prompts/          # LLM промпты (оптимизированные под модели)
├── migrations/       # Миграции БД с expert_id поддержкой
└── tests/            # Тесты валидации

frontend/
├── src/
│   ├── components/   # React компоненты с expertId поддержкой
│   ├── services/     # API клиент с SSE стримингом
│   └── types/        # TypeScript интерфейсы
└── public/           # Статика

data/
├── exports/          # Telegram JSON файлы по expert_id
└── experts.db        # SQLite база данных с мульти-экспертностью
```

### Мульти-экспертная архитектура

- **Полная изоляция данных**: Каждый пост, комментарий и результат анализа имеет `expert_id`
- **Параллельная обработка**: Все эксперты обрабатываются одновременно для снижения времени ответа
- **Масштабируемость**: Лёгкое добавление новых Telegram каналов через `expert_id`
- **SSE трекинг**: Отображение активных экспертов в реальном времени через progress events

## 🚀 Продакшен развёртывание

### Развертывание на Fly.io

```bash
# 1. Установка Fly CLI
curl -L https://fly.io/install.sh | sh
fly auth login

# 2. Деплой приложения
fly deploy

# 3. Настройка секретов
fly secrets set OPENROUTER_API_KEY=your-key-here

# 4. Проверка здоровья
curl https://experts-panel.fly.dev/health
```

## 📖 Документация

- [Pipeline Architecture](docs/pipeline-architecture.md)
- [Multi-Expert Setup](docs/multi-expert-guide.md)
- [API Documentation](http://localhost:8000/docs)
- [Development Guide](docs/development-guide.md)

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 🙏 Благодарности

- [OpenRouter](https://openrouter.ai/) за доступ к передовым AI моделям
- [FastAPI](https://fastapi.tiangolo.com/) за мощный фреймворк
- [React](https://reactjs.org/) за прекрасный UI фреймворк

---

**Experts Panel** — превращаем хаос Telegram каналов в структурированные знания 💡