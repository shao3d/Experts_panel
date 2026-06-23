# Expert Lens Global Skill Spec

Status: Draft v0.4 / global skill MVP installed 2026-05-28 / quality-gated
Owner: Андрей + Codex
Target skill name: `expert-lens-review`
Target install path: `~/.codex/skills/expert-lens-review/SKILL.md`
Installed files:

- `~/.codex/skills/expert-lens-review/SKILL.md`
- `~/.codex/skills/expert-lens-review/agents/openai.yaml`
- `~/.codex/skills/expert-lens-review/references/output-contract.md`
- `~/.codex/skills/expert-lens-review/references/panex-workflow.md`
- `~/.codex/skills/expert-lens-review/references/dogfood.md`
- `~/.codex/skills/expert-lens-review/references/quality-gate.md`

## 1. Purpose

`expert-lens-review` is a global Codex skill for producing a source-grounded
second opinion on a bounded project question through the corpus of a selected
Experts Panel expert.

It must not simulate the expert, invent the expert's likely opinion, or turn the
expert into a background watcher. It orchestrates:

1. a bounded project packet;
2. a Panex / Experts Panel evidence query;
3. targeted source expansion when needed;
4. parent-Codex applicability analysis with explicit uncertainty.

The useful output is not "what the expert would say". The useful output is a
critique packet: blind spots, critique language, source-grounded analogies, and
adversarial review, each separated from evidence and from Codex interpretation.

## 2. Core Doctrine

### 2.1 What The Skill Is

The skill is a workflow for applying practitioner evidence to a concrete
project decision, spec, PR, architecture sketch, or planning artifact.

It treats Panex as an evidence retrieval and digest engine. It treats the parent
Codex chat as the applicability and project-reasoning layer. The human remains
the decision maker.

### 2.2 What The Skill Is Not

The skill is not:

- a digital clone of an expert;
- a "what would Refat say" voice simulator;
- a permanent project watcher;
- a full repository audit by default;
- a replacement for code review, tests, evals, security review, or product
  judgment;
- a Panex backend feature or new Panex response mode;
- a way to make project-specific recommendations inside `experts_panel_researcher`.

## 3. Trigger Conditions

Use the skill when the user asks for any of these shapes:

- "посмотри через линзу Рефата";
- "сделай expert lens по <expert>";
- "проверь этот план через корпус <expert>";
- "source-grounded second opinion from <expert>";
- "что в корпусе <expert> может подсветить по этому решению";
- "используй Панэкс/Experts Panel как evidence, а сам примени к проекту";
- "адверсариальный review через <expert>".

Do not use the skill for generic Panex questions where the user only wants to
know what experts say. In that case, route to ordinary Panex usage. Do not use
the skill for generic web research or Reddit/community sentiment unless the
user separately asks for those channels.

## 3.1 Explicit Cost Boundary

Calling Panex is a production external call and may be slow or costly.

For MVP, these phrases count as explicit permission for one bounded Panex
`ask` call:

- "через линзу <expert>";
- "через корпус <expert>";
- "используй Панэкс/Experts Panel";
- "source-grounded second opinion from <expert>";
- direct `$expert-lens-review` invocation with an expert name.

If the user says only "review this like Refat" or otherwise sounds ambiguous,
ask one short clarification before calling Panex:

> Запускать Панэкс по корпусу эксперта или сделать обычный Codex review в этом
> стиле без внешнего вызова?

## 4. Required Inputs And Defaults

The skill should have three inputs:

| Input | Required | Default |
| --- | --- | --- |
| Expert | Yes | Ask one short clarification if absent or ambiguous. |
| Project target | Yes | Use the current conversation artifact if obvious; otherwise ask one short clarification. |
| Question / concern | Strongly preferred | If absent, infer a narrow review question from the user's latest request and state it. |

Optional inputs:

- files or directories to include;
- desired depth;
- whether to expand sources automatically;
- whether to use one expert or compare several experts;
- whether to save a reusable review artifact.

Default scope is narrow. The skill should not scan the whole repository unless
the user explicitly asks for a broad review and accepts the cost/noise tradeoff.

## 4.1 MVP Decisions

The first global skill version should make these choices, not leave them open:

- expert scope: one expert per run by default;
- multi-expert comparison: out of scope unless the user explicitly asks;
- source expansion: automatically expand 1-3 sources for high-impact,
  surprising, or weak/indirect claims unless the user says "без expand";
