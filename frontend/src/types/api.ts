/**
 * API types matching backend Pydantic models.
 * Generated from backend/src/api/models.py
 */

// ============================================================================
// Enums
// ============================================================================

/**
 * Relevance levels for posts (matches backend RelevanceLevel enum)
 */
export enum RelevanceLevel {
  HIGH = "HIGH",
  MEDIUM = "MEDIUM",
  LOW = "LOW",
  CONTEXT = "CONTEXT"
}

/**
 * Confidence levels for answers (matches backend ConfidenceLevel enum)
 */
export enum ConfidenceLevel {
  HIGH = "HIGH",
  MEDIUM = "MEDIUM",
  LOW = "LOW"
}

/**
 * Expert information from metadata
 */
export interface ExpertInfo {
  expert_id: string;
  display_name: string;
  channel_username: string;
  stats: {
    posts_count: number;
    comments_count: number;
  };
}

// ============================================================================
// Request Models
// ============================================================================

/**
 * Query request payload (matches backend QueryRequest)
 */
export interface QueryRequest {
  /** User's query in natural language (3-1000 chars) */
  query: string;

  /** Maximum number of posts to process (default: all) */
  max_posts?: number;

  /** Whether to include expert comments in response (default: true) */
  include_comments?: boolean;

  /** Whether to search for relevant Telegram comment groups (Pipeline B, default: false) */
  include_comment_groups?: boolean;

  /** Whether to stream progress updates via SSE (default: true) */
  stream_progress?: boolean;

  /** List of expert IDs to filter results (default: all experts) */
  expert_filter?: string[];

  /** Use only recent data (last 3 months) for fresh news (default: false) */
  use_recent_only?: boolean;

  /** Include Reddit community insights in response (default: true) */
  include_reddit?: boolean;
}

// ============================================================================
// Response Models
// ============================================================================

/**
 * Token usage statistics (matches backend TokenUsage)
 */
export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost?: number;
}

/**
 * Anchor post for comment groups (matches backend AnchorPost)
 */
export interface AnchorPost {
  /** Telegram message ID of the anchor post */
  telegram_message_id: number;

  /** Text content of the anchor post */
  message_text: string;

  /** When the anchor post was created */
  created_at: string;

  /** Author of the anchor post */
  author_name: string;

  /** Channel username for Telegram links */
  channel_username: string;
}

/**
 * Comment group response (matches backend CommentGroupResponse)
 */
export interface CommentGroupResponse {
  /** Telegram message ID of the anchor post */
  parent_telegram_message_id: number;

  /** Relevance level (HIGH/MEDIUM/LOW) */
  relevance: string;

  /** Explanation of why this comment group is relevant */
  reason: string;

  /** Number of comments in this group */
  comments_count: number;

  /** The anchor post that these comments belong to */
  anchor_post: AnchorPost;

  /** List of comments in this group */
  comments: CommentResponse[];
}

/**
 * Response from a single expert (matches backend ExpertResponse)
 */
export interface ExpertResponse {
  /** Expert identifier */
  expert_id: string;

  /** Human-readable expert name */
  expert_name: string;

  /** Telegram channel username */
  channel_username: string;

  /** Synthesized answer with inline references */
  answer: string;

  /** Main source post IDs (telegram_message_ids) */
  main_sources: number[];

  /** Confidence level of the answer */
  confidence: ConfidenceLevel;

  /** Total number of posts analyzed */
  posts_analyzed: number;

  /** Processing time for this expert in milliseconds */
  processing_time_ms: number;

  /** Relevant comment groups found (optional) */
  relevant_comment_groups?: CommentGroupResponse[];

  /** Synthesized insights from comment groups (optional) */
  comment_groups_synthesis?: string;
}

/**
 * Reddit post source information (matches backend RedditSource)
 */
export interface RedditSource {
  /** Post title */
  title: string;

  /** Post URL on Reddit */
  url: string;

  /** Post score (upvotes - downvotes) */
  score: number;

  /** Number of comments */
  comments_count: number;

  /** Subreddit name */
  subreddit: string;
}

/**
 * Reddit community response (matches backend RedditResponse)
 */
export interface RedditResponse {
  /** Raw markdown content from Reddit search */
  markdown: string;

  /** AI-generated synthesis of Reddit discussions */
  synthesis: string;

