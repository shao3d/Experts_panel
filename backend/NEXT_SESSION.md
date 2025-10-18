# Next Session: Telegram Comments Import

## ⚠️ CRITICAL: Fix Error Handling First!

**Problem:** Script continues on errors instead of stopping.

**Location:** `src/data/telegram_comments_fetcher.py`, line ~131-133

**Current code:**
```python
except Exception as e:
    print(f"  ⚠️  Ошибка получения комментариев для поста #{post_id}: {e}")
    return []  # ← Just continues!
```

**Fix needed:**
```python
except Exception as e:
    error_msg = str(e)
    
    # If it's just "no comments", that's OK
    if "no attribute 'replies'" in error_msg or "replies.comments" in error_msg:
        return []
    
    # But if it's PeerChannel error or similar - STOP!
    print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА для поста #{post_id}: {e}")
    print("   Остановка импорта для проверки проблемы...")
    raise  # Stop execution
```

## Credentials

- **API_ID:** (stored in .env file)
- **API_HASH:** (stored in .env file)
- **Channel:** nobilix
- **Phone:** (stored in .env file)
- **Session file:** telegram_fetcher.session (уже создана, код не нужен!)

## Run Command (After Fix)

```bash
cd /Users/andreysazonov/Documents/Projects/Experts_panel/backend

# Make sure .env file contains:
# TELEGRAM_API_ID=...
# TELEGRAM_API_HASH=...
# TELEGRAM_CHANNEL=nobilix
# TELEGRAM_PHONE=...

uv run python import_interactive.py
```

## Expected Output

```
🚀 Telegram Comments Fetcher
   Channel: @nobilix
   Phone: +380977782238
✅ Уже авторизован!

🔄 Запуск импорта комментариев...
============================================================

[1/153] Пост #5... —
[2/153] Пост #6... —
[3/153] Пост #7... ✅ 5 комментариев
...
💾 Сохранение 50 комментариев в БД...
...

✅ ИМПОРТ ЗАВЕРШЁН!
📊 Статистика:
   Обработано постов: 153
   Найдено комментариев: ~XXX
   Сохранено в БД: ~XXX
```

## After Import - Verify

```bash
sqlite3 data/experts.db "SELECT COUNT(*) FROM comments WHERE telegram_comment_id IS NOT NULL"
```

Should show number of imported Telegram comments.

## Then Continue With

1. Implement CommentGroupMapService
2. Create comment_group_map_prompt.txt
3. Update query endpoint
4. Build CommentGroupsList UI
5. Test end-to-end

See `/docs/comment_groups_architecture.md` for full architecture.
