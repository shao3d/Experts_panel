/**
 * Reddit Proxy Service
 *
 * Sidecar architecture for Experts Panel.
 * Talks to the Reddit OAuth API directly (no MCP layer): search + deep thread fetch,
 * with sanitization that preserves code blocks.
 */

import Fastify from 'fastify';
import { LRUCache } from 'lru-cache';
import { config } from 'dotenv';
import { z } from 'zod';

// Load environment variables
config();

// ============================================================================
// Configuration
// ============================================================================

const PORT = parseInt(process.env.PORT || '3000');
const REDDIT_USER_AGENT = process.env.REDDIT_USER_AGENT ||
  'android:com.experts.panel:v1.0 (by /u/External-Way5292)';
const CACHE_TTL_MS = parseInt(process.env.CACHE_TTL_MS || '300000'); // 5 minutes
const LOG_LEVEL = process.env.LOG_LEVEL || 'debug';

const REDDIT_OAUTH_BASE = 'https://oauth.reddit.com';

// ============================================================================
// Types
// ============================================================================

interface RedditSearchResult {
  id: string;
  title: string;
  url: string;
  score: number;
  numComments: number;
  subreddit: string;
  author: string;
  createdUtc: number;
  selftext?: string;
  permalink: string;
  top_comments?: any[];
}

interface SearchResponse {
  foundCount: number;
  sources: Array<{
    title: string;
    url: string;
    score: number;
    commentsCount: number;
    subreddit: string;
    created_utc?: number;
  }>;
  query: string;
  processingTimeMs: number;
}

// ============================================================================
// Logging
// ============================================================================

const logger = {
  debug: (...args: unknown[]) => LOG_LEVEL === 'debug' && console.log('[DEBUG]', ...args),
  info: (...args: unknown[]) => console.log('[INFO]', ...args),
  warn: (...args: unknown[]) => console.warn('[WARN]', ...args),
  error: (...args: unknown[]) => console.error('[ERROR]', ...args),
};

// ============================================================================
// Text Sanitization
// ============================================================================

/**
 * Remove Zalgo text (combining characters)
 */
function sanitizeZalgo(text: string): string {
  return text
    .replace(/[\u0300-\u036f]/g, '') // Combining Diacritical Marks
    .replace(/[\u1dc0-\u1dff]/g, '') // Combining Diacritical Marks Supplement
    .replace(/[\u20d0-\u20ff]/g, '') // Combining Diacritical Marks for Symbols
    .replace(/[\ufe20-\ufe2f]/g, '') // Combining Half Marks
    .replace(/[\u0483-\u0489]/g, ''); // Cyrillic combining marks
}

/**
 * Normalize whitespace - collapse multiple spaces/newlines
 */
function normalizeWhitespace(text: string): string {
  return text
    .replace(/\r\n/g, '\n')           // Normalize line endings
    .replace(/[ \t]+/g, ' ')          // Collapse horizontal whitespace
    .replace(/\n{3,}/g, '\n\n')       // Max 2 consecutive newlines
    .trim();
}

/**
 * Full sanitization pipeline that PRESERVES CODE BLOCKS
 */
function sanitizeText(text: string): string {
  if (!text) return '';

  const noZalgo = sanitizeZalgo(text);

  // Split by markdown code blocks; keep them AS IS (preserve indentation)
  const parts = noZalgo.split(/(```[\s\S]*?```)/g);

  return parts.map(part => {
    if (part.startsWith('```')) {
      return part;
    }
    return normalizeWhitespace(part);
  }).join('');
}

// ============================================================================
// Reddit Direct API Client (OAuth password grant)
// ============================================================================

let redditAccessToken: string | null = null;
let redditTokenExpiresAt = 0;
let tokenFetchInFlight: Promise<string> | null = null;

// Official allowance: 100 QPM per OAuth client (10-min average window).
// Track X-Ratelimit-* headers and back off BEFORE exhausting the bucket.
let rlRemaining: number | null = null;
let rlResetAt = 0; // epoch ms

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

