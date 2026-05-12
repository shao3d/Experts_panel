# Harvester VPS Battle Tests - 2026-05-09

**Status:** mixed
**Target:** InterServer VPS `153.75.248.11`
**Scope:** production-like Harvester/Searcharvester live tests on the private VPS sidecar.

This run tested the deployed Harvester stack with realistic research prompts:
fresh news, service comparison, technical documentation, controversial
infrastructure judgement, and a Russian-language request.

The goal was not to prove the factual correctness of every generated claim. The
goal was to test live system behavior: search/extract/research flow, Vertex AI
proxy stability, latency, artifact handling, citation grounding, and request
fidelity.

## Test Setup

- API target: `http://127.0.0.1:8000` on the VPS.
- Public exposure: none, accessed over SSH.
- Model path: Hermes -> local OpenAI-compatible Vertex proxy -> Vertex AI
  Gemini `gemini-3-flash-preview`.
- Runner parallelism: `2` concurrent `/research` jobs.
- Per-job runner timeout: `1200s`.
- Poll interval: `30s`.

## Results

| Scenario | Job ID | Status | Duration | Report | Evidence notes |
|---|---:|---:|---:|---:|---|
| Fresh news | `f9ca31d17ede4617` | completed | `706.9s` | `5406` chars | partial citations; terminal approval callback bug recovered |
| Service comparison | `c7bfcfae19c9436f` | completed | `797.3s` | `5411` chars | partial citations |
| Technical Vertex question | `f88da73a51764151` | completed | `1109.2s` | `4195` chars | no partial citations in final status; internal subagent timeouts occurred |
| Controversial SearXNG question | `eea6631bd36449b7` | timeout | `1236.0s` | none | subagent timeouts, partial citations, no final report |
| Russian context rot question | `066fec9848b74a41` | completed | `1051.5s` | `29561` chars | `no report.md`; API fell back to assistant messages |

## What Passed

- The Docker stack stayed up and healthy after the run.
- `tavily-adapter` and `vertex-openai-proxy` remained healthy.
- No Vertex 400 / thought-signature protocol failure was observed.
- The system can complete multi-agent research jobs on the VPS with the custom
  Vertex proxy.
- The Russian query eventually produced a Russian final synthesis, so locale
  following works at least at final-synthesis level.

## What Failed Or Needs Hardening

### 1. Citation Grounding Is Not Strict Enough

Four of the five scenarios surfaced partial citation grounding: subagents cited
some URLs without successful extract files. The pipeline records this as
`partial`, but the final report can still cite those URLs.

Product implication: for strict research, "found a URL" and "read/extracted the
source" must be separated. A final citation should require a successful extract,
or the report must label it as unverified/search-only.

Follow-up hardening in the source-controlled overlay and live VPS adapter now
enforces this at final-report time: URLs without a matching `./extracts/<id>.md`
are labeled `search_only_unverified`, surfaced in `citation_integrity`, and
mark the completed job as degraded.

Second-pass citation hardening tightens that policy further: unrepaired
unverified URLs are removed from the normal `## References` / `## Sources`
list and moved into the `## Citation Integrity` warning block as excluded
search-only reference lines. Inline/body mentions are still preserved but
marked with `search_only_unverified`. This keeps failed extracts useful as
leads without letting them look like extract-backed evidence.

### 2. Deep Research Is Too Slow For Default Daily Use

Completed jobs took roughly 12-18.5 minutes. One job exceeded 20 minutes and
timed out.

Product implication: the default mode should probably be cheaper than full deep
research. A practical shape is:

- `quick`: search + a small number of extracts + short answer;
- `standard`: bounded multi-source report;
- `deep`: current role-based multi-agent method with critic/fact-checker.

### 3. Internal Subagent Timeout Is A Real Failure Mode

The technical and controversial scenarios had internal subagents timing out
around `600s`. The system can sometimes recover, but this creates slow retries
and partial evidence.

Product implication: subagent budgets need to be explicit per mode, with fewer
URLs/tasks in default mode and clearer cancellation behavior.

### 4. `report.md` Artifact Contract Is Not Guaranteed

The Russian job completed, but no physical `report.md` was written under
`/opt/searcharvester/jobs/066fec9848b74a41/`. The API returned the report by
falling back to assistant message chunks and set:

```text
no report.md - using assistant message
```

Product implication: the API should guarantee a stable artifact for every
completed report. If the agent says `REPORT_SAVED: ./report.md` but the file is
missing, the orchestrator should either write the fallback into `report.md` or
mark the job as degraded.

