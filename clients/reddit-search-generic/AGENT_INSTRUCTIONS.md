# Reddit Search

When the user explicitly asks to search Reddit, check Reddit discussions, or
gather Reddit community sentiment, run:

```bash
reddit-search "<user question>"
```

- Use `--recent` only for an explicitly recent-only request.
- Use `--json` when structured output is useful.
- Report `completed` with the returned synthesis and real Reddit links.
- Report `abstained` honestly without adding unsupported general knowledge.
- Treat a non-zero exit code as a technical failure, not as no results.
- Never print, inspect, or include the Reddit Search token in prompts or output.
