# Panex Usage Guide

**Status:** Active
**Last updated:** 2026-05-07

This is the human-facing quick guide for using Панэкс from Codex/Claude chats
in any repo.

## What Панэкс Does

Панэкс is an explicit-only bridge to Experts Panel on Fly.io. It helps a parent
agent ask selected practitioners/experts for context, patterns, trade-offs, and
source-backed signals.

Default behavior:

- uses production Fly.io;
- searches selected experts with forced hybrid/embedding retrieval;
- returns `expert_digest`, not a giant raw bundle;
- includes direct comments under selected answer sources;
- includes `source_key` handles for follow-up expansion;
- keeps external links as author-supplied references;
- does not select drift comment groups by default.

## Ask For Help

In a Codex/Claude chat:

```text
Панэкс, помощь
Панэкс, что ты умеешь?
Как пользоваться Панэксом?
Покажи примеры Панэкса.
Как искать через Панэкс?
```

Панэкс should answer from its instructions and must not call the API for help
requests.

In a terminal:

```bash
panex guide
panex help
panex --help
panex ask --help
panex expand --help
```

`panex guide` and `panex help` are human-friendly and do not require
`AGENT_CONTEXT_API_TOKEN`.

## Ask Experts

Ask concrete experts:

```text
Спроси Панэкс у Refat и Akimov: когда subagents реально помогают?
```

Equivalent CLI shape:

```bash
panex ask --query "Когда subagents реально помогают?" --experts refat,akimov --json
```

Ask a group:

```text
Панэкс, спроси группу tech_business: что такое context rot?
```

```bash
panex ask --query "Что такое context rot?" --group tech_business --json
```

Ask all supported experts:

```bash
panex ask --query "Что думают про LLM caching?" --all --json
```

## Expand Sources

After an `expert_digest`, Панэкс can reveal selected sources without rerunning
the full search:

```text
Панэкс, раскрой по Рефату.
Панэкс, покажи источники.
Панэкс, что там в комментариях?
Панэкс, самый спорный источник.
```

Equivalent CLI shape:

```bash
panex expand --source-keys refat:238 --json
panex expand --source-keys refat:238 --max-comments-per-source 3 --json
```

`source_expand` is exact source lookup. It is not a new search, not a new
digest, and not a raw dump of every source.

## Raw/Audit Mode

Use raw `source_bundle` only when explicitly needed for audit/debug:

```bash
panex ask --query "..." --experts refat,akimov --response-mode source_bundle --json
```

Default Панэкс answers should use `expert_digest`.

## Diagnostics

Check local/global setup:

```bash
panex doctor
```

Run a tiny live production check:

```bash
panex doctor --live
```

`panex doctor` reports whether the token is configured, but does not print the
token value.

## Boundaries

- Панэкс must be invoked explicitly.
- Панэкс is not default web search.
- Панэкс should not be called automatically for every trends/software/architecture question.
- Production calls go to `https://experts-panel.fly.dev`.
- Localhost is used only through explicit `--local` or `--api-url`.
- External links are not opened, crawled, cloned, or summarized by default.
- Drift comment groups are not selected by default; current API only includes
  direct comments under selected `main_sources`.
- Practitioner posts and comments are opinion evidence, not proof of truth.