  /** Number of posts found */
  found_count: number;

  /** List of Reddit post sources */
  sources: RedditSource[];

  /** Query used for Reddit search */
  query: string;

  /** Reddit processing time in milliseconds */
  processing_time_ms: number;
}

/**
 * Multi-expert query response (matches backend MultiExpertQueryResponse)
 */
export interface MultiExpertQueryResponse {
  /** Original query */
  query: string;

  /** Responses from each expert */
  expert_responses: ExpertResponse[];

  /** Community insights from Reddit (optional) */
  reddit_response?: RedditResponse | null;

  /** Total processing time across all experts */
  total_processing_time_ms: number;

  /** Unique request ID for tracking */
  request_id: string;
}

/**
 * Query response - backward compatible version that works with both single and multi-expert responses
 */
export interface QueryResponse {
  /** Original user query */
  query: string;

  /** Synthesized answer with inline references */
  answer: string;

  /** Main source post IDs (telegram_message_ids) */
  main_sources: number[];

  /** Confidence level of the answer */
  confidence: ConfidenceLevel;

  /** Language of the response (ru/en) */
  language: string;

  /** Whether expert comments were included */
  has_expert_comments: boolean;

  /** Total number of posts analyzed */
  posts_analyzed: number;

  /** Number of expert comments included */
  expert_comments_included: number;

  /** Distribution of posts by relevance level */
  relevance_distribution: Record<string, number>;

  /** Token usage statistics */
  token_usage?: TokenUsage;

  /** Total processing time in milliseconds */
  processing_time_ms: number;

  /** Unique request ID for tracking */
  request_id: string;

  /** Relevant comment groups found (optional, if enabled) */
  relevant_comment_groups?: CommentGroupResponse[];

  /** Synthesized insights from comment groups (optional) */
  comment_groups_synthesis?: string;

  /** Expert responses for multi-expert mode */
  expert_responses?: ExpertResponse[];

  /** Reddit community insights (optional) */
  reddit_response?: RedditResponse | null;
}

// ============================================================================
// SSE Progress Events
// ============================================================================

/**
 * SSE progress event (matches backend ProgressEvent)
 */
export interface ProgressEvent {
  /** Type of progress event */
  event_type: 'phase_start' | 'progress' | 'phase_complete' | 'complete' | 'error' | 'expert_error';

  /** Current phase (map/resolve/reduce/final) */
  phase: string;

  /** Current status within phase */
  status: string;

  /** Human-readable progress message */
  message: string;

  /** Event timestamp */
  timestamp?: string;

  /** Additional event data */
  data?: Record<string, any>;

  /** Legacy fields for compatibility */
  current?: number;
  total?: number;
}

// ============================================================================
// Post Detail Models
// ============================================================================

/**
 * Comment on a post (matches backend CommentResponse)
 */
export interface CommentResponse {
  comment_id: number;
  comment_text: string;
  author_name: string;
  created_at: string;
  updated_at: string;
}

/**
 * Link between posts (matches backend LinkResponse)
 */
export interface LinkResponse {
  link_id: number;
  source_post_id: number;
  target_post_id: number;
  link_type: string;
  created_at: string;
}

/**
 * Detailed post information (matches backend PostDetailResponse)
 */
export interface PostDetailResponse {
  post_id: number;
  telegram_message_id: number;
  channel_id: string;
  channel_name?: string;
  message_text?: string;
  author_name?: string;
  author_id?: string;
  created_at: string;
  edited_at?: string;
  view_count: number;
  forward_count: number;
  reply_count: number;
  is_forwarded: boolean;
  forward_from_channel?: string;
  media_metadata?: Record<string, any>;
  comments: CommentResponse[];
  incoming_links: LinkResponse[];
  outgoing_links: LinkResponse[];
}

// ============================================================================
// Error Models
// ============================================================================

/**
 * API error response (matches backend ErrorResponse)
 */
export interface APIError {
  error: string;
  message: string;
  request_id?: string;
  timestamp?: string;
}

// ============================================================================
// Health Check
// ============================================================================

/**
 * Health check response
 */
export interface HealthResponse {
  status: 'healthy' | 'degraded';
  version: string;
  database: 'healthy' | 'unhealthy';
  openai_configured: boolean;
  timestamp: number;
}