function updateRateLimit(headers: Headers): void {
  const rem = headers.get('x-ratelimit-remaining');
  const reset = headers.get('x-ratelimit-reset');
  if (rem !== null && !Number.isNaN(parseFloat(rem))) rlRemaining = parseFloat(rem);
  if (reset !== null && !Number.isNaN(parseFloat(reset))) {
    rlResetAt = Date.now() + parseFloat(reset) * 1000;
  }
}

async function rateLimitGate(): Promise<void> {
  if (rlRemaining !== null && rlRemaining <= 2 && Date.now() < rlResetAt) {
    // Jitter so concurrent waiters do not all stampede at the same instant
    const waitMs = Math.min(Math.max(rlResetAt - Date.now(), 500), 15000)
      + Math.floor(Math.random() * 750);
    logger.warn(`Reddit rate limit nearly exhausted (${rlRemaining} left), waiting ${Math.round(waitMs)}ms`);
    await sleep(waitMs);
  }
}

async function requestNewToken(): Promise<string> {
  const clientId = process.env.REDDIT_CLIENT_ID;
  const clientSecret = process.env.REDDIT_CLIENT_SECRET;
  const username = process.env.REDDIT_USERNAME;
  const password = process.env.REDDIT_PASSWORD;

  if (!clientId || !clientSecret || !username || !password) {
    throw new Error('Missing Reddit credentials');
  }

  const auth = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');

  try {
    const response = await fetch('https://www.reddit.com/api/v1/access_token', {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${auth}`,
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': REDDIT_USER_AGENT
      },
      body: new URLSearchParams({
        grant_type: 'password',
        username,
        password
      }).toString()
    });

    if (!response.ok) {
      throw new Error(`Token fetch failed: ${response.status} ${response.statusText}`);
    }

    const data = await response.json() as { access_token: string, expires_in: number };

    redditAccessToken = data.access_token;
    redditTokenExpiresAt = Date.now() + (data.expires_in * 1000);

    logger.info('✅ Acquired new Reddit Access Token');
    return redditAccessToken;
  } catch (e) {
    logger.error('Failed to get Reddit token:', e);
    throw e;
  }
}

async function getRedditAccessToken(): Promise<string> {
  // Return cached token if valid (with 60s buffer)
  if (redditAccessToken && Date.now() < redditTokenExpiresAt - 60000) {
    return redditAccessToken;
  }
  // Single-flight: concurrent callers share one token request instead of stampeding
  if (!tokenFetchInFlight) {
    tokenFetchInFlight = requestNewToken().finally(() => { tokenFetchInFlight = null; });
  }
  return tokenFetchInFlight;
}

async function redditGet(pathAndQuery: string): Promise<any> {
  const maxAttempts = 3;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    await rateLimitGate();

    const token = await getRedditAccessToken();
    const response = await fetch(`${REDDIT_OAUTH_BASE}${pathAndQuery}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'User-Agent': REDDIT_USER_AGENT
      }
    });

    updateRateLimit(response.headers);

    if (response.status === 429) {
      const retryAfterSec = parseFloat(response.headers.get('retry-after') || '0');
      const waitMs = Math.min(Math.max(retryAfterSec, 2) * 1000 * attempt, 45000);
      logger.warn(`Reddit 429 (attempt ${attempt}/${maxAttempts}), backing off ${Math.round(waitMs)}ms`);
      if (attempt < maxAttempts) {
        await sleep(waitMs);
        continue;
      }
      throw new Error('Reddit API rate limited (429) after retries');
    }

    if (!response.ok) {
      throw new Error(`Reddit API error: ${response.status} ${await response.text().catch(() => '')}`.slice(0, 300));
    }

    return response.json();
  }

  throw new Error('Reddit API:unreachable'); // unreachable, appeases TS control flow
}

