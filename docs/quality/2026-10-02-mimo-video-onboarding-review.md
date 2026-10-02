# Independent review of MiMo VideoHub onboarding

Status: Repair accepted; scoped visual data release completed
Last updated: 2026-10-02

## Verdict

Initial review rejected the annotation despite successful imports. The owner
then authorized repair. All three videos have now been repaired, replacement
imported into staging, reindexed and checked through live Scout queries.
Downloaded media, ASR and existing frames were reused. Production promotion
completed on 2026-10-02 through the owner-authorized scoped visual release. The initial findings below are retained as audit history;
the repair acceptance and effort account follow.

Input handoff: `output/video_review/2026-10-02/REVIEW.md`.
Reviewed commit: `519ec04`. The initial review was read-only; the subsequent
owner-authorized repair changed staging through the existing import scripts.
Production contents were not independently read.

## Scope and checks

| Video | Segments | Chunks | Receipt and recomputed source keys |
|---|---:|---:|---|
| `AgUATWAOaKY` — Dan Kieft, AI editing | 24 | 6 | Pass |
| `cCDn0Z6AdmM` — Yapper, Naruto film | 21 | 4 | Pass |
| `FJfMTvZvX7w` — Dan Kieft, iPhone footage | 12 | 3 | Pass |

All 57 segment IDs are unique within their videos. All expected chunk JSONs
and all 69 referenced frame files exist. Each receipt matches the source SHA256,
has `searchable` status and the expected indexed count. Source keys and
cell-to-source mappings were independently recomputed from the annotation and
match the receipts. These are receipt checks, not a fresh scan of every database
index. Three targeted sources were additionally read through a fresh Scout run.

All 57 summaries and attached representative frames were screened. Risky
screen claims were inspected at native resolution, with adjacent frames used
to locate the actual evidence. This was not a frame-by-frame re-annotation of
all three videos, nor an independent retranscription of the audio.

Normalized five-word overlap with local ASR was 89.07%, 87.78% and 93.10%
respectively. Low-overlap passages were inspected; many are promotion, filler,
example dialogue or differences between captions and ASR. These percentages
are diagnostic text overlap, not completeness scores. The main confirmed loss
is in screen-only instructions.

Machine checks and inspection sheets:
`output/video_review/2026-10-02/independent_checks.json` and
`output/video_review/2026-10-02/*-attached-frames.jpg`.

## P1 — restore screen instructions and honest verbatim labels

`FJfMTvZvX7w`, segment **3006**, source `video_hub:292339432`:
the native frame at **325s** contains a long, readable prompt. The annotation
reduces it to an oral description. Missing details include preserving complete
source audio/dialogue, changing only voice identity, and assigning separate
roles to `@Video1` and `@Image1`–`@Image4`. The prompt explicitly distinguishes
the face/background, hat, exact shirt text and poster references.

`AgUATWAOaKY`, segment **2008**, source `video_hub:36004206`:
the purported full prompt has ellipses and omits visible instructions. At
**385s**, the screen specifies preserving unsaved edits and original timeline
audio, matching marker positions, and completion/polling behaviour. The saved
annotation does not preserve this full procedure. Segment **2003** also puts
an arrow-separated paraphrase into `showcase_prompt_verbatim`.

Repair: transcribe readable prompts from their actual native frames; mark
partial quotations and paraphrases honestly. Review every nonempty
`showcase_prompt_verbatim` field in this batch.

## P1 — correct evidence frames, timestamps and factual contradictions

Confirmed examples:

- **2008 / AgUATWAOaKY:** link at **320s** shows the Premiere timeline, not the
  claimed full prompt. The prompt is visible later, including **385s**.
- **1021 / cCDn0Z6AdmM:** attached **880s** frame shows the film; the complete
  cost table is visible at **915s**. The quoted cost amounts themselves match
  the later table.
- **1009 / cCDn0Z6AdmM:** declared range **275–300s** contains text spoken
  around **316–395s**. Its screen annotation concerns the earlier character
  sheet rather than the fight-opening workflow.
- **3006 / FJfMTvZvX7w:** annotation says `SD25/p`; the native **305s** frame
  identifies the skill as **`sd25-pe`**, with file `SD25-prompt optimizer.md`.
- **1020 / cCDn0Z6AdmM:** annotation claims **2K / 2560×1440**. The **905s**
  native frame shows **4K / 3840×2160**; the speech also says 4K.
- **1015 / cCDn0Z6AdmM:** summary says six beats of 30 seconds each, while the
  preserved speech says **six beats across 30 seconds**, about five seconds
  per beat. The summary must agree with the source.

There is a systematic evidence-selection problem: the 69 frame references
contain only 62 unique paths, and distinct references within a segment were
sometimes replaced with the same image. For example, chunk 2008 references
320s and 430s; the combined artifact references 320s twice. Segments 2009 and
2020 retain screen markers at 430s and 1190s while their replacement frames
are at 500s and 1275s. File existence cannot establish semantic correspondence.

