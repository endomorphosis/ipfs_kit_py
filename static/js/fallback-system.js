/**
 * CSS and JS Resource Fallback System
 * Implements CDN -> Local -> Base CSS architecture
 */
(function() {
    'use strict';

    const FALLBACK_CONFIG = {
        css: {
            fontawesome: {
                cdn: 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
                local: null, // No local file - use emoji fallback
                fallback: 'emoji' // Will use emoji icons
            },
            googlefonts: {
                cdn: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap',
                local: null, // No local font file - use system fonts
                fallback: 'system' // Will use system fonts
            }
        },
        js: {
            // Tailwind CSS is now built and loaded as CSS only - no JS needed
            chartjs: {
                cdn: 'https://cdn.jsdelivr.net/npm/chart.js',
                local: null, // No local file - will use mock fallback
                fallback: 'mock'
            }
        }
    };

    // Load CSS with fallback system. Prefer local built assets in production (avoid loading external CDN).
    function loadCSS(name, config) {
        return new Promise((resolve, reject) => {
            // If no local file and fallback is specified, use fallback directly
            if (config && !config.local && config.fallback) {
                loadFallbackCSS(name, config).then(resolve).catch(reject);
                return;
            }

            // If a local asset is provided, try it first to avoid external network calls.
            if (config && config.local) {
                loadLocalCSS(name, config).then(resolve).catch(() => {
                    // If local fails, fall back to CDN only if explicitly configured
                    if (config.cdn) {
                        tryLoadCdnCSS(name, config).then(resolve).catch(reject);
                    } else {
                        loadFallbackCSS(name, config).then(resolve).catch(reject);
                    }
                });
                return;
            }

            // Otherwise, attempt CDN (legacy behavior)
            if (config.cdn) {
                tryLoadCdnCSS(name, config).then(resolve).catch(reject);
            } else {
                reject(new Error('No source available'));
            }
        });
    }

    function tryLoadCdnCSS(name, config) {
        return new Promise((resolve, reject) => {
            const cdnLink = document.createElement('link');
            cdnLink.rel = 'stylesheet';
            cdnLink.href = config.cdn;

            const timeout = setTimeout(() => {
                console.warn(`CDN CSS timeout for ${name}, trying local fallback...`);
                if (config && config.local) {
                    loadLocalCSS(name, config).then(resolve).catch(reject);
                } else {
                    loadFallbackCSS(name, config).then(resolve).catch(reject);
                }
            }, 3000);

            cdnLink.onload = () => {
                clearTimeout(timeout);
                console.log(`CDN CSS loaded successfully: ${name}`);
                resolve('cdn');
            };

            cdnLink.onerror = () => {
                clearTimeout(timeout);
                console.warn(`CDN CSS failed for ${name}, trying local fallback...`);
                if (config && config.local) {
                    loadLocalCSS(name, config).then(resolve).catch(reject);
                } else {
                    loadFallbackCSS(name, config).then(resolve).catch(reject);
                }
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
            
            if (config.fallback === 'emoji' && name === 'fontawesome') {
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

    // Load JavaScript with fallback system. Prefer local built assets to avoid CDN in production.
    function loadJS(name, config) {
        return new Promise((resolve, reject) => {
            // If no local file and fallback is specified, use fallback directly
            if (config && !config.local && config.fallback) {
                loadFallbackJS(name, config).then(resolve).catch(reject);
                return;
            }

            // If a local asset is provided, try it first
            if (config && config.local) {
                loadLocalJS(name, config).then(resolve).catch(() => {
                    // If local fails, try CDN if configured
                    if (config.cdn) {
                        tryLoadCdnJS(name, config).then(resolve).catch(reject);
                    } else {
                        loadFallbackJS(name, config).then(resolve).catch(reject);
                    }
                });
                return;
            }

            // Legacy: try CDN
            if (config.cdn) {
                tryLoadCdnJS(name, config).then(resolve).catch(reject);
            } else {
                reject(new Error('No source available'));
            }
        });
    }

    function tryLoadCdnJS(name, config) {
        return new Promise((resolve, reject) => {
            const cdnScript = document.createElement('script');
            cdnScript.src = config.cdn;

            const timeout = setTimeout(() => {
                console.warn(`CDN JS timeout for ${name}, trying local fallback...`);
                if (config && config.local) {
                    loadLocalJS(name, config).then(resolve).catch(reject);
                } else {
                    loadFallbackJS(name, config).then(resolve).catch(reject);
                }
            }, 3000);

            cdnScript.onload = () => {
                clearTimeout(timeout);
                console.log(`CDN JS loaded successfully: ${name}`);
                resolve('cdn');
            };

            cdnScript.onerror = () => {
                clearTimeout(timeout);
                console.warn(`CDN JS failed for ${name}, trying local fallback...`);
                if (config && config.local) {
                    loadLocalJS(name, config).then(resolve).catch(reject);
                } else {
                    loadFallbackJS(name, config).then(resolve).catch(reject);
                }
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
                // Provide a minimal constructor-compatible mock for Chart.js (new Chart(ctx, cfg))
                const MockChart = function() { return undefined; };
                MockChart.prototype.update = function() {};
                MockChart.prototype.destroy = function() {};
                // Ensure callable as constructor
                function ChartCtor() {
                    return new MockChart();
                }
                // Attach minimal API surface used by our code
                ChartCtor.register = function() {};
                ChartCtor.defaults = { global: {} };
                // Legacy helpers (unused by our code, but harmless)
                ChartCtor.Line = function() { return { update: function(){}, destroy: function(){} }; };
                ChartCtor.Bar = function() { return { update: function(){}, destroy: function(){} }; };
                ChartCtor.Doughnut = function() { return { update: function(){}, destroy: function(){} }; };
                window.Chart = window.Chart || ChartCtor;
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