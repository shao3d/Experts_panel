# Semantic Arbitration Report: control_misha_karpov

## Verdict

`limited_scope`

Do not treat Misha Karpov as a full general AI-assisted development expert.
If admitted, he should be routed narrowly as a PM/founder-facing source for
Builder PM, human-AI workflow, and product-leadership transition questions.

## Short Rationale

Misha is not a weak or noisy candidate. The semantic passport shows a coherent
and practical point of view: PMs and founders should move from planning work to
directing AI teams, building prototypes, and managing agentic workflows.

However, he is overlap-heavy against the accepted roster. The technical/coding
and agentic workflow parts overlap strongly with Polyakov, AI Architect, Refat,
Neuraldeep, and Ilia. His strongest unique contribution is not "AI coding" in
general, but the product-leadership framing: Builder PM, CPO-to-AI-builder,
human-AI workflow, and agentic mindset for non-engineering leaders.

## Evidence Used

- Passport:
  `output/expert_admission/semantic_passports/control_misha_karpov/output/control_misha_karpov_semantic_passport.normalized.json`
- Candidate report:
  `output/expert_admission/candidates/control_misha_karpov/candidate_impact_report.md`
- Comparison references:
  - `output/expert_admission/candidates/polyakov/candidate_impact_report.md`
  - `output/expert_admission/candidates/ilia_izmailov/candidate_impact_report.md`
  - `output/expert_admission/candidates/ai_architect/candidate_impact_report.md`

## Candidate Signal

Deterministic preflight:

- candidate cells: 4
- clean gaps outside accepted overlap: 1
- adjacent viewpoints: 2
- likely duplicate: 1
- exact overlaps: 1
- related overlaps: 2
- dense overlap cells: 3
- recommendation: `overlap_heavy_needs_stronger_review`

Passport positioning:

- role: AI-Assisted Development Practitioner & C-Level Executive
- strongest value: practical transition from traditional product management to
  AI-assisted building and autonomous agent workflows
- weakest value: no deep ML/architecture layer; mostly application/product
  layer and management of AI agents

## Unique Value

Misha's strongest useful cell is:

`ai_product_pm/pm_workflow/build_human_ai_workflow`

This is a real gap-like signal. It is different from Polyakov's strongest
business/marketing automation angle and from Ilia's Claude Code/AJTBD product
validation angle. Misha's framing is closer to:

- how PMs become Builder PMs;
- how founders/CPOs manage AI workers;
- how backlogs become experiment factories;
- how non-engineering leaders should change their operating model around AI.

This is useful for Panex questions from PMs, founders, and product leaders who
are not asking for deep engineering architecture but for a practical transition
path into AI-assisted execution.

## Overlap Map

### Misha vs Polyakov

Polyakov is the closest accepted expert.

Overlap:

- AI agents as practical business tools;
- Claude/Codex workflow practice;
- product/business automation;
- AI-assisted building for non-traditional developers.

Difference:

- Polyakov is stronger on concrete tooling, custom skills, marketing/SEO
  automation, and practical integration artifacts.
- Misha is stronger on product-leadership narrative, Builder PM identity,
  founder/CPO workflow, and management mindset.

Verdict: complementary only in a narrow PM/founder lane; duplicate risk is high
outside that lane.

### Misha vs Ilia

Overlap:

- vibe coding;
- product validation;
- PM-to-builder transition;
- practical use of AI coding tools.

Difference:

- Ilia is more Claude Code/plugin/AJTBD-specific and more grounded in concrete
  AI coding workflows.
- Misha is more organizational and leadership-oriented: PM role evolution,
  AI teams, agent management, and founder operating rhythm.

Verdict: Misha should not replace Ilia for Claude Code or AI coding workflow
questions, but may complement him for PM leadership workflow questions.

### Misha vs AI Architect / Refat / Neuraldeep

Overlap:

- agentic workflow and AI-assisted development process.

Difference:

- AI Architect and Refat are stronger when the user needs structured SDLC,
  context engineering, codebase workflow, or rigorous agentic development
  mechanics.
- Neuraldeep is stronger on infrastructure, tool calling, deployment, and
  technical mechanism.
- Misha is weaker technically but more accessible for product leaders.

Verdict: Misha should not be routed for technical architecture questions.

## Source Utility

Good fit:

- "How should a PM become a Builder PM with AI?"
- "How do founders manage AI agents as a team?"
- "How should product backlogs change when agents can start work immediately?"
- "What human-AI workflow should a non-technical product leader adopt?"
- "How do we teach product people to build MVPs with Cursor, Lovable, n8n, or
  Conductor?"

Poor fit:

- "Which coding agent architecture should we use in a large codebase?"
- "How do we design tool-calling, hooks, memory, evals, or RAG?"
- "How do we optimize inference cost/latency?"
- "How do we build production-grade security/governance around AI agents?"

## Risks

- Commercial/course bias: the corpus includes promotion of paid courses and
  events. This does not invalidate the source, but it lowers trust for broad
  routing.
- No comments/community signal in the export, so we cannot evaluate audience
  pushback, corrections, or practical adoption feedback.
- The expert may sound more distinctive than he is because the accepted matrix
  already has strong nearby sources.
- The "agent as employee" framing is useful but can become motivational if not
  backed by concrete implementation details.

## Decision

Recommended final status:

`limited_scope`

Admit only if Experts Panel wants a dedicated product-leadership / founder
transition voice. Do not admit as another broad AI agents / AI coding expert.

If the current priority is strict roster compactness, `watchlist` is also
reasonable. I would not choose `reject`, because the clean PM/human-AI workflow
gap is real and useful.

## Routing Contract

If accepted:

- route as supporting or niche expert for PM/founder/human-AI workflow queries;
- avoid routing as primary for technical AI coding architecture;
- prefer Polyakov for custom skills, business automation, and marketing/SEO
  automation;
- prefer Ilia for Claude Code workflows and AI-assisted product validation;
- prefer AI Architect/Refat/Neuraldeep for technical agentic development,
  architecture, evals, tool calling, and infrastructure.

## Follow-Up Probe

Before production admission, run one targeted probe set:

- 2 PM/founder transition queries;
- 2 AI agent management workflow queries;
- 1 technical agentic workflow query where he should probably not be selected;
- 1 Polyakov/Ilia overlap query to test whether he adds a genuinely distinct
  source angle.

Acceptance threshold:

- Misha should add selected sources for PM/founder workflow questions;
- Misha should not dominate technical architecture questions;
- at least one answer should include a distinct "Builder PM / AI team
  management" angle not already supplied by Polyakov or Ilia.
