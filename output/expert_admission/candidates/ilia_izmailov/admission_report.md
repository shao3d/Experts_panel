# Candidate Admission Report: ilia_izmailov

## Verdict

accept

## Short Rationale

Ilia Izmailov is accepted as a valuable expert for the current Experts Panel
knowledge matrix.

The acceptance is based on a valid semantic passport, a positive deterministic
matrix preflight, and human review of the candidate impact report. Ilia is not a
duplicate-only source: the passport adds one new strong exact cell, one adjacent
viewpoint in an already important coding-agent tool-choice area, and one
supporting product/PM cell that remains probe-worthy but useful.

## Candidate Data

- Expert ID: `ilia_izmailov`
- Display name: Ilia Izmailov
- Channel username: `@ilia_izmailov`
- Corpus used for passport: 173 posts and 2,281 comments
- Passport prompt tokens: 337,054
- Passport output tokens: 11,860
- Passport generation finish reason: `STOP`
- Normalized passport: `output/expert_admission/semantic_passports/ilia_izmailov/output/ilia_izmailov_semantic_passport.normalized.json`
- Candidate impact report: `output/expert_admission/candidates/ilia_izmailov/candidate_impact_report.md`

## Coverage Contribution

Accepted contribution to the matrix:

| Cell | Admission interpretation |
|------|--------------------------|
| `coding_agents/claude_code_workflows/design_agentic_dev_workflow` | Strong new exact cell; main reason to accept. |
| `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool` | Adjacent viewpoint to existing coding-agent tool-choice coverage. |
| `ai_product_pm/pm_workflow/plan_ai_product_feature` | Supporting cell; useful but should remain probe-needed. |

Candidate preflight summary:

- Candidate cells: 3
- Fills gap: 1
- Adds adjacent viewpoint: 1
- Needs probe: 1
- Likely duplicate: 0
- Taxonomy extensions: 0
- Exact overlaps: 0
- Related overlaps: 1
- Preliminary recommendation: `promising_needs_human_review`

## Closest Existing Experts

Closest overlap is with AI Architect through the rollup
`coding_agents/choose_ai_coding_tool`.

This overlap is accepted as complementary rather than duplicate because Ilia's
passport is grounded in practical Claude Code / Cursor / agent-team workflows
and product-builder usage, while AI Architect covers a broader architect/system
view of coding-agent tools.

## Representative Posts

Representative source refs from the normalized passport:

- `P0076`: Claude Code plugins and custom AJTBD plugin creation.
- `P0117`: `/deep-thinking` plugin workflow.
- `P0126`: Agent Teams in Claude Code.
- `P0132`: `/team-feature` plugin with multi-level review and pre-code risk analysis.
- `P0023`, `P0074`, `P0089`, `P0140`, `P0160`: AI coding tool comparison and operational usage.
- `P0069`, `P0084`, `P0104`, `P0133`: AI-assisted product validation and PM workflows.

## Query Probe Results

No runtime-equivalent query probe was run for this acceptance.

This is acceptable for the current manual mode because Ilia's core value is
already visible in the semantic passport and matrix impact report. The
`ai_product_pm/pm_workflow/plan_ai_product_feature` cell remains marked as
probe-needed if we later want decision-grade retrieval evidence.

## Source Depth Review

The passport has strong source depth for Claude Code workflows and practical
AI-coding operations:

- `coding_agents/claude_code_workflows/design_agentic_dev_workflow`: strong,
  deep-practitioner, high-practicality cell.
- `coding_agents/cursor_windsurf_copilot/choose_ai_coding_tool`: strong,
  practical, adjacent to existing tool-choice coverage.
- `ai_product_pm/pm_workflow/plan_ai_product_feature`: moderate supporting
  product/PM contribution.

## Operational Cost and Risks

Accepted with these caveats:

- Do not treat Ilia as a general low-level software engineering expert.
- Use strongest routing for Claude Code workflows, agent-team patterns,
  AI-assisted product building, and tool-choice comparisons.
- Treat traditional backend/database/security/infrastructure questions as poor
  fit unless the query is explicitly AI-assisted workflow oriented.
- Runtime retrieval probes were not run, so source-ranking impact is not yet
  proven.

## Decision Notes

Human decision recorded on 2026-05-10 after reviewing:

- valid normalized semantic passport;
- deterministic candidate impact report;
- updated 5-passport knowledge matrix;
- leave-one-out candidate evaluator calibration.

Decision owner: project human review in the current manual admission flow.

## Next Action

Proceed with Ilia as accepted in the semantic knowledge matrix. Runtime probes
are optional and should be reserved for later calibration or if Ilia's
product/PM cell becomes important for production routing.
