# Semantic Arbitration Report: kornish

## Verdict Recommendation

accept

## Short Rationale

Kornishev is overlap-heavy but valuable enough to accept.

The deterministic preflight found 4 candidate cells: 1 clean gap, 1 deepening
signal, and 2 likely duplicates. The strongest value is not generic AI tool
coverage. It is pragmatic AI product management grounded in corporate R&D,
startup/consulting work, and concrete lessons from AI product failures.

The main data-quality note is legacy/offline only: current DB coverage has no
valid `post_metadata` for this expert. This does not limit runtime retrieval,
which uses source text, FTS, and embeddings.

## Evidence Used

- Normalized passport:
  `output/expert_admission/semantic_passports/kornish/output/kornish_semantic_passport.normalized.json`
- Candidate impact report:
  `output/expert_admission/candidates/kornish/candidate_impact_report.md`
- Corpus packet:
  468 posts, 1,690 comments, 638,693 input tokens
- Generation:
  15,173 output tokens, finish reason `STOP`, normalized validation passed

## Matrix Impact

Candidate cells:

| Cell | Preflight | Arbitration interpretation |
|------|-----------|----------------------------|
| `ai_product_pm/ai_product_strategy/plan_ai_product_feature` | deepens_existing_cell | Strong accepted value: AI product strategy, Stage-Gate adaptation, corporate R&D, Pearson/Skyeng case experience. |
| `prompt_engineering/reasoning_control/improve_retrieval_quality` | fills_gap | Useful clean gap: practical reasoning-control and SGR-style prompt/workflow methods. |
| `coding_agents/agentic_dev_process/design_agentic_dev_workflow` | likely_duplicate | Accepted only as product/prototyping caution: MVP/prototype vs production, not deep engineering architecture. |
| `model_landscape/model_comparison/compare_models_for_task` | likely_duplicate | Accepted only as product/tool-selection support; Etechlead remains stronger for senior engineering model comparison. |

## Differentiation Against Existing Experts

Closest overlaps:

- Akimov, Polyakov, Ilia, and Air already cover parts of AI product, business,
  and tool adoption.
- Etechlead now covers model comparison for software development more deeply.
- Doronin, AI_Grabli, Ostrikov, and others already cover coding-agent process.

Accepted differentiation:

- Kornishev brings unusually concrete AI product management and R&D experience:
  Skyeng, Pearson, Teaching Pal, corporate innovation, stage gates, PMF,
  stakeholders, strategy shifts, and team/process failure modes.
- He is stronger than technical coding-agent experts for questions about how to
  turn AI capability into a product decision, MVP/POC, business case, or
  organizational process.
- He adds anti-hype product judgment around vibe coding: good for prototypes
  and MVPs, dangerous for production without real engineering.

## Representative Source Evidence

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

## Risks

- Heavy overlap with accepted product/adoption and AI-coding experts.
- No valid legacy/offline `post_metadata` in the current DB snapshot; this
  affects old coverage diagnostics only and does not limit runtime source
  discovery.
- Some content is educational/course-oriented or personal/off-topic and should
  be filtered during retrieval.
- Not a deep ML/infrastructure expert.
- Not the first source for senior software-engineering model comparison; use
  Etechlead for that.

## Recommended Routing Caveat

accepted as AI product management / AI product strategy / corporate R&D and
AI prototyping expert; legacy/offline post_metadata is missing but runtime
FTS/embedding retrieval is unaffected; overlap-heavy with product/adoption and
coding-agent cells, avoid routing for deep ML engineering, infra, or senior
software-engineering model comparison

## Final Admission Advice

Accept.

Kornishev adds a product-management and organizational-learning layer that the
matrix should have. He should not be used as a broad technical source, but he is
valuable when the user asks how to plan, validate, prototype, sell internally,
or avoid failure in AI products.
