# Развертывание Experts Panel на Railway

## 🚀 Что нужно для деплоя

### Обязательно:
- Railway аккаунт
- OpenAI API ключ
- GitHub репозиторий с кодом

### Опционально:
- Telegram API (для синхронизации каналов)

## 📋 Пошаговая инструкция

### 1. Подготовка репозитория

```bash
# Добавить все файлы Docker в git
git add backend/Dockerfile backend/.dockerignore
git add frontend/Dockerfile frontend/.dockerignore frontend/nginx.conf
git add docker-compose.yml railway.toml DEPLOYMENT.md

# Сделать коммит
git commit -m "feat: Add Docker configuration for Railway deployment

- Add Dockerfiles for backend and frontend
- Configure nginx with API proxy
- Add docker-compose for local development
- Create Railway configuration
- Add deployment guide

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Запушить в GitHub
git push origin master
```

### 2. Настройка проекта в Railway

1. **Зайти в Railway dashboard**
   - https://railway.app
   - Login через GitHub

2. **Создать новый проект**
   - Click "New Project" → "Deploy from GitHub repo"
   - Выбрать ваш репозиторий
   - Railway автоматически обнаружит Docker конфигурацию

3. **Настроить переменные окружения**
   - Перейти в "Variables" таб
   - Добавить обязательные переменные:

```bash
# OpenAI API (обязательно)
OPENAI_API_KEY=sk-your-real-openai-api-key

# Railway автоматически добавит:
DATABASE_URL=postgresql://user:pass@host:port/dbname
PORT=8000
RAILWAY_ENVIRONMENT=production

# Дополнительные (опционально)
PRODUCTION_ORIGIN=https://your-app.railway.app
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Telegram API (если нужна синхронизация)
TELEGRAM_API_ID=your_telegram_api_id
TELEGRAM_API_HASH=your_telegram_api_hash
TELEGRAM_CHANNEL=your_channel_name
```

### 3. Настройка базы данных

Railway автоматически создаст PostgreSQL базу данных.

**Важно:** SQLite из локальной разработки не будет работать в продакшене!

**Миграция на PostgreSQL:**

```python
# В backend/src/api/main.py нужно изменить:
# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/experts.db")

# Railway автоматически установит DATABASE_URL в PostgreSQL формат
```

### 4. Настройка домена

1. Railway автоматически предоставит домен вида: `your-app-name.railway.app`
2. В переменных окружения установить:
   ```bash
   PRODUCTION_ORIGIN=https://your-app-name.railway.app
   ```

### 5. Проверка деплоя

1. **Health Check**:
   - Открыть `https://your-app-name.railway.app/health`
   - Должен вернуть JSON со статусом

2. **API тест**:
   ```bash
   curl -X POST https://your-app-name.railway.app/api/v1/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Test query", "stream_progress": false}'
   ```

## 🛠️ Локальная разработка с Docker

### Запуск локально:
```bash
# Создать .env файл с переменными
cp backend/.env.example .env
# Добавить OPENAI_API_KEY в .env

# Запустить Docker Compose
docker-compose up --build

# Приложение будет доступно:
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

### Остановка:
```bash
docker-compose down
```

### Перезапуск с пересборкой:
```bash
docker-compose up --build --force-recreate
```

## 🔧 Troubleshooting

### Проблема: OpenAI API ключ не работает
**Решение:** Убедитесь что ключ начинается с `sk-` и активен

### Проблема: База данных не подключается
**Решение:** Проверьте DATABASE_URL в Railway variables

### Проблема: Frontend не может достучаться к backend
**Решение:** Проверьте PRODUCTION_ORIGIN переменную

### Проблема: Синхронизация Telegram не работает
**Решение:** Добавьте Telegram API переменные в Railway

### Проблема: Медленная загрузка
**Решение:** Проверьте логи в Railway dashboard

## 📊 Мониторинг

### Railway предоставляет:
- **Логи реального времени** в dashboard
- **Метрики производительности**
- **Health checks**
- **Auto-restart при падениях**

### Что мониторить:
- Ответ time API эндпоинтов
- Успешность health checks
- Размер базы данных
- OpenAI API usage (через логи)

## 🔄 CI/CD

Railway автоматически:
- Деплоит при push в main/master
- Запускает health checks
- Перезапускает при падениях
- Обновляет переменные окружения

### Для настройки custom домена:
1. Перейти в "Settings" → "Custom Domains"
2. Добавить ваш домен
3. Настроить DNS записи

## 💰 Стоимость

### Railway:
- **Хостинг**: ~$5-20/месяц (зависит от нагрузки)
- **База данных**: включена в план
- **Пользовательский домен**: ~$10/месяц

### OpenAI API:
- **GPT-4o-mini**: ~$0.15/1M tokens
- **GPT-4o**: ~$2.50/1M tokens
- **Затраты зависят от количества запросов**

## 🚀 Оптимизация для продакшена

### 1. Кэширование
- Redis для кэширования результатов
- Кэширование на уровне frontend

### 2. Мониторинг
- Sentry для error tracking
- Railway analytics

### 3. Безопасность
- Rate limiting
- CORS настройки
- Environment variables security

### 4. Масштабирование
- Horizontal scaling в Railway
- Load balancing
- Database optimization

## 📝 Checklist перед продакшеном

- [ ] GitHub репозиторий обновлен
- [ ] Все Docker файлы добавлены в git
- [ ] OpenAI API ключ добавлен в Railway variables
- [ ] Health check работает
- [ ] Frontend подключается к backend
- [ ] База данных migrated (если нужно)
- [ ] Домен настроен
- [ ] Логи проверяются
- [ ] Тестовые запросы работают

## 🆘 Поддержка

Если что-то не работает:
1. **Проверьте Railway logs** в dashboard
2. **Проверьте переменные окружения**
3. **Проверьте health check**
4. **Сравните с локальной версией**
5. **Откройте issue в репозитории**

---

**Готово!** 🎉 Ваше приложение должно быть доступно по адресу `https://your-app-name.railway.app`