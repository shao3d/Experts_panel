# Adding New Videos (The "Video Hub" Pipeline)

**Pipeline:** `Map -> Resolve (Summary Bridging) -> Reduce (Digital Twin)`

## 🚀 Quick Command
Use the automated deployment script to import JSON and update production safely:

```bash
./scripts/deploy_video.sh path/to/video.json
```

> **Важно:** `deploy_video.sh` сам по себе **не вызывает Gemini / Vertex AI**. Он импортирует готовый JSON в SQLite и выкатывает обновлённую БД. Сам Video Hub отвечает через Vertex AI уже позже, во время реального query runtime.

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
5.  **Deploy:** Atomic operation on server:
    *   Deletes old WAL/SHM files (prevents corruption).
    *   Unzips new DB over old one.
    *   Fixes permissions (`chown appuser:appuser`).
    *   Restarts the app.

## 🔎 Important Runtime Note

- `deploy_video.sh` does **not** generate embeddings for fresh video segments.
- If you need new video segments to participate in Hybrid Search immediately, run:

```bash
python3 backend/scripts/embed_posts.py --continuous
```

- This embedding step uses the same Vertex AI credentials from `backend/.env`.

## 🐛 Troubleshooting

### "Timed out waiting for SSH connectivity"
If the script fails with this error after 45 seconds:
1.  **Check Status:** Run `fly status` manually. The machine might be in a crash loop.
2.  **Check Logs:** Run `fly logs` to see if the app is starting correctly.
3.  **Retry:** Sometimes Fly.io instances take longer to wake up. Just run the script again.

### "Permission denied" on DB
The script automatically runs `chown appuser:appuser`. If you still see permission errors in logs:
- Ensure the Dockerfile still creates the `appuser`.
- Check if the volume mount path in `fly.toml` matches `/app/data`.

---
**Note:** This process updates the **entire** production database with your local version. Ensure your local DB is up-to-date before running this if other people are working on it (though usually you are the single source of truth).
