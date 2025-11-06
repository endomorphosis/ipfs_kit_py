/**
 * JavaScript Error Handler for MCP Dashboard
 * 
 * This module provides functionality to capture JavaScript errors from the
 * MCP dashboard and report them to the backend for GitHub issue creation.
 */

class ErrorReporter {
    constructor(config = {}) {
        this.apiEndpoint = config.apiEndpoint || '/api/report-error';
        this.enabled = config.enabled !== false;
        this.maxReportsPerSession = config.maxReportsPerSession || 10;
        this.reportedErrors = new Set();
        this.reportsCount = 0;
        
        if (this.enabled) {
            this.install();
        }
    }
    
    /**
     * Install global error handlers
     */
    install() {
        // Handle uncaught exceptions
        window.addEventListener('error', (event) => {
            this.handleError({
                error_type: 'JavaScriptError',
                error_message: event.message,
                source_file: event.filename,
                line_number: event.lineno,
                column_number: event.colno,
                stack: event.error ? event.error.stack : null,
            });
        });
        
        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                error_type: 'UnhandledPromiseRejection',
                error_message: event.reason ? event.reason.toString() : 'Unknown promise rejection',
                stack: event.reason && event.reason.stack ? event.reason.stack : null,
            });
        });
        
        console.log('JavaScript error reporter installed');
    }
    
    /**
     * Generate a hash for an error to prevent duplicates
     */
    generateErrorHash(errorInfo) {
        const signature = `${errorInfo.error_type}:${errorInfo.error_message}:${errorInfo.source_file || ''}:${errorInfo.line_number || ''}`;
        return this.hashCode(signature);
    }
    
    """
    Simple hash code function
    """
    hashCode(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash | 0; // Convert to 32-bit integer
        }
        return hash.toString();
    }
    
    /**
     * Check if an error should be reported
     */
    shouldReportError(errorHash) {
        // Check if we've exceeded the session limit
        if (this.reportsCount >= this.maxReportsPerSession) {
            console.warn('Error reporting limit reached for this session');
            return false;
        }
        
        // Check if we've already reported this error
        if (this.reportedErrors.has(errorHash)) {
            console.debug('Error already reported in this session');
            return false;
        }
        
        return true;
    }
    
    /**
     * Handle an error by reporting it to the backend
     */
    handleError(errorInfo) {
        if (!this.enabled) {
            return;
        }
        
        // Add timestamp and environment info
        errorInfo.timestamp = new Date().toISOString();
        errorInfo.user_agent = navigator.userAgent;
        errorInfo.url = window.location.href;
        errorInfo.environment = {
            component: 'MCP Dashboard (JavaScript)',
            platform: navigator.platform,
        };
        
        // Generate error hash
        const errorHash = this.generateErrorHash(errorInfo);
        
        // Check if we should report this error
        if (!this.shouldReportError(errorHash)) {
            return;
        }
        
        // Report the error to the backend
        this.reportToBackend(errorInfo)
            .then(() => {
                this.reportedErrors.add(errorHash);
                this.reportsCount++;
                console.log('Error reported successfully');
            })
            .catch((err) => {
                console.error('Failed to report error:', err);
            });
    }
    
    /**
     * Report error to the backend API
     */
    async reportToBackend(errorInfo) {
        try {
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    error_info: errorInfo,
                    context: 'MCP Dashboard',
                }),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Error reporting to backend:', error);
            throw error;
        }
    }
    
    /**
     * Manually report an error
     */
    reportError(error, context = null) {
        const errorInfo = {
            error_type: error.name || 'Error',
            error_message: error.message || error.toString(),
            stack: error.stack || null,
        };
        
        if (context) {
            errorInfo.context = context;
        }
        
        this.handleError(errorInfo);
    }
}

// Initialize error reporter when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Check if error reporting is enabled (can be configured via meta tag)
    const metaTag = document.querySelector('meta[name="error-reporting"]');
    const enabled = metaTag ? metaTag.content !== 'false' : true;
    
    // Initialize global error reporter
    window.errorReporter = new ErrorReporter({
        enabled: enabled,
        apiEndpoint: '/api/report-error',
        maxReportsPerSession: 10,
    });
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorReporter;
}