async function searchRedditDirect(
  query: string,
  options: {
    subreddits?: string[];
    sort: string;
    time: string;
    limit: number;
  }
): Promise<RedditSearchResult[]> {
  const subs = (options.subreddits || []).map(s => s.trim()).filter(Boolean);
  const params = new URLSearchParams({
    q: query,
    sort: options.sort,
    t: options.time,
    limit: String(Math.min(Math.max(options.limit, 1), 50)),
    raw_json: '1',
  });
  // NOTE: '+' inside the subreddit list must be percent-encoded (%2B):
  // a raw '+' makes oauth.reddit.com answer 301 -> https://www.reddit.com/
  const subsPath = subs.map(s => encodeURIComponent(s)).join('%2B');
  const path = subs.length > 0
    ? `/r/${subsPath}/search?${params.toString()}&restrict_sr=1`
    : `/search?${params.toString()}`;

  logger.info(
    `[Direct API] search: sort=${options.sort} t=${options.time} subs=[${subs.join(',') || '-'}] q="${query}"`
  );

  const data = await redditGet(path);
  const children = data?.data?.children;
  if (!Array.isArray(children)) {
    throw new Error('Invalid Reddit search response format');
  }

  return children.map((c: any) => {
    const d = c.data || {};
    return {
      id: String(d.id || ''),
      title: d.title || '',
      url: d.url || '',
      score: typeof d.score === 'number' ? d.score : 0,
      numComments: typeof d.num_comments === 'number' ? d.num_comments : 0,
      subreddit: d.subreddit || '',
      author: d.author || '',
      createdUtc: typeof d.created_utc === 'number' ? d.created_utc : 0,
      selftext: d.selftext || '',
      permalink: d.permalink || '',
    };
  }).filter(r => r.id && r.title);
}

async function fetchDeepThread(
  postId: string,
  limit: number = 100,
  depth: number = 5
): Promise<any> {
  const data = await redditGet(`/comments/${postId}?limit=${limit}&depth=${depth}&sort=confidence`);

  // Reddit returns array: [post_listing, comment_listing]
  if (!Array.isArray(data) || data.length < 2) {
    throw new Error('Invalid Reddit API response format');
  }

  return {
    post: data[0].data.children[0].data,
    comments: data[1].data.children.map((c: any) => c.data)
  };
}

// ============================================================================
// Smart Aggregation
// ============================================================================

class RedditAggregator {

  /**
   * Smart Aggregation: Search xN → Filter → Fetch → Sanitize
   */
  async aggregate(query: string, options: {
    limit?: number;
    subreddits?: string[];
    sort?: 'relevance' | 'hot' | 'new' | 'top';
    time?: 'hour' | 'day' | 'week' | 'month' | 'year' | 'all';
  } = {}): Promise<SearchResponse> {
    const startTime = Date.now();
    const {
      limit = 10,
      subreddits,
      sort = 'relevance',
      time = 'all',
    } = options;

    logger.info('Starting aggregation for query:', query);

    try {
      // Step 1: Search (get more than needed to filter)
      const searchResults = await searchRedditDirect(query, {
        subreddits,
        sort,
        time,
        limit: Math.min(limit * 2, 25),
      });

      logger.info(`Found ${searchResults.length} raw results`);

      // Step 2: Filter (by score, relevance)
      const filtered = this.filterResults(searchResults, limit);
      logger.info(`Filtered to ${filtered.length} results`);

      // Step 3: Fetch (get full content for top results)
      const enriched = await this.enrichResults(filtered);
      logger.info('Enriched results with full content');

      // Step 4: Sanitize
      const sanitized = this.sanitizeResults(enriched);
      logger.info('Sanitized results');

      const processingTimeMs = Date.now() - startTime;

      return {
        foundCount: sanitized.length,
        sources: sanitized.map(r => ({
          title: r.title,
          url: r.permalink.startsWith('http') ? r.permalink : `https://reddit.com${r.permalink}`,
          score: r.score,
          commentsCount: r.numComments,
          subreddit: r.subreddit,
          selftext: r.selftext,
          top_comments: r.top_comments,
          created_utc: r.createdUtc
        })),
        query,
        processingTimeMs,
      };
    } catch (error) {
      logger.error('Aggregation failed:', error);
      throw error;
    }
  }

  /**
   * NOTE on Reddit semantics: the query is taken seriously only with
   * sort=relevance; sort=top/new drift toward popular/fresh content
   * regardless of the query — keep discovery channels relevance-first.
   */