Follow-up hardening in the source-controlled overlay and live VPS adapter now
narrows this fallback: only the last top-level `lead` message may be recovered
as the final report, the recovered text is persisted into `report.md`, and the
job is marked degraded. Sub-agent messages are not valid final report fallbacks.

### 5. Request Fidelity Needs Stronger Constraints

The Russian query asked for a short report. The final report was about `29.5k`
characters, which is not short. The run also showed that intermediate
researcher outputs can ignore the requested output language, even if the final
synthesis later corrects it.

Product implication: mode, length, and language should be part of the research
request contract, not only natural-language instructions inside the query.

### 6. Terminal Approval Callback Bug

The fresh-news scenario logged:

```text
Approval callback failed: ... unexpected keyword argument 'allow_permanent'
terminal failed: BLOCKED: User denied. Do NOT retry.
```

The job recovered by writing the report through another path, but the callback
mismatch should be fixed or avoided.

## Follow-Up: Citation Integrity Live Smoke

After implementing final-report citation hardening, a live VPS smoke was run
against `/research`:

```text
job_id: 88ccd3de1dc74950
query: Short cited smoke test for "what is SearXNG and why self-host it"
status: completed
duration_sec: 466.581114
report_chars: 5060
error: citation contract degraded - unverified citations: 7
```

Observed `citation_integrity`:

```json
{
  "total_urls": 15,
  "verified_urls": 8,
  "unverified_urls": 7
}
```

The live `report.md` persisted under
`/opt/searcharvester/jobs/88ccd3de1dc74950/report.md` and included:

- a `## Citation Integrity` section;
- `[search_only_unverified]` markers on unverified references;
- a final `done` event payload with `degraded: true`,
  `citation_integrity`, and `note`.

This confirms the API no longer silently blends search-only URLs with
extract-backed citations. It also confirms the remaining product issue:
even a short smoke query still ran the full deep pipeline and took about
7.8 minutes.

## Follow-Up: Standard Mode Live Smoke

After adding `POST /research` request modes, a short `mode=standard` smoke was
run against the live VPS:

```text
job_id: 1d1bf2594865414b
query: In 2 cited bullets, what is SearXNG and why would someone self-host it? Keep it short.
mode: standard
max_report_chars: 3000
language: en
status: completed
duration_sec: 26.594431
error: null
```

Observed `citation_integrity`:

```json
{
  "total_urls": 2,
  "verified_urls": 2,
  "unverified_urls": 0,
  "unverified": []
}
```

Snapshot checks:

```text
artifacts: plan.md=441, report.md=1374, hermes.log=1663
event_count: 22
delegate_mentions: 0
```

An earlier `mode=standard` smoke completed in about 34.6s but returned
`citation contract degraded - unverified citations: 1`. The standard
prompt/skill was tightened so final reports must not include raw URLs unless
that exact URL was extracted and read. The next smoke passed with no unverified
citations.

Product implication: Harvester now has the split needed by the four-channel
research operating model:

- `mode=standard`: bounded extract-backed report for `Вебсёрчер под Хафт`;
- `mode=deep`: existing multi-agent deep research for `Дипресёрчер`.

## Follow-Up: Standard Mode Pre-Haft Dogfood

After the first clean `mode=standard` smoke, five more production VPS dogfood
runs were executed with realistic pre-Haft / decision-grade prompts.

| Scenario | Job ID | Status | Duration | Citation integrity | Notes |
|---|---:|---:|---:|---:|---|
| Perplexity API vs Harvester | `d67b07b0237b44bf` | completed | `54.1s` | `4/4` verified | clean |
| Fly.io vs Railway vs VPS AI sidecar | `1ed0c75559874c2e` | completed | `56.2s` | `0` URLs in report | issue found: extracted sources existed, but final report cited extract IDs/names instead of source URLs |
| SearXNG vs Tavily vs Perplexity discovery | `5c74c649eeea4429` | completed | `49.3s` | `4/4` verified | clean |
| MCP vs REST agent tools | `dc40c6ccaec8475f` | completed | `43.4s` | `5/5` verified | clean |
| Gemini Flash for research pipelines | `79ca83797f5f4d40` | completed degraded | `85.4s` | `0/5` verified | issue found: markdown backticks around URLs caused false unverified matches; one search-only URL was also present |

Two hardening changes followed from this run:

- Standard reports must cite extracted/read sources by original source URL, not
  by `./extracts/<id>.md` file IDs alone.
- Citation verification now normalizes markdown/sentence wrappers around URLs
  before comparing report URLs with extract hashes.

