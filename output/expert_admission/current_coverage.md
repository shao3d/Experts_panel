# Expert Coverage Report

Generated: `2026-05-12T21:33:53+00:00`
DB: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db`
Experts included: `20`

This report is read-only and uses heuristic offline labels. Runtime proof
still requires source-level query probes through Agent Context.

## Interpretation

- Coverage status is raw-text keyword density only; it is not an admission verdict.
- No missing areas were found at the current coarse taxonomy level; candidate decisions should focus on incremental query utility, depth, freshness, and duplicate risk.
- Dense news/model coverage means another broad-news expert needs strong source-level evidence before admission.
- Some experts lack valid post_metadata, so current-roster coverage must be treated as text-derived for them: aimasters_me, deksden_notes, kornish, pashazloy, sergei_notevskii.

## Global Counts

| Metric | Count |
|---|---:|
| `expert_metadata` | 21 |
| `human_expert_metadata` | 20 |
| `posts` | 8608 |
| `text_posts` | 8137 |
| `post_embeddings` | 8137 |
| `posts_fts` | 8137 |

## Coverage Map

| Area | Status | Matching Posts | Experts | Top Experts |
|---|---|---:|---:|---|
| `coding_agents` | strong | 2103 | 20 | deksden_notes (253), akimov (208), doronin (181), ai_architect (154) |
| `agent_ops` | strong | 2667 | 20 | deksden_notes (353), doronin (287), silicbag (233), akimov (222) |
| `evals_quality` | strong | 627 | 20 | akimov (106), llm_under_hood (81), neuraldeep (57), refat (52) |
| `rag_retrieval_knowledge` | strong | 461 | 20 | neuraldeep (85), llm_under_hood (58), refat (38), silicbag (36) |
| `ai_product_pm` | strong | 1271 | 20 | kornish (270), akimov (116), doronin (96), refat (82) |
| `business_adoption` | strong | 1367 | 20 | kornish (168), llm_under_hood (130), akimov (128), silicbag (107) |
| `ai_ux_workflow` | strong | 511 | 20 | kornish (79), silicbag (53), akimov (50), deksden_notes (42) |
| `security_privacy_governance` | strong | 592 | 20 | akimov (89), kornish (73), refat (59), silicbag (51) |
| `ai_engineering_infra` | strong | 469 | 20 | akimov (70), neuraldeep (57), refat (53), llm_under_hood (39) |
| `model_landscape` | strong | 4183 | 20 | akimov (492), doronin (398), silicbag (366), deksden_notes (297) |
| `creative_multimodal` | strong | 306 | 20 | akimov (65), refat (39), doronin (36), silicbag (32) |
| `general_ai_news` | strong | 93 | 15 | sergei_notevskii (35), silicbag (15), doronin (11), glebkudr (10) |

## Gaps

Thin or missing areas:
- none

Experts without valid post_metadata:
- `aimasters_me`
- `deksden_notes`
- `kornish`
- `pashazloy`
- `sergei_notevskii`

Experts with embedding gaps:
- none

## Expert Summary

| Expert | Posts | Text | Metadata | Embeddings | Top Coverage | Warnings |
|---|---:|---:|---:|---:|---|---:|
| `ai_architect` | 238 | 230 | 196 | 230 | coding_agents:154, model_landscape:147, agent_ops:92 | 0 |
| `ai_grabli` | 363 | 357 | 330 | 357 | model_landscape:149, ai_product_pm:68, coding_agents:65 | 0 |
| `aimasters_me` | 322 | 307 | 0 | 307 | model_landscape:166, coding_agents:63, agent_ops:62 | 1 |
| `air_ai` | 169 | 168 | 143 | 168 | model_landscape:109, agent_ops:55, business_adoption:46 | 0 |
| `akimov` | 837 | 790 | 657 | 790 | model_landscape:492, agent_ops:222, coding_agents:208 | 0 |
| `deksden_notes` | 714 | 711 | 0 | 711 | agent_ops:353, model_landscape:297, coding_agents:253 | 1 |
| `doronin` | 881 | 692 | 631 | 692 | model_landscape:398, agent_ops:287, coding_agents:181 | 0 |
| `elkornacio` | 471 | 451 | 429 | 451 | model_landscape:193, coding_agents:118, agent_ops:115 | 0 |
| `etechlead` | 196 | 185 | 178 | 185 | model_landscape:118, coding_agents:106, agent_ops:98 | 0 |
| `glebkudr` | 485 | 468 | 364 | 468 | model_landscape:130, coding_agents:129, agent_ops:120 | 0 |
| `ilia_izmailov` | 178 | 173 | 145 | 173 | model_landscape:69, coding_agents:68, ai_product_pm:39 | 0 |
| `kornish` | 492 | 473 | 0 | 473 | model_landscape:275, ai_product_pm:270, business_adoption:168 | 1 |
| `llm_under_hood` | 324 | 324 | 266 | 324 | model_landscape:220, agent_ops:146, business_adoption:130 | 0 |
| `neuraldeep` | 523 | 503 | 406 | 503 | model_landscape:273, agent_ops:179, coding_agents:115 | 0 |
| `ostrikov` | 69 | 68 | 29 | 68 | agent_ops:41, model_landscape:28, coding_agents:23 | 1 |
| `pashazloy` | 414 | 398 | 0 | 398 | model_landscape:195, agent_ops:124, coding_agents:63 | 1 |
| `polyakov` | 314 | 265 | 200 | 265 | model_landscape:205, agent_ops:150, coding_agents:96 | 0 |
| `refat` | 240 | 239 | 193 | 239 | model_landscape:189, agent_ops:153, coding_agents:123 | 0 |
| `sergei_notevskii` | 424 | 398 | 0 | 398 | model_landscape:164, business_adoption:36, general_ai_news:35 | 1 |
| `silicbag` | 901 | 884 | 742 | 884 | model_landscape:366, agent_ops:233, coding_agents:112 | 0 |

## Warnings

- aimasters_me: no valid post_metadata; coverage is text-only
- deksden_notes: no valid post_metadata; coverage is text-only
- kornish: no valid post_metadata; coverage is text-only
- ostrikov: post_metadata coverage below 50%
- pashazloy: no valid post_metadata; coverage is text-only
- sergei_notevskii: no valid post_metadata; coverage is text-only