  /**
   * Order results for the enrichment pass. No score threshold here:
   * fresh low-score threads are exactly what discovery needs — precision
   * is enforced downstream by backend heuristic + AI rerank.
   */
  private filterResults(results: RedditSearchResult[], targetCount: number): RedditSearchResult[] {
    return [...results]
      .sort((a, b) => {
        // Combined scoring: balance upvotes and engagement
        const scoreA = a.score + a.numComments * 2;
        const scoreB = b.score + b.numComments * 2;
        return scoreB - scoreA;
      })
      .slice(0, targetCount);
  }

  /**
   * Enrich results with full content using direct thread fetch
   */
  private async enrichResults(results: RedditSearchResult[]): Promise<RedditSearchResult[]> {
    const enriched: RedditSearchResult[] = [];
    // Limit to top 5 to keep latency reasonable
    const topResults = results.slice(0, 5);
    const others = results.slice(5);

    logger.info(`Enriching top ${topResults.length} posts with details...`);

    // Process in parallel
    const promises = topResults.map(async (post) => {
      try {
        const details = await this.getPostDetails(post.id, 50, 3);

        if (details) {
          return {
            ...post,
            selftext: details.selftext || post.selftext,
            top_comments: details.top_comments
          };
        }
      } catch (e) {
        logger.warn(`Failed to enrich post ${post.id}:`, e);
      }
      return post; // Return original if failed
    });

    const enrichedTop = await Promise.all(promises);
    return [...enrichedTop, ...others];
  }

  /**
   * Sanitize all text fields in results
   */
  private sanitizeResults(results: RedditSearchResult[]): RedditSearchResult[] {
    return results.map(r => ({
      ...r,
      title: sanitizeText(r.title),
      selftext: sanitizeText(r.selftext || ''),
      subreddit: sanitizeText(r.subreddit),
      author: sanitizeText(r.author),
    }));
  }

  /**
   * Fetch details for a single post
   */
  async getPostDetails(
    postId: string,
    comment_limit: number = 50,
    comment_depth: number = 3
  ): Promise<RedditSearchResult | null> {
    try {
      logger.info(`[Direct API] getPostDetails: id=${postId}, limit=${comment_limit}, depth=${comment_depth}`);

      const rawData = await fetchDeepThread(postId, comment_limit, comment_depth);

      if (!rawData || !rawData.post) return null;

      const post = rawData.post;
      const rawComments = rawData.comments || [];

      function formatComments(comments: any[]): any[] {
        return comments
          .filter((c: any) => c.body && c.author !== '[deleted]')
          .map((c: any) => ({
            id: c.id,
            author: sanitizeText(c.author),
            score: c.score,
            body: sanitizeText(c.body),
            created_utc: c.created_utc,
            depth: c.depth,
            is_op: c.is_submitter,
            flair: c.author_flair_text ? sanitizeText(c.author_flair_text) : null,
            distinguished: c.distinguished ? sanitizeText(c.distinguished) : null,
            stickied: c.stickied,
            permalink: `https://reddit.com${c.permalink}`,
            replies: (c.replies && c.replies.data && c.replies.data.children)
              ? formatComments(c.replies.data.children.map((child: any) => child.data))
              : []
          }));
      }

      const formattedComments = formatComments(rawComments);

      function countComments(comments: any[]): number {
        let count = comments.length;
        for (const c of comments) {
          if (c.replies) count += countComments(c.replies);
        }
        return count;
      }

      const totalFetched = countComments(formattedComments);
      logger.info(`✅ Fetched deep thread: ${totalFetched} comments (requested limit: ${comment_limit})`);

      const result: RedditSearchResult = {
        id: post.id,
        title: post.title || "Unknown Title",
        url: post.url,
        score: post.score,
        numComments: post.num_comments,
        subreddit: post.subreddit,
        author: post.author,
        createdUtc: post.created_utc,
        selftext: post.selftext || "",
        permalink: `https://reddit.com${post.permalink}`,
        top_comments: formattedComments
      };

      return this.sanitizeResults([result])[0];

    } catch (e) {
      logger.warn(`Failed to get details for post ${postId}:`, e);
      return null;
    }
  }
}