The hardening was deployed to the VPS and the two failing scenarios were rerun:

| Scenario | Job ID | Status | Duration | Citation integrity | Notes |
|---|---:|---:|---:|---:|---|
| Fly.io vs Railway vs VPS AI sidecar rerun | `5fb79afd41bc4fa1` | completed | `55.5s` | `7/7` verified | fixed |
| Gemini Flash research pipeline rerun | `565daf0ca1ac4f2a` | completed | `375.7s` | `3/3` verified | fixed, but slow |

The second rerun shows an important product nuance: `mode=standard` is much
faster than `mode=deep` in normal cases, but can still take several minutes
when extraction/reporting pulls heavier model/vendor documentation. This is
acceptable for `Вебсёрчер под Хафт`, but the caller should still treat it as a
research operation, not an instant search.

## Follow-Up: Standard Report-File Contract Hardening

A fresh `web_researcher` pre-Haft smoke proved that the global agent now calls
Harvester `mode=standard`, but it also surfaced a standard-mode artifact issue:

```text
job_id: 42640dbf1d524db3
status: completed
duration_sec: 48.7497
citation_integrity: 4/4 verified
warning: report.md missing - recovered final lead message
```

Root cause from `events.jsonl`:

- the agent wrote `./plan.md`;
- it extracted and read sources;
- it did not emit `write: ./report.md`;
- it returned the full report as the final assistant message and appended
  `REPORT_SAVED: ./report.md`;
- the adapter recovered that final lead message and persisted `report.md`.

The fix tightened both the standard prompt suffix and the
`searcharvester-standard-research` skill:

- write `./report.md` with the file write/edit tool;
- do not put the report body in the final assistant message;
- verify the file with `wc -c ./report.md`;
- final assistant message must contain only `REPORT_SAVED: ./report.md`;
- do not claim `REPORT_SAVED` if the file cannot be written or verified.

Live VPS rerun:

```text
job_id: 6fd36cd5c5244192
query: In 2 cited bullets, what is trafilatura and why use it for LLM evidence extraction? Keep it short.
mode: standard
status: completed
duration_sec: 29.698797
error: null
citation_integrity: 3/3 verified
report.md: 931 bytes
```

Observed event sequence:

- `write: ./plan.md`
- `write: ./report.md`
- `terminal: wc -c ./report.md`
- final message: `REPORT_SAVED: ./report.md`
- final `done` payload had no `degraded` flag.

## Follow-Up: Global `web_researcher` Pre-Haft Five-Scenario Dogfood

Five fresh-session `web_researcher` subagents were run against realistic
pre-Haft decision prompts. Each prompt was expected to do normal discovery,
then call Harvester `mode=standard`, wait for terminal status, and return an
evidence packet without making the final Haft decision.

| Scenario | Harvester job | Harvester result | Agent behavior | Verdict |
|---|---:|---:|---|---|
| AI sidecar hosting: Cloud Run vs Fly.io vs Railway vs budget VPS | `a44261306e8846ae` | completed, `6/6` verified | waited for final status and surfaced `job_id`, `status`, `citation_integrity` | pass |
| Cross-repo research interface: MCP vs REST+CLI vs subagent | `ba88f9561c6a432f` | completed, `5/5` verified | waited for final status and kept the packet decision-oriented | pass |
| Web research model choice: Flash vs reasoning vs router/executor | `bdb7d65d37c14cab` | completed, `6/6` verified | returned while Harvester was still `running`; server completed later | agent wait fail |
| Private research service exposure: SSH vs reverse proxy vs bearer API | `ff10736e098f492c` | completed, `3/3` verified | returned while Harvester was still `running`; server completed later | agent wait fail |
| Psychology-adjacent AI cards: bounded AI ops vs universal AI coach | `c502e5286d65473f` | completed degraded, `5/6` verified | waited for final status and marked the unverified LinkedIn citation | pass with degraded citation |

Server-side observation:

- all five Harvester jobs reached a terminal status;
- all five had a final `wc -c ./report.md` check;
- four of five had fully verified citations;
- one had a deliberately surfaced degraded citation warning;
- the two failures were not Harvester completion failures, but
  `web_researcher` workflow failures: the agent treated `running` as something
  it could report as a usable Harvester packet.

Follow-up hardening applied to the global user-level agent:

- in `Pre-Haft Evidence Packet mode`, `web_researcher` must keep polling until
  Harvester reaches `completed`, `failed`, or `error`;
- `running`, `queued`, `pending`, and `citation_integrity: null` are not
  deliverable evidence;
