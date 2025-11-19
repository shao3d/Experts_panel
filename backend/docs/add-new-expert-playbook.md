# Adding a New Expert - Playbook

**Last Updated:** 2025-01-19 (Migration 009)
**Required Time:** ~5 minutes
**Prerequisites:** Telegram JSON export from expert's channel

---

## Quick Start

### Step 1: Export Telegram Channel Data

1. Open **Telegram Desktop**
2. Navigate to the target channel
3. Go to **Settings → Export chat history**
4. Select **JSON format**
5. Save to `~/Downloads/<channel>_export.json`

### Step 2: Run the Add Expert Script

```bash
cd backend

python tools/add_expert.py \
    <expert_id> \
    "<display_name>" \
    <channel_username> \
    ~/Downloads/<channel>_export.json
```

**Example:**
```bash
python tools/add_expert.py \
    ml_daily \
    "ML Daily Digest" \
    ml_daily_digest \
    ~/Downloads/ml_daily_export.json
```

**Arguments:**
- `expert_id`: Unique identifier (lowercase, no spaces, e.g., `ml_daily`)
- `display_name`: Human-readable name shown in UI (e.g., `"ML Daily Digest"`)
- `channel_username`: Telegram channel username without @ (e.g., `ml_daily_digest`)
- `json_file`: Path to exported JSON file

**Script Output:**
```
🚀 Adding expert: ml_daily

📝 Step 1/4: Adding expert metadata...
✅ Expert metadata added

📥 Step 2/4: Importing posts from ~/Downloads/ml_daily_export.json...
✅ Posts imported: 245 posts created

🔄 Step 3/4: Backfilling channel_username...
✅ Updated 245 posts with channel_username

🔍 Step 4/4: Validating...
✅ All posts have channel_username
✅ Total posts for expert: 245

🎉 Expert 'ml_daily' added successfully!
```

### Step 3: Sync Comments (Optional)

```bash
python sync_comments.py --expert-id ml_daily
```

### Step 4: Verify

**Check API:**
```bash
curl http://localhost:8000/api/v1/experts | jq '.'
```

**Check Frontend:**
```bash
open http://localhost:3000
# Refresh page (Cmd+R / Ctrl+R)
# New expert should appear in the list
```

---

## How It Works

### Architecture (Post-Migration 009)

The system now uses a **centralized expert metadata table** instead of hardcoded dictionaries:

1. **Database:** `expert_metadata` table stores all expert information
2. **Backend:** Functions query database instead of hardcoded dicts
3. **Frontend:** Fetches experts dynamically from `/api/v1/experts` API
4. **Sync Script:** Uses database to discover which experts to sync

**Benefits:**
- ✅ No code changes required to add experts
- ✅ Frontend automatically shows new experts
- ✅ Single source of truth
- ✅ No server restart needed

### What the Script Does

1. **Add to `expert_metadata` table:**
   - Stores `expert_id`, `display_name`, `channel_username`
   - Validates uniqueness constraints

2. **Import posts from JSON:**
   - Uses existing `json_parser` module
   - Associates all posts with `expert_id`
   - Extracts `channel_id` from Telegram data

3. **Backfill `channel_username`:**
   - Updates all posts with the channel username
   - Required for generating Telegram links

4. **Validate:**
   - Checks all posts have `channel_username`
   - Reports total posts imported

---

## Troubleshooting

### Problem 1: Expert Already Exists

**Error:**
```
❌ Expert already exists: ml_daily
   Error: UNIQUE constraint failed: expert_metadata.expert_id
```

**Cause:** Expert with same ID already in database

**Solution:**
```bash
# Delete existing expert
sqlite3 data/experts.db "DELETE FROM expert_metadata WHERE expert_id = 'ml_daily';"

# Delete associated posts (optional, if you want clean slate)
sqlite3 data/experts.db "DELETE FROM posts WHERE expert_id = 'ml_daily';"

# Retry
python tools/add_expert.py ml_daily "ML Daily" ml_daily_digest export.json
```

### Problem 2: JSON File Not Found

**Error:**
```
❌ File not found: exports/ml_daily.json
```

**Solution:**
- Check file path is correct (use absolute path if needed)
- Verify file was exported successfully from Telegram

### Problem 3: Posts Imported but Missing channel_username

**Symptom:**
```
⚠️  Warning: 120 posts missing channel_username
```

**Solution:**
```bash
# Manual backfill
sqlite3 data/experts.db "UPDATE posts SET channel_username = 'ml_daily_digest' WHERE expert_id = 'ml_daily';"

# Verify
sqlite3 data/experts.db "SELECT COUNT(*) FROM posts WHERE expert_id = 'ml_daily' AND channel_username IS NULL;"
# Should return: 0
```

### Problem 4: Frontend Doesn't Show New Expert

