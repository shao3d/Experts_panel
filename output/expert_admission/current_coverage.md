# Expert Coverage Report

Generated: `2026-05-10T19:50:25+00:00`
DB: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db`
Experts included: `17`

This report is read-only and uses heuristic offline labels. Runtime proof
still requires source-level query probes through Agent Context.

## Interpretation

- Coverage status is raw-text keyword density only; it is not an admission verdict.
- No missing areas were found at the current coarse taxonomy level; candidate decisions should focus on incremental query utility, depth, freshness, and duplicate risk.
- Dense news/model coverage means another broad-news expert needs strong source-level evidence before admission.
- Some experts lack valid post_metadata, so current-roster coverage must be treated as text-derived for them: kornish, pashazloy.

## Global Counts

| Metric | Count |
|---|---:|
| `expert_metadata` | 18 |
| `human_expert_metadata` | 17 |
| `posts` | 7049 |
| `text_posts` | 6622 |
| `post_embeddings` | 6622 |
| `posts_fts` | 6622 |

## Coverage Map

| Area | Status | Matching Posts | Experts | Top Experts |
|---|---|---:|---:|---|
| `coding_agents` | strong | 1737 | 17 | akimov (203), doronin (181), ai_architect (152), glebkudr (129) |
| `agent_ops` | strong | 2168 | 17 | doronin (282), silicbag (226), akimov (218), neuraldeep (174) |
| `evals_quality` | strong | 560 | 17 | akimov (105), llm_under_hood (79), neuraldeep (57), refat (51) |
| `rag_retrieval_knowledge` | strong | 428 | 17 | neuraldeep (84), llm_under_hood (57), refat (38), silicbag (35) |
| `ai_product_pm` | strong | 1140 | 17 | kornish (265), akimov (112), doronin (96), refat (80) |
| `business_adoption` | strong | 1208 | 17 | kornish (165), llm_under_hood (129), akimov (126), silicbag (101) |
| `ai_ux_workflow` | strong | 437 | 17 | kornish (77), silicbag (52), akimov (50), doronin (37) |
| `security_privacy_governance` | strong | 528 | 17 | akimov (87), kornish (70), refat (58), silicbag (51) |
| `ai_engineering_infra` | strong | 414 | 17 | akimov (66), neuraldeep (57), refat (52), llm_under_hood (39) |
| `model_landscape` | strong | 3500 | 17 | akimov (480), doronin (396), silicbag (359), kornish (270) |
| `creative_multimodal` | strong | 271 | 17 | akimov (61), refat (38), doronin (36), silicbag (32) |
| `general_ai_news` | strong | 54 | 12 | silicbag (15), doronin (11), glebkudr (10), ilia_izmailov (4) |

## Gaps

Thin or missing areas:
- none

Experts without valid post_metadata:
- `kornish`
- `pashazloy`

Experts with embedding gaps:
- none

## Expert Summary

| Expert | Posts | Text | Metadata | Embeddings | Top Coverage | Warnings |
|---|---:|---:|---:|---:|---|---:|
| `ai_architect` | 234 | 226 | 196 | 226 | coding_agents:152, model_landscape:144, agent_ops:92 | 0 |
| `ai_grabli` | 357 | 351 | 330 | 351 | model_landscape:147, ai_product_pm:67, coding_agents:62 | 0 |
| `air_ai` | 165 | 164 | 143 | 164 | model_landscape:106, agent_ops:52, business_adoption:44 | 0 |
| `akimov` | 822 | 775 | 657 | 775 | model_landscape:480, agent_ops:218, coding_agents:203 | 0 |
| `doronin` | 875 | 686 | 631 | 686 | model_landscape:396, agent_ops:282, coding_agents:181 | 0 |
| `elkornacio` | 465 | 445 | 429 | 445 | model_landscape:190, coding_agents:117, agent_ops:111 | 0 |
| `etechlead` | 196 | 185 | 178 | 185 | model_landscape:118, coding_agents:106, agent_ops:98 | 0 |
| `glebkudr` | 472 | 455 | 364 | 455 | coding_agents:129, model_landscape:127, agent_ops:116 | 0 |
| `ilia_izmailov` | 176 | 171 | 145 | 171 | coding_agents:68, model_landscape:68, ai_product_pm:39 | 0 |
| `kornish` | 487 | 468 | 0 | 468 | model_landscape:270, ai_product_pm:265, business_adoption:165 | 1 |
| `llm_under_hood` | 321 | 321 | 266 | 321 | model_landscape:218, agent_ops:143, business_adoption:129 | 0 |
| `neuraldeep` | 514 | 494 | 406 | 494 | model_landscape:269, agent_ops:174, coding_agents:114 | 0 |
| `ostrikov` | 68 | 67 | 29 | 67 | agent_ops:41, model_landscape:28, coding_agents:23 | 1 |
| `pashazloy` | 409 | 393 | 0 | 393 | model_landscape:192, agent_ops:121, coding_agents:63 | 1 |
| `polyakov` | 310 | 261 | 200 | 261 | model_landscape:201, agent_ops:147, coding_agents:94 | 0 |
| `refat` | 237 | 236 | 193 | 236 | model_landscape:187, agent_ops:150, coding_agents:121 | 0 |
| `silicbag` | 888 | 871 | 742 | 871 | model_landscape:359, agent_ops:226, coding_agents:106 | 0 |

## Warnings

- kornish: no valid post_metadata; coverage is text-only
- ostrikov: post_metadata coverage below 50%
- pashazloy: no valid post_metadata; coverage is text-only