- source expansion rationale: always state why these source keys were chosen,
  especially when the digest is broad/noisy;
- quality gate: before the final answer, parent Codex must run the Lens
  quality gate and show a compact `passed`, `partial`, or `failed` status with
  the weakest point;
- reusable review artifact: do not save a separate review file by default;
  answer in chat and cite Panex artifact paths/source handles;
- semantic passport: optional routing hint only, never final evidence;
- minimum novelty threshold: at least two project-specific, non-generic
  observations or one high-impact source-grounded critique question. Otherwise
  report `low signal`.
- negative-control rule: distinguish `no signal`, `adjacent signal`, and
  `strong lens`; a weakly related expert can still produce useful adjacent
  evidence, but it must be labeled with weaker applicability.

## 5. Operating Boundaries

### 5.1 Panex Boundary

Panex / `experts_panel_researcher` is evidence transport only.

Allowed Panex task:

> Find source-backed practitioner signals, caveats, anti-patterns, analogies,
> and source handles from the selected expert corpus that may be relevant to the
> bounded project question.

Forbidden Panex task:

> Decide what this project should do, make PM/product/backend/architecture
> recommendations, or produce a go/no-go verdict.

The parent Codex chat applies the evidence to the project after reading the
Panex digest and any expanded sources.

### 5.1.1 Long-Running Panex Discipline

After one `panex ask` or `panex expand` is submitted, treat it as the only
in-flight request for that review.

Do not start a duplicate request, broaden scope, restart Fly, update databases,
or run recovery mutations just because the request is slow, quiet, locally
timed out, or progress is unclear. If submission status is ambiguous, ask the
user before retrying.

Allowed read-only checks while waiting:

```bash
fly status --app experts-panel
curl --max-time 8 https://experts-panel.fly.dev/api/info
curl --max-time 8 https://experts-panel.fly.dev/api/v1/experts
```

For logs, use `timeout 10 fly logs --app experts-panel` when `timeout` exists,
`gtimeout` when GNU coreutils provides it, or a short manual `fly logs` check.

### 5.2 Passport Boundary

If an expert semantic passport is available, it may be used only as a routing
hint for query construction and topic vocabulary. It is not source proof.

Final claims must be grounded in:

- Panex `expert_digest` fields;
- `source_key` handles;
- `source_expand` evidence when claims are important, surprising, or weak;
- concrete project files/conversation artifacts read by Codex.

### 5.3 Evidence Language

Use:

- "in the expert corpus...";
- "the selected sources suggest...";
- "this pattern may apply to...";
- "applicability is weak/medium/strong because...".

Avoid:

- "<expert> would say...";
- "<expert> thinks your project should...";
- "the expert proves...";
- source-free personality claims.

## 6. Workflow

### Step 1. Bound The Review

Before calling Panex, define:

- selected expert id/display name;
- concrete project target;
- review question;
- files/docs/conversation artifacts included;
- what is out of scope.

If the target is too broad, propose a narrower first pass.

### Step 2. Build A Project Packet

Gather only enough project context to make the Panex query and final review
meaningful.

Default project packet size:

- 3-7 files or conversation artifacts;
- include the relevant spec/plan/code/docs, not the whole repo;
- summarize long files instead of pasting them into the query;
- include constraints, current design, known risks, and the decision under
  review;
- do not include secrets.

When a repo has its own navigation docs, follow them first. In Experts Panel,
start with `docs/DOCUMENTATION_MAP.md`.

### Step 3. Query Panex

Prefer the repo/user configured `experts_panel_researcher` when available and
the user explicitly invoked Panex/Experts Panel. If using direct CLI fallback,
use artifact-first transport.

Default CLI shape:

```bash
panex ask \
  --query "<bounded source-grounded retrieval query>" \
  --experts <expert_id> \
  --save \
  --receipt-json \
  --timeout 3600
```

Keep the final `--query` under the Agent Context API limit of 1000 characters.
Do not paste the full project packet into Panex; compress it to the decision,
constraints, and risk words. If `panex ask` returns HTTP 422 for invalid
request data, check query length first and retry only if no long-running
request was submitted.

Query template:

```text
Project context: <short bounded packet summary>.

Question: <specific decision/review question>.

For expert <expert_id>, find source-backed practitioner signals, caveats,
anti-patterns, analogies, and critique questions relevant to this project
question. Do not make project-specific recommendations or final verdicts.
Return source handles and caveats. Focus on evidence from the expert corpus,
not general advice.
```

