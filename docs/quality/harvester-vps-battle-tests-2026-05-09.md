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
- Standard-mode citation repair can now recover extractable report URLs before
  marking a job degraded; this was proved in the live container against
  `https://playwright.dev/docs/ci`.
- Parallel `mode=deep` stress testing produced terminal `timeout` statuses on
  all three heavy scenarios; the stack stayed healthy, but no final report or
  citation integrity was available.
- Partial URL grounding was a repeated, not theoretical, issue before
  final-report citation hardening.
- Before hardening, completed jobs did not always produce a physical
  `report.md`.

**Риск:**

- Final reports may still contain search-only URLs when repair extraction fails,
  but the adapter now labels them `search_only_unverified`; product surfaces
  must make that warning visible.
- Global subagents can still violate workflow discipline unless their
  instructions enforce terminal Harvester status before final delivery.
- `mode=deep` can exceed a normal interactive waiting budget, especially when
  several deep jobs run in parallel and the critic/fact-check round starts late.
- A user may ask for "short" or "на русском", but the system currently enforces
  those constraints softly.

## Recommended Next Slice

Continue hardening before broader product use:

1. Add deep-mode phase visibility to `/research/{job_id}`: current phase,
   delegate round, extract count, subagent completed/failed counts, and last
   progress timestamp.
2. Persist partial deep artifacts before each delegate round returns:
   `round1.md`, `critic_factcheck.md`, and/or `partial_report.md`.
3. Add explicit round budgets so the lead preserves enough time for final
   synthesis, or mark `partial` with a stable artifact instead of timing out
   without a report.
4. Keep `mode=deep` reserved for explicit deep-research requests until the
   partial-artifact contract is implemented and dogfooded.