- if interrupted or practically timed out, the agent may return only an
  explicit incomplete status with `job_id` and current status, not a
  decision-grade packet.

Post-hardening smoke:

```text
query: Playwright vs Chrome DevTools MCP vs browser-use style agent plugin
job_id: 1742d985c60e4301
status: completed
duration_sec: 176.123219
error: citation contract degraded - unverified citations: 2
citation_integrity: 3/5 verified
```

The smoke confirms the wait-rule fix at the agent layer: the subagent did not
return while Harvester was still `running`; it waited until the final
`completed` status. It also confirmed that degraded citation integrity remains
visible to the parent chat instead of being silently treated as clean evidence.

## Follow-Up: Standard Citation Repair Pass

The previous smoke still showed an important quality gap: Harvester can finish
as `completed degraded` when the report cites useful URLs that were discovered
but not saved under `./extracts/`. The concrete example was:

```text
job_id: 1742d985c60e4301
status: completed
error: citation contract degraded - unverified citations: 2
unverified:
- https://playwright.dev/docs/trace-viewer
- https://playwright.dev/docs/ci
```

Root cause:

- the final report cited Playwright docs URLs;
- those exact URLs were not present as saved extract artifacts;
- the adapter correctly labeled them `search_only_unverified`, but this still
  made the packet weaker than needed when the URLs were extractable.

Hardening added:

- standard-mode finalization now runs a bounded citation repair pass before
  declaring degraded citation integrity;
- for each unverified report URL, the adapter tries to call its own `/extract`
  endpoint, save the resulting markdown into `./extracts/<id>.md`, and then
  re-run citation verification;
- repaired URLs are reported in `citation_integrity.repaired_urls`;
- URLs that still fail extraction remain `search_only_unverified` and keep the
  job degraded.

Production verification:

```text
synthetic repair smoke:
input report URL: https://playwright.dev/docs/ci
status: completed
error: null
citation_integrity: 1/1 verified
repaired_urls: ["https://playwright.dev/docs/ci"]
search_only_unverified marker: false
```

Live standard research smoke after deployment:

```text
query: Playwright CI vs Trace Viewer for solo-developer UI validation
job_id: 8e7c366e1ff746f9
status: completed
duration_sec: 143.598987
error: null
citation_integrity: 3/3 verified
```

In the live research smoke, the agent extracted the Playwright docs itself, so
the repair pass was not needed. The synthetic in-container smoke proves the
repair path directly.

## Follow-Up: Parallel Deep-Mode Stress Test

Three production `mode=deep` jobs were launched in parallel to test the
explicit `Дипресёрчер` path under realistic heavy prompts:

| Scenario | Job ID | Status | Duration | Extracts | Report | Notes |
|---|---:|---:|---:|---:|---:|---|
| Workflow orchestration: Postgres queue vs Redis/Celery/RQ vs Temporal | `2a1eee9152ea479c` | timeout | `1209.3s` | `9` | none | first delegate round had 2 completed subagents and 1 timeout; second delegate round was still running when lead timed out |
| Current search APIs: Perplexity vs Tavily vs Exa vs Google/Vertex vs Harvester | `bdaa24e7854441ed` | timeout | `1209.2s` | `19` | none | first delegate round completed; second critic/fact-check round had 1 completed subagent and 1 timeout |
| Psychology/self-help AI safety: no-AI vs bounded AI ops vs open-ended chat | `daf75aa03b1c431c` | timeout | `1209.2s` | `30` | none | first delegate round completed; second critic/fact-check round did not finish before lead timeout |

Observed API result for all three:

```text
status: timeout
error: exceeded timeout of 1200s
citation_integrity: null
report_len: 0
```

What this proves:

- deep mode timeout semantics are explicit: jobs become terminal `timeout`
  instead of hanging forever;
- the VPS stack survived the parallel load and remained healthy after timeout;
- the jobs accumulated real extracts and sub-agent outputs before timeout;
- no partial report is exposed as a final `report.md`, so the API does not
  pretend incomplete deep research is completed evidence.

What failed product-wise:

- parallel deep mode is too slow for the current `1200s` job budget;
- the parent API exposes only `running` until timeout, even though internal
  phases and extracts are progressing;
- there is no stable partial artifact such as `round1.md`, `critic.md`, or
  `partial_report.md` for interrupted jobs;
- sub-agent evidence can be partial (`URLs cited without extract files`) before
  final report citation repair has a chance to run;
- the lead agent may lose the chance to synthesize because the second
  critic/fact-check delegate round consumes the remaining job budget;
