# Experts Panel 🔍

[![Deploy to Fly.io](https://github.com/shao3d/Experts_panel/actions/workflows/deploy-fly.yml/badge.svg)](https://github.com/shao3d/Experts_panel/actions/workflows/deploy-fly.yml)
[![CI/CD Pipeline](https://github.com/shao3d/Experts_panel/actions/workflows/ci.yml/badge.svg)](https://github.com/shao3d/Experts_panel/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-61dafb.svg)](https://reactjs.org/)

Интеллектуальная платформа для анализа дискуссий в Telegram-каналах с использованием 8-фазной архитектуры Map-Resolve-Reduce и гибридной системы реранкинга Medium постов с улучшенным UI для отслеживания прогресса.

**🌐 Live Demo:** https://experts-panel.fly.dev

## 🚀 Особенности

- **8-фазная Map-Resolve-Reduce архитектура** - эффективная обработка больших объемов сообщений с гибридным реранкингом и валидацией языка
- **Enhanced Progress UI** - улучшенный интерфейс с отображением активных экспертов, контекстными сообщениями и предупреждениями
- **Medium Posts Hybrid Reranking** - интеллектуальная система оценки и отбора релевантных постов (threshold ≥0.7 + top-5)
- **Умный поиск по контексту** - находит связанные посты через анализ ссылок и упоминаний с дифференциальной обработкой
- **Multi-Expert поддержка** - параллельная обработка данных от нескольких экспертов с полной изоляцией
- **Real-time прогресс** - SSE для отслеживания состояния обработки запроса с контекстными описаниями фаз
- **OpenRouter Multi-Model стратегия** - использование специализированных моделей для каждой фазы
- **Экспертные комментарии** - поддержка аннотаций от экспертов
- **Визуализация источников** - удобный просмотр найденных постов

## 🚀 Quick Start

### 🌐 Try Live Demo
Visit **[experts-panel.fly.dev](https://experts-panel.fly.dev)** to try the application without installation.

### 🛠 Local Development

#### Prerequisites
- Python 3.11+
- Node.js 18+
- OpenRouter API key (for Qwen 2.5-72B, Gemini 2.0 Flash, GPT-4o-mini)

#### Installation

**Backend:**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env
```

**Frontend:**
```bash
cd frontend
npm install
```

#### Run Locally

**1. Start Backend:**
```bash
cd backend
uv run uvicorn src.api.main:app --reload --port 8000
```

**2. Start Frontend:**
```bash
cd frontend
npm run dev
```

**3. Access Application:**
- Frontend: http://localhost:3001
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 🚀 Fly.io Deployment (Recommended)

The application is automatically deployed to [Fly.io](https://fly.io) via GitHub Actions CI/CD.

**Manual Deployment:**
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Deploy
fly deploy
```

**Features:**
- ✅ Automatic HTTPS
- ✅ Zero-downtime deployments
- ✅ Health monitoring
- ✅ Persistent storage for SQLite database

### 🐳 Docker Deployment

```bash
# Build and run locally
docker build -t experts-panel .
docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY=your_key_here \
  experts-panel
```

### 📊 Environment Setup

**Required Secrets:**
- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `FLY_API_TOKEN` - Fly.io deploy token (for CI/CD)

## 📚 API Endpoints

### Основные endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/query` | Выполнить поисковый запрос (SSE) |
| GET | `/api/v1/posts/{post_id}` | Получить детали поста |
| POST | `/api/v1/import` | Импортировать JSON файл |
| GET | `/api/v1/import/status/{job_id}` | Статус импорта |
| GET | `/health` | Проверка здоровья системы |
| GET | `/api/info` | Информация об API |

### Пример запроса

```bash
# Простой поисковый запрос
curl -X POST "http://localhost:8000/api/v1/query" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Какие основные темы обсуждаются в канале?",
       "max_posts": 100,
       "include_comments": true,
       "stream_progress": true
     }'

# Получение деталей поста
curl "http://localhost:8000/api/v1/posts/1"

# Запрос с фильтрацией по экспертам
curl -X POST "http://localhost:8000/api/v1/query" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Какие основные темы обсуждаются в канале?",
       "expert_filter": ["expert1", "expert2"],
       "stream_progress": false
     }'
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

### 8-фазная архитектура Map-Resolve-Reduce

1. **Map Phase** - Qwen 2.5-72B находит релевантные посты (HIGH/MEDIUM/LOW классификация)
2. **Medium Scoring Phase** - Qwen 2.5-72B оценивает Medium посты (≥0.7 threshold + top-5 отбор)
3. **Differential Resolve Phase** - HIGH посты обрабатываются через Resolve, отобранные Medium обходят Resolve
4. **Reduce Phase** - Gemini 2.0 Flash синтезирует ответ
5. **Language Validation Phase** - Qwen 2.5-72B валидирует язык ответа и переводит при необходимости
6. **Comment Groups Phase** - GPT-4o-mini находит релевантные дискуссии в комментариях
7. **Comment Synthesis Phase** - Gemini 2.0 Flash извлекает дополнительные инсайты
8. **Response Building** - Формирование финального multi-expert ответа

#### Enhanced Progress UI Features

- **Real-time Expert Count**: Отображение количества активных экспертов во время обработки
- **Contextual Phase Messages**: Понятные описания для каждой фазы обработки
- **Warning Indicators**: Визуальные предупреждения для долгих процессов (>300 секунд)
- **Frontend-only Final Results Phase**: Финальная фаза для определения завершения
- **Enhanced Resolve Phase**: Комбинированный статус resolve + medium_scoring событий

#### Medium Posts Hybrid Reranking

- **Двухэтапный фильтр**: порог ≥0.7 → топ-5 по наивысшему score
- **Управление памятью**: максимум 50 Medium постов обрабатывается
- **Дифференциальная обработка**: HIGH → Resolve, Medium → напрямую к Reduce
- **Multi-Expert поддержка**: полная изоляция данных между экспертами

### Логирование

Система использует комплексную систему логирования:
- Консольный вывод с цветовой кодировкой
- Файловые логи в `backend/logs/`
- SSE события для real-time мониторинга

## 🏗️ Architecture

### 8-Phase Map-Resolve-Reduce Pipeline

1. **Map Phase** - Qwen 2.5-72B находит релевантные посты (HIGH/MEDIUM/LOW классификация)
2. **Medium Scoring Phase** - Qwen 2.5-72B оценивает Medium посты (≥0.7 threshold + top-5 отбор)
3. **Differential Resolve Phase** - HIGH посты обрабатываются через Resolve, отобранные Medium обходят Resolve
4. **Reduce Phase** - Gemini 2.0 Flash синтезирует ответ
5. **Language Validation Phase** - Qwen 2.5-72B валидирует язык ответа и переводит при необходимости
6. **Comment Groups Phase** - GPT-4o-mini находит релевантные дискуссии в комментариях
7. **Comment Synthesis Phase** - Gemini 2.0 Flash извлекает дополнительные инсайты
8. **Response Building** - Формирование финального multi-expert ответа

### Multi-Model Strategy
- **Qwen 2.5-72B**: Map phase, Language Validation
- **Gemini 2.0 Flash**: Reduce phase, Comment Synthesis
- **GPT-4o-mini**: Comment Groups matching, Medium posts scoring

## 🧪 Testing

```bash
# Run validation tests
python tests/test_queries.py

# Performance check
python tests/test_queries.py --performance-check
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

**Development Setup:**
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📞 Support

For questions and support:
- 🐛 Create an [Issue](https://github.com/shao3d/Experts_panel/issues)
- 📖 Check [Documentation](docs/)
- 🚀 Try [Live Demo](https://experts-panel.fly.dev)

---

🤖 Generated with [Claude Code](https://claude.ai/code) • Deployed on [Fly.io](https://fly.io)