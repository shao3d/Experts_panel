# Candidate Evaluator Leave-One-Out Calibration

Generated: 2026-05-12T09:31:04.247080+00:00

## Summary

- Cases: 17
- Total candidate cells: 66
- Total positive impact signals: 28
- Total exact overlaps: 36
- Total related overlaps: 12
- Recommendations: `overlap_heavy_needs_stronger_review`=12, `probe_needed`=4, `promising_needs_human_review`=1

## Interpretation

- Some cases produced no positive impact and should be manually inspected before adding more experts.
- No case is duplicate-only under the current heuristics.
- Related-overlap detection is active and caught at least one adjacent expert relationship.
- Some cells still require probes; this is expected for supporting or lower-confidence cells.
- Some otherwise-positive cases are overlap-heavy and require a stronger admission review.

## Cases

| Candidate | Baseline | Recommendation | +Impact | Gap | Adjacent | Deepens | Duplicate | Probe | Exact | Related |
|-----------|----------|----------------|---------|-----|----------|---------|-----------|-------|-------|---------|
| `ai_architect` | `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 1 | 0 | 1 | 0 | 2 | 1 | 2 | 1 |
| `ai_grabli` | `ai_architect`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 1 | 1 | 0 | 0 | 2 | 1 | 2 | 0 |
| `air_ai` | `ai_architect`, `ai_grabli`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 4 | 0 | 3 | 1 | 0 | 0 | 1 | 3 |
| `akimov` | `ai_architect`, `ai_grabli`, `air_ai`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `probe_needed` | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 |
| `doronin` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 1 | 1 | 0 | 0 | 3 | 0 | 3 | 0 |
| `elkornacio` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `probe_needed` | 0 | 0 | 0 | 0 | 3 | 1 | 3 | 0 |
| `etechlead` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 4 | 2 | 0 | 2 | 2 | 0 | 4 | 0 |
| `glebkudr` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 2 | 2 | 0 | 0 | 2 | 0 | 2 | 0 |
| `ilia_izmailov` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `probe_needed` | 0 | 0 | 0 | 0 | 2 | 1 | 2 | 1 |
| `kornish` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 2 | 1 | 0 | 1 | 2 | 0 | 3 | 0 |
| `llm_under_hood` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `promising_needs_human_review` | 3 | 2 | 1 | 0 | 0 | 0 | 0 | 1 |
| `neuraldeep` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `ostrikov`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 3 | 1 | 1 | 1 | 2 | 0 | 3 | 1 |
| `ostrikov` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `pashazloy`, `polyakov`, `refat`, `silicbag` | `probe_needed` | 0 | 0 | 0 | 0 | 2 | 2 | 2 | 0 |
| `pashazloy` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `polyakov`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 1 | 0 | 1 | 0 | 2 | 0 | 2 | 1 |
| `polyakov` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `refat`, `silicbag` | `overlap_heavy_needs_stronger_review` | 2 | 0 | 2 | 0 | 2 | 0 | 2 | 2 |
| `refat` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `silicbag` | `overlap_heavy_needs_stronger_review` | 2 | 1 | 1 | 0 | 1 | 1 | 1 | 1 |
| `silicbag` | `ai_architect`, `ai_grabli`, `air_ai`, `akimov`, `doronin`, `elkornacio`, `etechlead`, `glebkudr`, `ilia_izmailov`, `kornish`, `llm_under_hood`, `neuraldeep`, `ostrikov`, `pashazloy`, `polyakov`, `refat` | `overlap_heavy_needs_stronger_review` | 1 | 0 | 1 | 0 | 3 | 0 | 3 | 1 |

## Cell Details

### AI Architect

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `agent_ops/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.811 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `coding_agents/claude_code_workflows/choose_ai_coding_tool` | likely_duplicate | 4.406 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/learn_ai_assisted_development` | check_representative_posts_before_counting_as_unique |
| `coding_agents/codex_workflows/choose_ai_coding_tool` | adds_adjacent_viewpoint | 4.387 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/learn_ai_assisted_development` | human_review_overlap_or_complement |
| `security_privacy_governance/security_privacy_controls/manage_security_privacy_governance` | needs_probe | 4.208 |  | run_deeper_candidate_probe |

### Tech_AI_grabli

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.811 | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `rag_retrieval_knowledge/hybrid_retrieval/improve_retrieval_quality` | fills_gap | 4.792 |  | human_review_then_possible_accept |
| `prompt_engineering/reasoning_control/build_ai_dev_eval` | needs_probe | 4.387 |  | run_deeper_candidate_probe |
| `coding_agents/claude_code_workflows/choose_ai_coding_tool` | likely_duplicate | 4.519 | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |

### Air

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `prompt_engineering/model_specific_formatting/learn_ai_assisted_development` | deepens_existing_cell | 5.0 | `prompt_engineering/learn_ai_assisted_development` | human_review_then_possible_accept |
| `business_adoption/financial_modeling/assess_ai_tool_business_adoption` | adds_adjacent_viewpoint | 5.0 | `business_adoption/assess_ai_tool_business_adoption` | human_review_overlap_or_complement |
| `prompt_engineering/reasoning_control/learn_ai_assisted_development` | adds_adjacent_viewpoint | 4.623 | `prompt_engineering/learn_ai_assisted_development` | human_review_overlap_or_complement |
| `rag_retrieval_knowledge/rag_architecture/design_rag_knowledge_base` | adds_adjacent_viewpoint | 4.0 | `rag_retrieval_knowledge/design_rag_knowledge_base` | human_review_overlap_or_complement |

### Akimov

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.811 | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `ai_product_pm/adoption_roadmaps/assess_ai_tool_business_adoption` | fills_gap | 4.311 |  | human_review_then_possible_accept |

### Doronin

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `coding_agents/claude_code_workflows/design_agentic_dev_workflow` | likely_duplicate | 4.925 | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.792 | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `agent_ops/mcp_tooling/build_human_ai_workflow` | fills_gap | 4.708 |  | human_review_then_possible_accept |
| `rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base` | likely_duplicate | 4.292 | `rag_retrieval_knowledge/design_rag_knowledge_base` | check_representative_posts_before_counting_as_unique |

### Elkornacio

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | likely_duplicate | 5.0 | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `agent_ops/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.774 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `agent_ops/mcp_tooling/manage_security_privacy_governance` | needs_probe | 4.0 |  | run_deeper_candidate_probe |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | likely_duplicate | 4.0 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |

### Etechlead

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | likely_duplicate | 5.0 | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `coding_agents/claude_code_workflows/choose_ai_coding_tool` | deepens_existing_cell | 5.0 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` | human_review_then_possible_accept |
| `model_landscape/model_comparison/compare_models_for_task` | deepens_existing_cell | 5.0 | `model_landscape/compare_models_for_task` | human_review_then_possible_accept |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | likely_duplicate | 4.623 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `agent_ops/context_compression/improve_retrieval_quality` | fills_gap | 5.0 |  | human_review_then_possible_accept |
| `ai_engineering_infra/agentic_dev_process/build_human_ai_workflow` | fills_gap | 4.585 |  | human_review_then_possible_accept |

### Glebkudr

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `agent_ops/multi_agent_orchestration/design_agentic_dev_workflow` | likely_duplicate | 4.774 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `prompt_engineering/context_compression/optimize_inference_cost_latency` | fills_gap | 5.0 |  | human_review_then_possible_accept |
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | likely_duplicate | 4.0 | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/model_comparison/compare_models_for_task` | fills_gap | 4.189 |  | human_review_then_possible_accept |

### Ilia Izmailov

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `coding_agents/claude_code_workflows/design_agentic_dev_workflow` | likely_duplicate | 4.774 | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | likely_duplicate | 4.434 | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `ai_product_pm/pm_workflow/plan_ai_product_feature` | needs_probe | 4.0 | `ai_product_pm/plan_ai_product_feature` | run_deeper_candidate_probe |

### Kornishev

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `ai_product_pm/ai_product_strategy/plan_ai_product_feature` | deepens_existing_cell | 4.849 | `ai_product_pm/plan_ai_product_feature` | human_review_then_possible_accept |
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.434 | `coding_agents/design_agentic_dev_workflow`<br>`coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `prompt_engineering/reasoning_control/improve_retrieval_quality` | fills_gap | 4.189 |  | human_review_then_possible_accept |
| `model_landscape/model_comparison/compare_models_for_task` | likely_duplicate | 4.283 | `model_landscape/compare_models_for_task` | check_representative_posts_before_counting_as_unique |

### Rinat

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `agent_ops/reasoning_control/design_agentic_dev_workflow` | adds_adjacent_viewpoint | 5.0 | `agent_ops/design_agentic_dev_workflow` | human_review_overlap_or_complement |
| `evals_quality/llm_evals/build_ai_dev_eval` | fills_gap | 4.849 |  | human_review_then_possible_accept |
| `agent_ops/agentic_dev_process/learn_ai_assisted_development` | fills_gap | 4.849 |  | human_review_then_possible_accept |

### Neuraldeep

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `ai_engineering_infra/inference_cost_latency/optimize_inference_cost_latency` | adds_adjacent_viewpoint | 5.0 | `ai_engineering_infra/optimize_inference_cost_latency` | human_review_overlap_or_complement |
| `agent_ops/tool_calling_hooks_skills/design_agentic_dev_workflow` | likely_duplicate | 5.0 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/deployment_observability/manage_security_privacy_governance` | fills_gap | 5.0 |  | human_review_then_possible_accept |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | likely_duplicate | 4.434 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `prompt_engineering/agentic_dev_process/learn_ai_assisted_development` | deepens_existing_cell | 4.66 | `prompt_engineering/learn_ai_assisted_development` | human_review_then_possible_accept |

### Ostrikov

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.774 | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `agent_ops/multi_agent_orchestration/design_agentic_dev_workflow` | likely_duplicate | 4.849 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/rag_architecture/design_rag_knowledge_base` | needs_probe | 4.038 |  | run_deeper_candidate_probe |
| `business_adoption/human_ai_workflow/build_human_ai_workflow` | needs_probe | 3.774 |  | run_deeper_candidate_probe |