- one plan-write attempt used shell heredoc with an `&` character in text and
  was blocked as backgrounding. The agent recovered with the file write tool,
  but deep skills should prefer file write/edit over shell heredocs for
  markdown artifacts.

Product implication:

`mode=deep` is not ready as a default "better search" mode. It should remain an
explicit `Дипресёрчер` path with long-run expectations, and its next hardening
should focus on phase visibility, partial artifacts, and bounded round budgets
rather than citation repair alone.

## Follow-Up: Deep Timeout Progress And Partial Artifact Hardening

Root-cause analysis after the three parallel deep timeouts:

- running three deep jobs in parallel amplified load, but was not the only
  cause;
- each deep job already contains internal parallelism: researcher batch first,
  then critic/fact-checker batch;
- the old deep skill let the work expand too far: 2-3 researchers, 4-6 extracts
  each, then additional adversarial/fact-check extracts;
- the second delegate round could consume the remaining `1200s` budget, leaving
  no time for lead synthesis;
- the API exposed only `running` until terminal timeout even when extracts and
  sub-agent messages had already accumulated.

Hardening added on 2026-05-10:

- `GET /research/{job_id}` now includes `progress`:
  - phase;
  - delegate round count;
  - sub-agent spawned/done/status counts;
  - extract count;
  - artifact sizes;
  - last observed event.
- On timeout, the orchestrator runs a final `_backfill_subagents(...)` pass and
  writes `partial_report.md`.
- `partial_report.md` is assembled mechanically from already observed events,
  sub-agent summaries, saved extracts, and artifact sizes. It does not call an
  LLM and is not a second synthesis layer.
- Timeout responses expose `partial_report` and `progress`, while keeping:
  - `status: timeout`;
  - `report: null`;
  - `citation_integrity: null`.
- The deep skill now has a smaller default completion budget:
  - 2 researchers by default;
  - 3 only for broad three-branch questions;
  - 3-4 successful extracts per researcher;
  - critic targets top 2-3 contestable claims;
  - fact-checker verifies top 3 facts/dates/numbers;
  - no third delegate round.

Verification:

```text
local orchestrator/mode tests: 15 passed
VPS container tests: 25 passed
VPS health: ok
```

This does not make deep research "fast"; it makes it bounded and inspectable.
The product rule remains: use `mode=standard` for normal pre-Haft evidence and
reserve `mode=deep` for explicit `Дипресёрчер` requests.

## Follow-Up: Single Deep Dogfood After Budget Hardening

A fresh single-job `mode=deep` smoke was run after the timeout/progress and
budget changes, without parallel deep load:

```text
job_id: 339bba2f499d4bd0
query: VPS vs Google Cloud Run for a private AI research sidecar, 3-10 requests/day
mode: deep
max_report_chars: 12000
language: en
status: completed
duration_sec: 715.477497
report.md: 5334 bytes
extracts: 7
delegate_rounds: 2
subagents done: 4 completed
error: citation contract degraded - unverified citations: 4
citation_integrity: 4/8 verified
```

Observed behavior:

- the new deep budget worked at the decomposition layer: Round 1 launched 2
  researchers, not 3;
- Round 1 completed quickly for deep mode: 2 researcher tasks in about `102s`;
- Round 2 completed but dominated runtime: critic/fact-checker took about
  `557s`;
- the lead wrote a physical `report.md` after the heredoc write was blocked by
  the `&` backgrounding guard; it recovered via the file write tool;
- the final report surfaced a useful critic correction: Cloud Run warm-instance
  cost and egress are less favorable than the initial researcher framing;
- the final job completed inside the `1200s` budget, so the single-job deep
  path is viable after budget hardening.

Remaining issues found:

- Round 2 still wastes budget on tool-discipline mistakes: attempts included
  non-existent shell commands / tools such as `google_search`, `read_file`, and
  wrong skill paths before recovering.
- The ACP stream still does not expose sub-agent spawn metadata reliably when
  `raw_input` is null; `subagents.done` is backfilled, but `subagents.spawned`
  remains `0`.
- Deep-mode finalization does not run the standard-mode citation repair pass.
  The completed report stayed degraded with four unverified URLs:
  - `https://www.danilchenko.dev/posts/digitalocean-to-hetzner-migration/`
  - `https://cloud.google.com/run/docs/instances`
  - `https://www.hetzner.com/cloud`
  - `https://cloud.google.com/blog/products/serverless/whats-new-in-cloud-run-at-next-26`

Follow-up hardening applied after this dogfood:

