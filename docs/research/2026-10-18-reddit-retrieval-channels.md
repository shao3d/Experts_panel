# Reddit Retrieval Beyond OAuth Search — Channels, Arctic Shift, and Ranking (2025–2026)

**Дата анализа:** 2026-10-18 · **Статус:** evidence, не SSOT (текущее поведение — `docs/architecture/reddit-service.md`).

**Что подтвердилось нашими замерами (18.10.2026, `docs/roadmap/2026-10-18-reddit-search-v2-fix-plan.md`):**
Serper отвечает и авторизуется штатно (канал крутится в проде; «UNVERIFIED» ниже снят), а формулировка запроса к нему измерена в 0.6.1; Arctic Shift жив, но требует ограниченного окна времени и ключевых слов, и отдача у него низкая (0.5); RSS-обход Reddit отклонён как обход границы.

**Method.** `web_search` was unavailable (no API key), so this is built from `web_fetch` against primary sources plus **live HTTP calls I made on 2026-10-18**. Status codes are from my own calls; anything I could not verify from a primary source is marked **UNVERIFIED**.

---

## A) Ranked inventory of channels

Ranked by retrieval value per unit of integration effort, for a service that already has OAuth search + one archive + Google discovery.

### 1. Reddit's own endpoints — highest reliability, hardest access
- **OAuth API:** `/search` and `/r/{sub}/search` (needs `restrict_sr`), OAuth2 bearer. Listings share `after`/`before` (fullname anchors), `limit` (max 100), `count`, `show`; add `raw_json=1` to stop `&lt;` escaping ([reddit.com/dev/api](https://www.reddit.com/dev/api/)).
- **Subreddit search RSS** — ✅ **verified live, no auth**: `https://www.reddit.com/r/{sub}/search.rss?q=laptop&restrict_sr=1&sort=top&t=year&limit=3` → HTTP 200 Atom with title, permalink, author, `published`. Also `/r/{sub}/top/.rss?t=year` → 200.
- **Site-wide `search.rss`** — ❌ failed in my test (`unsupported content type`); existence **UNVERIFIED**.
- **`.json` on www/old** — ❌ HTTP 403 "network policy" from a datacenter IP without OAuth (why your proxy exists).
- **robots.txt** — `User-agent: * / Disallow: /`: Reddit disallows *all* crawling ([robots.txt](https://www.reddit.com/robots.txt)), pointing to the [Public Content Policy](https://support.reddithelp.com/hc/en-us/articles/26410290525844). Support pages 403'd behind Cloudflare for me, so policy details are **UNVERIFIED**.

RSS is the standout: zero auth, no documented quota, supports `sort`/`t`/`limit`, returns exactly the post IDs you need before enrichment. **No selftext, no comments** — discovery only.

### 2. Arctic Shift — best archive; see §B
Alive and current (data through 2026-10-18 in my calls). Best history depth + comments + comment trees.

### 3. Google/SERP proxies (Serper) — you already have this
[Serper](https://serper.dev/) advertises 2,500 free queries, no credit card. `docs.serper.dev` **failed DNS** for me this session, so endpoint/auth are **UNVERIFIED**.

### 4. Brave Search API — strongest *live* vendor hedge
`POST https://api.search.brave.com/res/v1/llm/context` (also `/res/v1/web/search`), auth header **`X-Subscription-Token`** — confirmed from Brave's own code sample ([brave.com/search/api](https://brave.com/search/api/)). Up to $20 free calls/month, prepaid, no subscription. Brave's page states Microsoft *retired* Bing and Google *closed* CSE — both independently confirmed below. Its index is self-built, so it is not exposed to those shutdowns.

### 5. Exa / Tavily — semantic web search with extracted text
[Exa pricing](https://exa.ai/pricing): $4/1k (Instant), $7/1k (Fast/Auto), $12–15/1k (Deep), +$1/1k per extra result above 10; **10 QPS free, 25 QPS PAYG**; $10 free credits/month. It returns page text/highlights, so it can skip a fetch hop. Tavily's Search endpoint is documented ([docs.tavily.com](https://docs.tavily.com/documentation/api-reference/endpoint/search)); I could not read past the nav, so its exact path/header/price are **UNVERIFIED**.

### 6. Dead or gated — do not build on these
| Source | Status (my calls, 2026-10-18) |
|---|---|
| **Bing Web Search API** | **DEAD.** "Public Bing Search and Bing Custom Search APIs were retired on 11th August 2025" — [Microsoft Learn](https://learn.microsoft.com/en-us/previous-versions/bing/search-apis/). |
| **Google Custom Search JSON API** | **Closed to new customers**; existing customers until **2027-01-01**; 100 q/day free, $5/1k up to 10k/day — [Google](https://developers.google.com/custom-search/v1/overview). |
| **Pushshift** | `api.pushshift.io/...` → **403 `{"detail":"Not authenticated"}`**. No longer open. |
| **PullPush** | `api.pullpush.io/reddit/search/submission/` → **429**: *"does not provide free scraping resources for agents… paid scraping service"*. Site 403'd via Cloudflare. Treat as gated. |
| **SocialGrep** | **HTTP 523, origin unreachable.** Down. |
| **Watchful1/PushshiftDumps** | Repo exists ([link](https://github.com/Watchful1/PushshiftDumps)) — batch dump scripts, not a live API. |
| **Arctic Shift dumps** | [download_links.md](https://github.com/ArthurHeitmann/arctic_shift/blob/master/download_links.md) + [releases](https://github.com/ArthurHeitmann/arctic_shift/releases); [download-tool](https://arctic-shift.photon-reddit.com/download-tool) for single users/small subs. |

---

## B) Arctic Shift: correct usage and the 422

**Base URL:** `https://arctic-shift.photon-reddit.com` ([API README](https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md)). Status: [status.arctic-shift.photon-reddit.com](https://status.arctic-shift.photon-reddit.com) (reported "Available" for me).

**Endpoints:** `/api/posts/search`, `/api/comments/search`, `/api/posts/ids`, `/api/comments/ids` (≤500 ids), `/api/comments/tree`, `/api/posts|comments/search/aggregate`, `/api/subreddits/search|rules|wikis`, `/api/users/search`, `/api/short_links`, `/api/time_series`.

**Params:** `subreddit`, `author`, `after`/`before` (epoch s/ms, ISO-8601, or relative `1year`, `3m`, `2d`), `limit` (1–100 or `"auto"` → 100–1000), `sort=asc|desc` (by `created_utc`), `fields`, `md2html`, `format=json|rss|jsonfeed`. Posts: `query`, `title`, `selftext`, `link_flair_text`, `url`, `crosspost_parent_id`, `over_18`. Comments: `body`, `link_id`, `parent_id`.

**Two hard constraints I verified live (HTTP 400):** `query` requires `author` or `subreddit`; `body` requires `author`, `subreddit`, `link_id` or `parent_id`. **There is no global keyword search** — you must fan out per subreddit/author, which is likely a root cause of your failures. Also, `limit=auto` is rejected with `query`. **Pagination:** no cursor/offset param exists; page by **time-window slicing** (`sort=asc` + `after`/`before`, advancing `after` to the last `created_utc`).

**Rate limits:** dynamic; 429 returns `X-RateLimit-Reset` and `X-RateLimit-Reset-At`. I hit **429 `{"error":"Too many requests"}`** after ~6 rapid calls, so the practical concurrency budget is low.

**⚠️ The 422 is NOT rate limiting.** Literal body: `{"data":null,"error":"Timeout. Maybe slow down a bit"}`. The docs describe a *different* message ("Query timed out"), so almost nobody documents this one. It is a **server-side query timeout**, so sleeping/backing off does not fix it — reducing query cost does.

**What I measured** (r/AskReddit, `query=laptop`):
| Request | Result |
|---|---|
| `limit=10` | ✅ 200 |
| `limit=25` | ✅ 200 |
| `limit=25` + `fields=` | ❌ 422 |
| `limit=50` + `after/before` + `fields=` | ❌ 422 |
| `limit=100` (×2, incl. narrow window) | ❌ 422 |
| `subreddit=AskReddit&limit=100` (no keyword) | ✅ 200 |

**Read:** cost is driven by keyword search + `limit`, and counter-intuitively **`fields` projection made things worse**, not better (docs only claim it "potentially" reduces time). The threshold is load-dependent, so treat ~25–50 as a soft ceiling and degrade gracefully. Mitigations in order: drop `fields`; keep `limit` ≤25–50; slice by `after`/`before` and iterate windows; prefer `title`/`link_flair_text` on targeted subs over broad `query`; cap in-flight concurrency at 1–2; use dumps for bulk. Also: `score`/`num_comments` are **1/0 for ~36 h** after posting (docs), so recency-window ranking needs a re-fetch. Self-hosting is **not documented** in the README → **UNVERIFIED**.

---

## C) Filtering & ranking that practitioners recommend

1. **Never trust one channel's relevance.** Union OAuth search + RSS + archive + SERP, dedupe on post **ID** (base36, normalising `t3_`), and collapse crossposts via `crosspost_parent_id` / `url` — Arctic Shift exposes `crosspost_parent_id` and `url_exact` for this.
2. **Target subreddits, not the firehose.** With no global keyword search, keep a curated subreddit list per topic; expand it with `/api/subreddits/search?subreddit_prefix=`.
3. **Flair as a precision filter:** `link_flair_text` (posts) and `author_flair_text` (both) — the cheapest relevance win on modded subs.
4. **Top-of-time-window selection:** rank a window by `score` + `num_comments`, not recency — but re-fetch scores for posts <36 h old.
5. **Comment-level retrieval, not just posts:** `/api/comments/search?link_id=...&body=` finds answer-bearing comments on posts whose *titles* don't match; `/api/comments/tree?link_id=...&limit=9999` returns a whole tree for enrichment in one call.
6. **Cheap lexical prefilter → embedding rerank.** Since `fields` is fragile, fetch full objects at low `limit` and rerank client-side over a cached archive slice; the dumps are the right substrate for a persistent embedding index.

---

## D) Top 5 recommended additions

1. **Reddit subreddit-search RSS.** **Payoff high, cost ~zero** — verified live, no auth, no documented quota, returns post IDs for enrichment; complements OAuth and survives OAuth outages. **Risk low**, but unsupported/undocumented and could vanish; cache it.
2. **Fix Arctic Shift usage** (per-sub fan-out, `limit` ≤25–50, no `fields`, date-window paging, concurrency 1–2). **Payoff high** — you already pay for it; recovering this channel is the largest single retrieval gain. **Risk low** (code-only), but the 422 ceiling is load-dependent, so keep it non-blocking.
3. **Brave Search API** as a second discovery vendor. **Payoff medium-high** — removes the Google-proxy single point of failure; its own index is immune to the Bing/Google shutdowns. **Risk low-medium** — new key, per-query cost, snippet-only so you still fetch Reddit pages.
4. **Exa (or Tavily)** for paraphrased queries keyword search misses. **Payoff medium** — returns extracted text, directly serving the "more posts reach rerank" goal. **Risk medium** — higher $/query, vendor-specific result shape.
5. **Arctic Shift dumps → local index** (posts + comments). **Payoff high long-term** — no rate limits, true semantic rerank. **Risk medium-high** — real storage/ETL work; do it only after 1–3 are stable.

Do **not** build on Pushshift, PullPush, Bing, or SocialGrep. If you rely on Google CSE anywhere, note it is closed to new customers and sunsets **2027-01-01**.
