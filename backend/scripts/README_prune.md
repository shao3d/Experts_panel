# Prune Old Posts - Удаление старых постов

## Быстрый старт

```bash
# Анализ (без удаления)
python3 backend/scripts/prune_old_posts.py

# Удаление с подтверждением
python3 backend/scripts/prune_old_posts.py
# → введите 'y' для подтверждения

# Принудительное удаление (без подтверждения)
FORCE_DELETE=1 python3 backend/scripts/prune_old_posts.py
```

## Что делает скрипт

1. **Создаёт backup** в `backend/data/backups/`
2. **Анализирует** что будет удалено
3. **Удаляет в правильном порядке:**
   - Сначала `comment_group_drift` (нет CASCADE)
   - Потом `posts` (CASCADE удалит comments и links)
4. **Проверяет** корректность удаления
5. **Выполняет VACUUM** для освобождения места

## Безопасность

- ✅ Автоматический backup перед удалением
- ✅ Транзакционность (ROLLBACK при ошибках)
- ✅ Проверка orphaned records
- ✅ Foreign keys включены (PRAGMA foreign_keys = ON)

## Что удаляется сейчас

| Параметр | Значение |
|----------|----------|
| Эксперты | `polyakov`, `ai_grabli` |
| Дата отсечки | `2024-01-01` |
| Постов | 34 (25 + 9) |
| Комментариев | 10 (cascade) |
| Drift записей | 7 (вручную) |
| Ссылок | 3 (cascade) |

## Восстановление из backup

```bash
# Найти последний backup
ls -t backend/data/backups/experts.db.backup.* | head -1

# Восстановить
cp backend/data/backups/experts.db.backup.XXXXXX backend/data/experts.db
```
