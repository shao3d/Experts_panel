/**
 * Reddit MCP Proxy Service
 * 
 * Sidecar architecture for Experts Panel
 * Provides resilient Reddit search via MCP protocol with Watchdog pattern
 */

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { spawn } from 'cross-spawn';
import type { ChildProcess } from 'child_process';
import Fastify from 'fastify';
import PQueue from 'p-queue';
import { LRUCache } from 'lru-cache';
import { config } from 'dotenv';
import { z } from 'zod';

// Load environment variables
config();

// ============================================================================
// Configuration
// ============================================================================

const PORT = parseInt(process.env.PORT || '3000');
const MCP_TIMEOUT_MS = parseInt(process.env.MCP_TIMEOUT_MS || '15000');
const REDDIT_USER_AGENT = process.env.REDDIT_USER_AGENT || 
  'android:com.experts.panel:v1.0 (by /u/External-Way5292)';
const MCP_COMMAND = process.env.MCP_COMMAND || 'npx';
const MCP_ARGS = (process.env.MCP_ARGS || '-y reddit-mcp-buddy').split(' ');
const CACHE_TTL_MS = parseInt(process.env.CACHE_TTL_MS || '300000'); // 5 minutes
const LOG_LEVEL = process.env.LOG_LEVEL || 'debug';

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
  body?: string;
  permalink: string;
  top_comments?: any[];
}

