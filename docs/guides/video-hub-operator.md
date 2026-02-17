# 🎥 Video Hub Operator Playbook

**Role:** Expert Digital Twin Creator
**Status:** Active Workflow
**Owner:** System Architect (Gemini CLI)

---

## 🎯 Objective
Transform raw video content (YouTube/MP4) into a structured Knowledge Graph (Segments & Topics) for the Expert Panel.

---

## 🧠 Phase 1: Segmentation (AI Studio)

Use **Google AI Studio** with the prompt below to generate JSON.

### 📝 The Golden Prompt (System Instructions)
*Copy this into AI Studio System Instructions:*

```text
Ты — Senior AI Knowledge Architect. Твоя задача — провести глубокий мультимодальный анализ видео и превратить его в структурированную базу знаний (Knowledge Nodes).

ПРАВИЛА АНАЛИЗА:
1. ВИЗУАЛЬНЫЙ КОНТЕКСТ (MULTIMODAL): Описывай, что происходит на экране (код, схемы, слайды) в квадратных скобках [НА ЭКРАНЕ: ...].
2. СЕМАНТИЧЕСКИЕ ГРАНИЦЫ: Один сегмент = одна законченная мысль. Не режь на полуслове.
3. ПРАВИЛО "КЛЕЯ": Конец сегмента N дублируется в начале сегмента N+1 (1-2 предложения).
4. ТЕМАТИЧЕСКИЕ НИТИ (TOPIC_ID): 
   - Группируй сегменты одной темы под одним ID.
   - ВАЖНО: Меняй topic_id при смене логического блока (главы) или каждые 10-15 минут.
   - ИЗБЕГАЙ гигантских тем на все видео. Используй гранулярные ID: "rag_intro", "rag_architecture".
5. ДОСЛОВНОСТЬ: Речь автора сохраняй дословно.

ФОРМАТ ВЫХОДА (JSON):
{
  "video_metadata": { "title": "...", "author": "Gleb Kudryavtcev", "url": "...", "duration_seconds": 0 },
  "segments": [
    {
      "segment_id": 1001,
      "topic_id": "slug",
      "title": "Заголовок",
      "summary": "Резюме",
      "content": "[НА ЭКРАНЕ: ...] Текст...",
      "timestamp_seconds": 123
    }
  ]
}
```

---

## 🎬 Phase 2: Processing Scenarios

### Scenario A: Short Video (< 30 min)
1.  Generate **one JSON file** covering the entire video.
2.  Save as `video.json`.
3.  Deploy:
    ```bash
    ./scripts/deploy_video.sh video.json
    ```

### Scenario B: Long Video (> 30 min)
**Strategy:** "Overlap & Merge" (Нахлест и Склейка).

1.  **Generate Part 1:**
    *   Input: First 35 mins.
    *   User Prompt: "Analyze video content from 00:00 to 35:00. Finish at a logical pause."
    *   Save JSON (`part1.json`).

2.  **Generate Part 2:**
    *   Input: From 30:00 to End.
    *   User Prompt: "Analyze video content starting from timestamp 30:00 to the end. Ignore the intro, begin with the first complete thought after 30:00."
    *   *Note:* It is normal for `segment_id` to reset to 1001 here. Gemini CLI will renumber them.
    *   Save JSON (`part2.json`).

3.  **Merge & Deploy (Via Gemini CLI):**
    *   **Action:** Paste both JSON parts directly into the Gemini CLI chat.
    *   **Command:** *"Here are Part 1 and Part 2. Merge them, check the overlap, and deploy."*

### 🤖 Gemini Agent Protocol (For AI)
*When instructed to execute "Merge & Deploy", follow this precise workflow:*
1.  **Receive:** Wait for user to provide Part 1 and Part 2 JSON blocks.
2.  **Validate:** Check syntax (fix trailing commas, ensure `segments` array exists).
3.  **Smart Merge Logic:**
    *   Identify the last segment of Part 1.
    *   Find the corresponding/overlapping segment in Part 2 (match by `title` or `content` context).
    *   **Slice:** Keep Part 1 entirely. Remove overlapping segments from Part 2.
    *   **Re-index:** Update `segment_id` in Part 2 starting from `(Part 1 Max ID + 1)`.
    *   **Stitch Topics:** If `topic_id` at the seam is identical, keep it.
4.  **Execute:**
    *   Save merged content to `merged_video.json`.
    *   Run `./scripts/deploy_video.sh merged_video.json`.
    *   Delete `merged_video.json` upon success.

---

## 🐛 Troubleshooting

### Common Issues
1.  **"Timed out waiting for SSH connectivity"**:
    *   The deployment script waits 45s for the machine to wake up.
    *   **Fix:** Just run the script again. Fly.io cold starts can be slow.

2.  **"JSON Parse Error"**:
    *   AI Studio sometimes outputs invalid JSON (trailing commas, missing brackets).
    *   **Fix:** Paste the JSON into Gemini CLI and ask: *"Fix this JSON syntax"*.

3.  **"Lost Middle" (Missing Content)**:
    *   If a video is long (60m+) and you try to do it in one pass, the output will be truncated.
    *   **Fix:** Use **Scenario B** immediately.

---

## 🛠️ Maintenance
- **Script Location:** `scripts/deploy_video.sh`
- **Database:** `backend/data/experts.db` (Local & Prod synced via script)
