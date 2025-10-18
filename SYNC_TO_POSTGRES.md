# Синхронизация SQLite → PostgreSQL для Railway

## Назначение

Скрипт `sync_to_postgres.py` предназначен для переноса данных из локальной SQLite базы данных в PostgreSQL базу данных на Railway.

## Когда использовать

1. **Первый деплой на Railway** - когда нужно перенести локальные данные в продакшн
2. **Обновление данных** - когда локальная база была обновлена и нужно синхронизировать изменения
3. **Восстановление данных** - если данные в PostgreSQL были повреждены или удалены

## Подготовка

### 1. Убедитесь что PostgreSQL сервис добавлен в Railway

В Railway dashboard должен быть добавлен PostgreSQL сервис. После добавления Railway автоматически создаст переменную окружения `DATABASE_URL`.

### 2. Получите DATABASE_URL из Railway

В Railway dashboard:
1. Перейдите в ваш проект
2. Выберите PostgreSQL сервис
3. Перейдите в таб "Variables"
4. Скопируйте значение `DATABASE_URL`

### 3. Убедитесь что локальная база актуальна

Проверьте что локальная база данных `data/experts.db` содержит все необходимые данные:

```bash
# Проверить количество постов
sqlite3 data/experts.db "SELECT COUNT(*) FROM posts;"

# Проверить наличие комментариев
sqlite3 data/experts.db "SELECT COUNT(*) FROM comments;"

# Проверить drift анализ
sqlite3 data/experts.db "SELECT COUNT(*) FROM comment_group_drift WHERE has_drift=1;"
```

## Использование

### Способ 1: Через переменные окружения

```bash
# Установите DATABASE_URL
export DATABASE_URL="postgresql://user:password@host:port/dbname"

# Запустите скрипт
cd backend
python sync_to_postgres.py
```

### Способ 2: Прямо в командной строке

```bash
cd backend
DATABASE_URL="postgresql://user:password@host:port/dbname" python sync_to_postgres.py
```

### Способ 3: Через .env файл

Создайте или обновите `.env` файл:

```bash
# Добавьте в .env
DATABASE_URL="postgresql://user:password@host:port/dbname"
SQLITE_DB_PATH="data/experts.db"
```

Затем запустите:

```bash
cd backend
python sync_to_postgres.py
```

## Что делает скрипт

### Таблицы которые копируются:

1. **posts** - основной контент с постами
2. **links** - ссылки между постами
3. **comments** - комментарии к постам
4. **sync_state** - состояние синхронизации Telegram
5. **comment_group_drift** - результаты drift анализа

### Особенности обработки:

- **JSON поля**: drift_topics преобразуются из SQLite TEXT в PostgreSQL JSON
- **Очистка данных**: PostgreSQL таблицы очищаются перед копированием (TRUNCATE CASCADE)
- **Сохранение зависимостей**: копирование идет в правильном порядке для сохранения foreign keys
- **Обработка ошибок**: откат изменений при ошибке любой таблицы

## Пример вывода

```
============================================================
🔄 СИНХРОНИЗАЦИЯ SQLITE → POSTGRESQL
============================================================

🔄 Начинаю синхронизацию SQLite → PostgreSQL
   Источник: data/experts.db
   Назначение: railway.db.railway.app:5432/dbname

✅ Подключения к базам данных установлены

📋 Копирование таблицы: posts
  ✅ Скопировано 156 записей в таблицу posts

📋 Копирование таблицы: links
  ✅ Скопировано 89 записей в таблицу links

📋 Копирование таблицы: comments
  ✅ Скопировано 1245 записей в таблицу comments

📋 Копирование таблицы: sync_state
  ✅ Скопировано 3 записей в таблицу sync_state

📋 Копирование таблицы: comment_group_drift
  ✅ Скопировано 156 записей в таблицу comment_group_drift

🎉 Синхронизация успешно завершена!
   Теперь можно перезапустить деплой на Railway
```

## После синхронизации

1. **Перезапустите деплой на Railway**
   - Railway должен автоматически перезапуститься после успешной синхронизации
   - Проверьте что health check проходит успешно

2. **Проверьте работу приложения**
   ```bash
   curl https://your-app.railway.app/health
   ```

3. **Сделайте тестовый запрос**
   ```bash
   curl -X POST https://your-app.railway.app/api/v1/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Тестовый запрос", "stream_progress": false}'
   ```

## Troubleshooting

### Ошибка: variable "DATABASE_URL" not set

**Решение**: Убедитесь что переменная окружения DATABASE_URL установлена перед запуском скрипта.

### Ошибка: connection to server... failed

**Решение**: Проверьте что DATABASE_URL правильный и PostgreSQL сервис запущен в Railway.

### Ошибка: permission denied for database

**Решение**: Проверьте права доступа пользователя в DATABASE_URL. Возможно нужно создать пользователя с правами на запись.

### Ошибка: table "posts" does not exist

**Решение**: Убедитесь что PostgreSQL база данных проинициализирована. Railway делает это автоматически, но если база пустая, может потребоваться инициализация схемы.

### Ошибка: column "expert_id" does not exist

**Решение**: Убедитесь что миграции применены в PostgreSQL. Railway может не иметь последних миграций.

## Автоматизация

Для регулярной синхронизации можно добавить скрипт в CI/CD pipeline:

```yaml
# .github/workflows/sync-to-railway.yml
name: Sync to Railway

on:
  push:
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Sync to PostgreSQL
        env:
          DATABASE_URL: ${{ secrets.RAILWAY_DATABASE_URL }}
        run: |
          cd backend
          python sync_to_postgres.py
```

## Безопасность

- **Не храните DATABASE_URL в git** - используйте secrets
- **Используйте read-only пользователь** если нужна только синхронизация
- **Создавайте бэкапы** перед синхронизацией в production
- **Проверяйте права доступа** пользователя в PostgreSQL

## Альтернативы

Для более сложных сценариев можно использовать:

1. **pg_dump/pg_restore** для полной миграции
2. **DBeaver** или другие GUI инструменты
3. **Railway console** для прямого доступа к базе данных
4. **Custom migration scripts** для специфических преобразований данных