### PashaZloy

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `ai_engineering_infra/local_agent_setup/optimize_inference_cost_latency` | adds_adjacent_viewpoint | 4.811 | `ai_engineering_infra/optimize_inference_cost_latency` | human_review_overlap_or_complement |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | likely_duplicate | 4.857 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `prompt_engineering/agentic_dev_process/learn_ai_assisted_development` | likely_duplicate | 4.387 | `prompt_engineering/learn_ai_assisted_development` | check_representative_posts_before_counting_as_unique |

### Polyakov

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `agent_ops/tool_calling_hooks_skills/design_agentic_dev_workflow` | likely_duplicate | 5.0 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `coding_agents/claude_code_workflows/learn_ai_assisted_development` | adds_adjacent_viewpoint | 4.849 | `coding_agents/learn_ai_assisted_development`<br>`coding_agents/choose_ai_coding_tool` | human_review_overlap_or_complement |
| `ai_product_pm/ai_product_strategy/plan_ai_product_feature` | likely_duplicate | 4.34 | `ai_product_pm/plan_ai_product_feature` | check_representative_posts_before_counting_as_unique |
| `coding_agents/codex_workflows/learn_ai_assisted_development` | adds_adjacent_viewpoint | 4.189 | `coding_agents/learn_ai_assisted_development`<br>`coding_agents/choose_ai_coding_tool` | human_review_overlap_or_complement |

### Refat (Tech & AI)

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `agent_ops/claude_code_workflows/design_agentic_dev_workflow` | adds_adjacent_viewpoint | 4.925 | `agent_ops/design_agentic_dev_workflow` | human_review_overlap_or_complement |
| `rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base` | likely_duplicate | 4.462 | `rag_retrieval_knowledge/design_rag_knowledge_base` | check_representative_posts_before_counting_as_unique |
| `ai_engineering_infra/llm_evals/build_ai_dev_eval` | needs_probe | 4.311 |  | run_deeper_candidate_probe |
| `ai_engineering_infra/deployment_observability/build_ai_dev_eval` | fills_gap | 4.311 |  | human_review_then_possible_accept |

### SilicBag

| Cell | Classification | Score | Related rollups | Next action |
|------|----------------|-------|-----------------|-------------|
| `agent_ops/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.434 | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `prompt_engineering/model_specific_formatting/learn_ai_assisted_development` | likely_duplicate | 4.34 | `prompt_engineering/learn_ai_assisted_development` | check_representative_posts_before_counting_as_unique |
| `rag_retrieval_knowledge/knowledge_base_design/design_rag_knowledge_base` | likely_duplicate | 4.434 | `rag_retrieval_knowledge/design_rag_knowledge_base` | check_representative_posts_before_counting_as_unique |
| `business_adoption/roi_business_cases/assess_ai_tool_business_adoption` | adds_adjacent_viewpoint | 4.0 | `business_adoption/assess_ai_tool_business_adoption` | human_review_overlap_or_complement |

## Detailed Report Paths

- `ai_architect`: `output/expert_admission/candidate_calibration/per_candidate/ai_architect/candidate_impact_report.md`
- `ai_grabli`: `output/expert_admission/candidate_calibration/per_candidate/ai_grabli/candidate_impact_report.md`
- `air_ai`: `output/expert_admission/candidate_calibration/per_candidate/air_ai/candidate_impact_report.md`
- `akimov`: `output/expert_admission/candidate_calibration/per_candidate/akimov/candidate_impact_report.md`
- `doronin`: `output/expert_admission/candidate_calibration/per_candidate/doronin/candidate_impact_report.md`
- `elkornacio`: `output/expert_admission/candidate_calibration/per_candidate/elkornacio/candidate_impact_report.md`
- `etechlead`: `output/expert_admission/candidate_calibration/per_candidate/etechlead/candidate_impact_report.md`
- `glebkudr`: `output/expert_admission/candidate_calibration/per_candidate/glebkudr/candidate_impact_report.md`
- `ilia_izmailov`: `output/expert_admission/candidate_calibration/per_candidate/ilia_izmailov/candidate_impact_report.md`
- `kornish`: `output/expert_admission/candidate_calibration/per_candidate/kornish/candidate_impact_report.md`
- `llm_under_hood`: `output/expert_admission/candidate_calibration/per_candidate/llm_under_hood/candidate_impact_report.md`
- `neuraldeep`: `output/expert_admission/candidate_calibration/per_candidate/neuraldeep/candidate_impact_report.md`
- `ostrikov`: `output/expert_admission/candidate_calibration/per_candidate/ostrikov/candidate_impact_report.md`
- `pashazloy`: `output/expert_admission/candidate_calibration/per_candidate/pashazloy/candidate_impact_report.md`
- `polyakov`: `output/expert_admission/candidate_calibration/per_candidate/polyakov/candidate_impact_report.md`
- `refat`: `output/expert_admission/candidate_calibration/per_candidate/refat/candidate_impact_report.md`
- `silicbag`: `output/expert_admission/candidate_calibration/per_candidate/silicbag/candidate_impact_report.md`
