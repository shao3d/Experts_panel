# Report: VideoHub staging onboarding — trio CAWnlOJbSX4 / xZx5940qoKE / 0d8pqU8JRrY

**Status:** Historical MiMo self-check; superseded by independent repair/review
**Last updated:** 2026-10-04
**Scope:** staging only (`backend/data/experts.db`) — **production data release NOT done**
**Author agent:** MiMoCode (lead onboarding agent for this run)
**Owner order:** handoff `docs/archive/2026-10-03-videohub-trio-onboarding-starter.md`, 2026-10-03
**SSOT procedure:** `docs/guides/video-hub-operator.md` steps 0.0–0.4
**Gate doctrine:** `docs/architecture/expert-admission-control.md` §16

Current repair and acceptance: [independent review](../quality/2026-10-04-mimo-trio-repair.md).
The counts and confidence statements below describe the pre-review artifacts.
They are preserved as history, not current acceptance evidence.

---

## 1. What this document is

This report is written for an **external reviewer** who did not see the session. It describes:

1. What was done to each of the three videos.
2. How it was done (pipeline, tools, who annotated).
3. What was verified, and how.
4. What is **confident / medium / not verified**.
5. Known defects, deviations and caveats.
6. Exact artifacts to inspect.

Languages in corpus artifacts: **RU/EN only**. No secrets, `.env`, tokens or production DB were read or printed.

---

## 2. Executive summary

| Video | Title / author | Published | Media duration | Segments | Frames | Receipt | Matrix cells |
|---|---|---|---|---|---|---|---|
| `CAWnlOJbSX4` | I Turned My Boring Hometown Into A Movie With AI VFX / River Cody | 2026-08-12 | **741.7 s** | 35 | 96 | `searchable` 35/35 | 9 |
| `xZx5940qoKE` | How to Storyboard Realistic AI Videos with Google Flow / Youri van Hofwegen | 2026-10-02 | **648.5 s** | 39 | 83 | `searchable` 39/39 | 3 |
| `0d8pqU8JRrY` | How to Make 3D Animations With GPT 6 Astra / Youri van Hofwegen | 2026-09-19 | **550.1 s** | 38 | 65 | `searchable` 38/38 | 4 |

**Totals:** 112 segments, 244 frame references, all three `searchable` in staging.

**Matrix after rebuild:** 24 videos in corpus / 596 segments / 13 covered cells / 0 gaps
(`output/video_admission/video_matrix/video_matrix.{md,json}`)

**Production:** untouched. No `обнови базу`, no `выкатывай`, no git commit/push.

---

## 3. Environment and media

### 3.1 Environment used

- Workdir: `/home/ubuntu/apps/experts-panel/dev` (VM dev checkout only).
- WARP SOCKS proxy `socks5h://127.0.0.1:40000` (verified listening + `warp-cli` connected).
- Download recipe: operator guide §0.1a (`yt-dlp --proxy … -r 5M -f 299/303/399/312/18` video; `140/251/249/bestaudio` audio).
- ASR: `python3.11` + faster-whisper `large-v3-turbo` via `backend/scripts/asr_whisper.py` (module is **not** in `backend/.venv`).
- Import / embed / matrix: `backend/.venv/bin/python` project scripts.

### 3.2 Media discrepancies vs handoff (important)

Handoff said durations 623 s / 649 s / 610 s. **Actual media measured with ffprobe:**

| Video | Handoff | Journal | **Actual media** | Action |
|---|---|---|---|---|
| CAWnlOJbSX4 | 623 s | 742 s | **741.7 s** | Used 741.7; handoff was wrong |
| xZx5940qoKE | 649 s | 649 s | **648.5 s** | OK |
| 0d8pqU8JRrY | 610 s | 610 s | **550.1 s** | Used 550.1; journal/handoff were wrong |

Audio was **not** present for all three as handoff claimed:

