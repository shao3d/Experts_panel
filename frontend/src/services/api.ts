/**
 * API client for backend communication.
 * Handles POST requests with SSE streaming for real-time progress.
 */

import {
  QueryRequest,
  QueryResponse,
  ProgressEvent,
  PostDetailResponse,
  HealthResponse,
  ExpertInfo,
  APIError,
  ConfidenceLevel
} from '../types/api';

import { logSSEEvent } from '../utils/debugLogger';

/**
 * Callback type for progress events during query processing
 */
export type ProgressCallback = (event: ProgressEvent) => void;

/**
 * Determine if a query is in English (for translation UX)
 * Simple heuristic: check if majority of words are English
 */
export function isEnglishQuery(query: string): boolean {
  if (!query || !query.trim()) return false;

  const words = query.trim().split(/\s+/);
  const englishWords = words.filter(word =>
    /^[a-zA-Z][a-zA-Z]*$/.test(word) ||
    /^[a-zA-Z]+$/.test(word)
  );

  // If at least 70% of words are English, consider it an English query
  return words.length > 0 && (englishWords.length / words.length) >= 0.7;
}

/**
 * API client for Experts Panel backend
 */
export class APIClient {
  private baseURL: string;

  constructor(baseURL?: string) {
    // For production/PR apps, use relative URLs to work with the same domain
    // For local development, use localhost or VITE_API_URL if specified
    if (import.meta.env.PROD) {
      this.baseURL = '';  // Use relative URLs in production
    } else {
      this.baseURL = baseURL || import.meta.env.VITE_API_URL || 'http://localhost:8000';
    }
  }

  /**
   * Attach admin secret header if configured
   */
  private buildHeaders(headers?: HeadersInit): HeadersInit {
    const adminSecret = import.meta.env.VITE_ADMIN_SECRET;

    if (!adminSecret) {
      return headers || {};
    }

    if (headers instanceof Headers) {
      const cloned = new Headers(headers);
      cloned.set('X-Admin-Secret', adminSecret);
      return cloned;
    }

    if (Array.isArray(headers)) {
      const fromArray = new Headers(headers);
      fromArray.set('X-Admin-Secret', adminSecret);
      return fromArray;
    }

    return {
      ...(headers || {}),
      'X-Admin-Secret': adminSecret
    };
  }

