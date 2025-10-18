---
name: sync
description: Multi-expert Telegram channels synchronization
---

# Multi-Expert Telegram Channels Sync

Синхронизируй все каналы Telegram в multi-expert системе с локальной базой данных.

## Что делаю:

1. **Multi-expert detection** - автоматически определяю всех экспертов в базе данных
2. **Preflight checks** - проверяю Telegram session и API credentials
3. **Per-expert sync** - последовательно синхронизирую каждый канал:
   - Dry-run preview (показываю что будет синхронизировано)
   - Новые посты (incremental sync от last_synced_message_id)
   - Обновление комментариев для последних 10 постов
   - Создание pending drift записей для новых постов+комментариев
4. **Multi-expert summary** - показываю результаты по каждому эксперту

## Детали процесса:

- **Multi-expert**: Автоматически определяет экспертов из БД (refat, ai_architect, neuraldeep)
- **Новые посты**: Incremental sync (только новые с last_synced_message_id для каждого канала)
- **Комментарии**: Глубина 10 постов для проверки новых комментариев (~30 дней)
- **Drift маркировка**: Создает/обновляет `comment_group_drift.analyzed_by = 'pending'`
- **Изоляция данных**: Каждый эксперт обрабатывается независимо с proper channel_id фильтрацией
- **Channel mapping**: nobilix → refat, the_ai_architect → ai_architect, neuraldeep → neuraldeep

## Алгоритм drift анализа:

1. **Новые посты + комментарии**: Создает запись в `comment_group_drift` с `analyzed_by = 'pending'`
2. **Существующие посты + новые комментарии**: Сбрасывает `analyzed_by = 'pending'`, обнуляет `drift_topics`
3. **Автоопределение expert_id**: Используется `expert_id = (SELECT expert_id FROM posts WHERE post_id = <ID>)`

## Текущие эксперты в системе:
- refat (nobilix) - channel_id: 2273349814
- ai_architect (the_ai_architect) - channel_id: 2293112404
- neuraldeep (neuraldeep) - channel_id: 1972880113

## Prerequisites:

- ✅ Telegram session authenticated (telegram_fetcher.session)
- ✅ .env file с TELEGRAM_API_ID, TELEGRAM_API_HASH
- ✅ Multi-expert база данных инициализирована
- ✅ sync_state таблица существует для всех экспертов

## Output:
- JSON в stdout с результатами по всем экспертам
- Прогресс и summary в stderr
- Автоматическая маркировка drift записей для последующей обработки

Запускаю multi-expert workflow...
