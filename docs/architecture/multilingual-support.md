# Multilingual Support (RU/EN)

**Status:** Production
**Scope:** Query language detection, answer language enforcement, source translation, persistent translation cache.
**Last verified against codebase: 2026-08-23**

Experts Panel answers in the language of the question — Russian or English — regardless of the language the source material was written in. This document is the single source of truth for how that works.

---

## Language detection: one detector, one answer

Detection lives in `detect_query_language()` (`backend/src/utils/language_utils.py`) and returns exactly two values: `Russian` or `English`.

- **Russian-first by design.** A single Cyrillic word makes the query Russian. The audience mixes English tech terms into Russian sentences ("What is the best RAG подход?"), and tech loanwords are not language markers — Russian connective words are.
- **The backend is the single source of truth.** Every `ExpertResponse` carries a `detected_language` field. The frontend uses it to decide whether source posts need translation instead of running its own heuristic. (A local `isEnglishQuery` fallback remains only for results persisted by older backends.)

Every consumer — pipeline phases, language validation, source translation, the frontend — reads the same detector result. Mixed-language queries can no longer produce a half-translated result.

## How the answer stays in the query language

Two mechanisms, one per layer:

1. **Prompt enforcement (prevention).** Every LLM phase (Reduce, Meta-Synthesis, Comment Synthesis, Comment Group scoring, Medium Scoring) receives a strict language instruction in the system message, generated from the detected query language.
2. **Language validation (cure).** After Reduce, `LanguageValidationService` detects the language of the produced answer. If it does not match the query language, the answer is translated — **in both directions** (Russian answer + English query → English; English answer + Russian query → Russian). Video Hub runs the same validation as its final phase.

Translation preserves `[post:ID]` citation markers and markdown links exactly, so cited sources stay clickable after translation.

## Source translation for English queries

Expert corpora are Russian. When the query is English, the cited sources are translated to English too:

- **Source posts** — translated on fetch in `GET /api/v1/query` post details; the frontend loads them progressively with a translation progress indicator.
- **Comments on source posts** — translated together with the post.
- **Comment groups** (anchor posts + community comments) — translated in the expert pipeline before the response is returned.

Proper names (author names, channel names) are intentionally left untranslated.

For Russian queries nothing is translated: the audience reads technical English natively.

## Reddit direction is inverted

Reddit content is English, so for **Russian** queries the Reddit pipeline converts the query into an optimal English Reddit search query first (named entities preserved, community wording preferred), then synthesizes the Reddit answer back in the query language.

## Persistent translation cache

Translations are deterministic and source posts are static, so every translation is computed once and reused forever:

- Table `translation_cache` (model: `backend/src/models/translation_cache.py`), keyed by `sha256(normalized text + language pair)`. Created automatically at startup.
- `TranslationService` is a shared singleton (`get_translation_service()`), with an in-memory LRU on top of the DB cache.
- A post, comment, or answer text pays for exactly one LLM translation across all requests, restarts, and deployments.

## Translation model

Translations use `MODEL_ANALYSIS` (default `google/gemini-3.1-flash-lite` via OpenRouter): the cheapest, fastest tier — translation quality is not bottlenecked by the model, and source translation adds latency inside the pipeline for English queries, where speed matters. Overridable via the `MODEL_ANALYSIS` environment variable.

## Failure behavior

All translation paths degrade gracefully: on any failure the original text is returned untranslated and the query still succeeds. The language of the answer is enforced first by prompts; validation/translation is the safety net, not a hard gate.
