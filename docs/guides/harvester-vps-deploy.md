# Harvester VPS Deploy Runbook

**Status:** Active sidecar runbook
**Last updated:** 2026-05-10
**Scope:** Searcharvester/Harvester stack on the InterServer VPS for web search,
extraction, and Hermes deep research through Vertex AI.

This document is the repo-local artifact for the current Harvester deployment.
It is intentionally operational: where it lives, how it is wired, how to verify
it, and how to update it without leaking secrets.

The source-controlled overlay now lives in:

```text
infra/harvester-overlay/
```

The live VPS directory `/opt/searcharvester` is the deployed copy. Do not treat
runtime files from the VPS as source unless they are explicitly listed in the
overlay manifest below.

## Short Answer

Harvester is deployed as a private sidecar on:

- host: `153.75.248.11`
- SSH user: `deploy`
- app dir: `/opt/searcharvester`
- repo overlay: `infra/harvester-overlay/`
- public exposure: none, except SSH
- local access pattern: SSH tunnel

The LLM path is:

```text
Hermes Agent -> OpenAI-compatible local proxy -> Vertex AI Gemini
```

We do not use LiteLLM for this deployment. The local proxy mirrors the Experts
Panel Vertex AI auth pattern and converts OpenAI-style chat/tool calls into
Vertex `generateContent` requests.

## Current VPS State

Verified state as of 2026-05-09:

- Ubuntu `22.04.5 LTS`
- Docker `29.4.3`
- Docker Compose plugin `v5.1.3`
- root SSH login disabled
- password SSH login disabled
- `deploy` user has passwordless sudo and docker access
- UFW active:
  - allow: `22/tcp`
  - default incoming: deny
- Harvester service ports bind only to localhost:
  - `127.0.0.1:8000` -> `tavily-adapter`
  - `127.0.0.1:8999` -> `searxng`
  - `127.0.0.1:9762` -> frontend
  - `vertex-openai-proxy` is internal only on Docker network port `8080`

Do not open `8000`, `8999`, or `9762` publicly until an auth/reverse-proxy
boundary is designed.

## Runtime Topology

Compose services in `/opt/searcharvester/docker-compose.yaml`:

| Service | Purpose | Exposure |
|---|---|---|
| `searxng` | metasearch backend | `127.0.0.1:8999` |
| `tavily-adapter` | Harvester API: `/search`, `/extract`, `/research` | `127.0.0.1:8000` |
| `vertex-openai-proxy` | OpenAI-compatible proxy to Vertex AI | Docker network only |
| `frontend` | Harvester UI | `127.0.0.1:9762` |
| `redis` | Valkey/Redis runtime dependency | Docker network only |

API endpoints:

- `POST /search` - Tavily-compatible search through SearXNG.
- `POST /extract` - URL to markdown extraction through trafilatura.
- `POST /research` - standard or deep research job through Hermes.
- `GET /research/{job_id}` - status and final `report.md`.
- `GET /research/{job_id}/events` - structured job events.
- `GET /research/{job_id}/logs` - Hermes logs.
- `DELETE /research/{job_id}` - cancel running job.

## Secrets And Env

Secrets live only on the VPS. Do not commit them.

Expected secret files:

```text
/opt/searcharvester/.env
/opt/searcharvester/secrets/vertex-sa.json
```

Expected `.env` shape, without secret values:

```bash
VERTEX_AI_PROJECT_ID=<gcp-project-id>
VERTEX_AI_LOCATION=us-central1
VERTEX_DEFAULT_MODEL=gemini-3-flash-preview
VERTEX_PROXY_TIMEOUT_SECONDS=300

OPENAI_API_KEY=vertex-proxy-local
OPENAI_BASE_URL=http://vertex-openai-proxy:8080/v1

HERMES_UID=1000
HERMES_GID=1000
VITE_API_URL=http://localhost:8000
```

The service account JSON is mounted read-only into `vertex-openai-proxy` as:

```text
/run/secrets/vertex-sa.json
```

