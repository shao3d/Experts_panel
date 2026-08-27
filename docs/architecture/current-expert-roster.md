# Current Expert Roster

**Status:** Active roster reference
**Last updated:** 2026-05-20

This file documents the intended active expert roster and the places that must
stay in sync when experts are added, removed, or regrouped. For live production
claims, verify the production API/Oracle SQLite; a git push alone does not update
the mounted SQLite database.

---

## Source of Truth

| Layer | Source |
|-------|--------|
| UI groups, display names, and sort order | `frontend/src/config/expertConfig.ts` |
| Runtime expert list and stats | `expert_metadata` + related rows in SQLite |
| Local SQLite path | `backend/data/experts.db` |
| Oracle production SQLite path | `/home/ubuntu/apps/experts-panel/data/experts.db` on the VM, mounted at `/app/data/experts.db` in `panel` |

Important: a normal `git push` updates code, frontend and Reddit search, but it
does **not** update production SQLite. The standard data release runs
`./scripts/update_production_db.sh` from the Oracle VM `dev` checkout; see
`docs/operations.md`.

---

## Active UI Groups

These are frontend groups. Some backend `display_name` values differ; the UI label below is the effective sidebar label after `expertConfig.ts` mapping.

Agent-facing selection uses these UI labels as the preferred human names.
`Панэкс` / `experts_panel_researcher` translates UI labels and obvious Russian
spellings to backend `expert_id` values before calling the Agent Context CLI.

### Tech

| expert_id | UI label | Telegram channel |
|-----------|----------|------------------|
| `ai_architect` | AI_Arch | `the_ai_architect` |
| `neuraldeep` | Kovalskii | `neuraldeep` |
| `ilia_izmailov` | Ilia | `ilia_izmailov` |
| `polyakov` | Polyakov | `countwithsasha` |
| `etechlead` | Etechlead | `etechlead` |
| `rodion_mostovoy` | Rodion | `ai_driven` |
| `glebkudr` | Glebkudr | `gleb_pro_ai` |
| `ostrikov` | Ostrikov | `aostrikov_ai_agents` |
| `pashazloy` | PashaZloy | `evilfreelancer` |
| `sergei_notevskii` | Notevskii | `sergeinotevskii` |
| `deksden_notes` | DEKSDEN | `deksden_notes` |

### Tech & Business

| expert_id | UI label | Telegram channel |
|-----------|----------|------------------|
| `ai_grabli` | AI_Grabli | `oestick` |
| `refat` | Refat | `nobilix` |
| `akimov` | Akimov | `ai_product` |
| `llm_under_hood` | Rinat | `llm_under_hood` |
| `elkornacio` | Elkornacio | `elkornacio` |
| `doronin` | Doronin | `kdoronin_blog` |
| `vlad_kooklev` | Kooklev | `prod1337` |
| `air_ai` | Air | `realtimeforai` |
| `silicbag` | SilicBag | `prompt_design` |
| `kornish` | Kornishev | `NGI_ru` |
| `aimasters_me` | Aimasters | `aimastersme` |

### Knowledge Hub

| expert_id | UI label | Runtime role |
|-----------|----------|--------------|
| `video_hub` | Video_Hub | Isolated video sidecar, not a Telegram-sync expert |

---

## Removed Experts

| expert_id | Display name | Channel | Removed from |
|-----------|--------------|---------|--------------|
| `mkarpov` | MKarpov | `todo2go` | UI config, local DB, production DB |

`mkarpov` was removed from the active system on 2026-04-27. Historical reports may still contain old benchmark rows such as `mkarpov: 166`; treat those as dated snapshots, not current roster truth.

---

## Verification Commands

Local DB:

```bash
sqlite3 backend/data/experts.db "SELECT expert_id FROM expert_metadata ORDER BY expert_id;"
sqlite3 backend/data/experts.db "SELECT COUNT(*) FROM expert_metadata WHERE expert_id='mkarpov' OR channel_username='todo2go';"
```

Production API:

```bash
curl -sS https://expa.beyondhorizon.dev/api/v1/experts
curl -sS https://expa.beyondhorizon.dev/health
fly releases -a experts-panel
fly status -a experts-panel
```

Frontend bundle sanity check:

```bash
curl -sS https://expa.beyondhorizon.dev/ -o /tmp/experts-panel-index.html
# Fetch the referenced /assets/index-*.js and verify:
# - pashazloy/PashaZloy is present
# - mkarpov/MKarpov is absent
```