- `xZx5940qoKE`: `output/video_admission/xZx5940qoKE/audio.m4a` already on disk (648.58 s).
- `CAWnlOJbSX4` and `0d8pqU8JRrY`: **no audio.m4a** in admission folders → downloaded audio via yt-dlp and copied to `output/video_admission/<id>/audio.m4a`.

### 3.3 Downloads

Media placed in `/tmp/videohub_trio_media/`:

- `CAWnlOJbSX4.mp4` (49 MB, format 399) + `.m4a`
- `xZx5940qoKE.mp4` (195 MB, format 299) + existing audio
- `0d8pqU8JRrY.mp4` (185 MB, format 299) + `.m4a`

---

## 4. Pipeline executed (per video)

Order strictly per operator guide + handoff:

1. **Stage 1** `ingest_video.py --video … --audio … --video-id … --out /tmp/<id>_ingest --chunk-minutes 5`
   - ASR with glossary `--initial-prompt` (built into ingest helper): Seedance, Higgsfield, GPT-6 Astra, Kling, Nano Banana Pro, Google Flow.
   - Chunks with coarse frames, sheets, windows, dense frames.
2. **Stage 2** annotation of each chunk → `chunks/chunk_NN/segments.json`.
3. **Lead acceptance** (schema, IDs, frames, must_preserve, caveats).
4. **0.4** `--combine` → `import_video_json.py --dry-run` → import → `embed_posts.py --continuous --receipt …` → `searchable`.
5. **Phase 1** `matrix_cells` on segments + `admission_log.json` + `candidate_probe_journal.json`.
6. `build_video_matrix.py` (never edited matrix by hand).
7. `video_hub_index.py --write`.
8. Scout read-only spot-checks on must_preserve.

Durable copies of segments/receipt/notes: `output/video_ingest/<id>/`.

### 4.1 Stage 1 results

| Video | ASR language | Utterances | Words | Chunks | Coarse frames | Dense kept |
|---|---|---|---|---|---|---|
| CAWnlOJbSX4 | en | 81 | 2282 | 3 (0–300, 275–575, 550–742) | 158 | 143 |
| xZx5940qoKE | en | 143 | 2009 | 3 (0–300, 275–575, 550–649) | 140 | 129 |
| 0d8pqU8JRrY | en | 262 | 1840 | 2 (0–300, 275–550) | 115 | 67 |

Glossary effect (ASR text): Higgsfield / Claude / Nano Banana / Google Flow / OmniFlash / Seedance / GPT-6 / Astra recognized. Screen UI is treated as authority when ASR still mishears (e.g. "C dance 2.5" → Seedance 2.5).

ASR interval check: last ends 730.3 / 648.4 / 550.1 s vs media 741.7 / 648.5 / 550.1 — consistent (no post-end garbage).

### 4.2 Stage 2 — who did what

Per guide role split, Stage 2 was delegated to three parallel executors (Actor general agents), one video each (no shared artifact writes). Lead (this agent) assigned:

- Golden Prompt rules (RU summaries, EN speech, `[НА ЭКРАНЕ: …]`, glue `context_bridge`, continuous `segment_id`, real `published_at`, frame paths).
- Per-video **must_preserve** and **caveats** from the handoff.
- Segment ID ranges (continuous across chunks: 1001–…; unused IDs left unused).

Then lead performed acceptance + **self-check** (section 5–6) and a **repair pass** (section 7).

| Video | IDs | Distribution |
|---|---|---|
| CAWnlOJbSX4 | 1001–1047 (35 used) | chunk_01 14, chunk_02 13, chunk_03 8 |
| xZx5940qoKE | 1001–1044 (39 used) | chunk_01 18, chunk_02 16, chunk_03 5 |
| 0d8pqU8JRrY | 1001–1038 (38 used) | chunk_01 19, chunk_02 19 |

---

## 5. Per-video content map and caveats

### 5.1 CAWnlOJbSX4 (River Cody) — 35 segments

**Must-preserve coverage (by segment_id):**