The proxy reads it via:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/vertex-sa.json
```

This follows the same auth family as Experts Panel backend:

- `VERTEX_AI_SERVICE_ACCOUNT_JSON`
- `VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH`
- `GOOGLE_APPLICATION_CREDENTIALS`
- ADC fallback where available

For the VPS deployment, prefer file mount + `GOOGLE_APPLICATION_CREDENTIALS`.

## Local Changes Applied To Upstream Searcharvester

The deployed stack is upstream `vakovalskii/searcharvester` plus a small local
overlay:

1. Added `vertex-openai-proxy/`.
   - FastAPI service.
   - Exposes `GET /health`, `GET /v1/models`, `POST /v1/chat/completions`.
   - Converts OpenAI chat messages/tools/tool results to Vertex `generateContent`.
   - Converts Vertex `functionCall` parts back to OpenAI `tool_calls`.
   - Handles Gemini 3 `thoughtSignature` across tool-call turns.
   - Groups consecutive OpenAI `tool` messages into one Vertex user turn with
     multiple `functionResponse` parts.
   - Non-streaming only; Harvester/Hermes streaming is disabled in the adapter
     image patch.

2. Patched `docker-compose.yaml`.
   - Binds public service ports to `127.0.0.1`.
   - Adds `vertex-openai-proxy`.
   - Points Hermes/OpenAI env to `http://vertex-openai-proxy:8080/v1`.
   - Mounts `./secrets/vertex-sa.json`.
   - Mounts `./hermes_skills` into the adapter container.

3. Patched `simple_tavily_adapter/docker/entrypoint-adapter.sh`.
   - Syncs upstream bundled Hermes skills.
   - Copies Harvester custom skills from `/opt/searcharvester-hermes-skills`
     into `$HERMES_HOME/skills`.

4. Patched `hermes-data/config.yaml`.
   - `provider: custom`
   - `model.default: gemini-3-flash-preview`
   - `base_url: http://vertex-openai-proxy:8080/v1`

Minimum overlay files/directories that must exist before `docker compose up`:

```text
docker-compose.yaml
config.example.yaml
frontend/
simple_tavily_adapter/
hermes-data/config.yaml
hermes-data/SOUL.md
hermes_skills/
vertex-openai-proxy/
```

Do not treat the whole live `hermes-data/` directory as source. After startup it
contains generated/runtime state. For the overlay, keep only the intentional
config files such as `hermes-data/config.yaml` and `hermes-data/SOUL.md`; bundled
and custom skills are synced at container startup.

Runtime-only paths that must not be committed or copied into docs:

```text
.env
secrets/
jobs/
config.yaml
hermes-data/.env
hermes-data/cron/
hermes-data/home/
hermes-data/logs/
hermes-data/memories/
hermes-data/plans/
hermes-data/sessions/
hermes-data/skills/
hermes-data/workspace/
```

## Bootstrap From Scratch

Use this only for rebuilding a fresh VPS. Do not paste secrets into docs or
chat logs.

1. Prepare the server.

```bash
ssh deploy@153.75.248.11
sudo apt-get update
sudo apt-get install -y ca-certificates curl ufw
```

Docker is already installed on the current server. On a fresh server, install
Docker from the official Docker repo, then verify:

```bash
docker version
docker compose version
docker run --rm hello-world
```

2. Create the app directory.

```bash
sudo mkdir -p /opt/searcharvester
sudo chown -R deploy:deploy /opt/searcharvester
```

3. Copy the prepared Harvester overlay into `/opt/searcharvester`.

The repo-local source is `infra/harvester-overlay/`. Copy its contents to the
VPS app directory; do not copy unrelated repo files.

```bash
scp -r infra/harvester-overlay/* deploy@153.75.248.11:/opt/searcharvester/
scp infra/harvester-overlay/.gitignore infra/harvester-overlay/.env.example \
  deploy@153.75.248.11:/opt/searcharvester/
```

4. Add secrets on the VPS only.

```bash
mkdir -p /opt/searcharvester/secrets
chmod 700 /opt/searcharvester/secrets

# Copy the Vertex service account JSON securely, then:
chmod 600 /opt/searcharvester/secrets/vertex-sa.json

# Create /opt/searcharvester/.env with the non-secret env names above.
chmod 600 /opt/searcharvester/.env
```

5. Generate SearXNG config secret if needed.