// ============================================================================
// Fastify Server
// ============================================================================

const fastify = Fastify({
  logger: LOG_LEVEL === 'debug',
});

const aggregator = new RedditAggregator();

// Cache for search results
const searchCache = new LRUCache<string, SearchResponse>({
  max: 100,
  ttl: CACHE_TTL_MS,
});

// Request validation schemas
const searchRequestSchema = z.object({
  query: z.string().min(1).max(500),
  limit: z.number().min(1).max(25).default(10),
  subreddits: z.array(z.string()).optional(),
  sort: z.enum(['relevance', 'hot', 'new', 'top']).default('relevance'),
  time: z.enum(['hour', 'day', 'week', 'month', 'year', 'all']).default('all'),
});

const detailsRequestSchema = z.object({
  postId: z.string().min(1),
  // NB: no subreddit param — Reddit resolves a post by id alone.
  comment_limit: z.number().optional(),
  comment_depth: z.number().optional(),
});

// Health check endpoint
fastify.get('/health', async () => {
  const credsConfigured = Boolean(
    process.env.REDDIT_CLIENT_ID &&
    process.env.REDDIT_CLIENT_SECRET &&
    process.env.REDDIT_USERNAME &&
    process.env.REDDIT_PASSWORD
  );
  return {
    status: credsConfigured ? 'healthy' : 'degraded',
    redditCredsConfigured: credsConfigured,
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
    redditRateLimitRemaining: rlRemaining,
  };
});

// Search endpoint
fastify.post('/search', async (request, reply) => {
  const parseResult = searchRequestSchema.safeParse(request.body);

  if (!parseResult.success) {
    reply.code(400);
    return {
      error: 'Invalid request',
      details: parseResult.error.format(),
    };
  }

  const { query, limit, subreddits, sort, time } = parseResult.data;

  // Check cache
  const cacheKey = JSON.stringify({ query, limit, subreddits, sort, time });
  const cached = searchCache.get(cacheKey);
  if (cached) {
    logger.info('Cache hit for query:', query);
    return cached;
  }

  try {
    const result = await aggregator.aggregate(query, {
      limit,
      subreddits,
      sort,
      time,
    });

    // Cache the result
    searchCache.set(cacheKey, result);

    return result;
  } catch (error) {
    logger.error('Search failed:', error);
    reply.code(500);
    return {
      error: 'Search failed',
      message: error instanceof Error ? error.message : 'Unknown error',
    };
  }
});

// Details endpoint
fastify.post('/details', async (request, reply) => {
  const parseResult = detailsRequestSchema.safeParse(request.body);

  if (!parseResult.success) {
    reply.code(400);
    return {
      error: 'Invalid request',
      details: parseResult.error.format(),
    };
  }

  const { postId, comment_limit, comment_depth } = parseResult.data;

  try {
    const result = await aggregator.getPostDetails(postId, comment_limit, comment_depth);

    if (!result) {
      reply.code(404);
      return {
        error: 'Post not found or details unavailable',
      };
    }

    return result;
  } catch (error) {
    logger.error('Details fetch failed:', error);
    reply.code(500);
    return {
      error: 'Details fetch failed',
      message: error instanceof Error ? error.message : 'Unknown error',
    };
  }
});

// ============================================================================
// Graceful Shutdown
// ============================================================================

async function shutdown(signal: string) {
  logger.info(`Received ${signal}, shutting down gracefully...`);

  try {
    await fastify.close();
    logger.info('Shutdown complete');
    process.exit(0);
  } catch (error) {
    logger.error('Error during shutdown:', error);
    process.exit(1);
  }
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// ============================================================================
// Main
// ============================================================================

async function main() {
  logger.info('Starting Reddit Proxy Service (direct OAuth API)...');
  logger.info('Configuration:');
  logger.info(`  Port: ${PORT}`);
  logger.info(`  Cache TTL: ${CACHE_TTL_MS}ms`);

  try {
    await fastify.listen({ port: PORT, host: '::' });
    logger.info(`Server listening on port ${PORT}`);
  } catch (error) {
    logger.error('Failed to start:', error);
    process.exit(1);
  }
}

main();