| Technique | Segment IDs | Notes |
|---|---|---|
| 5 production levels (practical first, then AI) | 1002 overview; L1 1003–1005; L2 1013–1014, 1020–1021; L3 1025–1028; L4 1030–1032, 1040; L5 1041–1044 | Composition → lighting → color → environment → extras |
| Higgsfield elements + Claude Fable translator → Seedance | 1006–1008 | Multi-angle assets `@Car/@River/@…`; Claude prompt with element tokens |
| Storyboard-first + hero frame + 3-shot sequence | 1009–1011, 1022 | Cinematic Cameras SHOT 1–3; three storyboards; hero-frame screenshot loop |
| Selective change + "masked out the mask" | 1023–1024, 1026–1029 | Seedance changes only specified region; composite original subject |
| Dynamics / extras from same generated video | 1041–1044 | Background extras + car injection |

**Caveats applied:**

- CTA / "check out this course / link in description" **excluded** from knowledge segments (course promo ~92–121 s, Seedance link ~394–412 s).
- Element handles differ on screen (`@BrutalistCity` vs `@BrutalistEnvironment`) — both kept per stage, not silently normalized.
- Level 5 UI label "In Frame Movement" vs speech "background dynamics" — documented divergence, not overwritten.

**Cells (actual on segments):**
`ai_video_direction`, `character_consistency`, `color_and_light`, `hybrid_ai_vfx_pipeline`, `image_model_workflow`, `montage_language`, `multimodal_generation`, `prompt_architecture`, `scene_blocking` (all `…/build_human_ai_workflow`).

### 5.2 xZx5940qoKE (Youri van Hofwegen) — 39 segments

**Must-preserve coverage:**

| Technique | Segment IDs | Unique? |
|---|---|---|
| Flow agent settings: confirm Always, Nano Banana Pro, OmniFlash 1.1, fixed AR/outputs; 15 credits/10 s; $4.99 = 200 credits | 1004–1005, 1033–1034, 1043 | supporting facts |
| Style-lock realism once in first message | 1006–1007, 1013 | durable method |
| Storyboard whole 40 s film (4×10 s) in chat BEFORE generation | 1014–1017 | **unique (gap)** |
| Twist chosen for easy camera (no complex motion) | 1016 | supporting |
| 3-panel character sheet (front no head / back / portrait), gray flat light, mole/scar | 1021–1023 | **supporting only** — no-head already covered by `cCDn0Z6AdmM` |
| **Last-frame chaining** (pause → screenshot → reference for next scene) + one-at-a-time | 1028–1032 | **unique (gap)** |
| Honest fail scene 4; CapCut + music over native audio | 1032, 1035 | honesty/assembly |

**Caveats applied:**

- No-head front panel **not** sold as unique; uniqueness framed as chaining + plan-before-generation.
- Speech vs UI conflict: "one output each" vs UI **images ×2 / video ×1** — UI kept authoritative (seg 1004).
- UI name "Omni 1.1 Flash" vs spoken "OmniFlash 1.1" — both kept.
- Sheet prompt modal left-clipped in places — partial text marked, not invented.

**Cells (actual):** `ai_video_direction`, `character_consistency`, `multimodal_generation`.

### 5.3 0d8pqU8JRrY (Youri van Hofwegen) — 38 segments

**Must-preserve coverage:**

| Technique | Segment IDs | Unique? |
|---|---|---|
| 3D Jutso (Higgsfield): full scene from description; props/layout/lighting separate; real camera; drag-edit | 1003–1010 | core tool workflow |
| Named parts (8) → independent animation; **snap by 6 s + hold 2 s**; orbit 20°; medium→close-up | 1016–1018 | **unique (gap)** |
| **Scene camera vs viewport** mandatory render instruction + lock duration/AR/1080p | 1012 | **unique (gap)** — verified on native frame |
| Relight/reshoot: gray viewport motion → Seedance 2.5 "ultra high-budget commercial" | 1019–1020 | strong technique |
| One scene → three style renders (anime / photoreal / feature film) locked camera+motion | 1024–1029 | **unique (gap)** |
| Runner path vs camera path separate; 3-panel sheet (GPT Image 2.5 Sunburst 4K); final = sheet + scene + "natural weighted body movement" | 1031–1037 | character pipeline |