```bash
cd /opt/searcharvester
python3 - <<'PY'
from pathlib import Path
import secrets

src = Path("config.example.yaml").read_text()
secret = secrets.token_urlsafe(48)
Path("config.yaml").write_text(src.replace("ultrasecretkey", secret))
PY
chmod 600 config.yaml
```

6. Start the stack.

```bash
cd /opt/searcharvester
docker compose --env-file .env config >/tmp/searcharvester.compose.rendered.yml
docker compose --env-file .env up -d --build
```

Compose interpolation can use variables from the ambient shell before values
from `--env-file`. For local config validation, prefer a clean env, for example:

```bash
cd infra/harvester-overlay
env -u OPENAI_API_KEY -u OPENAI_BASE_URL -u OPENROUTER_API_KEY \
  -u ANTHROPIC_API_KEY -u GEMINI_API_KEY \
  docker compose --env-file .env.example config
```

## Update Existing VPS

The paths in this section are relative to `infra/harvester-overlay/`.

When changing only the proxy:

```bash
cd infra/harvester-overlay
scp vertex-openai-proxy/app.py deploy@153.75.248.11:/opt/searcharvester/vertex-openai-proxy/app.py
ssh deploy@153.75.248.11 'cd /opt/searcharvester && docker compose --env-file .env up -d --build vertex-openai-proxy'
```

When changing compose or adapter entrypoint:

```bash
cd infra/harvester-overlay
scp docker-compose.yaml deploy@153.75.248.11:/opt/searcharvester/docker-compose.yaml
scp simple_tavily_adapter/docker/entrypoint-adapter.sh deploy@153.75.248.11:/opt/searcharvester/simple_tavily_adapter/docker/entrypoint-adapter.sh
ssh deploy@153.75.248.11 'cd /opt/searcharvester && docker compose --env-file .env up -d --build tavily-adapter'
```

After any update, run the verification checklist below.

## Access From Local Machine

Use SSH tunnels:

```bash
ssh -L 8000:127.0.0.1:8000 -L 9762:127.0.0.1:9762 deploy@153.75.248.11
```

Then open locally:

- API: `http://localhost:8000`
- UI: `http://localhost:9762`

## Verification Checklist

Run on the VPS:

```bash
cd /opt/searcharvester
docker compose --env-file .env ps
curl -sS http://127.0.0.1:8000/health
```

Expected:

- all containers are `Up`
- `tavily-adapter` is `healthy`
- `vertex-openai-proxy` is `healthy`
- health returns `{"status":"ok", ...}`

Check Vertex proxy health from inside the container:

```bash
cd /opt/searcharvester
docker compose --env-file .env exec -T vertex-openai-proxy \
  python -c 'import urllib.request; print(urllib.request.urlopen("http://localhost:8080/health", timeout=10).read().decode())'
```

Search smoke:

```bash
curl -sS -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"OpenAI Codex CLI","max_results":3}' | python3 -m json.tool
```

Extract smoke:

```bash
curl -sS -X POST http://127.0.0.1:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://developers.openai.com/codex/cli","size":"s"}' | python3 -m json.tool
```

Research smoke:

```bash
curl -sS -X POST http://127.0.0.1:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query":"In 3 cited bullets, what is SearXNG? Use 2 sources. Keep the report short.","mode":"standard"}'
```

Then poll:

```bash
curl -sS http://127.0.0.1:8000/research/<job_id>
```

Successful real smoke observed on 2026-05-09:

```text
job_id: d782d003d3b84604
status: completed
duration_sec: 307.846573
report_bytes: 1107
```

The run completed:

- skill loading;
- `plan.md` creation;
- `mode=deep` round 1 researcher delegation;
- `mode=deep` round 2 critic/fact-checker delegation;
- final `report.md` write;
- report retrieval through `GET /research/{job_id}`.

Broader live battle-test report:

- `docs/quality/harvester-vps-battle-tests-2026-05-09.md`
- 5 production-like `/research` scenarios
- 5 additional production `mode=standard` pre-Haft scenarios
- verdict: infra and Vertex proxy passed; `mode=standard` is usable for
  extract-backed pre-Haft packets, with citation-contract hardening now catching
  missing/source-ID-only URLs and markdown-wrapped URL edge cases.

## Public Exposure Check

Run locally:

```bash
curl -sS --connect-timeout 5 http://153.75.248.11:8000/health
```

