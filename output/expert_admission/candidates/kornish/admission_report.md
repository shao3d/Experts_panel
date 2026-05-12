# Candidate Admission Report: kornish

## Verdict

accept

## Short Rationale

Kornishev is accepted as a valuable AI product management and AI product
strategy source for the Experts Panel knowledge matrix.

He is not accepted as a broad technical engineering source. His strongest value
is product/organizational judgment: AI product discovery, Stage-Gate adaptation,
corporate R&D lessons, AI prototyping, and practical failure modes from Skyeng,
Pearson, and Teaching Pal.

## Candidate Data

- Expert ID: `kornish`
- Display name: Kornishev
- Channel username: `@NGI_ru`
- Corpus used for passport: 468 posts and 1,690 comments
- Comment cap: none
- Passport prompt tokens: 638,693
- Passport output tokens: 15,173
- Passport thoughts tokens: 3,725
- Passport generation finish reason: `STOP`
- Normalized passport: `output/expert_admission/semantic_passports/kornish/output/kornish_semantic_passport.normalized.json`
- Candidate impact report: `output/expert_admission/candidates/kornish/candidate_impact_report.md`
- Arbitration report: `output/expert_admission/candidates/kornish/arbitration_report.md`
- Data quality note: current DB snapshot has no valid legacy/offline
  `post_metadata` for this expert; runtime FTS/embedding retrieval is
  unaffected

## Coverage Contribution

Accepted contribution to the matrix:

| Cell | Admission interpretation |
|------|--------------------------|
| `ai_product_pm/ai_product_strategy/plan_ai_product_feature` | Strong product-management contribution: AI product strategy, Stage-Gate adaptation, corporate R&D, Pearson/Skyeng case experience. |
| `prompt_engineering/reasoning_control/improve_retrieval_quality` | Useful clean gap: practical reasoning-control and SGR-style prompt/workflow methods. |
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | Accepted only as product/prototyping caution: MVP/prototype vs production, not deep engineering architecture. |
| `model_landscape/model_comparison/compare_models_for_task` | Accepted only as product/tool-selection support; Etechlead remains stronger for senior engineering model comparison. |

Candidate preflight summary:

- Candidate cells in `matrix_export`: 4
- Fills gap: 1
- Adds adjacent viewpoint: 0
- Deepens existing cell: 1
- Needs probe: 0
- Likely duplicate: 2
- Taxonomy extensions: 0
- Exact overlaps: 3
- Related overlaps: 0
- Preliminary recommendation: `overlap_heavy_needs_stronger_review`

## Closest Existing Experts

Closest overlap is expected:

- Akimov, Polyakov, Ilia, Air, and SilicBag already cover parts of AI product,
  business, adoption, and tool-use territory.
- Etechlead covers model comparison for software development more deeply.
- Doronin, AI_Grabli, Ostrikov, and others already cover coding-agent process.

Accepted differentiation:

- Kornishev brings concrete AI PM and corporate R&D experience: Skyeng,
  Pearson, Teaching Pal, stage gates, PMF, stakeholder management, strategy
  shifts, and team/process failure modes.
- He is stronger than technical coding-agent experts for questions about how
  to turn AI capability into a product decision, MVP/POC, business case, or
  organizational process.
- He adds anti-hype product judgment around vibe coding: good for prototypes
  and MVPs, risky for production without real engineering.

## Representative Source Evidence

Representative source refs from the normalized passport and manual review:

- `P0002`: Stage-Gate style process for AI product development.
- `P0248`, `P0259`, `P0268`: Pearson Teaching Pal case study and postmortem;
  strategy, management, team, and product failure lessons.
- `P0350`: AI implementation challenges in MedTech.
- `P0368`: critique of "AI makes you a developer" marketing and production
  readiness claims.
- `P0164`, `P0285`, `P0361`, `P0390`: practical reasoning-control, paper
  analysis, reverse prompt engineering, SGR, and sycophancy mitigation.
- `P0464`, `P0466`: product-oriented tool/model comparison, including agents
  and local models.

## Query Probe Results

No runtime-equivalent query probe was run for this acceptance.

This is acceptable in the current manual mode because the decision is based on
the semantic passport, deterministic preflight, qualitative arbitration, and
manual source review. If Kornishev later receives broad production routing
weight, run probes focused on AI product strategy, AI PM, Stage-Gate/POC/MVP
planning, and product-oriented prototyping.

## Source Depth Review

The passport shows strong product and practical workflow depth:

- `ai_product_pm/ai_product_strategy/plan_ai_product_feature`: strong,
  deep-practitioner, primary role.
- `prompt_engineering/reasoning_control/improve_retrieval_quality`: strong,
  practical, primary role.
- `coding_agents/agentic_dev_process/design_agentic_dev_workflow`: strong
  practical overlap, product/prototyping lens.
- `model_landscape/model_comparison/compare_models_for_task`: strong practical
  overlap, product/tool-selection lens.

## Operational Cost and Risks

Accepted with these caveats:

- Current DB snapshot has no valid legacy/offline `post_metadata` for this
  expert. This affects old coverage diagnostics only; runtime source discovery
  uses text, FTS, and embeddings.
- Do not route as a deep ML engineering, infrastructure, or senior software
  engineering model-comparison source.
- Some educational, promotional, personal, or off-topic content should be
  filtered during retrieval.
- Use strongest routing for AI product strategy, AI PM, corporate R&D lessons,
  POC/MVP validation, AI prototyping, and product failure analysis.

## Decision Notes

Human decision recorded on 2026-05-12 after reviewing:

- valid normalized semantic passport;
- deterministic candidate impact report;
- qualitative arbitration report;
- manual review of representative source refs.

Decision owner: project human review in the current manual admission flow.

## Next Action

Proceed with Kornishev as accepted in the semantic knowledge matrix. Keep the
routing caveat: he is primarily an AI product management / corporate R&D /
AI prototyping source; missing legacy `post_metadata` is not a runtime retrieval
limitation.