Repair: inspect all screen claims against actual frames, restore multiple
frames where a procedure spans several screens, and align speech ranges and
navigation timestamps. Do not repair missing evidence by an arbitrary nearby
frame or move interval boundaries merely to satisfy validation.

## P2 — finish Phase 1 matrix reconciliation

The receipt and segment annotations contain **8 / 8 / 5** cells, but generated
matrix records retain only **4 / 4 / 3**. `video_record()` intentionally filters
receipt cells by the approved admission entry. The entries were not reconciled
with the final segmentation, so some actual contributions are absent from the
matrix. For example, iPhone montage and prompt-architecture contributions are
missing from that video's matrix record.

Review the additional assignments, reconcile approved existing cells with the
final evidence, then rebuild the matrix. Do not blindly add every proposed cell.
The report's “0 gaps” is a property of this taxonomy/map, not proof that video
content was captured without omissions.

## P2 — keep corrections reproducible

Combined artifacts include timestamp/range corrections absent from their
chunk JSONs: AgUATWAOaKY 2009/2020 and cCDn0Z6AdmM 1002/1003/1004/1008.
Ordinary relative-to-absolute frame path normalization is expected, but these
semantic changes are not just normalization. Correct chunk sources first and
combine again, so a later rebuild does not restore the errors.

The handoff also names nonexistent generic `scout_probe1/2.md` paths for two
videos. Actual probe files exist as `scout_cd_probe1/2.md` and
`scout_fj_probe1.md`; fix the references during handoff cleanup.

## Downstream reproduction

Fresh read-only Scout run:
`output/scout_runs/20261002-062857-1166693` — 41s, 17 tool calls, exit 0,
integrity exit 0, three fully read cited sources.

Scout repeated **`/SD25/p` as screen-confirmed** and directed the full-prompt
question to **320s**. It correctly noticed the abbreviated prompt and derived
the correct 30-second total from the speech despite the bad summary. Thus
citation integrity succeeds while incorrect source annotations still produce
incorrect answers. Improve the source annotation rather than trying to prompt
Scout to infer what the original screen contained.

## Minimal acceptance after repair

1. Correct all screen prompts, exact names/numbers and their evidence frames;
   reconcile speech intervals in the affected segments. Reuse existing media.
2. Apply corrections to chunk JSONs, combine, and inspect the resulting diff.
3. Perform an authorized replacement import and refresh indexing receipts;
   old receipts become stale as soon as source JSON changes.
4. Reconcile approved matrix cells and rebuild the matrix.
5. Repeat the three failing Scout questions and add the 4K/upscale question.
   Check actual frames as well as citation integrity.
6. Promote corrected data only with the owner's data-release authorization.

For this first reviewed MiMo batch, detailed screen verification is warranted
across all three videos. Repeating the entire ingest pipeline is not warranted.
Keep the same acceptance requirements for every model; deterministic checks
alone cannot validate what is written on an image.


## Repair acceptance — 2026-10-02

| Video | Corrected source annotations | Frame references before → after | Verified matrix cells before → after |
|---|---:|---:|---:|
| FJfMTvZvX7w — iPhone footage | 12 | 14 → 23 | 3 → 5 |
| AgUATWAOaKY — editing course | 24 | 28 → 67 | 4 → 8 |
| cCDn0Z6AdmM — Naruto film | 21 | 27 → 45 | 4 → 8 |

Every screen annotation was checked against contact sheets; precise text and
numbers were checked in native frames. All 57 visual annotations were revised.
This does not mean all 57 originally contained a critical error.

- **iPhone footage:** restored `sd25-pe`, the complete visible user prompt at
  325s, separate video/image roles, audio preservation, Pen Mask composition,
  and the visible knight-shot prompt with its five actions, camera and audio.
- **Editing course:** restored marker/export/completion/live-timeline safeguards,
  including unsaved edits, original audio, exact In/Out and matching jobs to
  clips. Fixed screen anchors, the character-sheet completeness claim, grading
  and sound instructions. Removed unrelated duplicated speech from the dedicated
  screen-document segment. Corrected the 2005 speech boundary from 280–300s to
  273.3–301.5s after ASR matching. Recorded the source's own VFX discrepancy:
  spoken 107/279/567 versus on-screen 110/259/306/556/588. The new camera must
  not make the performer turn toward it; source voice, breaths and speed remain.
- **Naruto film:** aligned the early speech intervals and actual screen frames;
  corrected six beats **within** 30 seconds, **4K / 3840×2160**, and the complete
  cost-table anchor at 915s. Recorded 480p speech versus the visible 720p UI
  state at 440s, and unequal beat intervals, rather than silently merging them.