Expected today:

```text
curl: (28) Failed to connect ... Timeout was reached
```

Run on VPS:

```bash
sudo ufw status verbose
ss -ltnp | grep -E ':(22|8000|8999|9762|8080)'
```

Expected:

- UFW allows only `22/tcp`.
- Harvester ports listen on `127.0.0.1`.

## Known Edge Cases

- Some sites block extraction with `403`, `422`, or `502`.
  - Example: Wikipedia returned `403` during initial smoke.
  - OpenAI docs extraction passed.
- Hermes delegated tasks can cite a URL even when not every source was verified
  by an extract file. Events may show `partial: N URLs verified by extracts, M
  cited without extract files`.
  - The current overlay/live adapter enforces this at final-report time:
    URLs in `report.md` without a matching `./extracts/<id>.md` are labeled
    `search_only_unverified`, surfaced in `citation_integrity`, and mark the
    completed job as degraded.
  - Treat degraded citation integrity as a research-quality warning, not an
    infra failure.
- Standard reports must cite extracted/read sources by their original source
  URL, not only by `./extracts/<id>.md`. If extracts exist but the final report
  contains no source URLs, the current overlay/live adapter marks the job
  degraded with `citation contract degraded - no report URLs`.
- Report URL verification normalizes common markdown/sentence wrappers such as
  trailing backticks and punctuation before comparing URLs to extract hashes.
- If the agent finishes without physically writing `report.md`, the current
  overlay/live adapter may recover only from the last top-level `lead` message,
  persist that text back into `report.md`, and mark the job as degraded:
  `report.md missing - recovered final lead message`.
  - Sub-agent messages are never used as report fallback.
  - If there is no final lead message, the job fails with
    `agent finished without report.md or final lead message`.
  - Standard mode was hardened on 2026-05-10 so the agent must write
    `./report.md` with the file write/edit tool, verify it with
    `wc -c ./report.md`, and then return only `REPORT_SAVED: ./report.md`.
    A live VPS smoke (`6fd36cd5c5244192`) completed without recovery warning.
- `/research` is naturally slow. The successful smoke took about 5 minutes for
  a small deep query. `mode=standard` is the bounded extract-backed path for
  fast/Haft-ready evidence packets; `mode=deep` keeps the multi-agent
  researcher + critic/fact-checker pipeline.
- Gemini 3 tool-calling through Vertex requires protocol care:
  - keep `thoughtSignature` with function calls;
  - return all tool responses for a multi-call model turn as one Vertex user
    turn.
- The adapter image inherits from `nousresearch/hermes-agent:latest`, which is
  mutable. A future rebuild can pull a different upstream Hermes image and
  change behavior. For repeatable production, pin image digests or preserve a
  known-good deploy archive.

## Security Notes

- Do not commit `/opt/searcharvester/.env`.
- Do not commit `/opt/searcharvester/secrets/vertex-sa.json`.
- Do not paste service account JSON or provider passwords into chat.
- Rotate the InterServer/control-panel password if it was pasted into any chat
  or reused as another password.
- Keep public ports closed until there is a deliberate auth/reverse-proxy plan.

## Global Agent Integration

`web_researcher` is configured at user level:

```text
/Users/andreysazonov/.codex/agents/web-researcher.toml
```

For normal quick web research, it stays on ordinary web/Tavily/Reddit search.
For `Pre-Haft Evidence Packet mode`, it must also call this private VPS
Harvester sidecar with:

```json
{
  "mode": "standard",
  "max_report_chars": 9000,
  "language": "auto"
}
```

The agent must return Harvester `job_id`, `status`, `error`/warnings when
present, and `citation_integrity`, and it must keep search-only discovery
separate from extract-backed Harvester sources.

`mode=deep` remains explicit-only for `Дипресёрчер` / `deep research`.

## Next Hardening Options

1. Run a live `web_researcher` pre-Haft dogfood from a fresh Codex session and
   verify it actually calls Harvester `mode=standard`.
2. Add a small authenticated reverse proxy if browser/API access without SSH
   tunnel becomes necessary.
3. Add scheduled `docker compose ps` / health probe and log rotation checks.
4. Add a restore script that rebuilds `/opt/searcharvester` from the repo
   overlay plus externally supplied secrets.
