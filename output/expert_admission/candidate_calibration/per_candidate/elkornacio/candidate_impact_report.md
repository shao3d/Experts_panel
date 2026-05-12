# Candidate Impact Report: Elkornacio

## Preliminary Recommendation

- Recommendation: `probe_needed`
- Admission verdict: `not_assessed`
- Evaluation mode: `semantic_matrix_preflight`

This is a deterministic preflight report, not a final admission decision.

## Candidate Data

- Expert ID: `elkornacio`
- Display name: Elkornacio
- Channel username: `@elkornacio`
- Passport cells: 4
- Passport: `/Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission/semantic_passports/elkornacio/output/elkornacio_semantic_passport.normalized.json`

## Baseline

- Baseline passports: 16
- Baseline experts: 16
- Baseline exact cells: 42
- Baseline domain + intent rollups: 28

## Impact Summary

- Candidate cells: 4
- Fills gap: 0
- Adds adjacent viewpoint: 0
- Deepens existing cell: 0
- Likely duplicate: 3
- Taxonomy extension: 0
- Needs probe: 1
- Noise risk: 0
- Exact overlaps: 3
- Related overlaps: 0
- Overlap-heavy caveat: True
- Clean gaps outside accepted overlap: 0
- Dense overlap cells: 3

## Cell Impacts

| Candidate cell | Classification | Score | Exact match | Related rollups | Next action |
|----------------|----------------|-------|-------------|-----------------|-------------|
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | likely_duplicate | 5.0 | `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | `coding_agents/choose_ai_coding_tool` | check_representative_posts_before_counting_as_unique |
| `agent_ops/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | 4.774 | `agent_ops/agentic_dev_process/design_agentic_dev_workflow` | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |
| `agent_ops/mcp_tooling/manage_security_privacy_governance` | needs_probe | 4.0 |  |  | run_deeper_candidate_probe |
| `agent_ops/mcp_tooling/design_agentic_dev_workflow` | likely_duplicate | 4.0 | `agent_ops/mcp_tooling/design_agentic_dev_workflow` | `agent_ops/design_agentic_dev_workflow` | check_representative_posts_before_counting_as_unique |

## Closest Existing Experts

| Expert | Matches | Exact | Related | Rollups |
|--------|---------|-------|---------|---------|
| Etechlead | 3 | 2 | 1 | `agent_ops/design_agentic_dev_workflow`<br>`coding_agents/choose_ai_coding_tool` |
| Polyakov | 3 | 0 | 3 | `agent_ops/design_agentic_dev_workflow`<br>`coding_agents/choose_ai_coding_tool` |
| Neuraldeep | 3 | 1 | 2 | `agent_ops/design_agentic_dev_workflow` |
| PashaZloy | 3 | 1 | 2 | `agent_ops/design_agentic_dev_workflow` |
| Rinat | 2 | 0 | 2 | `agent_ops/design_agentic_dev_workflow` |
| Refat (Tech & AI) | 2 | 0 | 2 | `agent_ops/design_agentic_dev_workflow` |
| Ilia Izmailov | 2 | 1 | 1 | `coding_agents/choose_ai_coding_tool` |
| AI Architect | 1 | 1 | 0 | `agent_ops/design_agentic_dev_workflow` |
| Tech_AI_grabli | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool` |
| Kornishev | 1 | 0 | 1 | `coding_agents/choose_ai_coding_tool` |
| SilicBag | 1 | 1 | 0 | `agent_ops/design_agentic_dev_workflow` |
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