- Round 2 critic/fact-checker templates now have an explicit allowlist:
  `search.py`, `extract.py`, `grep`, `head`, `sed`, `cat`, and `ls ./extracts`.
- Round 2 templates explicitly forbid the failure modes observed in the smoke:
  `google_search`, `skill_view`, `read_file`, `curl`, `wget`, `netstat`, `ss`,
  and direct probes of `http://searxng:*`.
- Completed deep reports now use the same bounded citation repair pass as
  standard reports: extractable report URLs are saved into `./extracts/` before
  citation integrity is finalized.

Verification:

```text
local orchestrator/mode tests: 16 passed
VPS container tests: 26 passed
VPS health: ok
```

Conclusion:

`mode=deep` is now usable as an explicit long-running `Дипресёрчер` path for a
single request, but still needs another live dogfood after Round 2 tool
discipline and deep citation repair. The remaining high-value hardening is
progress telemetry for live delegate sub-agents when ACP does not include
`raw_input`.

## Follow-Up: Single Deep Dogfood After Round 2 And Citation Repair Hardening

A fresh single-job `mode=deep` smoke was run after Round 2 tool-discipline
instructions and deep citation repair were deployed:

```text
job_id: f456f9d05a91456a
query: VPS vs Google Cloud Run for a private AI research sidecar, 3-10 requests/day
mode: deep
max_report_chars: 12000
language: en
status: completed
duration_sec: 392.056596
report.md: 5095 bytes
extracts: 16
delegate_rounds: 2
subagents done: 4 completed
error: null
citation_integrity: 11/11 verified
repaired_urls: 6
```

Comparison with the previous single deep dogfood `339bba2f499d4bd0`:

| Metric | Before | After | Result |
|---|---:|---:|---|
| Total duration | `715.5s` | `392.1s` | improved |
| Round 1 duration | about `102s` | about `168s` | slower in this run, but not the bottleneck |
| Round 2 duration | about `557s` | about `157s` | improved |
| Extracts | `7` | `16` | improved evidence coverage |
| Citation integrity | `4/8` verified | `11/11` verified | fixed for this run |
| Final error | `citation contract degraded - unverified citations: 4` | `null` | fixed for this run |

What improved:

- Deep completed inside the `1200s` budget with a large margin.
- Deep finalization repaired six URLs by extracting them before final citation
  verification.
- The final report had no `search_only_unverified` references.
- Round 2 no longer dominated the whole job; critic/fact-checker time dropped
  from roughly nine minutes to about two and a half minutes.

What remains imperfect:

- Round 2 still attempted some invalid or blocked tool paths before recovering:
  `google_search`, `searcharvester-search` as a shell command, `ss`, direct
  probing of `http://searxng:8080`, and a shell command that tried to inspect
  available tools.
- Those attempts did not break the job, but they still burn model/tool budget
  and show that prompt-level tool discipline is not enough.
- `subagents.spawned` remains `0` in progress telemetry even though
  `subagents.done` was backfilled as `4 completed`; ACP still does not expose
  reliable live spawn metadata for delegate calls with `raw_input: null`.

Product conclusion:

The deep path is now materially better: citation repair works on completed deep
reports, and a single `Дипресёрчер` run is viable on the VPS. The remaining
optimization is not citation quality; it is stronger tool routing for delegated
critic/fact-checker tasks. Prompt warnings reduced damage and duration, but did
not fully prevent imagined tools or internal-service probes.

## Follow-Up: Delegated Tool Routing Hardening

The post-hardening deep dogfood proved that prompt-level instructions reduced
damage but did not fully prevent bad delegated tool attempts. Structural
hardening was added:

- `HERMES_HOME/bin` is prepended to the Hermes subprocess `PATH`.
- Short wrapper commands now exist:
  - `searcharvester-search`
  - `searcharvester-extract`
- Deep skill instructions now prefer those wrappers and version the skill as
  `2.6.0`.
- Deep `plan.md` creation now instructs the lead to use the file write/edit
  tool instead of shell heredocs, avoiding false backgrounding/security blocks
  when user text contains `&`.
- Hermes config registers a `pre_tool_call` shell hook:
  `/opt/data/hooks/research_terminal_guard.py`.
- The hook blocks known bad delegated routes:
  `google_search`, `read_file`, `curl`, `wget`, `netstat`, `ss`,
  direct `http://searxng:*` probes, and container-introspection commands.
- The guard was then tightened from blocklist to default-deny allowlist:
  unknown terminal commands are blocked, safe file readers are bounded to
  `./extracts`, `extracts/`, `report.md`, and `plan.md`, and search/extract
  wrappers must use valid flag syntax.
