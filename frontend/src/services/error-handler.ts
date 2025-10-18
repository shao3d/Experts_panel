import toast from 'react-hot-toast';

export enum ErrorType {
  NETWORK = 'NETWORK',
  TIMEOUT = 'TIMEOUT',
  SERVER = 'SERVER',
  VALIDATION = 'VALIDATION',
  UNKNOWN = 'UNKNOWN'
}

export interface ErrorDetails {
  type: ErrorType;
  message: string;
  statusCode?: number;
  retry?: () => void;
}

class ErrorHandler {
  private static instance: ErrorHandler;

  private constructor() {}

  static getInstance(): ErrorHandler {
    if (!ErrorHandler.instance) {
      ErrorHandler.instance = new ErrorHandler();
    }
    return ErrorHandler.instance;
  }

  /**
   * Parse error and return user-friendly message
   */
  parseError(error: any): ErrorDetails {
    // Network errors
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      return {
        type: ErrorType.NETWORK,
        message: 'Unable to connect to server. Please check your internet connection.'
      };
    }

    // Timeout errors
    if (error.name === 'AbortError' || error.message?.includes('timeout')) {
      return {
        type: ErrorType.TIMEOUT,
        message: 'Request took too long. The server might be busy.'
      };
    }

    // API errors with status codes
    if (error.status || error.statusCode) {
      const statusCode = error.status || error.statusCode;
      return {
        type: ErrorType.SERVER,
        statusCode,
        message: this.getMessageForStatusCode(statusCode, error.message)
      };
    }

    // Validation errors
    if (error.message?.includes('validation') || error.message?.includes('invalid')) {
      return {
        type: ErrorType.VALIDATION,
        message: error.message
      };
    }

    // Default unknown error
    return {
      type: ErrorType.UNKNOWN,
      message: error.message || 'An unexpected error occurred'
    };
  }

  /**
   * Get user-friendly message for HTTP status codes
   */
  private getMessageForStatusCode(code: number, defaultMessage?: string): string {
    const messages: Record<number, string> = {
      400: 'Invalid request. Please check your input.',
      401: 'Authentication required. Please log in.',
      403: 'You don\'t have permission to perform this action.',
      404: 'The requested resource was not found.',
      408: 'Request timeout. Please try again.',
      429: 'Too many requests. Please wait a moment.',
      500: 'Server error. Our team has been notified.',
      502: 'Service temporarily unavailable.',
      503: 'Service under maintenance. Please try again later.',
      504: 'Gateway timeout. The server took too long to respond.'
    };

    return messages[code] || defaultMessage || `Server error (${code})`;
  }

  /**
   * Show error toast notification
   */
  showError(error: any, options?: { duration?: number; retry?: () => void }) {
    const errorDetails = this.parseError(error);

    toast.error(errorDetails.message, {
      duration: options?.duration || 5000,
      position: 'top-right',
      style: {
        background: '#ff6b6b',
        color: 'white',
      },
      iconTheme: {
        primary: 'white',
        secondary: '#ff6b6b',
      }
    });

    // Log error for debugging
    console.error('Error occurred:', error);
  }

  /**
   * Show success toast notification
   */
  showSuccess(message: string, duration: number = 3000) {
    toast.success(message, {
      duration,
      position: 'top-right',
      style: {
        background: '#51cf66',
        color: 'white',
      },
      iconTheme: {
        primary: 'white',
        secondary: '#51cf66',
      }
    });
  }

  /**
   * Show loading toast with promise
   */
  showLoading<T>(
    promise: Promise<T>,
    messages: {
      loading: string;
      success: string | ((data: T) => string);
      error: string | ((err: any) => string);
    }
  ) {
    return toast.promise(
      promise,
      {
        loading: messages.loading,
        success: messages.success,
        error: messages.error,
      },
      {
        position: 'top-right',
      }
    );
  }
}

export const errorHandler = ErrorHandler.getInstance();