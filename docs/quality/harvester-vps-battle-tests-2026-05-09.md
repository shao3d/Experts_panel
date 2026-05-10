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
- Partial URL grounding was a repeated, not theoretical, issue before
  final-report citation hardening.
- Before hardening, completed jobs did not always produce a physical
  `report.md`.

**Риск:**

- Final reports may still contain search-only URLs, but the adapter now labels
  them `search_only_unverified`; product surfaces must make that warning visible.
- `mode=deep` can exceed a normal interactive waiting budget.
- A user may ask for "short" or "на русском", but the system currently enforces
  those constraints softly.

## Recommended Next Slice

Continue hardening before broader product use:

1. Run a broader fresh-session dogfood of global `web_researcher` pre-Haft mode
   on 2-3 real decision questions, verifying Harvester `job_id`,
   `citation_integrity`, and no `report.md` recovery warnings.
2. Keep monitoring `mode=deep` separately; deep mode can still exceed normal
   interactive waiting budgets and may have different artifact behavior.
3. Keep `mode=deep` reserved for explicit deep-research requests, because the
   production battle tests show it can exceed a normal interactive waiting
   budget.
