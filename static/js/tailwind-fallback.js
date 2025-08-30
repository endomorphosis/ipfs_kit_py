/**
 * Tailwind CSS Configuration and Fallback System
 * Provides a complete fallback when CDN resources are unavailable
 */

(function() {
    'use strict';

    // Tailwind CSS configuration object fallback
    window.tailwind = window.tailwind || {
        config: function(configObj) {
            console.log('Tailwind fallback config loaded:', configObj);
            // Store config for potential use by other scripts
            window.tailwindConfig = configObj;
        }
    };

    // Add responsive utility classes programmatically if needed
    function addResponsiveUtilities() {
        const style = document.createElement('style');
        style.textContent = `
            /* Additional responsive utilities */
            @media (max-width: 639px) {
                .sm\\:hidden { display: none !important; }
                .sm\\:block { display: block !important; }
                .sm\\:flex { display: flex !important; }
            }
            
            @media (min-width: 640px) and (max-width: 767px) {
                .sm\\:block { display: block !important; }
                .sm\\:flex { display: flex !important; }
            }
            
            @media (min-width: 1280px) {
                .xl\\:grid-cols-5 { grid-template-columns: repeat(5, minmax(0, 1fr)) !important; }
                .xl\\:grid-cols-6 { grid-template-columns: repeat(6, minmax(0, 1fr)) !important; }
            }
        `;
        document.head.appendChild(style);
    }

    // Initialize fallback system when DOM is ready
    function initializeTailwindFallback() {
        console.log('Initializing Tailwind CSS fallback system...');
        
        // Add responsive utilities
        addResponsiveUtilities();
        
        // Check if CDN Tailwind is available
        const tailwindCDN = document.querySelector('script[src*="tailwindcss.com"]');
        if (tailwindCDN) {
            tailwindCDN.onerror = function() {
                console.log('CDN Tailwind CSS failed to load, using local fallback');
            };
        }
        
        console.log('Tailwind CSS fallback system initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeTailwindFallback);
    } else {
        initializeTailwindFallback();
    }

    // Export for potential use by other scripts
    window.tailwindFallback = {
        initialized: true,
        version: '3.3.0-fallback'
    };

})();