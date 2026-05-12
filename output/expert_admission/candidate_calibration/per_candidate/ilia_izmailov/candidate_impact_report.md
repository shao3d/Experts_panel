# Candidate Impact Report: Ilia Izmailov

## Preliminary Recommendation

- Recommendation: `probe_needed`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `ilia_izmailov`
- Display name: Ilia Izmailov
- Channel username: `@ilia_izmailov`
- Passport cells: 3
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/ilia_izmailov/output/ilia_izmailov_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 42
- Baseline domain + intent rollups: 29

## Impact Summary

- Candidate cells: 3
- Fills gap: 0
- Adds adjacent viewpoint: 0
- Deepens existing cell: 0
- Likely duplicate: 2
- Taxonomy extension: 0
- Needs probe: 1
- Noise risk: 0
- Exact overlaps: 2
- Related overlaps: 1
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 0
- Dense overlap cells: 3

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `coding_agents/claude_code_workflows/design_agentic_dev_workflow` | likely_duplicate | 4.774 | `coding_agents/claude_code_workflows/design_agentic_dev_workflow` | `coding_agents/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | likely_duplicate | 4.434 | `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `ai_product_pm/pm_workflow/plan_ai_product_feature` | needs_probe | 4.0 |  | `ai_product_pm/plan_ai_product_feature` | run_deeper_candidate_probe |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Etechlead | 3 | 1 | 2 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Elkornacio | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool` |
| Doronin | 2 | 1 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Polyakov | 2 | 0 | 2 | `ai_product_pm/plan_ai_product_feature`<br>`coding_agents/choose_ai_coding_tool` |
| Kornishev | 2 | 0 | 2 | `ai_product_pm/plan_ai_product_feature`<br>`coding_agents/choose_ai_coding_tool` |
| Tech_AI_grabli | 2 | 0 | 2 | `coding_agents/choose_ai_coding_tool`<br>`coding_agents/design_agentic_dev_workflow` |
| Akimov | 1 | 0 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Ostrikov | 1 | 0 | 1 | `coding_agents/design_agentic_dev_workflow` |
| Glebkudr | 1 | 1 | 0 | `coding_agents/choose_ai_coding_tool` |

## Taxonomy Flags

No candidate taxonomy extensions.

## Limitations

- Diagnostic-only report; it does not make a final admission decision.
- Comparison is deterministic over passport matrix_export cells and matrix rollups.
- It does not inspect raw posts, runtime retrieval behavior, embeddings, or source_bundle quality.
- LLM arbitration is still useful for borderline duplicate-vs-complement cases.

## Next Action

Run a deeper candidate probe only if the candidate is strategically important.