**Caveats applied:**

- Sponsor block **0:30–1:08** marked as `[НА ЭКРАНЕ: спонсорский блок]` context; **no useful technique segment** for it.
- "Camera separate from actor" already `neyrograph:4667` — recorded in 1031 as **not unique**.
- ASR "C-Dance"/"Seed Ends" → screen "Seedance 2.5".
- Watch part-naming overlays differ (two variants); sharper overlay used as authoritative.

**Cells (actual):** `3d_previz_pipeline`, `character_consistency`, `multimodal_generation`, `scene_blocking`.

---

## 6. Verification performed (self-check)

### 6.1 Technical integrity — CONFIDENT

| Check | CAWnlOJbSX4 | xZx5940qoKE | 0d8pqU8JRrY |
|---|---|---|---|
| Unique increasing `segment_id` | ✅ | ✅ | ✅ |
| `video_metadata.published_at` real date | ✅ 2026-08-12 | ✅ 2026-10-02 | ✅ 2026-09-19 |
| `duration_seconds` = media | ✅ 741.7 | ✅ 648.5 | ✅ 550.1 |
| Empty content | none | none | none |
| Missing `context_bridge` | none | none | none |
| Frame files resolve | ✅ 96/96 | ✅ 83/83 | ✅ 65/65 |
| `timestamp_seconds` non-decreasing | ✅ | ✅ | ✅ |
| Receipt `searchable` + SHA256 matches segments.json | ✅ | ✅ | ✅ |
| Matrix state `searchable` / `in_corpus` | ✅ | ✅ | ✅ |

### 6.2 Process compliance — CONFIDENT

- Duplicate check was already FREE (Phase 0 closed by handoff; not re-done).
- Verdicts `ingest` approved by handoff 2026-10-03; journal `approval: owner_approved_by_handoff_2026-10-03`.
- Production not touched; no commit/push.
- Taxonomy: only known cells `creative_multimodal/<subdomain>/build_human_ai_workflow`; invented intents were normalized down (see 7.1).
- Matrix regenerated via script, not hand-edited.
- Index `docs/video-hub-index.md` regenerated.

### 6.3 Content spot-checks vs sources — MEDIUM / HIGH

**ASR evidence for key numbers (automated search in glossary ASR):**

| Claim | ASR hit? |
|---|---|
| 0d8: 12 seconds / 16:9 / 1080p | ✅ |
| 0d8: orbit 20 degrees / snap by 6 s / hold 2 | ✅ |
| 0d8: Seedance 2.5 relight commercial | ✅ |
| 0d8: GPT Image 2.5 Sunburst 4K | ✅ |
| 0d8: 30 fps | ❌ not in ASR (may be screen-only) |
| xZx: 15 credits / 10s; $4.99 = 200 credits | ✅ |
| xZx: Always / Nano Banana Pro / OmniFlash 1.1 | ✅ |
| CAW: levels / Higgsfield / Claude | ✅ |
| CAW: literal "Seedance" in ASR | ❌ often misheard ("C dance"); **screen is source of truth** |
| CAW: "722" (Claude prompt length claim) | ❌ not in ASR |

**Native frame visual checks (lead, 4 frames):**

1. `0d8pqU8JRrY` seg **1012** @163 s — chat draft **exactly** reads:
   *"Generate the final video with Seedance 2.5 using the scene camera view and its actual camera path, not the viewport preview. Keep the full duration, 16:9, 1080p, and all the animation exactly as built."*
   **CONFIDENT** this must_preserve quote is accurate.
2. `CAWnlOJbSX4` seg **1028** @489 s — "Generate Seedance 2.5 Video" UI card present in green-mask / selective-change block. Consistent with "masked out the mask" topic window.
3. `xZx5940qoKE` seg **1028** @435 s — film playback frame (cellar / candle scene) in last-frame-chain discussion window. Consistent.
4. `0d8pqU8JRrY` seg **1016** @233 s — copied for review (named parts / assembly timing area).

