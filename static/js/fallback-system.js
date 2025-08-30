/**
 * CSS and JS Resource Fallback System
 * Implements CDN -> Local -> Base CSS architecture
 */
(function() {
    'use strict';

    const FALLBACK_CONFIG = {
        css: {
            tailwind: {
                cdn: 'https://cdn.tailwindcss.com',
                local: '/static/css/tailwind.css',
                fallback: 'inline' // Will use inline CSS if local fails
            },
            fontawesome: {
                cdn: 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
                local: '/static/css/fontawesome.css',
                fallback: 'emoji' // Will use emoji icons
            },
            googlefonts: {
                cdn: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap',
                local: '/static/fonts/inter.css',
                fallback: 'system' // Will use system fonts
            }
        },
        js: {
            tailwind: {
                cdn: 'https://cdn.tailwindcss.com',
                local: '/static/js/tailwind-fallback.js',
                fallback: 'none'
            },
            chartjs: {
                cdn: 'https://cdn.jsdelivr.net/npm/chart.js',
                local: '/static/js/chart.min.js',
                fallback: 'mock'
            }
        }
    };

    // Load CSS with fallback system
    function loadCSS(name, config) {
        return new Promise((resolve, reject) => {
            // Try CDN first
            const cdnLink = document.createElement('link');
            cdnLink.rel = 'stylesheet';
            cdnLink.href = config.cdn;
            
            const timeout = setTimeout(() => {
                console.warn(`CDN CSS timeout for ${name}, trying local fallback...`);
                loadLocalCSS(name, config).then(resolve).catch(reject);
            }, 3000);

            cdnLink.onload = () => {
                clearTimeout(timeout);
                console.log(`CDN CSS loaded successfully: ${name}`);
                resolve('cdn');
            };

            cdnLink.onerror = () => {
                clearTimeout(timeout);
                console.warn(`CDN CSS failed for ${name}, trying local fallback...`);
                loadLocalCSS(name, config).then(resolve).catch(reject);
            };

            document.head.appendChild(cdnLink);
        });
    }

    function loadLocalCSS(name, config) {
        return new Promise((resolve, reject) => {
            const localLink = document.createElement('link');
            localLink.rel = 'stylesheet';
            localLink.href = config.local;
            
            const timeout = setTimeout(() => {
                console.warn(`Local CSS timeout for ${name}, using base fallback...`);
                loadFallbackCSS(name, config).then(resolve).catch(reject);
            }, 2000);

            localLink.onload = () => {
                clearTimeout(timeout);
                console.log(`Local CSS loaded successfully: ${name}`);
                resolve('local');
            };

            localLink.onerror = () => {
                clearTimeout(timeout);
                console.warn(`Local CSS failed for ${name}, using base fallback...`);
                loadFallbackCSS(name, config).then(resolve).catch(reject);
            };

            document.head.appendChild(localLink);
        });
    }

    function loadFallbackCSS(name, config) {
        return new Promise((resolve) => {
            console.log(`Loading base CSS fallback for: ${name}`);
            
            if (config.fallback === 'inline' && name === 'tailwind') {
                // Add basic Tailwind-compatible CSS
                const style = document.createElement('style');
                style.textContent = `
                    /* Base Tailwind Fallback */
                    .flex { display: flex; }
                    .grid { display: grid; }
                    .hidden { display: none; }
                    .bg-white { background-color: #ffffff; }
                    .bg-blue-500 { background-color: #3b82f6; }
                    .bg-gray-100 { background-color: #f3f4f6; }
                    .text-white { color: #ffffff; }
                    .text-gray-800 { color: #1f2937; }
                    .p-4 { padding: 1rem; }
                    .m-4 { margin: 1rem; }
                    .rounded { border-radius: 0.25rem; }
                    .shadow { box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1); }
                    .cursor-pointer { cursor: pointer; }
                    .transition { transition: all 0.3s ease; }
                `;
                document.head.appendChild(style);
                resolve('fallback-inline');
            } else if (config.fallback === 'emoji' && name === 'fontawesome') {
                // FontAwesome emoji fallbacks already included in main CSS
                resolve('fallback-emoji');
            } else if (config.fallback === 'system' && name === 'googlefonts') {
                // Use system fonts
                const style = document.createElement('style');
                style.textContent = `
                    body, .font-inter {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    }
                `;
                document.head.appendChild(style);
                resolve('fallback-system');
            } else {
                resolve('fallback-none');
            }
        });
    }

    // Load JavaScript with fallback system
    function loadJS(name, config) {
        return new Promise((resolve, reject) => {
            // Try CDN first
            const cdnScript = document.createElement('script');
            cdnScript.src = config.cdn;
            
            const timeout = setTimeout(() => {
                console.warn(`CDN JS timeout for ${name}, trying local fallback...`);
                loadLocalJS(name, config).then(resolve).catch(reject);
            }, 3000);

            cdnScript.onload = () => {
                clearTimeout(timeout);
                console.log(`CDN JS loaded successfully: ${name}`);
                resolve('cdn');
            };

            cdnScript.onerror = () => {
                clearTimeout(timeout);
                console.warn(`CDN JS failed for ${name}, trying local fallback...`);
                loadLocalJS(name, config).then(resolve).catch(reject);
            };

            document.head.appendChild(cdnScript);
        });
    }

    function loadLocalJS(name, config) {
        return new Promise((resolve, reject) => {
            const localScript = document.createElement('script');
            localScript.src = config.local;
            
            const timeout = setTimeout(() => {
                console.warn(`Local JS timeout for ${name}, using base fallback...`);
                loadFallbackJS(name, config).then(resolve).catch(reject);
            }, 2000);

            localScript.onload = () => {
                clearTimeout(timeout);
                console.log(`Local JS loaded successfully: ${name}`);
                resolve('local');
            };

            localScript.onerror = () => {
                clearTimeout(timeout);
                console.warn(`Local JS failed for ${name}, using base fallback...`);
                loadFallbackJS(name, config).then(resolve).catch(reject);
            };

            document.head.appendChild(localScript);
        });
    }

    function loadFallbackJS(name, config) {
        return new Promise((resolve) => {
            console.log(`Loading base JS fallback for: ${name}`);
            
            if (config.fallback === 'mock' && name === 'chartjs') {
                // Create a mock Chart.js object
                window.Chart = window.Chart || {
                    register: () => {},
                    defaults: { global: {} },
                    Line: function() { return { update: () => {}, destroy: () => {} }; },
                    Bar: function() { return { update: () => {}, destroy: () => {} }; },
                    Doughnut: function() { return { update: () => {}, destroy: () => {} }; }
                };
                resolve('fallback-mock');
            } else {
                resolve('fallback-none');
            }
        });
    }

    // Initialize the fallback system
    async function initializeFallbackSystem() {
        console.log('Initializing CSS/JS Fallback System...');
        const results = {
            css: {},
            js: {}
        };

        // Load CSS resources
        for (const [name, config] of Object.entries(FALLBACK_CONFIG.css)) {
            try {
                results.css[name] = await loadCSS(name, config);
            } catch (error) {
                console.error(`Failed to load CSS for ${name}:`, error);
                results.css[name] = 'failed';
            }
        }

        // Load JS resources
        for (const [name, config] of Object.entries(FALLBACK_CONFIG.js)) {
            try {
                results.js[name] = await loadJS(name, config);
            } catch (error) {
                console.error(`Failed to load JS for ${name}:`, error);
                results.js[name] = 'failed';
            }
        }

        console.log('Fallback System Results:', results);
        
        // Store results globally for debugging
        window.fallbackResults = results;
        
        // Dispatch custom event to indicate resources are loaded
        document.dispatchEvent(new CustomEvent('fallbackSystemReady', { detail: results }));
    }

    // Start initialization when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeFallbackSystem);
    } else {
        initializeFallbackSystem();
    }

    // Export the system for manual control if needed
    window.FallbackSystem = {
        load: initializeFallbackSystem,
        config: FALLBACK_CONFIG,
        loadCSS: loadCSS,
        loadJS: loadJS
    };

})();