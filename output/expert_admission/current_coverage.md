# Expert Coverage Report

Generated: `2026-05-13T14:47:12+00:00`
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
| `posts` | 8169 |
| `text_posts` | 7731 |
| `post_embeddings` | 7731 |
| `posts_fts` | 7731 |

## Coverage Map

| Area | Status | Matching Posts | Experts | Top Experts |
|---|---|---:|---:|---|
| `coding_agents` | strong | 2091 | 20 | deksden_notes (253), akimov (208), doronin (179), ai_architect (154) |
| `agent_ops` | strong | 2639 | 20 | deksden_notes (353), doronin (276), silicbag (233), akimov (222) |
| `evals_quality` | strong | 615 | 20 | akimov (106), llm_under_hood (81), neuraldeep (57), refat (52) |
| `rag_retrieval_knowledge` | strong | 455 | 20 | neuraldeep (85), llm_under_hood (58), refat (38), silicbag (36) |
| `ai_product_pm` | strong | 1199 | 20 | kornish (246), akimov (116), refat (82), doronin (80) |
| `business_adoption` | strong | 1309 | 20 | kornish (157), llm_under_hood (130), akimov (128), silicbag (107) |
| `ai_ux_workflow` | strong | 498 | 20 | kornish (76), silicbag (53), akimov (50), deksden_notes (42) |
| `security_privacy_governance` | strong | 578 | 20 | akimov (89), kornish (69), refat (59), silicbag (51) |
| `ai_engineering_infra` | strong | 462 | 20 | akimov (70), neuraldeep (57), refat (53), llm_under_hood (39) |
| `model_landscape` | strong | 4069 | 20 | akimov (493), doronin (376), silicbag (366), deksden_notes (297) |
| `creative_multimodal` | strong | 295 | 20 | akimov (65), refat (39), doronin (34), silicbag (32) |
| `general_ai_news` | strong | 86 | 13 | sergei_notevskii (35), silicbag (15), glebkudr (10), doronin (8) |

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
| `ai_architect` | 239 | 231 | 196 | 231 | coding_agents:154, model_landscape:147, agent_ops:93 | 0 |
| `ai_grabli` | 211 | 209 | 183 | 209 | model_landscape:120, coding_agents:62, agent_ops:48 | 0 |
| `aimasters_me` | 256 | 243 | 0 | 243 | model_landscape:145, coding_agents:62, agent_ops:59 | 1 |
| `air_ai` | 169 | 168 | 143 | 168 | model_landscape:109, agent_ops:55, business_adoption:46 | 0 |
| `akimov` | 838 | 791 | 657 | 791 | model_landscape:493, agent_ops:222, coding_agents:208 | 0 |
| `deksden_notes` | 714 | 711 | 0 | 711 | agent_ops:353, model_landscape:297, coding_agents:253 | 1 |
| `doronin` | 814 | 627 | 565 | 627 | model_landscape:376, agent_ops:276, coding_agents:179 | 0 |
| `elkornacio` | 471 | 451 | 429 | 451 | model_landscape:193, coding_agents:118, agent_ops:115 | 0 |
| `etechlead` | 149 | 146 | 139 | 146 | model_landscape:109, coding_agents:101, agent_ops:91 | 0 |
| `glebkudr` | 485 | 468 | 364 | 468 | model_landscape:130, coding_agents:129, agent_ops:120 | 0 |
| `ilia_izmailov` | 178 | 173 | 145 | 173 | model_landscape:69, coding_agents:68, ai_product_pm:39 | 0 |
| `kornish` | 442 | 423 | 0 | 423 | model_landscape:254, ai_product_pm:246, business_adoption:157 | 1 |
| `llm_under_hood` | 324 | 324 | 266 | 324 | model_landscape:220, agent_ops:146, business_adoption:130 | 0 |
| `neuraldeep` | 523 | 503 | 406 | 503 | model_landscape:273, agent_ops:179, coding_agents:115 | 0 |
| `ostrikov` | 71 | 70 | 29 | 70 | agent_ops:43, model_landscape:28, coding_agents:23 | 1 |
| `pashazloy` | 415 | 399 | 0 | 399 | model_landscape:196, agent_ops:125, coding_agents:64 | 1 |
| `polyakov` | 252 | 220 | 154 | 220 | model_landscape:191, agent_ops:145, coding_agents:95 | 0 |
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