- `delegation.subagent_auto_approve: true` is set inside the Hermes
  `delegation` block, not as a top-level key. This matters: the top-level
  form did not prevent subagent auto-denials in live testing.
- The guard now blocks malformed wrapper calls before execution:
  `searcharvester-search` without `--query`, chained search/extract commands,
  and `searcharvester-extract --url` with extra positional URLs.

Verification:

```text
local focused tests: 25 passed
VPS focused container tests: 21 passed, then 25 passed after syntax validation
VPS full container tests: 55 passed, 1 skipped
VPS health: ok
Hermes hooks doctor: all hooks healthy
```

Live standard smoke after deployment:

```text
job_id: 5a67923244e94a81
mode: standard
status: completed
duration_sec: 62.140356
error: null
citation_integrity: 1/1 verified
extracts: 2
```

Runtime checks:

- Hermes shell hook allowlist shows
  `python3 /opt/data/hooks/research_terminal_guard.py` as `pre_tool_call`
  `✓ allowed`.
- The live smoke log had zero occurrences of:
  `google_search`, `searcharvester-search: command not found`,
  `http://searxng`, `ss: command not found`, or
  `Tool terminal returned error`.

Product conclusion:

The system now has actual routing rails: subagents can use concise
Searcharvester commands, and common bad or malformed routes are blocked before execution.
This does not prove every future deep Round 2 will be noise-free, because
unknown model/tool behavior can still surface new variants, but the previously
observed bad paths now have structural coverage instead of prompt-only
coverage.

Live deep smoke after strict guard and `delegation.subagent_auto_approve`:

```text
job_id: 844852f329284ba6
mode: deep
status: completed
duration_sec: 253.392096
extracts: 20
subagents: 4 completed
citation_integrity: 10/10 verified
old routing noise:
  auto-denied dangerous command: 0
  command not found: 0
  google_search: 0
  http://searxng: 0
```

Live deep smoke after wrapper-argument validation:

```text
job_id: 54ef6a059cd5476b
mode: deep
status: completed
duration_sec: 297.562675
extracts: 19
citation_integrity: 11/12 verified
error: citation contract degraded - unverified citations: 1
routing/syntax noise:
  auto-denied dangerous command: 0
  command not found: 0
  google_search: 0
  http://searxng: 0
  usage: search.py: 0
  usage: extract.py: 0
  malformed wrapper guard blocks: 0
```

The remaining terminal errors in that smoke were HTTP 502/422 extraction
failures and `grep` no-match exits, not delegated-tool routing failures.
The remaining product gap is therefore extraction/citation reliability for
hard-to-fetch sources such as Medium, not command routing.

## Follow-Up: Unverified Reference Demotion

The next citation-quality slice tightened the final report contract for failed
extracts. Previously, unrepaired URLs stayed in the normal `## References`
section with a `search_only_unverified` marker. That was visible, but still too
easy for a reader or parent agent to treat as a normal citation.

New behavior:

- URLs without matching extract files still run through the bounded repair
  pass first.
- If repair succeeds, the URL becomes normal extract-backed evidence.
- If repair fails and the URL is in a normal `## References`, `## Sources`,
  `## Bibliography`, or `## Links` section, that reference line is removed from
  the main source list.
- Removed lines are preserved under `## Citation Integrity` as
  `Excluded References`, with `excluded_reference_lines` in
  `citation_integrity`.
- Inline/body mentions are not deleted, but they are marked
  `search_only_unverified`.

Verification:

```text
local focused tests:
  tests/test_orchestrator_finalize.py
  tests/test_orchestrator_modes.py
  tests/test_research_terminal_guard.py
  36 passed

VPS full container tests:
  56 passed, 1 skipped

VPS health:
  ok

Hermes hooks doctor:
  all hooks healthy
```

Operational note: the VPS rebuild again pulled a fresh
`nousresearch/hermes-agent:latest` digest. The overlay still passed, but this
reinforces the existing risk that `latest` can change behavior underneath us.

## Follow-Up: Alternate-Source Retry

The next extraction-quality slice reduces degraded reports when a cited source
is relevant but the original URL cannot be extracted.

New behavior:

- Finalization still starts with the strict citation contract.
- For each unverified URL, the adapter first tries to extract the exact cited
  URL.
- If that exact extract fails, the adapter derives a search query from the
  reference line or URL path, calls `/search`, and tries replacement candidates.
- The report URL is rewritten only if the replacement URL has a saved
  `./extracts/<id>.md` artifact.