Use `expert_digest` by default. Use `source_bundle` only if the user explicitly
asks for raw/audit mode.

If `panex` is unavailable, token setup fails, or network access is blocked, do
not imitate an expert-lens review from memory. Report that the evidence layer is
unavailable and offer a normal Codex review as a separate fallback.

### Step 4. Read The Artifact

Never dump large Panex artifacts with `cat`.

Read:

```bash
panex read --path <artifact_path> --manifest --json
panex read --path <artifact_path> --expert <expert_id> --json
```

For wide or multi-expert work, export:

```bash
panex export --path <artifact_path> --json
```

### Step 5. Choose Sources To Expand

Do not expand all sources by default.

Expand 1-3 sources when:

- a final blind-spot claim depends on the source;
- the digest evidence is surprising or high-impact;
- evidence quality is weak/indirect and needs inspection;
- direct comments may change interpretation;
- the user asks for proof/details/comments.

Default CLI shape:

```bash
panex expand \
  --source-keys <expert_id:source_id,...> \
  --save \
  --receipt-json \
  --timeout 3600
```

Then read the expansion artifact:

```bash
panex read --path <artifact_path> --source-key <expert_id:source_id> --json
```

If expanded source content or comments are truncated and an important claim
depends on the missing part, ask before re-expanding with higher limits or mark
that evidence as incomplete.

### Step 6. Produce The Expert Lens Review Packet

The parent Codex output must include the four core operations:

1. Blind spots;
2. Critique language;
3. Source-grounded analogies;
4. Adversarial review.

It must also include an applicability ledger and a no-signal statement when the
evidence is too weak.

## 7. Output Contract

Default answer structure:

```text
Короткий вывод
<1-3 sentences. Include whether the lens produced useful signal.>

Scope
- expert: <id/display>
- project target: <files/docs/conversation artifact>
- question: <bounded question>
- Panex artifact: <path or request_id if useful>
- expanded sources: <source_keys or none>
- expansion rationale: <why these source keys were expanded instead of others>

Evidence Boundary
- Source-grounded: <what came from Panex/source_expand>
- Codex interpretation: <what Codex is applying to the project>
- Weak/unknown: <where evidence is missing or indirect>

Lens Quality Gate
- status: <passed|partial|failed>
- weakest point: <main caveat, or "none material">

1. Blind Spots
<source-keyed blind spots, each tied to a project locus>

2. Critique Language
<questions the human/team can ask; not verdicts>

3. Source-Grounded Analogies
<patterns from the corpus and why the analogy is strong/medium/weak>

4. Adversarial Review
<where the plan/spec/decision could fail, including counterarguments>

Applicability Ledger
| Source signal | Source key | Project locus | Applicability | Caveat |

Decision Boundary
<what the human should decide next; no fake expert verdict>
```

For small chat replies, this can be compressed, but the same semantics must be
preserved.

## 8. Applicability Labels

Use four labels:

- Strong: the source discusses the same class of workflow/problem and the
  project packet contains a concrete matching locus.
- Medium: the source discusses a similar pattern, but context differs or the
  project packet is incomplete.
- Weak: the source is only adjacent, abstract, old, comment-heavy, or the
  project locus is speculative.
- No signal: the selected evidence does not materially improve a normal Codex
  review for the bounded project question.

If most evidence is weak, say that the lens did not produce enough signal.

## 9. Quality Gates

The global skill includes a lightweight self-check in
`references/quality-gate.md`. In the Experts Panel repo, the stable project
rubric is `docs/quality/expert-lens-review-rubric.md`.

The skill passes only if:

- every non-trivial blind spot has a source handle or is clearly labeled as
  Codex interpretation;
- every source-grounded analogy includes an applicability label;
- the project packet is listed clearly enough for the user to see what was and
  was not reviewed;
- source expansion choices are justified, or digest-only scope is explicit;
- no sentence claims what the expert "would say";
- no project-specific verdict is attributed to Panex;
- weak or missing evidence is explicitly called out;
- the final answer helps the human ask better questions or make a decision.

The skill fails if:

- it produces generic advice that ordinary Codex could have produced without
  the expert corpus;
- it uses the expert persona as authority;
- it hides uncertainty;
- it turns Panex into a second summarizer or project advisor;
- it expands sources indiscriminately;
- it broadens from a bounded question into a full project audit without user
  approval.

## 10. Dogfood And Evaluation

Before installing or promoting the skill, run at least these dogfood cases:

### Case A. Refat On Expert Lens Workflow

Question:

> Through Refat's corpus, critique the proposed Expert Lens workflow for risk
> of fake expertise, context rot, eval gaps, and production discipline.

Expected:

- useful critique questions;
- explicit "not a digital Refat" boundary;
- source handles for important claims;
- no final product verdict.

### Case B. Architecture Plan Review

Use a real bounded design doc from a project and ask one expert for a second
opinion.

Expected:

- at least two non-generic blind spots;
- at least one weak/medium applicability caveat;
- project locus references.

### Case C. Negative Control

Ask a weakly related expert about the same project question.

Expected:

- the skill should distinguish `no signal`, `adjacent signal`, and
  `strong lens`;
- if a weakly related expert still returns useful adjacent evidence, the skill
  should label it as weaker applicability instead of pretending the run failed;
- it should not force a confident lens.

### Case D. No Expansion Baseline

Run with digest only, then run with 1-2 expanded sources.

Expected:

- expansion should either strengthen, weaken, or clarify claims;
- if it does not change anything, the skill should say so.

Suggested evaluation rubric:

| Dimension | Pass condition |
| --- | --- |
| Grounding | Important claims have source handles or are marked interpretation. |
| Novelty | Output contains at least one useful non-generic question/critique. |
| Honesty | Weak/no signal is admitted when evidence is thin. |
| Boundary | Panex remains evidence transport; parent Codex owns applicability. |
| Quality gate | Output reports `passed`, `partial`, or `failed` and names the weakest point. |
| Usability | Human can decide a next step from the packet. |

## 11. Implementation Plan

### Phase 1. Spec Only

Create this concept spec and use it manually in one or two reviews.

### Phase 2. Global Skill MVP

Status: installed on 2026-05-28.

Create:

```text
~/.codex/skills/expert-lens-review/
  SKILL.md
  agents/openai.yaml
  references/output-contract.md
  references/panex-workflow.md
  references/dogfood.md
  references/quality-gate.md
```

`SKILL.md` should be concise, with detailed output and Panex mechanics moved to
`references/`. The frontmatter must be:

```yaml
---
name: expert-lens-review
description: Use when the user asks to review a bounded project decision, spec, PR, plan, or architecture question through the corpus or lens of a named Experts Panel expert via Panex. Produces source-grounded blind spots, critique questions, analogies, and adversarial review without simulating the expert or attributing project verdicts to them.
---
```

Installed MVP uses a slightly richer description that also includes Russian
trigger phrases such as "через линзу Рефата", "через корпус эксперта", and
"взгляд эксперта" so Codex can trigger the skill reliably in Russian chats.

Do not add scripts in the first version. The workflow is judgment-heavy and
should remain text-guided until dogfood proves repeated deterministic steps.

### Phase 3. Forward Test

Run 3-5 real requests across different projects:

- one Experts Panel architecture question;
- one code/PR review;
- one product/roadmap question;
- one negative-control expert;
- one no-signal case.

Record failures before adding more machinery.

### Phase 4. Tighten Or Retire

Promote the skill only if it repeatedly produces useful critique not available
from ordinary Codex review.

Retire or keep it manual-only if it mostly produces:

- generic advice;
- overconfident analogies;
- too much Panex cost for too little signal;
- noisy source expansion;
- expert-authority theater.

## 12. Deferred Questions

The MVP decisions are closed in section 4.1. These questions stay deferred until
dogfood produces evidence:

1. Should later versions support first-class multi-expert comparison?
2. Should a deterministic helper script assemble review packets from Panex
   artifacts?
3. Should high-value reviews be saved into project-local docs by default?
4. Should semantic passports become a first-class optional routing input outside
   the Experts Panel repo?
5. Should negative-control runs become mandatory before trusting high-impact
   lens reviews?

## 13. CTO Recommendation

Build the global skill, not a Panex backend mode.

Reason:

- Panex already has the right retrieval, digest, source handles, expansion, and
  artifact-first transport primitives.
- The risky part is interpretation, not retrieval.
- Keeping the lens in the parent Codex skill preserves the existing Panex
  boundary.
- A global skill is cheap to install, easy to revise, and easy to retire if
  dogfood shows low value.

The first production-quality version should be conservative:

- one expert;
- one bounded question;
- digest first;
- targeted expansion only;
- no expert voice;
- no automatic project-wide scan;
- no project verdict attributed to the expert.
