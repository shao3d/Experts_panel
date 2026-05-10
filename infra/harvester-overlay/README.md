# Harvester VPS Overlay

This directory is the source-controlled overlay for the live
Searcharvester/Harvester sidecar deployed on the InterServer VPS.

The live server path is:

```text
/opt/searcharvester
```

The overlay intentionally includes only rebuildable source/config artifacts:

- `docker-compose.yaml`
- `config.example.yaml`
- `frontend/`
- `simple_tavily_adapter/`
- `vertex-openai-proxy/`
- `hermes_skills/`
- `hermes-data/config.yaml`
- `hermes-data/SOUL.md`

It intentionally excludes runtime and secret material:

- `.env`
- `config.yaml`
- `secrets/`
- `jobs/`
- generated `hermes-data/` state, sessions, logs, memories, skills, and DB files

To deploy, copy this directory to the VPS, provide secrets out-of-band, generate
`config.yaml` from `config.example.yaml`, then run Docker Compose.

`simple_tavily_adapter` owns the `/research` result contract. Completed jobs
must read a physical `report.md`; if that file is missing, recovery is allowed
only from the final top-level lead-agent message. Recovered reports are written
back to `report.md` and marked degraded. Sub-agent messages are not valid final
report fallbacks.

Final reports also get citation-integrity enforcement. URLs in `report.md` are
checked against saved `./extracts/<id>.md` artifacts. URLs without a matching
extract first go through a bounded standard-mode repair pass: the adapter tries
to extract the missing report URLs itself, saves successful extracts back under
`./extracts/`, and then re-runs citation verification. URLs that still cannot be
extracted are labeled `search_only_unverified`, reported in
`citation_integrity`, and mark the completed job as degraded rather than
silently passing as evidence.

Deep-mode timeouts are also handled explicitly. If `mode=deep` exceeds the
job timeout, the adapter now performs a final sub-agent backfill and writes a
mechanical `partial_report.md` from already observed events, sub-agent
summaries, and saved extracts. This artifact is exposed as `partial_report`
and `progress` through `GET /research/{job_id}`; it is not treated as a final
`report.md` and has no citation-integrity verdict.

See:

```text
docs/guides/harvester-vps-deploy.md
docs/quality/harvester-vps-battle-tests-2026-05-09.md
```
