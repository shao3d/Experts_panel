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
  APIError,
  ConfidenceLevel
} from '../types/api';

/**
 * Callback type for progress events during query processing
 */
export type ProgressCallback = (event: ProgressEvent) => void;

/**
 * API client for Experts Panel backend
 */
export class APIClient {
  private baseURL: string;

  constructor(baseURL: string = 'http://localhost:8000') {
    this.baseURL = baseURL;
  }

  /**
   * Health check endpoint
   *
   * @returns Health status of the backend
   */
  async checkHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseURL}/health`);

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
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
      const response = await fetch(`${this.baseURL}/api/v1/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
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
      // No experts responded, create empty response
      return {
        query: multiResponse.query || '',
        answer: '',
        main_sources: [],
        confidence: ConfidenceLevel.LOW,
        language: 'ru',
        has_expert_comments: false,
        posts_analyzed: 0,
        expert_comments_included: 0,
        relevance_distribution: {},
        processing_time_ms: multiResponse.total_processing_time_ms || 0,
        request_id: multiResponse.request_id || '',
        expert_responses: multiResponse.expert_responses || []
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
      expert_responses: multiResponse.expert_responses || []
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
              if (onProgress) onProgress(event);
              if (event.event_type === 'complete' && event.data?.response) {
                const rawResponse = event.data.response as any;
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

            // Debug logging
            console.log('[SSE] Event received:', {
              type: event.event_type,
              phase: event.phase,
              status: event.status,
              hasData: !!event.data,
              hasResponse: event.data?.response !== undefined
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
   * Get detailed information about a specific post
   *
   * @param postId - Post ID to fetch
   * @param expertId - Optional expert ID to filter posts (required for multi-expert)
   * @returns Post details with comments and links
   */
  async getPostDetail(postId: number, expertId?: string): Promise<any> {
    const url = expertId
      ? `${this.baseURL}/api/v1/posts/${postId}?expert_id=${encodeURIComponent(expertId)}`
      : `${this.baseURL}/api/v1/posts/${postId}`;
    const response = await fetch(url);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Post with ID ${postId} not found`);
      }
      const error: APIError = await response.json();
      throw new Error(error.message || 'Failed to fetch post details');
    }

    return response.json();
  }

  /**
   * Fetch multiple posts by their IDs
   *
   * @param postIds - Array of post IDs
   * @param expertId - Optional expert ID to filter posts (required for multi-expert)
   * @returns Array of post details
   */
  async getPostsByIds(postIds: number[], expertId?: string): Promise<PostDetailResponse[]> {
    console.log('[API] Fetching posts by IDs:', postIds, 'for expert:', expertId);
    const promises = postIds.map(id => this.getPostDetail(id, expertId));

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
export const apiClient = new APIClient();

// Export class for custom instances
export default APIClient;