interface SearchResponse {
  markdown: string;
  foundCount: number;
  sources: Array<{
    title: string;
    url: string;
    score: number;
    commentsCount: number;
    subreddit: string;
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
 * Zalgo uses Unicode combining characters (U+0300–U+036F and beyond)
 */
function sanitizeZalgo(text: string): string {
  // Remove combining characters (Unicode ranges for diacritics)
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
  
  // First, remove Zalgo characters globally
  const noZalgo = sanitizeZalgo(text);
  
  // Split by markdown code blocks (```...```)
  // The capturing group () ensures separators are included in the result array
  const parts = noZalgo.split(/(```[\s\S]*?```)/g);
  
  return parts.map(part => {
    // If it's a code block, keep it AS IS (preserve indentation)
    if (part.startsWith('```')) {
       return part; 
    }
    // If it's normal text, crush whitespaces to save tokens
    return normalizeWhitespace(part);
  }).join('');
}

/**
 * Escape markdown special characters for safe rendering
 */
function escapeMarkdown(text: string): string {
  return text
    .replace(/\\/g, '\\\\')
    .replace(/\*/g, '\\*')
    .replace(/_/g, '\\_')
    .replace(/\[/g, '\\[')
    .replace(/\]/g, '\\]')
    .replace(/\(/g, '\\(')
    .replace(/\)/g, '\\)')
    .replace(/`/g, '\\`');
}

// ============================================================================
// Watchdog MCP Manager
// ============================================================================

class WatchdogMCPManager {
  private client: Client | null = null;
  private transport: StdioClientTransport | null = null;
  private process: ChildProcess | null = null;
  private queue: PQueue;
  private isReady = false;
  private restartCount = 0;
  private readonly maxRestarts = 10;

  constructor() {
    this.queue = new PQueue({ concurrency: 1 });
  }

  /**
   * Spawn the MCP server process with retry logic
   */
  async spawn(): Promise<void> {
    if (this.restartCount >= this.maxRestarts) {
      throw new Error(`Max restarts (${this.maxRestarts}) exceeded. MCP server unstable.`);
    }

    logger.info('Spawning MCP server:', MCP_COMMAND, MCP_ARGS.join(' '));
    
    // Clean up any existing resources before spawning
    await this.cleanup();

    // Spawn child process with environment
    this.process = spawn(MCP_COMMAND, MCP_ARGS, {
      env: {
        ...process.env,
        REDDIT_USER_AGENT,
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    if (!this.process.pid) {
      throw new Error('Failed to spawn MCP server process');
    }

    this.restartCount++;
    logger.info(`MCP process spawned with PID: ${this.process.pid}, restart #${this.restartCount}`);

    // Log stderr for debugging
    this.process.stderr?.on('data', (data: Buffer) => {
      const message = data.toString().trim();
      if (message) {
        logger.debug('MCP stderr:', message);
      }
    });

    // Handle process exit
    this.process.on('exit', (code: number | null, signal: NodeJS.Signals | null) => {
      logger.warn(`MCP process exited with code ${code}, signal ${signal}`);
      this.isReady = false;
    });

    // Create transport with all Reddit credentials
    this.transport = new StdioClientTransport({
      command: MCP_COMMAND,
      args: MCP_ARGS,
      env: {
        ...process.env,
        REDDIT_USER_AGENT,
        REDDIT_CLIENT_ID: process.env.REDDIT_CLIENT_ID || '',
        REDDIT_CLIENT_SECRET: process.env.REDDIT_CLIENT_SECRET || '',
        REDDIT_USERNAME: process.env.REDDIT_USERNAME || '',
        REDDIT_PASSWORD: process.env.REDDIT_PASSWORD || '',
      } as Record<string, string>,
    });

    // Create client
    this.client = new Client(
      {
        name: 'experts-reddit-proxy',
        version: '1.0.0',
      },
      {
        capabilities: {},
      }
    );

    // Connect
    await this.client.connect(this.transport);
    this.isReady = true;
    logger.info('MCP client connected successfully');
  }

  /**
   * Clean up resources without full reset
   */
  private async cleanup(): Promise<void> {
    // Close client connection
    if (this.client) {
      try {
        await this.client.close();
      } catch (e) {
        logger.debug('Error closing client during cleanup:', e);
      }
      this.client = null;
    }

    // Kill process if still running
    if (this.process && !this.process.killed) {
      this.process.kill('SIGKILL');
      
      // Wait for process to exit with timeout
      await new Promise<void>((resolve) => {
        const timeout = setTimeout(() => {
          logger.warn('Force cleanup: process did not exit in time');
          this.process?.kill('SIGTERM');
          resolve();
        }, 2000);

        this.process?.once('exit', () => {
          clearTimeout(timeout);
          resolve();
        });
      });
    }
    this.process = null;
    this.transport = null;
  }

  /**
   * Kill the MCP process and reset state
   */
  async kill(): Promise<void> {
    logger.warn('Killing MCP process...');
    await this.cleanup();
    this.isReady = false;
    logger.info('MCP process killed');
  }

  /**
   * Respawn the MCP process
   */
  async respawn(): Promise<void> {
    logger.info('Respawning MCP process...');
    await this.kill();
    await this.spawn();
  }

  /**
   * Execute MCP tool call with timeout and watchdog
   */
  async executeTool<T = unknown>(toolName: string, args: Record<string, unknown>): Promise<T> {
    // Auto-restart if not ready
    if (!this.isReady || !this.client) {
      logger.warn('MCP client not ready, attempting respawn...');
      try {
        await this.respawn();
      } catch (spawnError) {
        logger.error('Failed to respawn MCP server:', spawnError);
        throw new Error('MCP client not ready and respawn failed');
      }
    }

    return this.queue.add(async () => {
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => {
          reject(new Error(`MCP tool call timeout after ${MCP_TIMEOUT_MS}ms`));
        }, MCP_TIMEOUT_MS);
      });

      const toolPromise = this.client!.callTool({
        name: toolName,
        arguments: args,
      });

      try {
        const result = await Promise.race([toolPromise, timeoutPromise]);
        
        // Extract content from MCP result
        if (result && result.content && Array.isArray(result.content)) {
          const textContent = result.content
            .filter((item: { type?: string; text?: string }) => item.type === 'text')
            .map((item: { text?: string }) => item.text)
            .join('\n');
          
          // Safely parse JSON with fallback
          try {
            return JSON.parse(textContent) as T;
          } catch (parseError) {
            logger.warn('JSON parse failed, returning raw text:', parseError);
            // Return the text content wrapped in a predictable structure
            return { rawText: textContent, _parseError: true } as unknown as T;
          }
        }
        
        return result as T;
      } catch (error) {
        // If timeout or error, respawn and rethrow
        if (error instanceof Error && error.message.includes('timeout')) {
          logger.error('Tool call timeout, triggering respawn...');
          await this.respawn();
        }
        throw error;
      }
    }) as Promise<T>;
  }

  getClient(): Client | null {
    return this.client;
  }

  get isHealthy(): boolean {
    return this.isReady && this.process !== null && !this.process.killed;
  }
}

// ============================================================================
// Smart Aggregation
// ============================================================================

class RedditAggregator {
  private mcp: WatchdogMCPManager;

  constructor(mcp: WatchdogMCPManager) {
    this.mcp = mcp;
  }

  /**
   * Smart Aggregation: Search x2 → Filter → Fetch → Sanitize
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
      // Step 1: Search x2 (search for posts + get details)
      const searchResults = await this.searchReddit(query, {
        subreddits,
        sort,
        time,
        limit: Math.min(limit * 2, 25), // Get more to filter
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

      // Build markdown
      const markdown = this.buildMarkdown(sanitized, query);
      const processingTimeMs = Date.now() - startTime;

      return {
        markdown,
        foundCount: sanitized.length,
        sources: sanitized.map(r => ({
          title: r.title,
          url: r.permalink.startsWith('http') ? r.permalink : `https://reddit.com${r.permalink}`,
          score: r.score,
          commentsCount: r.numComments,
          subreddit: r.subreddit,
          selftext: r.selftext,
          top_comments: r.top_comments
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
   * Search Reddit using MCP tool
   */
  private async searchReddit(
    query: string,
    options: {
      subreddits?: string[];
      sort: string;
      time: string;
      limit: number;
    }
  ): Promise<RedditSearchResult[]> {
    // Always use search_reddit to ensure the query is respected.
    // browse_subreddit ignores the query and just returns top posts, which is bad for specific searches.
    
    logger.info('Executing search_reddit for query:', query, 'subreddits:', options.subreddits);
    const rawResult = await this.mcp.executeTool<unknown>('search_reddit', {
      query,
      subreddits: options.subreddits || [],
      sort: options.sort,
      time: options.time,
      limit: options.limit,
    });

    // Check if result is valid and has posts
    if (!rawResult || typeof rawResult !== 'object') {
      logger.error('Invalid response from searchReddit:', rawResult);
      throw new Error('Invalid response from Reddit MCP server');
    }

    // DEBUG: Log raw result structure
    logger.debug('Raw search result:', JSON.stringify(rawResult, null, 2));

    // Handle raw text fallback (when JSON parsing failed)
    if ('_parseError' in rawResult && 'rawText' in rawResult) {
      logger.error('MCP returned raw text instead of JSON:', rawResult.rawText);
      throw new Error('Reddit MCP server returned unexpected format');
    }

    const result = rawResult as { 
      posts?: Array<{
        id: string;
        title: string;
        author: string;
        score: number;
        upvote_ratio: number;
        num_comments: number;
        created_utc: number;
        url: string;
        permalink: string;
        subreddit: string;
        is_video: boolean;
        is_text_post: boolean;
        content?: string;
        nsfw: boolean;
        stickied: boolean;
        link_flair_text?: string;
      }>;
      results?: Array<{
        id: string;
        title: string;
        author: string;
        score: number;
        upvote_ratio: number;
        num_comments: number;
        created_utc: number;
        url: string;
        permalink: string;
        subreddit: string;
        is_video: boolean;
        is_text_post: boolean;
        content?: string;
        nsfw: boolean;
        link_flair_text?: string;
      }>;
      total_posts?: number;
      total_results?: number;
    };

    // Handle different response formats:
    // - browse_subreddit returns { posts: [...], total_posts: N }
    // - search_reddit returns { results: [...], total_results: N }
    const postsArray = result.posts || result.results || [];
    logger.info(`search_reddit found ${postsArray.length} posts (total_results: ${result.total_results || 0})`);

    // Map to our internal format
    return postsArray.map(post => ({
      id: post.id,
      title: post.title,
      url: post.url,
      score: post.score,
      numComments: post.num_comments,
      subreddit: post.subreddit,
      author: post.author,
      createdUtc: post.created_utc,
      selftext: post.content,
      permalink: post.permalink,
    }));
  }

  /**
   * Filter results by quality criteria
   */
  private filterResults(results: RedditSearchResult[], targetCount: number): RedditSearchResult[] {
    // Score threshold: posts with negative or very low score are likely low quality
    const MIN_SCORE = 5;
    
    const filtered = results
      .filter(r => r.score >= MIN_SCORE)
      .sort((a, b) => {
        // Combined scoring: balance upvotes and engagement
        const scoreA = a.score + a.numComments * 2;
        const scoreB = b.score + b.numComments * 2;
        return scoreB - scoreA;
      });

    return filtered.slice(0, targetCount);
  }

  /**
   * Enrich results with full content using get_post_details
   */
  private async enrichResults(results: RedditSearchResult[]): Promise<RedditSearchResult[]> {
    const enriched: RedditSearchResult[] = [];
    // Limit to top 5 to keep latency reasonable
    const topResults = results.slice(0, 5);
    const others = results.slice(5);

    logger.info(`Enriching top ${topResults.length} posts with details...`);

    // Process in parallel with concurrency limit
    const promises = topResults.map(async (post) => {
      try {
        // Call get_post_details tool
        // Note: reddit-mcp-buddy uses 'url' or 'post_id' + 'subreddit'
        const details = await this.mcp.executeTool<any>('get_post_details', {
          post_id: post.id,
          subreddit: post.subreddit,
          comment_limit: 50, // Get top 50 comments for broad coverage
          comment_depth: 3   // Capture depth (replies) to understand the debate
        });

        // DEBUG LOGGING
        logger.info(`[DEBUG] get_post_details for ${post.id} returned keys:`, details ? Object.keys(details) : 'null');
        if (details && typeof details === 'object') {
            logger.debug(`[DEBUG] details sample:`, JSON.stringify(details).substring(0, 200));
        }

        if (details) {
            // Extract content and comments from tool output
            // The structure depends on reddit-mcp-buddy implementation
            // Usually returns { selftext: "...", comments: [...] } or string content
            
            let fullContent = post.selftext || "";
            let comments: any[] = [];

            // Helper to extract text from generic tool result
            if (typeof details === 'string') {
                fullContent = details;
            } else if (typeof details === 'object') {
                // Handle nested 'post' object (reddit-mcp-buddy structure)
                if (details.post) {
                    fullContent = details.post.selftext || details.post.content || fullContent;
                } else {
                    // Fallback for flat structure
                    if (details.selftext) fullContent = details.selftext;
                    if (details.content) fullContent = details.content;
                }

                // Handle comments - prioritize top_comments from result
                if (Array.isArray(details.top_comments)) {
                    comments = details.top_comments;
                } else if (Array.isArray(details.comments)) {
                    comments = details.comments;
                }
            }

            return {
                ...post,
                selftext: fullContent || post.selftext, // Update if we got better content
                top_comments: comments // Add comments
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
      body: sanitizeText(r.body || ''),
      subreddit: sanitizeText(r.subreddit),
      author: sanitizeText(r.author),
    }));
  }

  /**
   * Build markdown from results
   */
  private buildMarkdown(results: RedditSearchResult[], query: string): string {
    if (results.length === 0) {
      return `No Reddit discussions found for "${query}".`;
    }

    const sections = results.map((r, i) => {
      // Fix: permalink might already contain full URL
      const url = r.permalink.startsWith('http') 
        ? r.permalink 
        : `https://reddit.com${r.permalink}`;
      const content = r.selftext || r.body || '';
      const truncatedContent = content.length > 500 
        ? content.substring(0, 500) + '...' 
        : content;

      return `### ${i + 1}. ${r.title}

**r/${r.subreddit}** | Score: ${r.score} | Comments: ${r.numComments}

${truncatedContent}

[Read on Reddit](${url})`;
    });

    return sections.join('\n\n---\n\n');
  }
}

// ============================================================================
// Fastify Server
// ============================================================================

const fastify = Fastify({
  logger: LOG_LEVEL === 'debug',
});

// Initialize MCP and Aggregator
const mcpManager = new WatchdogMCPManager();
const aggregator = new RedditAggregator(mcpManager);

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

// Health check endpoint
fastify.get('/health', async () => {
  return {
    status: mcpManager.isHealthy ? 'healthy' : 'unhealthy',
    mcpReady: mcpManager.isHealthy,
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
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

// ============================================================================
// Graceful Shutdown
// ============================================================================

async function shutdown(signal: string) {
  logger.info(`Received ${signal}, shutting down gracefully...`);
  
  try {
    await fastify.close();
    await mcpManager.kill();
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
  logger.info('Starting Reddit MCP Proxy Service...');
  logger.info('Configuration:');
  logger.info(`  Port: ${PORT}`);
  logger.info(`  MCP Timeout: ${MCP_TIMEOUT_MS}ms`);
  logger.info(`  Cache TTL: ${CACHE_TTL_MS}ms`);

  try {
    // Initialize MCP
    await mcpManager.spawn();
    
    // Start server
    await fastify.listen({ port: PORT, host: '::' });
    logger.info(`Server listening on port ${PORT}`);
  } catch (error) {
    logger.error('Failed to start:', error);
    await mcpManager.kill();
    process.exit(1);
  }
}

main();