- Successful replacements are recorded in `citation_integrity.replaced_urls`;
  the replacement URL is also listed in `citation_integrity.repaired_urls`.
- This is a mechanical repair step, not another LLM summary/reduce pass.

Verification:

```text
local focused tests:
  tests/test_orchestrator_finalize.py
  12 passed

local nearby suite:
  tests/test_orchestrator_finalize.py
  tests/test_orchestrator_modes.py
  tests/test_research_terminal_guard.py
  37 passed

VPS nearby suite:
  37 passed

VPS full container suite:
  57 passed, 1 skipped

VPS health:
  ok

Hermes hooks doctor:
  all hooks healthy
```

## Verdict

The VPS deployment is operational, but not yet "strict research grade".

**Dоказано:**

- The Harvester stack runs on the VPS and survives several real research jobs.
- The custom Vertex AI proxy is viable for Hermes tool-calling in this setup.
- The current deep-research flow can produce useful reports, but it is slow.
- `mode=standard` can complete a short extract-backed report without
  `delegate_task`; the first clean VPS smoke finished in about 26.6 seconds
  with 2/2 URLs verified by extracts.
- Five realistic pre-Haft `mode=standard` dogfood runs completed, and the two
  citation-contract defects found there were fixed and rerun successfully on
  production VPS.
- The global `web_researcher` pre-Haft route now calls Harvester
  `mode=standard`; a real smoke returned a Harvester `job_id` and verified
  citation integrity.
- Standard-mode `report.md` writing was hardened and proved on VPS: the agent
  wrote `report.md`, verified it with `wc -c`, and returned only the marker.
- Five realistic global `web_researcher` pre-Haft dogfood scenarios proved that
  Harvester itself can complete realistic standard-mode jobs, including one
  degraded-citation case that was surfaced instead of hidden.
- Citation repair can now recover extractable report URLs before marking a job
  degraded; standard-mode repair was proved in the live container against
  `https://playwright.dev/docs/ci`, and deep-mode repair is covered by the VPS
  container test suite.
- Parallel `mode=deep` stress testing produced terminal `timeout` statuses on
  all three heavy scenarios; the stack stayed healthy, but no final report or
  citation integrity was available.
- Deep timeout handling now produces inspectable `progress` and
  `partial_report.md` without pretending the job completed.
- Deep skill defaults are now budgeted to preserve time for final synthesis.
- Deep Round 2 now has explicit tool-discipline rules to avoid burning budget
  on imagined tools or internal service probes.
- Delegated tool routing now has structural coverage through
  `searcharvester-search` / `searcharvester-extract` wrappers, a strict Hermes
  `pre_tool_call` guard hook, and `delegation.subagent_auto_approve` guarded
  by that allowlist.
- A fresh post-hardening single deep dogfood completed in `392.1s` with
  `11/11` verified citations; deep citation repair recovered six URLs before
  final verification.
- Partial URL grounding was a repeated, not theoretical, issue before
  final-report citation hardening.
- Before hardening, completed jobs did not always produce a physical
  `report.md`.

**Риск:**

- Final reports may still mention search-only URLs when repair extraction
  fails, but normal reference-list entries are now demoted into the
  `Citation Integrity` warning block instead of staying beside extract-backed
  references.
- Failed exact-URL extracts can now be repaired by an alternate-source retry,
  but only if `/search` returns a candidate that can be extracted successfully.
  Otherwise the report remains degraded and visibly marked.
- Global subagents can still violate workflow discipline unless their
  instructions enforce terminal Harvester status before final delivery.
- `mode=deep` can still exceed a normal interactive waiting budget, especially
  when several deep jobs run in parallel and the critic/fact-check round starts
  late. The result is now inspectable, but not final evidence.
- `mode=deep` delegated critic/fact-checker tasks can still spend time on
  failed external extracts or no-match file searches, but the known command
  routing and wrapper syntax failures now have structural guards.
- A user may ask for "short" or "на русском", but the system currently enforces
  those constraints softly.

## Recommended Next Slice

Continue hardening before broader product use:

1. If deep still times out often, add per-round time budgeting rather than only
   prompt-level budgets.
2. Consider optional `round1.md` / `critic_factcheck.md` artifacts if
   `partial_report.md` is useful but too coarse.
3. Keep `mode=deep` reserved for explicit deep-research requests.
4. For extraction/citation quality, collect a few real degraded reports after
   alternate-source retry and compare whether `replaced_urls` reduces visible
   citation degradation without introducing weaker substitute sources.