  /**
   * Health check endpoint
   *
   * @returns Health status of the backend
   */
  async checkHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseURL.replace(/\/$/, '')}/health`, {
      headers: this.buildHeaders()
    });

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get list of available experts
   */
  async getExperts(): Promise<ExpertInfo[]> {
    const response = await fetch(`${this.baseURL.replace(/\/$/, '')}/api/v1/experts`, {
      headers: this.buildHeaders()
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch experts: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Submit query with SSE streaming for real-time progress
   *
   * @param request - Query request with user's question
   * @param onProgress - Callback for progress events
   * @returns Promise that resolves with final QueryResponse
   */
  async submitQuery(
    request: QueryRequest,
    onProgress?: ProgressCallback
  ): Promise<QueryResponse> {
    // Enable streaming by default
    const requestBody: QueryRequest = {
      ...request,
      stream_progress: request.stream_progress !== false
    };

    try {
      const response = await fetch(`${this.baseURL.replace(/\/$/, '')}/api/v1/query`, {
        method: 'POST',
        headers: this.buildHeaders({
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        let errorMessage = 'Query processing failed';
        try {
          const error: APIError = await response.json();
          errorMessage = error.message || errorMessage;
        } catch {
          // If response is not JSON (e.g., 502 from proxy)
          errorMessage = `Server error: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }

      // If streaming disabled, just return JSON response
      if (!requestBody.stream_progress) {
        return response.json();
      }

      // Parse SSE stream
      return this.parseSSEStream(response, onProgress);
    } catch (err) {
      // Handle network errors (connection refused, timeout, DNS failure)
      if (err instanceof TypeError && err.message.includes('fetch')) {
        throw new Error('Cannot connect to server. Make sure backend is running on ' + this.baseURL);
      }
      // Re-throw other errors (including our custom error messages)
      throw err;
    }
  }

  /**
   * Normalize response to handle both single and multi-expert formats
   */
  private normalizeResponse(rawResponse: any): QueryResponse {
    // Check if it's already in the old format (has answer field directly)
    if (rawResponse.answer !== undefined) {
      return rawResponse as QueryResponse;
    }

    // It's a multi-expert response, convert to legacy format
    const multiResponse = rawResponse as any;
    const firstExpert = multiResponse.expert_responses?.[0];

    if (!firstExpert) {
      // Check if we have error information from the backend
      const lastProgressEvent = multiResponse.last_progress_event;
      let errorMessage = '';

      if (lastProgressEvent?.data?.error_type && lastProgressEvent?.data?.user_message) {
        // Use user-friendly message from backend error detector
        errorMessage = lastProgressEvent.data.user_message;
        console.log('[API] Using backend error message:', {
          error_type: lastProgressEvent.data.error_type,
          message: errorMessage,
          original_error: lastProgressEvent.data.original_error
        });
      } else {
        // Default message for no experts responded
        errorMessage = '🔧 Сервис обработки запросов временно недоступен. Пожалуйста, попробуйте позже.';
        console.log('[API] Using default error message - no error info from backend');
      }

      // No experts responded, create empty response with user-friendly message
      // FIX: Include reddit_response even when no experts found
      return {
        query: multiResponse.query || '',
        answer: errorMessage,
        main_sources: [],
        confidence: ConfidenceLevel.LOW,
        language: 'ru',
        has_expert_comments: false,
        posts_analyzed: 0,
        expert_comments_included: 0,
        relevance_distribution: {},
        processing_time_ms: multiResponse.total_processing_time_ms || 0,
        request_id: multiResponse.request_id || '',
        expert_responses: multiResponse.expert_responses || [],
        reddit_response: multiResponse.reddit_response
      };
    }

    // Map first expert to legacy fields for backward compatibility
    return {
      query: multiResponse.query || '',
      answer: firstExpert.answer || '',
      main_sources: firstExpert.main_sources || [],
      confidence: firstExpert.confidence || ConfidenceLevel.LOW,
      language: 'ru', // Default to Russian as per the system
      has_expert_comments: false, // These fields are not in ExpertResponse
      posts_analyzed: firstExpert.posts_analyzed || 0,
      expert_comments_included: 0,
      relevance_distribution: {},
      token_usage: undefined,
      processing_time_ms: firstExpert.processing_time_ms || multiResponse.total_processing_time_ms || 0,
      request_id: multiResponse.request_id || '',
      relevant_comment_groups: firstExpert.relevant_comment_groups,
      comment_groups_synthesis: firstExpert.comment_groups_synthesis,
      expert_responses: multiResponse.expert_responses || [],
      reddit_response: multiResponse.reddit_response
    };
  }

  /**
   * Parse Server-Sent Events stream from response
   *
   * @param response - Fetch response with SSE stream
   * @param onProgress - Callback for progress events
   * @returns Promise that resolves with final QueryResponse
   */
  private async parseSSEStream(
    response: Response,
    onProgress?: ProgressCallback
  ): Promise<QueryResponse> {
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    let buffer = '';
    let finalResponse: QueryResponse | null = null;
    let lastErrorEvent: ProgressEvent | null = null; // Track last error event

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          // Process all remaining complete lines in buffer
          const remainingLines = buffer.split('\n').filter(line => line.trim());
          for (const line of remainingLines) {
            if (!line.startsWith('data:')) continue;

            let jsonString = line.substring(5).trim();
            // Handle double prefix (backend bug workaround)
            if (jsonString.startsWith('data: ')) {
              jsonString = jsonString.substring(6).trim();
            }
            if (!jsonString) continue;

            try {
              const event: ProgressEvent = JSON.parse(jsonString);

              // Log SSE events for debugging
              logSSEEvent(event.phase || 'unknown', event.event_type, event, event.message);

              // Track error events for later use
              if (event.event_type === 'error' || event.event_type === 'expert_error') {
                lastErrorEvent = event;
              }

              if (onProgress) onProgress(event);
              if (event.event_type === 'complete' && event.data?.response) {
                const rawResponse = event.data.response as any;
                // Attach last error event to response for error handling
                if (lastErrorEvent) {
                  (rawResponse as any).last_progress_event = lastErrorEvent;
                }
                finalResponse = this.normalizeResponse(rawResponse);
              }
            } catch (e) {
              console.error('Failed to parse final SSE event:', jsonString, e);
            }
          }
          break;
        }

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process all complete lines (ending with \n)
        const lines = buffer.split('\n');
        
        // The last element of split() is the part after the last \n.
        // If the buffer doesn't end with \n, this is an incomplete line.
        // If it does, this is an empty string. In either case, we save it for the next chunk.
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data:')) continue;

          // Extract JSON after "data: " prefix
          // Remove "data: " prefix (handle double prefix case)
          let jsonString = line.substring(5).trim();
          // Check if there's another "data: " prefix (backend bug workaround)
          if (jsonString.startsWith('data: ')) {
            jsonString = jsonString.substring(6).trim();
          }
          if (!jsonString) continue; // Skip empty data: lines (keep-alive)

          try {
            const event: ProgressEvent = JSON.parse(jsonString);

            // Track error events for later use
            if (event.event_type === 'error' || event.event_type === 'expert_error') {
              lastErrorEvent = event;
            }

            // Debug logging
            console.log('[SSE] Event received:', {
              type: event.event_type,
              phase: event.phase,
              status: event.status,
              hasData: !!event.data,
              hasResponse: event.data?.response !== undefined,
              isLastError: event.event_type === 'error' || event.event_type === 'expert_error'
            });

            // Call progress callback if provided
            if (onProgress) {
              onProgress(event);
            }

            // Check if this is the final result
            if (event.event_type === 'complete' && event.data?.response) {
              console.log('[SSE] Found final response in event.data.response:', event.data.response);
              // Handle multi-expert response format
              const rawResponse = event.data.response as any;
              // Attach last error event to response for error handling
              if (lastErrorEvent) {
                (rawResponse as any).last_progress_event = lastErrorEvent;
              }
              finalResponse = this.normalizeResponse(rawResponse);
            }

            // Check for errors
            if (event.event_type === 'error') {
              throw new Error(event.message || 'Query processing failed');
            }
          } catch (parseError) {
            console.error('Failed to parse SSE event:', jsonString, parseError);
            // Continue processing other events
          }
        }
      }

      console.log('[SSE] Stream ended. Final response:', finalResponse);

      if (!finalResponse) {
        throw new Error('Query completed but no result received');
      }

      return finalResponse;
    } finally {
      try {
        await reader.cancel();
      } catch (e) {
        // Ignore errors during stream cancellation
      }
      reader.releaseLock();
    }
  }

  /**
   * Sleep utility for retry delays
   */
  private async sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get detailed information about a specific post with retry mechanism
   *
   * @param postId - Post ID to fetch
   * @param expertId - Optional expert ID to filter posts (required for multi-expert)
   * @param query - Optional user query to determine if translation is needed
   * @param translate - Boolean flag to force translation
   * @param maxRetries - Maximum number of retry attempts (default: 3)
   * @returns Post details with comments and links
   */
  async getPostDetail(
    postId: number,
    expertId?: string,
    query?: string,
    translate = false,
    maxRetries = 3
  ): Promise<any> {
    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(`[API] Fetching post ${postId} (attempt ${attempt}/${maxRetries})`);

        const baseUrl = this.baseURL.replace(/\/$/, '');
        let url = expertId
          ? `${baseUrl}/api/v1/posts/${postId}?expert_id=${encodeURIComponent(expertId)}`
          : `${baseUrl}/api/v1/posts/${postId}`;

        // Add query parameters if provided
        const params = new URLSearchParams();
        if (query) params.append('query', query);
        if (translate) params.append('translate', 'true');

        if (params.toString()) {
          url += url.includes('?') ? `&${params.toString()}` : `?${params.toString()}`;
        }

        const response = await fetch(url, {
          headers: this.buildHeaders()
        });

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error(`Post with ID ${postId} not found`);
          }
          const error: APIError = await response.json();
          throw new Error(error.message || 'Failed to fetch post details');
        }

        const result = await response.json();
        console.log(`[API] Successfully fetched post ${postId} on attempt ${attempt}`);
        return result;

      } catch (error) {
        lastError = error as Error;
        console.warn(`[API] Post ${postId} fetch failed (attempt ${attempt}/${maxRetries}):`, error);

        // If this is the last attempt, don't wait
        if (attempt === maxRetries) {
          console.error(`[API] Post ${postId} failed after ${maxRetries} attempts`);
          break;
        }

        // Exponential backoff: 1s, 2s, 4s (max 5s)
        const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
        console.log(`[API] Retrying post ${postId} after ${delay}ms delay`);
        await this.sleep(delay);
      }
    }

    // All retries failed - throw the last error
    throw lastError || new Error(`Failed to fetch post ${postId} after ${maxRetries} attempts`);
  }

  /**
   * Fetch multiple posts by their IDs
   *
   * @param postIds - Array of post IDs
   * @param expertId - Optional expert ID to filter posts (required for multi-expert)
   * @param query - Optional user query to determine if translation is needed
   * @returns Array of post details
   */
  async getPostsByIdsProgressive(
    postIds: number[],
    expertId?: string,
    query?: string,
    onPostReady?: (post: PostDetailResponse) => void,
    onProgress?: (completed: number, total: number) => void,
    onRetry?: (postId: number, attempt: number, maxRetries: number) => void
  ): Promise<PostDetailResponse[]> {
    console.log('[API] Fetching posts progressively in parallel:', postIds, 'for expert:', expertId, 'with query:', query);

    // Determine if translation is needed
    const needsTranslation = query ? isEnglishQuery(query) : false;
    let completed = 0;
    const completedResults: any[] = [];

    // Create individual promises with wrapped metadata and retry support
    const postPromises = postIds.map(async (postId, index) => {
      let lastError: Error | null = null;
      let retryCount = 0;
      const maxRetries = 3;

      for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
          console.log(`[API] Starting fetch for post ${postId} (${index + 1}/${postIds.length}, attempt ${attempt}/${maxRetries})`);

          const post = await this.getPostDetail(postId, expertId, query, needsTranslation, maxRetries);

          // If retry succeeded and we're here after multiple attempts, notify about successful retry
          if (onRetry && attempt > 1) {
            onRetry(postId, attempt - 1, maxRetries);
          }

          console.log(`[API] Successfully fetched post ${postId} on attempt ${attempt}`);
          return { post, postId, index, success: true, retryCount: attempt - 1 };

        } catch (error) {
          lastError = error as Error;
          retryCount = attempt;

          if (attempt < maxRetries) {
            console.warn(`[API] Post ${postId} failed (attempt ${attempt}/${maxRetries}), retrying...`);

            // Notify about retry attempt
            if (onRetry) {
              onRetry(postId, attempt, maxRetries);
            }

            // Exponential backoff is handled inside getPostDetail
            continue;
          }
        }
      }

      // All retries failed - try without translation as fallback
      if (needsTranslation) {
        console.log(`[API] Translation failed for post ${postId} after ${maxRetries} attempts, trying original post`);
        try {
          const originalPost = await this.getPostDetail(postId, expertId, query, false, 1);
          console.log(`[API] Successfully fetched original post ${postId} as fallback`);
          return { post: originalPost, postId, index, success: true, fallback: true, retryCount };
        } catch (fallbackError) {
          console.error(`[API] Fallback also failed for post ${postId}`);
          return { post: null, postId, index, success: false, error: lastError, retryCount };
        }
      } else {
        console.error(`[API] Post ${postId} failed after ${maxRetries} attempts`);
        return { post: null, postId, index, success: false, error: lastError, retryCount };
      }
    });

    // Process posts as they complete using Promise.race - TRUE progressive loading
    const pendingPromises = postPromises.map((promise, index) => ({
      promise,
      index,
      completed: false
    }));

    while (pendingPromises.some(p => !p.completed)) {
      // Race between all pending promises
      const racePromises = pendingPromises
        .filter(p => !p.completed)
        .map(p => p.promise.then(result => ({ result, originalIndex: p.index })));

      if (racePromises.length === 0) break;

      try {
        // Wait for the next promise to complete
        const { result, originalIndex } = await Promise.race(racePromises);

        // Mark this promise as completed
        const promiseMeta = pendingPromises[originalIndex];
        promiseMeta.completed = true;

        completed++;
        completedResults.push(result);

        const statusText = result.fallback ? ' (fallback to original)' : result.retryCount > 0 ? ` (after ${result.retryCount} retries)` : '';
        console.log(`[API] Post completed in real-time: ${result.postId}${statusText}, ${completed}/${postIds.length}`);

        // Update progress in real-time
        if (onProgress) {
          onProgress(completed, postIds.length);
        }

        // Notify about post ready immediately (REAL progressive loading!)
        if (result.success && result.post && onPostReady) {
          onPostReady(result.post);
        }

      } catch (error) {
        console.error('[API] Error in Promise.race:', error);
        completed++;

        // Still update progress on race error
        if (onProgress) {
          onProgress(completed, postIds.length);
        }
      }
    }

    // Sort successful results by original index to maintain order
    const successfulResults = completedResults
      .filter(result => result.success)
      .sort((a, b) => a.index - b.index);

    const orderedPosts = successfulResults.map(result => result.post);

    console.log(`[API] TRUE Progressive fetch with retries completed: ${orderedPosts.length}/${postIds.length} posts successful`);
    return orderedPosts;
  }

  async getPostsByIds(
    postIds: number[],
    expertId?: string,
    query?: string
  ): Promise<PostDetailResponse[]> {
    console.log('[API] Fetching posts by IDs:', postIds, 'for expert:', expertId, 'with query:', query);
    // Determine if translation is needed
    const needsTranslation = query ? isEnglishQuery(query) : false;
    const promises = postIds.map(id => this.getPostDetail(id, expertId, query, needsTranslation));

    // Fetch all posts in parallel
    const results = await Promise.allSettled(promises);

    // Log results for debugging
    const successful = results.filter(r => r.status === 'fulfilled').length;
    const failed = results.filter(r => r.status === 'rejected').length;
    console.log(`[API] Posts fetch results: ${successful} successful, ${failed} failed`);

    if (failed > 0) {
      const errors = results.filter(r => r.status === 'rejected');
      console.error('[API] Failed to fetch some posts:', errors);
    }

    // Filter out failed requests and return successful ones
    const posts = results
      .filter((result): result is PromiseFulfilledResult<PostDetailResponse> =>
        result.status === 'fulfilled'
      )
      .map(result => result.value);

    console.log('[API] Successfully fetched posts:', posts.length);
    return posts;
  }
}

// Export singleton instance for convenience
export const apiClient = new APIClient(import.meta.env.VITE_API_URL || 'http://localhost:8000');

// Export class for custom instances
export default APIClient;
