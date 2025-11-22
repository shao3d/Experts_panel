/**
 * Debug Logger Utility for Frontend
 * Logs console messages, SSE events, and API requests to file via backend
 */

interface DebugEvent {
  timestamp: string;
  type: 'console' | 'sse' | 'api' | 'error' | 'warn';
  source: string;
  message: string;
  data?: any;
}

class DebugLogger {
  private logBuffer: DebugEvent[] = [];
  private maxBufferSize = 1000;

  constructor() {
    this.setupConsoleOverride();
    this.setupNetworkInterception();
  }

  private getLogEndpoint(): string {
    if (import.meta.env.PROD) {
      return '/api/v1/log-batch';
    }

    const base = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    return `${base}/api/v1/log-batch`;
  }

  // Override console methods to capture logs
  private setupConsoleOverride() {
    const originalLog = console.log;
    const originalWarn = console.warn;
    const originalError = console.error;

    console.log = (...args: any[]) => {
      originalLog.apply(console, args);
      // Only log if not already our debug prefix to avoid recursion
      const message = args.map(String).join(' ');
      if (!message.startsWith('[CONSOLE]') && !message.startsWith('[WARN]') && !message.startsWith('[ERROR]')) {
        this.logEvent('console', 'console.log', message, args);
      }
    };

    console.warn = (...args: any[]) => {
      originalWarn.apply(console, args);
      const message = args.map(String).join(' ');
      if (!message.startsWith('[CONSOLE]') && !message.startsWith('[WARN]') && !message.startsWith('[ERROR]')) {
        this.logEvent('warn', 'console.warn', message, args);
      }
    };

    console.error = (...args: any[]) => {
      originalError.apply(console, args);
      const message = args.map(String).join(' ');
      if (!message.startsWith('[CONSOLE]') && !message.startsWith('[WARN]') && !message.startsWith('[ERROR]')) {
        this.logEvent('error', 'console.error', message, args);
      }
    };
  }

  // Intercept fetch/XHR for API logging
  private setupNetworkInterception() {
    // Intercept fetch
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      const [url, options] = args;
      const startTime = Date.now();

      // Don't log logging requests to avoid loops
      if (String(url).includes('/api/v1/log-batch')) {
        return originalFetch(...args);
      }

      this.logEvent('api', 'fetch.request', `${options?.method || 'GET'} ${url}`);

      try {
        const response = await originalFetch(...args);
        const endTime = Date.now();
        const duration = endTime - startTime;

        this.logEvent('api', 'fetch.response', `${response.status} ${url}`, {
          status: response.status,
          statusText: response.statusText,
          duration,
        });

        return response;
      } catch (error) {
        this.logEvent('error', 'fetch.error', `Failed to fetch ${url}`, {
          error: (error as Error).message,
        });
        throw error;
      }
    };
  }

  // Log SSE events specifically
  logSSEEvent(phase: string, eventType: string, data: any, message?: string) {
    this.logEvent('sse', `sse.${phase}`, message || eventType, {
      phase,
      eventType,
      data,
      timestamp: new Date().toISOString()
    });
  }

  // Generic log event method
  private logEvent(type: DebugEvent['type'], source: string, message: string, data?: any) {
    const event: DebugEvent = {
      timestamp: new Date().toISOString(),
      type,
      source,
      message,
      data
    };

    this.logBuffer.push(event);

    // Keep buffer size manageable
    if (this.logBuffer.length > this.maxBufferSize) {
      this.logBuffer.shift();
    }
  }

  // Get recent logs for debugging
  getRecentLogs(count = 50): DebugEvent[] {
    return this.logBuffer.slice(-count);
  }

  // Send logs to backend for persistent storage
  async flushLogsToBackend() {
    if (this.logBuffer.length === 0) {
      return;
    }

    const logsToSend = [...this.logBuffer];
    this.logBuffer = []; // Clear buffer immediately

    try {
      const logEndpoint = this.getLogEndpoint();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (import.meta.env.VITE_ADMIN_SECRET) {
        headers['X-Admin-Secret'] = import.meta.env.VITE_ADMIN_SECRET;
      }

      await fetch(logEndpoint, {
        method: 'POST',
        headers,
        body: JSON.stringify(logsToSend),
      });
    } catch (error) {
      console.warn('[DebugLogger] Error sending logs to backend:', error);
      // If sending fails, put logs back into buffer to retry next time
      this.logBuffer.unshift(...logsToSend);
    }
  }
}

// Create global instance
export const debugLogger = new DebugLogger();

// Auto-send logs every 10 seconds
setInterval(() => {
  debugLogger.flushLogsToBackend();
}, 10000);

// Export SSE logging function for use in API client
export const logSSEEvent = (phase: string, eventType: string, data: any, message?: string) => {
  debugLogger.logSSEEvent(phase, eventType, data, message);
};