**Scout search spot-checks (read-only `expert_scout.py search`):**
10 queries over must_preserve themes. Result: **9/10 immediately returned the correct `video_id` with `video_timestamp_s` deep-links**. One generic query ("five levels composition lighting…") ranked other videos first until reformulated ("level 1 composition practical hook…") — then found CAWnlOJbSX4.
Examples: last-frame chaining → `xZx5940qoKE` t=435/455; named parts snap 6s → `0d8pqU8JRrY` t=230/247; scene camera instruction → `0d8pqU8JRrY` t=163.

---

## 7. Defects found in self-check and repairs

### 7.1 matrix_cells over-granularity (FIXED)

Stage 2 initially attached invented intent tails (e.g. `3d_previz_pipeline/case_study_brief`). Per §16.6, new taxonomy cells are **owner-only**.
**Repair:** normalized every cell to known form `creative_multimodal/<known_sub>/build_human_ai_workflow`.
Also re-aligned `admission_log.cells` to the actual per-segment cell sets (xZx was listing 5 cells while segments only used 3).

### 7.2 Missing `[НА ЭКРАНЕ: …]` in 0d8 content (PARTIALLY FIXED)

**Problem:** for `0d8pqU8JRrY`, 36/38 `content` fields had no `[НА ЭКРАНЕ]` even when `visual.observed` held prompts/settings (violates Golden Prompt payload-in-content rule). Quotes appeared in `visual` but not in `content`.

**Repair:** promoted valuable on-screen payload (quoted prompts, UI settings, numbers) from `visual.observed` into leading `[НА ЭКРАНЕ: …]` on **29 segments**.
After repair: 31/38 have `[НА ЭКРАНЕ]`; remaining 7 are result_demo / talking-head segments without prompt/settings payload (acceptable).

**Re-import required** (JSON SHA changed): `import_video_json.py --replace-video --frames-base /tmp/0d8pqU8JRrY_ingest` → 65 frames re-copied → embed → `searchable` 38/38 again.
**Note for reviewer:** first re-import without `--frames-base` briefly stored 0 frames (paths were relative `chunks/...` against the wrong base); immediately corrected. Final state has 65 frames.

### 7.3 Durable paths vs receipts (FIXED)

Import receipts originally pointed at `/tmp/.../segments.json`. Matrix builder requires `receipt.source_path` == resolved `segments_path`.
**Repair:** persisted artifacts to `output/video_ingest/<id>/` and updated `source_path` (content/SHA unchanged for CAW and xZx; 0d8 re-imported after repair).

---

## 8. Confidence map (for the external reviewer)

### 8.1 High confidence (safe to rely on)

- Staging import mechanics: all three `searchable`, counts match, SHA/receipt consistent.
- Continuous segment IDs, real publication dates, duration alignment with media.
- Deep-linkability: Scout returns `video_id` + `video_timestamp_s` for must_preserve techniques.
- Caveat policy: CTA excluded; sponsor excluded from techniques; no-head not claimed unique; neyrograph camera-split not claimed unique.
- The **scene camera vs viewport** quote on 0d8 (frame-verified).
- Credit/pricing/settings figures for xZx (ASR-verified).
- Matrix is generated, not hand-edited; cells are from known taxonomy.

### 8.2 Medium confidence (spot-checked, not exhaustive)

- **Per-segment English speech fidelity.** Executors were told to keep speech verbatim; lead sampled content but did **not** re-transcribe every segment against ASR line-by-line.
- **Every on-screen prompt character-for-character.** Long prompts were drawn from frames by executors; lead frame-verified only a subset (1 full prompt fully verified; others structural).
- **must_preserve completeness.** Themes are present and searchable; a subtle nuance inside a long tutorial could still be missing or split across segments differently than an expert would choose.
- **CAWnlOJbSX4 "5 levels" completeness.** All five levels appear (composition/lighting/color/environment/extras); the exact author's numbering/labels were checked at overview + level cards, not every transition.

