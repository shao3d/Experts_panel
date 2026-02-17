# Adding New Videos (The "Video Hub" Pipeline)

**Pipeline:** `Map -> Resolve (Summary Bridging) -> Reduce (Digital Twin)`

## 🚀 Quick Command
Use the automated deployment script to import JSON and update production safely:

```bash
./scripts/deploy_video.sh path/to/video.json
```

## 📋 Prerequisite: JSON Format
Ensure your JSON file follows the **Segmented Topic Structure**:
- `topic_id`: Must change every 10-15 mins or at logical chapters.
- `segments`: Must be granular (one thought per segment).

**Example:**
```json
{
  "video_metadata": {
    "title": "My Video",
    "author": "Gleb Kudryavtcev",
    "url": "youtube_id"
  },
  "segments": [
    {
      "segment_id": 1001,
      "topic_id": "chapter_1_intro",
      "title": "Intro",
      "summary": "...",
      "content": "...",
      "timestamp_seconds": 0
    }
  ]
}
```

## 🛠️ What the script does
1.  **Backup:** Creates a local backup in `backend/data/backups/`.
2.  **Import:** Runs `backend/scripts/import_video_json.py` to add segments to local SQLite.
3.  **Compress:** Gzips the updated database.
4.  **Upload:** SFTPs the database to Fly.io (`/app/data/experts.db.gz`).
5.  **Deploy:** Unzips on server and restarts the app.

---
**Note:** This process updates the **entire** production database with your local version. Ensure your local DB is up-to-date before running this if other people are working on it (though usually you are the single source of truth).