**Cause:** Browser cached old expert list

**Solution:**
```bash
# Hard refresh browser
Ctrl+Shift+R (Windows/Linux)
Cmd+Shift+R (Mac)

# Or clear cache
Open DevTools → Application → Clear Storage → Clear site data
```

### Problem 5: API Returns 500 Error

**Symptom:**
```bash
curl http://localhost:8000/api/v1/experts
# Returns 500 Internal Server Error
```

**Diagnosis:**
```bash
# Check backend logs
tail -f backend.log

# Verify database
sqlite3 data/experts.db "SELECT * FROM expert_metadata;"
```

**Common Causes:**
- Database migration not run (table doesn't exist)
- Database file permissions issue
- Backend server not running

**Solution:**
```bash
# Run migrations
sqlite3 data/experts.db < migrations/009_create_expert_metadata.sql
sqlite3 data/experts.db < migrations/010_backfill_channel_username.sql

# Restart backend
cd backend && python -m uvicorn src.api.main:app --reload
```

---

## Manual Operations

### View All Experts

```bash
sqlite3 data/experts.db "SELECT * FROM expert_metadata;"
```

### View Posts for Expert

```bash
sqlite3 data/experts.db "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM posts WHERE expert_id = 'ml_daily';"
```

### Update Expert Display Name

```bash
sqlite3 data/experts.db "UPDATE expert_metadata SET display_name = 'New Name' WHERE expert_id = 'ml_daily';"
```

### Update Channel Username

```bash
# Update metadata
sqlite3 data/experts.db "UPDATE expert_metadata SET channel_username = 'new_username' WHERE expert_id = 'ml_daily';"

# Update posts
sqlite3 data/experts.db "UPDATE posts SET channel_username = 'new_username' WHERE expert_id = 'ml_daily';"
```

### Delete Expert

```bash
# Delete from metadata
sqlite3 data/experts.db "DELETE FROM expert_metadata WHERE expert_id = 'ml_daily';"

# Optionally delete posts and comments
sqlite3 data/experts.db "DELETE FROM comments WHERE post_id IN (SELECT post_id FROM posts WHERE expert_id = 'ml_daily');"
sqlite3 data/experts.db "DELETE FROM posts WHERE expert_id = 'ml_daily';"
```

---

## Validation Checklist

After adding a new expert, verify:

- [ ] Expert appears in database: `sqlite3 data/experts.db "SELECT * FROM expert_metadata WHERE expert_id = 'new_expert';"`
- [ ] Posts imported: `sqlite3 data/experts.db "SELECT COUNT(*) FROM posts WHERE expert_id = 'new_expert';"`
- [ ] All posts have channel_username: `sqlite3 data/experts.db "SELECT COUNT(*) FROM posts WHERE expert_id = 'new_expert' AND channel_username IS NULL;"` (should be 0)
- [ ] API returns expert: `curl http://localhost:8000/api/v1/experts | grep new_expert`
- [ ] Frontend shows expert: Open http://localhost:3000 and check expert list

---

## Advanced: Batch Import Multiple Experts

```bash
#!/bin/bash
# batch_import.sh

EXPERTS=(
    "ml_daily:ML Daily Digest:ml_daily_digest:exports/ml_daily.json"
    "ai_weekly:AI Weekly:ai_weekly_news:exports/ai_weekly.json"
)

for expert in "${EXPERTS[@]}"; do
    IFS=':' read -r id name username file <<< "$expert"
    echo "Adding $id..."
    python tools/add_expert.py "$id" "$name" "$username" "$file"
    echo ""
done
```

---

## Reference: Old vs New Process

### Before Migration 009 (Hardcoded)

```python
# Had to edit backend/src/api/models.py
names = {
    'refat': 'Refat (Tech & AI)',
    'ml_daily': 'ML Daily Digest',  # ADD THIS
}

# Had to edit backend/sync_channel_multi_expert.py
CHANNEL_MAPPING = {
    'refat': 'nobilix',
    'ml_daily': 'ml_daily_digest',  # ADD THIS
}

# Had to edit frontend/src/App.tsx
new Set(['refat', 'ai_architect', 'ml_daily'])  # ADD THIS

# Then restart backend AND frontend
```

**Problems:**
- 4 files to edit
- Easy to miss one
- Code changes for data updates
- Server restart required

### After Migration 009 (Database-driven)

```bash
# One command
python tools/add_expert.py ml_daily "ML Daily" ml_daily_digest export.json

# That's it! ✅
```

**Benefits:**
- Single command
- No code changes
- No server restart
- Automatic UI update

---

## Support

**Issues:** Report at https://github.com/your-repo/issues
**Documentation:** See `../CLAUDE.md` for full architecture
**Migrations:** See `../migrations/` for database schema changes