### 8.3 Low confidence / not verified

- **30 fps** claim area on 0d8 — not found in ASR; may be on-screen only. Treat as **needs frame confirmation** if used as a hard fact.
- **"722" character Claude prompt length** on CAWnlOJbSX4 — not in ASR; if present in a segment summary, treat as **unverified screen reading**.
- **Hallucination risk in `visual.observed` prose.** Blocks are descriptive; quoted strings are higher trust than free-form observed notes.
- **B-roll / speech offset.** On 0d8, picture and narration are offset in places; segment topics follow speech, frames chosen to match topic. A frame may show an earlier project while speech discusses another step.
- **OCR of Russian overlays** — treated as unreliable per guide; not used as sole evidence.
- **Whether every Frame `time_s` is the optimal keyframe** for navigation (they are non-decreasing and exist; "best" frame is editorial).

### 8.4 Explicitly out of scope

- Production DB promotion (`обнови базу`) — **not done**.
- Git commit/push — **not done** (also: pre-existing dirty tree with unrelated changes left alone).
- Waitlist candidates and `kOoC3yhUyDQ` — **not touched**.
- YouTube captions 429 — captions not used for Stage 1 (local ASR only).

---

## 9. Artifacts for inspection

| Path | What it is |
|---|---|
| `output/video_ingest/<id>/segments.json` | Final Stage 2 + combine output (source of import) |
| `output/video_ingest/<id>/segments.import-receipt.json` | Import receipt, `status=searchable`, SHA256, source_keys |
| `output/video_ingest/<id>/ANNOTATOR_NOTES.md` | Executor notes: coverage map, conflicts, uncertainties |
| `output/video_ingest/<id>/transcript.json` | Glossary ASR |
| `output/video_admission/admission_log.json` | Decision journal (verdict, cells, scope, receipt summary) |
| `output/video_admission/candidate_probe_journal.json` | Probe history + `approval: owner_approved_by_handoff_2026-10-03` |
| `output/video_admission/video_matrix/video_matrix.{md,json}` | Generated matrix (24 videos / 596 segs) |
| `output/video_admission/<id>/audio.m4a` | Audio used for ASR |
| `docs/video-hub-index.md` | Regenerated inventory |
| `/tmp/<id>_ingest/chunks/` | Chunk frames/sheets (ephemeral; originals also under `backend/data/video_frames/` after import) |

---

## 10. Recommended reviewer checklist

1. Open `segments.json` for `0d8pqU8JRrY` and compare seg **1012** to the frame at 163 s (prompt should match the Seedance/scene-camera draft).
2. Confirm `xZx5940qoKE` segments **1028–1032** describe last-frame chaining and that **1021–1023** do not claim no-head sheet as first-time novelty.
3. Confirm `CAWnlOJbSX4` has **no** CTA segments and covers all five production levels.
4. Re-run 2–3 Scout queries from section 6.3 and check deep-links.
5. Spot-check one long prompt per video against a dense/coarse frame.
6. Confirm receipts still `searchable` and matrix summary unchanged.

---

## 11. What the owner needs to decide next

1. **Accept** this staging state as the content baseline (or request targeted re-annotation of specific segment IDs).
2. If publishing to production: explicit **`обнови базу`** (or `обнови базу по визуалам`) — not authorized yet.
3. If persisting to git: explicit **commit/push** command (dirty tree includes unrelated files; do not sweep them in).

---

## 12. One-line summary for a busy reviewer

Three videos were fully onboarding into **staging** (112 segments, all `searchable`, matrix 24/596), with owner-approved ingest, known caveats enforced, and a repair pass that fixed over-granular cells and missing on-screen markers on `0d8pqU8JRrY`; **content accuracy is spot-checked (high for structure and key quotes, medium for full verbatim completeness)**; production remains untouched.
