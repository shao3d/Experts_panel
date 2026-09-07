# Super-Passport Search Architecture (Experts Panel v2.0)

> [!NOTE]
> **Feature Evolution:** This architecture has evolved. The current implementation (Embs&Keys Search) combines the Entity-Centric FTS5 approach described here with **vector search (`sqlite-vec`)** and merges them via the *Reciprocal Rank Fusion (RRF)* algorithm. See `hybrid_retrieval_plan.md` and the source code of `hybrid_retrieval_service.py` as the current SSOT.

**Status:** ✅ Evolved into Hybrid Retrieval (Updated 2026-05-06)
**Feature Flag:** `use_super_passport` (exposed via the "Embs&Keys" UI checkbox; backend default = `false`, current frontend init = `true`)
**Goal:** Scale the pre-filtering of posts for the Map Phase via a hybrid split (Vector + FTS5) and prevent OOM/CPU spikes.

---

## 📊 Current Architecture (from code and DB)

The solution rests on three pillars:
1. **Bulkhead Pattern:** A global concurrency cap (`MAX_CONCURRENT_EXPERTS=5`) → protects the server from OOM.
2. **Two-stage funnel (FTS5 + Vector KNN):** Pre-filtering of posts via SQLite FTS5 + Vector KNN (sqlite-vec) with RRF → reduces the input to the Map Phase by 70–90%.
3. **AI Scout (Entity-Centric v3):** The LLM generates OR-only entity clouds (e.g., `rag OR retrieval OR vector`) with bilingual expansion, ignoring verbs so they do not pollute BM25 with noise.

### Full Pipeline (6+ Phases)

FTS5 affects ONLY step 1. All other phases operate on the Map output, not on the original posts.

```
1. AI Scout generates the FTS5 MATCH query (OR-only Entity Cloud); in parallel, the orchestrator computes the query embedding.
2. Post loading:
   - FTS5 searches for matches in `message_text`; before SQL, a shared sanitizer normalizes dangerous tokens (`file-fist*`, `метод?*`, unbalanced quotes) into a safe OR-only query.
   - Vector KNN searches over pre-computed embeddings (`sqlite-vec`).
   - RRF with Soft Freshness Decay merges the results into a single shortlist.
   - If hybrid retrieval does not produce a usable shortlist, the service falls back to the standard loading of all expert posts.
3. Map Phase (LLM chunks of 50 posts)
4. HIGH/MEDIUM split → Medium Scoring (second LLM)
5. Resolve (link expansion from the links table)
6. Reduce (final synthesis)
7. Language Validation
8. Comment Groups (drift analysis)
```

---

## 🔬 Pipeline Evolution (A/B Tests)

### v1 Problem: The AND Filter Killed Recall
The first Scout version generated queries with `AND` (e.g., `(rag OR вектор*) AND (настрой* OR config*)`). 
It filtered out 87% of relevant posts, because experts rarely use both word types in a single post. **Recall dropped to 15%**.

### v2 Solution: Entity-Centric Scout
The Scout was switched to OR-only queries. AI Scout now extracts only technical entities and expands them into a broad cloud (`rag OR retrieval* OR вектор* OR эмбеддинг*`).
*Result:* Recall rose to **70%**. FTS5 works as a wide "vacuum", while the Map Phase filters the noise out semantically.

### v2 Problem: Semantic Gap
FTS5 is lexical search. An expert post — *"Отличный гайд по подаче данных в модель по документам"* — is semantically about RAG, but FTS5 will never find it, since it contains neither the word "RAG" nor "вектор".

### Final Solution: Hybrid Retrieval (Vector KNN + FTS5 + RRF)

> **Note:** The intermediate solution based on Pre-computed Metadata (`enrich_post_metadata.py`) was removed in March 2026. AI Scout v3 with bilingual OR-queries and wildcards fully closes the Semantic Gap on the FTS5 side, while Vector KNN (`sqlite-vec`) adds semantic search over embeddings.

The current architecture:
1. **AI Scout v3** generates an OR-only Entity Cloud (`rag OR retrieval* OR вектор* OR эмбеддинг*`) with bilingual expansion.
2. **FTS5** searches the raw `message_text` (no LLM metadata; migration 023).
3. **Vector KNN** (`sqlite-vec`) searches over pre-computed embeddings (`embed_posts.py`).
4. **RRF** merges the FTS5 and Vector KNN results with Soft Freshness Decay.
5. **Smart Fallback** returns the standard selection of expert posts if the hybrid path does not produce a sufficient result.

### Sanitation hardening (2026-05-06)

Production logs for an Agent Context query containing `file-fist`, `метод?`,
and `хорошо?` showed two separate safety needs:

- AI Scout can successfully call Vertex but still return invalid FTS5 syntax,
  such as an unbalanced quote. In that case `AIScoutService.generate_match_query()`
  correctly marks Scout as fallback-used.
- The fallback query itself must still be FTS5-safe. It now tokenizes user
  punctuation before adding wildcards, and `sanitize_fts5_query()` converts
  hyphens/punctuation/unbalanced quote fragments into conservative OR-only
  terms. Example: `file-fist* OR метод?* OR хорошо?*` becomes
  `file* OR fist* OR метод* OR хорошо*`.

This keeps the FTS5 side of Hybrid Retrieval from failing with parser errors
such as `no such column: fist`; the Vector KNN side remains available either way.

---

## 🛡️ Safeguards and Edge Cases

| # | Edge Case | Severity | Mitigation |
|---|-----------|-------------|---------|
| 1 | FTS5 Syntax Error on special characters, hyphens, punctuation, and quotes | 🔴 | The Scout translates `C++` into `cpp OR "си плюс плюс"`. The fallback and the shared sanitizer never release `C++*`, `file-fist*`, `метод?*`, or unbalanced phrases into FTS5. |
| 2 | BM25 Pollution (noise in results) | 🔴 | The Scout prompt strictly forbids verbs and generic words (настройка, опыт). |
| 3 | Hybrid path produced no usable shortlist | 🟡 | Smart Fallback: fall back to the standard loading of expert posts (e.g., when there are no embeddings or retrieval yields no usable shortlist). |
| 4 | Semantic Gap | 🟡 | Solved via Vector KNN (sqlite-vec) + AI Scout v3 bilingual expansion. |
| 5 | Video Hub incompatibility | 🟡 | Explicit exclusion `if expert_id == "video_hub"`. The video sidecar runs independently. |
| 6 | Map Phase I/O explosion | 🟡 | Global `Semaphore(MAX_CONCURRENT_EXPERTS=5)`. |
| 7 | JSON errors in Map Phase | 🟡 | `MAP_CHUNK_SIZE` reduced from 100 to 50 for stable generation of long JSON responses. |

---

## 🚀 Future Plans

The Semantic Gap is fully closed by Hybrid Retrieval (Vector KNN + FTS5 + RRF). Metadata enrichment and Hybrid Mode (random interleaving) were removed as redundant.
