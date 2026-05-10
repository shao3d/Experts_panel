---
name: searcharvester-standard-research
description: >
  Bounded extract-backed research without sub-agents. Search for candidate
  URLs, extract the key sources, read the saved markdown, and write a compact
  cited report to ./report.md. Use for standard research, pre-Haft evidence
  packets, and source-backed answers that should be faster than deep research.
version: 1.0.0
author: Searcharvester
license: MIT
metadata:
  hermes:
    tags: [research, standard-research, extract-backed, citations, pre-haft]
    category: research
    related_skills:
      - searcharvester-search
      - searcharvester-extract
---

# Searcharvester Standard Research

Produce a compact report grounded in pages you actually extracted. This is the
fast path for evidence-backed research. It is intentionally not a multi-agent
deep-research workflow.

## Hard Boundary

Do not use `delegate_task`.

You are the only researcher for this mode. Do not spawn researchers, critics,
fact-checkers, or other sub-agents. If the question requires that level of work,
say that deep research is the right mode instead of silently escalating.

## Procedure

1. Write a short plan to `./plan.md`.
2. Run 1-3 focused searches with `searcharvester-search`:

```bash
python3 /opt/data/skills/searcharvester-search/scripts/search.py \
  --query "<query>" --max-results 8
```

3. Choose 3-7 key URLs. Prefer official/primary sources, independent analysis,
   GitHub/docs/issues, and high-signal community sources when relevant.
4. Extract each chosen URL with `searcharvester-extract`:

```bash
python3 /opt/data/skills/searcharvester-extract/scripts/extract.py \
  --url "<url>"
```

5. Read the saved extracts before using them as evidence:

```bash
head -120 ./extracts/<id>.md
grep -ni "<keyword>" ./extracts/<id>.md
sed -n '120,260p' ./extracts/<id>.md
```

6. Write `./report.md` using the file write/edit tool. Do not put the report
   body in the final assistant message.
7. Verify that `./report.md` exists and is non-empty:

```bash
wc -c ./report.md
```

8. End the final assistant message with exactly this marker and no report body:

```text
REPORT_SAVED: ./report.md
```

If you cannot write or verify `./report.md`, say why instead of claiming
`REPORT_SAVED`.

## Report Shape

Use this shape unless the user asks for a different one:

```markdown
# Standard Research Report

## Answer
<short direct answer>

## Extracted Evidence
- <finding> — <source title / URL>

## Caveats And Unknowns
- <what remains weak, stale, blocked, or search-only>

## Candidate Decision Inputs
- <risks, comparison dimensions, or open questions when relevant>

## References
- <title> — <url>
```

For pre-Haft requests, make `Candidate Decision Inputs` explicit and include
possible constraints, risks, comparison dimensions, disagreements, and unknowns.

## Source Quality

Separate these categories:

- `extracted/read`: URL was extracted and you read the saved markdown file.
- `search-only`: URL was found but not successfully extracted or not actually
  read; do not use it as strong evidence and do not include the raw URL in the
  final report.
- `community signal`: Reddit/forum/GitHub discussion style source; useful for
  practitioner signal, not proof of factual truth.

## Verification

Before writing the report, check that `./extracts/` contains files for the URLs
you cite. The final adapter also enforces citation integrity, but this skill
should avoid unverified citations proactively.

Only URLs that were extracted and read may appear in `## References` or inline
citations. If a search-only page helped with discovery, mention that a
search-only source existed without printing the URL, or omit it entirely.

Do not cite sources by extract IDs alone. `./extracts/<id>.md` proves that the
page was read, but the final report still needs the original source URL so the
API citation contract can verify and expose provenance.