- **Matrix:** reviewed the additional existing cells with concrete supporting
  segments, reconciled admission entries and rebuilt the generated matrix.
  Corrected probe filenames, the skill name and the six-clips/six-beats wording
  in the admission metadata. No new taxonomy or runtime mechanism was added.

Authoritative repaired annotations live in the 13 original chunk JSONs.
A fresh combine of each video is byte-identical to its accepted combined JSON.
The acceptance script independently recomputes all 57 source keys and cell
mappings, validates source hashes/readiness receipts, existing frame paths,
unique per-segment frame references, navigation/range bounds and chunk equality.
All 57 segments are confirmed indexed by the import/embedding readiness check;
all 135 frame references pass structural checks. Embedding errors: zero.

Reproducible evidence:

- `output/video_review/2026-10-02/verify_repair.py`
- `output/video_review/2026-10-02/repair-verification.json`
- `output/video_review/2026-10-02/repair-effort.json`
- Each video's refreshed `post-import-verification.json`; original MiMo checks
  retained as `post-import-verification.mimo-before-repair.json`.

Three live Sol Scout runs passed citation integrity and manual answer review:

| Run | Seconds | Tool calls | Questions checked |
|---|---:|---:|---|
| `20261002-064530-1172464` | 26 | 3 | Exact skill name, audio, two-role mask |
| `20261002-065325-1175192` | 58 | 7 | B/C safeguards, VFX discrepancy, beats, 4K, budget, partial prompts |
| `20261002-065819-1176825` | 46 | 5 | New-angle gaze/voice/speed; knight motion, camera and sound |

The last run read the final updated camera-direction source. No Scout code,
model, UI or prompt configuration was changed for these tests.

### Limits retained honestly

This was a detailed screen/evidence repair, not independent listening to every
second of all three videos. ASR and downloaded media were reused. Speech-range
screening used unique eight-word matches against timed ASR plus direct review
of flagged intervals; that check is not an audio transcription accuracy score.

For the B/C document, sections 1–4 are a checked paraphrase and sections 5–6
are transcribed verbatim. The long character-sheet panel is cropped in the
source; the separate short request is preserved verbatim. The VFX prompt tail
and some other panels remain off-screen. Partial excerpts are labelled; hidden
text was not invented. Scout's `coverage=unknown` is not silently upgraded to
an exhaustive-coverage claim. Original YouTube links were checked structurally,
not by playing every link in a browser.

### Effort and model comparison

Measured acceptance work ran from **06:37:28 to 06:59:58 UTC: 22m30s**, excluding
prior independent audit and MiMo onboarding. The ledger records this interval;
final documentation work brings the measured total to approximately 25 minutes. Work included **36 contact sheets and 41
native-frame views**, three extra frames extracted locally, 57 revised screen
annotations and three live Scout runs. No redownload and no new ASR pass.

There were **five replacement imports**: one each for iPhone/Naruto and three
for the editing course. Two follow-up editing imports captured a corrected
speech boundary and an additional readable camera instruction. That overhead
is included, not hidden. They generated **105 embeddings** in total, with zero
errors; the final corpus still contains the same 57 segments for this batch.

The main chat does **not** expose a reliable token counter. Primary-agent tokens
and cost therefore remain **unknown**, rather than estimated from text size.
For the three Scout subprocesses, measured API counters total **386,037 input
tokens**, including **309,504 cached input tokens**, and **4,888 output tokens**.
Cached input is a subset, not an extra charge to add again; these counters are
not total repair tokens or a monetary bill. Scout wall time totals **130s**.

This batch demonstrates substantial semantic rework after MiMo. Its download,
ASR, chunk preparation and initial segmentation were reusable, but acceptance
was not a cheap spot-check: all screen annotations needed inspection. There is
no controlled Astra/Sol onboarding run on the same unseen videos, and complete
MiMo/primary-chat usage is unavailable, so an exact savings percentage would
be unsupported. Practical recommendation: keep mechanical preparation cheap,
and have the stronger reviewer inspect screen-heavy annotation before import.
Do not yet treat autonomous MiMo annotation plus a superficial final check as
an established economical replacement. The observed failure is in this
workflow/batch, not proof that MiMo is universally incapable.

No commit, push, deployment or production data promotion was performed during
repair. Production needs an explicit owner-authorized scoped visual data release
before its corpus can use these corrections. A code release alone is insufficient.

## Production data release — 2026-10-02

The owner authorized documentation, scoped visual data release and code release.
`./scripts/update_production_db.sh --scope visual` completed with exit code 0
at approximately 08:12 UTC. The five visual Telegram channels were synchronized;
five new posts were embedded with zero errors. MiMo processed all seven pending
drift groups successfully. Staging and promoted SQLite integrity checks passed;
the release verified compressed transfer, replaced the database and restarted
the panel. The public `/health` endpoint returned `healthy`. This promotes the
repaired VideoHub annotations; video and segment counts remain 20 / 458.
Production source contents were not separately queried or re-audited.
