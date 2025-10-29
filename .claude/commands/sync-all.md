---
name: sync-all
description: Multi-expert Telegram channels synchronization
---

# Multi-Expert Telegram Channels Sync

Синхронизируй все каналы Telegram в multi-expert системе с локальной базой данных.

## Что делаю:

Выполняю полный multi-expert workflow с todo transparency:

1. **Create todo list** - создаю подробный план действий
2. **Preflight checks** - проверяю Telegram session и API credentials
3. **Multi-expert detection** - определяю всех экспертов в базе данных
4. **Dry-run preview** - запускаю `python backend/sync_channel_multi_expert.py --dry-run`
5. **User confirmation** - жду подтверждения перед реальной синхронизацией
6. **Actual sync** - запускаю `python backend/sync_channel_multi_expert.py`
7. **Results parsing** - парсю JSON output
8. **Multi-expert summary** - показываю детальные результаты по каждому эксперту
9. **Auto drift analysis** - запускаю drift-on-synced агента для pending групп

## Детальный алгоритм выполнения:

### Шаг 1: Создание todo списка
```
☐ Preflight checks (session файл, API credentials)
☐ Multi-expert detection (проверка БД на экспертов)
☐ Dry-run sync (предпросмотр изменений)
☐ User confirmation (подтверждение реального запуска)
☐ Actual sync (реальная синхронизация)
☐ Results parsing (парсинг JSON вывода)
☐ Multi-expert summary (детальный отчет)
☐ Auto drift analysis (drift-on-synced агент)
```

### Шаг 2: Preflight проверки
- Проверить наличие `backend/telegram_fetcher.session`
- Проверить переменные окружения: TELEGRAM_API_ID, TELEGRAM_API_HASH
- Проверить доступность БД `data/experts.db`
- Проверить наличие `sync_state` таблицы

### Шаг 3: Multi-expert detection
- Выполнить SQL: `SELECT DISTINCT expert_id FROM posts WHERE expert_id IS NOT NULL`
- Ожидаемые эксперты: refat, ai_architect, neuraldeep
- Показать channel mapping для каждого эксперта

### Шаг 4: Dry-run синхронизация
```bash
cd backend
python sync_channel_multi_expert.py --dry-run
```
- Показать что будет синхронизировано
- Показать новые посты и комментарии
- Показать группы которые будут помечены как `pending` для drift анализа

### Шаг 5: Запуск реальной синхронизации
```bash
cd backend
python sync_channel_multi_expert.py
```
- Incremental sync от last_synced_message_id
- **🔥 НОВАЯ ЛОГИКА**: Проверка комментариев для ВСЕХ новых постов + последние 10 постов
- **Новые посты**: создаются drift записи с `has_drift=0, analyzed_by='pending'`
- **Посты с НОВЫМИ комментариями**: drift сбрасывается в `analyzed_by='pending'`
- **Посты без новых комментариев**: drift записи НЕ трогаются
- Дедупликация комментариев: система не сохраняет дубликаты

### Шаг 6: Обработка результатов
- Спарсить JSON из stdout
- Извлечь статистику по новым постам и комментариям
- Показать детальную статистику по каждому эксперту
- Подсчитать итоговое количество pending drift групп
- **🔥 НОВОЕ**: Автоматически запустить drift-on-synced агента

### Шаг 7: Auto Drift Analysis
- **Условие**: Запускать только если есть pending drift группы
- **Агент**: drift-on-synced (специализированный для synced данных)
- **Цель**: Анализ только pending групп (не всех подряд)
- **Результат**: Детальный drift отчет по обработанным группам

### Результаты последней синхронизации (пример):
- ✅ **Новые посты**: 6 (ai_architect: 3, neuraldeep: 2, refat: 1)
- ✅ **Новые комментарии**: 592 (включая 37 для neuraldeep/1659!)
- ✅ **Pending drift групп**: 25 (автоматически обработаны drift-on-synced агентом)
- ✅ **Drift анализ**: 15 групп с drift, 10 без drift

## Технические детали:

### Channel mapping:
- refat → nobilix (channel_id: 2273349814)
- ai_architect → the_ai_architect (channel_id: 2293112404)
- neuraldeep → neuraldeep (channel_id: 1972880113)

### Скрипты для запуска:
- **Основной**: `backend/sync_channel_multi_expert.py`
- **Dry-run**: `--dry-run` флаг
- **Глубина**: 10 постов (--depth 10)

### 🚀 Ключевые улучшения (v2.0):
- **Новый метод `update_specific_posts_comments`**: Проверяет комментарии для ВСЕХ новых постов
- **Исправленная drift логика**: Только посты с НОВЫМИ комментариями сбрасывают drift
- **Надежность**: Добавлены retry механизмы для map phase
- **Дедупликация**: Система не сохраняет дубликаты комментариев

### База данных:
- Таблица: `sync_state` для tracking incremental sync
- Drift подготовка: `comment_group_drift.analyzed_by = 'pending'` и `drift_topics = NULL`
- **🔥 НОВОЕ**: Автоматический drift-on-synced анализ встроен в workflow
- **Результат**: `analyzed_by = 'drift-on-synced'` после анализа

### 🔄 Новый Workflow (v3.0):
```
/sync-all → Sync Data → Find Pending Groups → Run drift-on-synced → Analysis Complete
```

**Старый workflow (для сравнения):**
```
/sync-all → Sync Data → Manual drift-extraction → Separate command
```

## Prerequisites:

- ✅ Файл `backend/telegram_fetcher.session` существует
- ✅ .env файл содержит TELEGRAM_API_ID, TELEGRAM_API_HASH
- ✅ Multi-expert БД инициализирована
- ✅ sync_state таблица существует

## Ожидаемый output:

### Dry-run:
- JSON preview с new_posts и new_comment_groups
- Статистика по каждому эксперту
- Запрос подтверждения

### Actual sync:
- JSON с результатами синхронизации
- Детальная статистика по каждому эксперту
- **Новые посты**: Все добавляются в БД с drift=0, analyzed_by='pending'
- **Новые комментарии**: Собираются для ВСЕХ новых постов (новая логика!)
- **Pending drift группы**: Только посты с новыми комментариями сбрасывают drift
- Multi-expert summary report
- **🔥 НОВОЕ**: Автоматический drift-on-synced анализ
- **Полный результат**: Данные готовы к запросам за один запуск
- **Workflow**: Sync → Drift Analysis → Ready for queries

### Drift Analysis Results:
- **Обработано групп**: 25 pending групп (пример)
- **С drift**: 15 групп (пример)
- **Без drift**: 10 групп (пример)
- **Успешность**: 100% (все pending группы обработаны)
- **Время анализа**: ~1-3 минуты
- **Итог**: Все данные готовы к использованию!

## Error handling:

Если preflight checks не проходят:
- Показать конкретную ошибку
- Дать инструкции по исправлению
- Предложить retry после исправления

Запускаю multi-expert workflow с todo transparency...