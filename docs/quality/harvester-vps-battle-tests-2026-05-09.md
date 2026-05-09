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

## Verdict

The VPS deployment is operational, but not yet "strict research grade".

**Dоказано:**

- The Harvester stack runs on the VPS and survives several real research jobs.
- The custom Vertex AI proxy is viable for Hermes tool-calling in this setup.
- The current deep-research flow can produce useful reports, but it is slow.
- Partial URL grounding is a repeated, not theoretical, issue.
- Before hardening, completed jobs did not always produce a physical
  `report.md`.

**Риск:**

- Final reports may look polished while mixing extracted evidence with
  search-only or unextracted URLs.
- The default deep-research path can exceed a normal interactive waiting budget.
- A user may ask for "short" or "на русском", but the system currently enforces
  those constraints softly.

## Recommended Next Slice

Implement a strict evidence mode before broader product use:

1. Final citations require successful extract files by default.
2. URLs without extract are either omitted or labeled `search_only_unverified`.
3. Re-test the `report.md` recovery hardening with an end-to-end missing-report
   case: completed recovered jobs must persist `report.md`, mark the result
   degraded, and never use sub-agent messages as fallback.
4. Add request-level knobs for `mode`, `language`, and `max_report_chars`.
5. Re-run the same five scenarios and compare latency, partial counts, and
   report fidelity.
