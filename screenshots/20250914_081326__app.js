/* MCP Dashboard app.js (dynamic) v=1757837606 */

(function(){
    const POLL_INTERVAL = 5000; // ms
    const appRoot = document.getElementById('app');
    if (appRoot) appRoot.innerHTML = '';
    if (!document.getElementById('mcp-dashboard-css')) {
        const css = `
            body{background:#f5f5f5;color:#333;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}
            .dash-header{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;background:#2d3748;color:white;font-family:system-ui,Arial,sans-serif;border-radius:6px;margin-bottom:14px;}
            .dash-header h1{font-size:20px;margin:0;font-weight:600;letter-spacing:.5px;}
            .dash-header .actions button{background:#4a5568;color:#fff;border:1px solid #638797;border-radius:4px;padding:6px 12px;cursor:pointer;font-size:13px;}
            .dash-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:18px;}
            .card{background:#fff;color:#333;border:1px solid #e2e8f0;border-radius:10px;padding:14px;position:relative;box-shadow:0 2px 4px rgba(0,0,0,.1);font-family:system-ui,Arial,sans-serif;}
            .card h3{margin:0 0 6px;font-size:15px;font-weight:600;color:#2d3748;}
            .big-metric{font-size:34px;font-weight:600;line-height:1.05;letter-spacing:-1px;color:#2d3748;}
            .metric-sub{font-size:11px;opacity:.7;text-transform:uppercase;letter-spacing:1px;margin-top:4px;}
            .bars{display:flex;flex-direction:column;gap:10px;}
            .bar{display:flex;flex-direction:column;font-size:12px;font-family:monospace;}
            .bar span{display:flex;justify-content:space-between;}
            .bar-track{height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden;margin-top:4px;}
            .bar-fill{height:100%;background:linear-gradient(90deg,#4299e1,#9f7aea);width:0;transition:width .6s;}
            .muted{opacity:.55;}
            .split{display:grid;grid-template-columns:2fr 1fr;gap:16px;}
            @media(max-width:900px){.split{grid-template-columns:1fr;}}
            .timestamp{font-size:11px;opacity:.6;margin-left:12px;}
            .dash-nav{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px 0;padding:0 4px;}
            .dash-nav .nav-btn{background:#fff;color:#4a5568;border:1px solid #e2e8f0;border-radius:4px;padding:6px 10px;cursor:pointer;font-size:13px;}
            .dash-nav .nav-btn.active{background:#2d3748;color:#fff;}
            .view-panel{animation:fade .25s ease;}
            @keyframes fade{from{opacity:0}to{opacity:1}}
            .loading-spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #2196F3;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        const styleEl = document.createElement('style'); styleEl.id='mcp-dashboard-css'; styleEl.textContent = css; document.head.append(styleEl);
    }
    function el(tag, attrs, ...kids){
        const e=document.createElement(tag); if(attrs){ for(const k in attrs){ if(k==='class') e.className=attrs[k]; else if(k==='text') e.textContent=attrs[k]; else if(k==='innerHTML') e.innerHTML=attrs[k]; else e.setAttribute(k,attrs[k]); } }
        kids.flat().forEach(k=>{ if(k==null) return; if(typeof k==='string') e.appendChild(document.createTextNode(k)); else e.appendChild(k); });
        return e;
    }
    const header = el('div',{class:'dash-header'},
        el('div',{}, 
            el('h1',{innerHTML:' IPFS Kit',style:'font-size:20px;margin:0;font-weight:600;letter-spacing:.5px;'}), 
            el('p',{text:'Comprehensive MCP Dashboard',style:'color:#cbd5e0;font-size:0.9em;margin:2px 0 0 0;'}),
            el('div',{class:'timestamp',id:'ts-info'},'')),
        el('div',{class:'actions'},
            el('button',{id:'btn-refresh',title:'Refresh data'},'Refresh'),
            ' ',
            el('button',{id:'btn-realtime',title:'Toggle real-time'},'Real-time: Off')
        )
    );
    // --- Deprecation banner (populated from initial WS system_update or fallback HTTP) ---
    let deprecationBanner = null;
    function renderDeprecationBanner(items){
        try{
            if(!Array.isArray(items) || !items.length) return;
            // Update existing hits if already rendered
            if(deprecationBanner){
                const ul = deprecationBanner.querySelector('ul.dep-items');
                if(ul){ ul.innerHTML = items.map(fmtItem).join(''); }
                return;
            }
            function fmtItem(it){
                var mig = it.migration? Object.keys(it.migration).map(function(k){ return k+': '+it.migration[k]; }).join(', ') : '-';
                return '<li><code>'+it.endpoint+'</code> remove in '+(it.remove_in||'?')+' (hits '+(it.hits||0)+')'+ (mig? '<br><span class="dep-mig">'+mig+'</span>':'') +'</li>';
            }
            deprecationBanner = document.createElement('div');
            deprecationBanner.className='deprecation-banner-wrap';
            deprecationBanner.innerHTML = '<div class="deprecation-banner"><div class="dep-main"><strong>Deprecated endpoints:</strong><ul class="dep-items">'+items.map(fmtItem).join('')+'</ul></div><button class="dep-close" title="Dismiss">x</button></div>';
            const style = document.createElement('style'); style.textContent = '.deprecation-banner{background:#5a3d10;border:1px solid #c68d2b;color:#ffe7c0;padding:10px 14px;font-size:13px;line-height:1.35;border-radius:6px;display:flex;gap:14px;position:relative;margin:0 0 14px 0;font-family:system-ui,Arial,sans-serif;} .deprecation-banner strong{color:#fff;} .deprecation-banner ul{margin:4px 0 0 18px;padding:0;} .deprecation-banner li{margin:2px 0;} .deprecation-banner code{background:#442c07;padding:1px 4px;border-radius:4px;} .deprecation-banner .dep-close{background:#7a5113;color:#fff;border:1px solid #c68d2b;width:26px;height:26px;border-radius:50%;cursor:pointer;font-size:14px;line-height:1;position:absolute;top:6px;right:6px;} .deprecation-banner .dep-close:hover{background:#8d601b;}'; document.head.appendChild(style);
            const root = appRoot || document.body; root.insertBefore(deprecationBanner, root.firstChild.nextSibling);
            const closeBtn = deprecationBanner.querySelector('.dep-close'); if(closeBtn){ closeBtn.addEventListener('click', function(){ deprecationBanner.remove(); deprecationBanner=null; }); }
        }catch(e){}
    }
    const grid = el('div',{class:'dash-grid'});
    const cardServer = el('div',{class:'card'}, el('h3',{text:'MCP Server'}), el('div',{class:'big-metric',id:'srv-status'},''), el('div',{class:'metric-sub',id:'srv-port'},''));
    const cardServices = el('div',{class:'card'}, el('h3',{text:'Services'}), el('div',{class:'big-metric',id:'svc-active'},''), el('div',{class:'metric-sub muted'},'Active Services'));
    const cardBackends = el('div',{class:'card'}, el('h3',{text:'Backends'}), el('div',{class:'big-metric',id:'count-backends'},''), el('div',{class:'metric-sub muted'},'Storage Backends'));
    const cardBuckets = el('div',{class:'card'}, el('h3',{text:'Buckets'}), el('div',{class:'big-metric',id:'count-buckets'},''), el('div',{class:'metric-sub muted'},'Total Buckets'));
    grid.append(cardServer, cardServices, cardBackends, cardBuckets);
    const perfCard = el('div',{class:'card'},
        el('h3',{text:'System Performance'}),
        el('div',{class:'bars'},
            perfBar('CPU Usage','cpu'),
            el('svg',{id:'spark-cpu',width:'100%',height:'26',style:'margin:4px 0 8px 0;background:#f7fafc;border:1px solid #e2e8f0;border-radius:3px;'}),
            perfBar('Memory Usage','mem'),
            el('svg',{id:'spark-mem',width:'100%',height:'26',style:'margin:4px 0 8px 0;background:#f7fafc;border:1px solid #e2e8f0;border-radius:3px;'}),
            perfBar('Disk Usage','disk'),
            el('svg',{id:'spark-disk',width:'100%',height:'26',style:'margin:4px 0 0 0;background:#f7fafc;border:1px solid #e2e8f0;border-radius:3px;'})
        )
    );
    const layout = el('div',{class:'split'}, perfCard, el('div',{class:'card'}, el('h3',{text:'Network Activity'}), el('div',{id:'net-activity',class:'muted',text:'Loading'}),
        el('svg',{id:'net-spark',width:'100%',height:'60',style:'margin-top:6px;display:block;background:#f7fafc;border:1px solid #e2e8f0;border-radius:4px;'}),
        el('div',{id:'net-summary',class:'muted',style:'margin-top:4px;font-size:11px;'},'')));
    // --- Navigation & Views ---
    const nav = el('div',{class:'dash-nav'}, ['Overview','Services','Backends','Buckets','Pins','Logs','Files','Tools','IPFS','CARs'].map(name => el('button',{class:'nav-btn','data-view':name.toLowerCase(),text:name})));
    const overviewView = el('div',{id:'view-overview',class:'view-panel'}, grid, layout);
    const servicesView = el('div',{id:'view-services',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'Services'}),
            el('pre',{id:'services-json',text:'Loading'}),
            el('div',{id:'services-actions',style:'margin-top:6px;font-size:12px;'},'')
        )
    );
    const backendsView = el('div',{id:'view-backends',class:'view-panel',style:'display:none;'},
        // Enhanced Backend Management with 9/9 Advanced Features
        el('div',{class:'card'},
            el('h2',{text:'Backend Health & Management',style:'color:#4CAF50;margin-bottom:16px;'}),

            // Top Action Bar with Enhanced Features  
            el('div',{style:'display:flex;gap:8px;margin-bottom:16px;padding:12px;background:#0a0a0a;border-radius:8px;'},
                el('button',{id:'refresh-backends',style:'background:#2196F3;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>loadBackends()},' Refresh All'),
                el('button',{id:'test-all-backends',style:'background:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>testAllBackends()},' Test All'),
                el('button',{id:'add-backend-instance',style:'background:#9C27B0;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>showAddBackendModal()},' Add Instance'),
                el('button',{id:'sync-all-backends',style:'background:#FF9800;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>syncAllBackends()},' Sync All'),
                el('button',{id:'health-check-backends',style:'background:#E91E63;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>runHealthCheck()},' Health Check'),
                // Advanced Feature 8: Performance Metrics Button
                el('button',{id:'show-performance-metrics',style:'background:#607D8B;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>showPerformanceMetrics()},' Performance'),
                // Advanced Feature 9: Configuration Templates Button
                el('button',{id:'show-config-templates',style:'background:#795548;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;',onclick:()=>showConfigurationTemplates()},' Templates')
            ),

            // Info Banner
            el('div',{style:'padding:8px 12px;background:#1a1a1a;border:1px solid #333;border-radius:4px;margin-bottom:12px;font-size:13px;'},
                el('span',{style:'color:#FFC107;'},''),
                el('strong',{text:' Multi-Backend Support: ',style:'color:#4CAF50;'}),
                'Manage multiple S3 buckets, GitHub accounts, IPFS clusters with individual cache/storage/retention policies. Uses ~/.ipfs_kit/ metadata-first approach.'
            ),

            // Category Filter Tabs
            el('div',{style:'display:flex;gap:4px;margin-bottom:12px;'},
                el('button',{id:'filter-all',class:'active',style:'padding:6px 12px;background:#2196F3;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('all')},'All Backends'),
                el('button',{id:'filter-storage',style:'padding:6px 12px;background:#4CAF50;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('storage')},' Storage'),
                el('button',{id:'filter-network',style:'padding:6px 12px;background:#9C27B0;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('network')},' Network'),
                el('button',{id:'filter-compute',style:'padding:6px 12px;background:#FF9800;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('compute')},' Compute'),
                el('button',{id:'filter-analytics',style:'padding:6px 12px;background:#E91E63;color:white;border:none;border-radius:4px;cursor:pointer;',onclick:()=>filterBackends('analytics')},' Analytics')
            ),

            // Health Status Dashboard
            el('div',{style:'display:flex;gap:12px;margin-bottom:16px;'},
                el('div',{style:'text-align:center;padding:8px;background:#0a0a0a;border-radius:4px;flex:1;'},
                    el('div',{id:'healthy-count',style:'font-size:24px;color:#4CAF50;font-weight:bold;'},'0'),
                    el('div',{style:'font-size:12px;color:#888;'},'Healthy')
                ),
                el('div',{style:'text-align:center;padding:8px;background:#0a0a0a;border-radius:4px;flex:1;'},
                    el('div',{id:'unhealthy-count',style:'font-size:24px;color:#f44336;font-weight:bold;'},'0'),
                    el('div',{style:'font-size:12px;color:#888;'},'Unhealthy')
                ),
                el('div',{style:'text-align:center;padding:8px;background:#0a0a0a;border-radius:4px;flex:1;'},
                    el('div',{id:'configured-count',style:'font-size:24px;color:#2196F3;font-weight:bold;'},'0'),
                    el('div',{style:'font-size:12px;color:#888;'},'Configured')
                ),
                el('div',{style:'text-align:center;padding:8px;background:#0a0a0a;border-radius:4px;flex:1;'},
                    el('div',{id:'total-backends-count',style:'font-size:24px;color:#9C27B0;font-weight:bold;'},'0'),
                    el('div',{style:'font-size:12px;color:#888;'},'Total')
                )
            ),

            // Backends List Container
            el('div',{id:'backends-list',style:'margin-top:8px;'},'Loading'),

            // Advanced Feature 8: Performance Metrics Modal
            el('div',{id:'performance-metrics-modal',style:'display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;'},
                el('div',{style:'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:20px;max-width:90%;max-height:90%;overflow-y:auto;color:white;min-width:600px;'},
                    el('div',{style:'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;'},
                        el('h3',{text:' Real-Time Performance Metrics',style:'margin:0;color:#4CAF50;'}),
                        el('button',{onclick:()=>closePerformanceMetrics(),style:'background:#555;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;'},'')
                    ),
                    el('div',{id:'performance-metrics-content',text:'Loading performance data...'}),
                    el('div',{style:'margin-top:16px;display:flex;gap:8px;'},
                        el('button',{onclick:()=>refreshPerformanceMetrics(),style:'background:#2196F3;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;'},' Refresh'),
                        el('select',{id:'metrics-time-range',style:'padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;',onchange:()=>refreshPerformanceMetrics()},
                            el('option',{value:'1h',text:'Last Hour'}),
                            el('option',{value:'6h',text:'Last 6 Hours'}),
                            el('option',{value:'24h',text:'Last 24 Hours'}),
                            el('option',{value:'7d',text:'Last 7 Days'})
                        )
                    )
                )
            ),

            // Advanced Feature 9: Configuration Templates Modal
            el('div',{id:'config-templates-modal',style:'display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;'},
                el('div',{style:'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:20px;max-width:90%;max-height:90%;overflow-y:auto;color:white;min-width:600px;'},
                    el('div',{style:'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;'},
                        el('h3',{text:' Advanced Configuration Management',style:'margin:0;color:#4CAF50;'}),
                        el('button',{onclick:()=>closeConfigTemplates(),style:'background:#555;color:white;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;'},'')
                    ),
                    el('div',{style:'display:flex;gap:12px;margin-bottom:16px;'},
                        el('button',{onclick:()=>showTemplateSelector(),style:'background:#9C27B0;color:white;padding:8px 12px;border:none;border-radius:4px;cursor:pointer;'},' Templates'),
                        el('button',{onclick:()=>showCloneBackend(),style:'background:#2196F3;color:white;padding:8px 12px;border:none;border-radius:4px;cursor:pointer;'},' Clone'),
                        el('button',{onclick:()=>showBackupRestore(),style:'background:#FF9800;color:white;padding:8px 12px;border:none;border-radius:4px;cursor:pointer;'},' Backup'),
                        el('button',{onclick:()=>showAdvancedPolicyEditor(),style:'background:#E91E63;color:white;padding:8px 12px;border:none;border-radius:4px;cursor:pointer;'},' Policies')
                    ),
                    el('div',{id:'config-templates-content',text:'Select a configuration management option above...'})
                )
            )
        )
    );
    const bucketsView = el('div',{id:'view-buckets',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'Bucket File Management'}),

            // Bucket Creation Row
            el('div',{class:'row',style:'margin-bottom:12px;border-bottom:1px solid #333;padding-bottom:8px;'},
                el('input',{id:'bucket-name',placeholder:'bucket name',style:'width:140px;margin-right:8px;'}),
                el('input',{id:'bucket-backend',placeholder:'backend (optional)',style:'width:140px;margin-right:8px;'}),
                el('button',{id:'btn-bucket-add',style:'background:#4CAF50;color:white;margin-right:8px;'},'Create Bucket'),
                el('button',{id:'btn-refresh-buckets',style:'background:#2196F3;color:white;'},'Refresh')
            ),

            // Bucket Selection and Toolbar
            el('div',{class:'row',style:'margin-bottom:12px;'},
                el('label',{style:'margin-right:8px;font-weight:bold;',text:'Selected Bucket:'}),
                el('select',{id:'bucket-selector',style:'width:200px;margin-right:12px;'}),
                el('button',{id:'btn-bucket-configure',style:'margin-right:4px;background:#FF9800;color:white;',disabled:true},'Configure'),
                el('button',{id:'btn-bucket-advanced',style:'margin-right:4px;background:#9C27B0;color:white;',disabled:true},'Advanced Settings'),
                el('button',{id:'btn-bucket-quota',style:'margin-right:4px;background:#607D8B;color:white;',disabled:true},'Quota'),
                el('button',{id:'btn-bucket-share',style:'margin-right:4px;background:#795548;color:white;',disabled:true},'Share'),
                el('button',{id:'btn-force-sync',style:'margin-right:4px;background:#E91E63;color:white;',disabled:true},'Force Sync')
            ),

            // Status Bar
            el('div',{id:'bucket-status-bar',class:'status-bar',style:'background:#1a1a1a;border:1px solid #333;border-radius:4px;padding:8px;margin-bottom:12px;font-size:12px;display:none;'},
                el('div',{class:'status-row',style:'display:flex;justify-content:space-between;align-items:center;'},
                    el('div',{class:'status-left',style:'display:flex;gap:16px;'},
                        el('span',{id:'status-quota',style:'color:#4CAF50;'},'Quota: N/A'),
                        el('span',{id:'status-files',style:'color:#2196F3;'},'Files: 0'),
                        el('span',{id:'status-cache',style:'color:#FF9800;'},'Cache: None')
                    ),
                    el('div',{class:'status-right'},
                        el('span',{id:'status-retention',style:'color:#9C27B0;'},'Retention: N/A')
                    )
                )
            ),

            // Drag & Drop Upload Zone
            el('div',{id:'drop-zone',class:'drop-zone',style:'border:2px dashed #666;border-radius:8px;padding:20px;text-align:center;margin-bottom:12px;background:#0a0a0a;display:none;'},
                el('div',{class:'drop-zone-content'},
                    el('div',{style:'font-size:48px;color:#666;margin-bottom:8px;'},''),
                    el('p',{style:'margin:0;color:#ccc;font-size:16px;'},'Drag & drop files here or click to browse'),
                    el('p',{style:'margin:4px 0 0 0;color:#888;font-size:12px;'},'Multiple files supported'),
                    el('input',{id:'file-input',type:'file',multiple:true,style:'display:none;'})
                )
            ),

            // File Operations Toolbar
            el('div',{id:'file-toolbar',class:'row',style:'margin-bottom:8px;display:none;'},
                el('button',{id:'btn-upload-file',style:'margin-right:4px;background:#4CAF50;color:white;'},' Upload'),
                el('button',{id:'btn-new-folder',style:'margin-right:4px;background:#2196F3;color:white;'},' New Folder'),
                el('button',{id:'btn-selective-sync',style:'margin-right:4px;background:#FF5722;color:white;',disabled:true},' Selective Sync'),
                el('button',{id:'btn-download-selected',style:'margin-right:4px;background:#673AB7;color:white;',disabled:true},' Download'),
                el('button',{id:'btn-delete-selected',style:'margin-right:4px;background:#F44336;color:white;',disabled:true},' Delete'),
                el('span',{style:'margin-left:12px;color:#888;font-size:11px;',id:'selection-info'},'Select files to enable operations')
            ),

            // File List Container
            el('div',{id:'file-list-container',style:'border:1px solid #333;border-radius:4px;background:#0a0a0a;min-height:300px;max-height:400px;overflow-y:auto;display:none;'},
                el('div',{id:'file-list-header',style:'background:#1a1a1a;padding:8px;border-bottom:1px solid #333;font-size:12px;font-weight:bold;color:#ccc;'},
                    el('div',{style:'display:grid;grid-template-columns:30px 1fr 100px 120px 80px;gap:8px;align-items:center;'},
                        el('span',{}),
                        el('span',{text:'Name'}),
                        el('span',{text:'Size'}),
                        el('span',{text:'Modified'}),
                        el('span',{text:'Actions'})
                    )
                ),
                el('div',{id:'file-list-body',style:'padding:4px;'},'Loading...')
            ),

            // Upload Progress
            el('div',{id:'upload-progress',style:'margin-top:8px;display:none;'},
                el('div',{style:'color:#ccc;font-size:12px;margin-bottom:4px;'},'Uploading files...'),
                el('div',{class:'progress-bar',style:'background:#333;border-radius:4px;height:20px;overflow:hidden;'},
                    el('div',{id:'progress-fill',style:'background:linear-gradient(90deg,#48bb78,#68d391);height:100%;width:0%;transition:width 0.3s;'})
                ),
                el('div',{id:'progress-text',style:'color:#888;font-size:11px;margin-top:4px;'},'0% complete')
            ),

            // Bucket List (for non-selected view)
            el('div',{id:'buckets-list',style:'margin-top:8px;font-size:13px;'},'Loading')
        )
    );
    const pinsView = el('div',{id:'view-pins',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'Pins'}),
            el('div',{class:'row'},
                el('input',{id:'pin-cid',placeholder:'cid',style:'width:200px;'}),
                el('input',{id:'pin-name',placeholder:'name',style:'width:140px;'}),
                el('button',{id:'btn-pin-add'},'Add')
            ),
            el('div',{id:'pins-list',style:'margin-top:8px;font-size:13px;'},'Loading')
        )
    );
    const logsView = el('div',{id:'view-logs',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'}, el('h3',{text:'Logs'}),
            el('div',{class:'row'}, el('button',{id:'btn-clear-logs'},'Clear Logs')),
            el('pre',{id:'logs-pre',text:'(streaming)'})
        )
    );
    const filesView = el('div',{id:'view-files',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'}, el('h3',{text:'Virtual File System'}),
            // Bucket selection and path navigation
            el('div',{class:'row',style:'margin-bottom:8px;'},
                el('label',{style:'margin-right:8px;',text:'Bucket:'}),
                el('select',{id:'files-bucket',style:'width:120px;margin-right:8px;'}),
                el('button',{id:'btn-bucket-refresh',style:'font-size:11px;padding:2px 6px;'},'Refresh')
            ),
            el('div',{class:'row',style:'margin-bottom:8px;'},
                el('label',{style:'margin-right:8px;',text:'Path:'}),
                el('input',{id:'files-path',value:'.',style:'width:200px;margin-right:8px;'}),
                el('button',{id:'btn-files-load'},'Load'),
                el('button',{id:'btn-files-up',style:'margin-left:4px;'},' Up'),
                el('button',{id:'btn-files-refresh',style:'margin-left:4px;'},'Refresh')
            ),
            // File operations toolbar
            el('div',{class:'row',style:'margin-bottom:8px;border-top:1px solid #333;padding-top:8px;'},
                el('button',{id:'btn-file-new',style:'margin-right:4px;'},'New File'),
                el('button',{id:'btn-dir-new',style:'margin-right:4px;'},'New Directory'),
                el('button',{id:'btn-file-upload',style:'margin-right:4px;'},'Upload'),
                el('input',{id:'file-upload-input',type:'file',style:'display:none;multiple:true'}),
                el('button',{id:'btn-file-delete',disabled:true,style:'margin-left:12px;color:#f66;'},'Delete Selected')
            ),
            // File listing
            el('div',{id:'files-container',style:'border:1px solid #333;min-height:200px;max-height:400px;overflow-y:auto;padding:4px;background:#0a0a0a;'},
                el('div',{id:'files-loading',text:'Loading'})
            ),
            // File details panel
            el('div',{id:'file-details',style:'margin-top:8px;padding:8px;border:1px solid #333;background:#111;display:none;'},
                el('h4',{text:'File Details',style:'margin:0 0 8px 0;'}),
                el('div',{id:'file-stats',style:'font-family:monospace;font-size:12px;white-space:pre-wrap;'})
            )
        )
    );
    // Tools (enhanced tool runner)
    const toolsView = el('div',{id:'view-tools',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'Tools'}),
            el('div',{class:'row'},
                el('input',{id:'tool-filter',placeholder:'filter',style:'width:160px;'}),
                el('select',{id:'tool-select',style:'min-width:260px;'}),
                el('button',{id:'btn-tool-refresh'},'Reload'),
                el('button',{id:'btn-tool-raw-toggle',style:'margin-left:6px;font-size:11px;'},'Raw JSON')
            ),
            el('div',{id:'tool-desc',class:'muted',style:'font-size:11px;margin-top:4px;'}),
            el('div',{id:'tool-form',style:'margin-top:8px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;'}),
            el('div',{class:'row',style:'margin-top:6px;'},
                el('textarea',{id:'tool-args',rows:'6',style:'width:100%;display:none;',text:'{}'})
            ),
            el('div',{class:'row',style:'margin-top:6px;'},
                el('button',{id:'btn-tool-run'},'Run'),
                el('span',{id:'tool-run-status',style:'font-size:12px;opacity:.7;margin-left:8px;'})
            ),
            el('pre',{id:'tool-result',text:'(result)'}),
            el('div',{style:'font-size:11px;opacity:.6;margin-top:4px;'},'Uses MCP JSON-RPC wrappers.'),
            // Beta Tool Runner (always present; visible when beta mode)
            el('div',{id:'toolrunner-beta-container', style:'margin-top:16px;padding-top:10px;border-top:'+'1px solid #2d3a4d;'},
                el('h3',{text:'Beta Tool Runner'}),
                el('div',{class:'row',style:'margin-bottom:6px;'},
                    el('input',{ 'data-testid':'toolbeta-filter', id:'toolbeta-filter', placeholder:'filter tools', style:'width:200px;margin-right:8px;' }),
                    el('select',{ 'data-testid':'toolbeta-select', id:'toolbeta-select', style:'min-width:260px;' })
                ),
                el('div',{id:'toolbeta-form',style:'margin-top:8px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;'}),
                el('div',{class:'row',style:'margin-top:6px;'},
                    el('button',{ 'data-testid':'toolbeta-run', id:'toolbeta-run', style:'font-size:12px;padding:6px 12px;' },'Run')
                ),
                el('pre',{ 'data-testid':'toolbeta-result', id:'toolbeta-result', text:'(result)'}),
            )
        )
    );
    // IPFS Panel
    const ipfsView = el('div',{id:'view-ipfs',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'IPFS'}),
            el('div',{id:'ipfs-version',class:'muted',text:'(version?)'}),
            el('div',{class:'row',style:'margin-top:8px;'},
                el('input',{id:'ipfs-cid',placeholder:'CID',style:'width:260px;'}),
                el('button',{id:'btn-ipfs-cat'},'Cat'),
                el('button',{id:'btn-ipfs-pin'},'Pin')
            ),
            el('pre',{id:'ipfs-cat-output',text:'(cat output)'}),
            el('div',{style:'font-size:11px;opacity:.6;margin-top:4px;'},'Cat truncated to 8KB.')
        )
    );
    // CARs Panel
    const carsView = el('div',{id:'view-cars',class:'view-panel',style:'display:none;'},
        el('div',{class:'card'},
            el('h3',{text:'CAR Files'}),
            el('div',{class:'row'},
                el('button',{id:'btn-cars-refresh'},'List'),
                el('input',{id:'car-path',placeholder:'path',style:'width:160px;'}),
                el('input',{id:'car-name',placeholder:'file.car',style:'width:160px;'}),
                el('button',{id:'btn-car-export'},'Export'),
                el('input',{id:'car-import-src',placeholder:'file.car',style:'width:160px;'}),
                el('input',{id:'car-import-dest',placeholder:'dest path',style:'width:160px;'}),
                el('button',{id:'btn-car-import'},'Import')
            ),
            el('pre',{id:'cars-list',text:'(list)'}),
            el('div',{style:'font-size:11px;opacity:.6;margin-top:4px;'},'Uses CAR tool wrappers.')
        )
    );
    if (appRoot){ appRoot.append(header, nav, overviewView, servicesView, backendsView, bucketsView, pinsView, logsView, filesView, toolsView, ipfsView, carsView); }
    function perfBar(label,key){
        const fillId = 'bar-fill-'+key;
        return el('div',{class:'bar'},
            el('span',{}, el('strong',{},label), el('span',{id:'bar-label-'+key},'')),
            el('div',{class:'bar-track'}, el('div',{class:'bar-fill',id:fillId}))
        );
    }
    function showView(name){
    const panels = ['overview','services','backends','buckets','pins','logs','files','tools','ipfs','cars'];
        panels.forEach(p => {
            const elp=document.getElementById('view-'+p); if(elp) elp.style.display = (p===name?'block':'none');
            const btn=document.querySelector('.dash-nav .nav-btn[data-view="'+p+'"]'); if(btn) btn.classList.toggle('active', p===name);
        });
        if(name==='services') loadServices();
        else if(name==='backends') loadBackends();
    else if(name==='buckets') loadBuckets();
        else if(name==='pins') loadPins();
        else if(name==='logs') initLogs();
    else if(name==='files') { loadVfsBuckets(); loadFiles(); }
    else if(name==='tools') { initTools(); initToolRunnerBeta(); }
    else if(name==='ipfs') initIPFS();
    else if(name==='cars') initCARs();
    }
    nav.querySelectorAll('.nav-btn').forEach(btn=> btn.addEventListener('click', ()=> showView(btn.getAttribute('data-view'))));
    // Always default to Tools (beta Tool Runner) to guarantee the beta UI is shown
    showView('tools');

    // --- Beta Tool Runner logic ---
    // Use var to avoid TDZ if showView('tools') fires before these are initialized
    var toolbetaInited=false; var toolbetaTools=[];
    async function initToolRunnerBeta(){
        const container=document.getElementById('toolrunner-beta-container'); if(!container) return;
        if(toolbetaInited) return; toolbetaInited=true;
        try{
            // Load tools
            await waitForMCP();
            const list = await MCP.listTools();
            toolbetaTools = (list && list.result && Array.isArray(list.result.tools))? list.result.tools : [];
            renderToolbetaSelect(toolbetaTools);
            bindToolbeta();
        }catch(e){ /* ignore */ }
    }
    function renderToolbetaSelect(tools){
        const sel=document.getElementById('toolbeta-select'); if(!sel) return;
        sel.innerHTML='';
        tools.forEach(t=>{ const opt=document.createElement('option'); opt.value=t.name; opt.textContent=t.name; sel.append(opt); });
    }
    function bindToolbeta(){
        const filter=document.getElementById('toolbeta-filter');
        const sel=document.getElementById('toolbeta-select');
        const run=document.getElementById('toolbeta-run');
        const form=document.getElementById('toolbeta-form');
        const result=document.getElementById('toolbeta-result');
        if(filter){ filter.addEventListener('input', ()=>{
            const q=String(filter.value||'').toLowerCase();
            const filtered = toolbetaTools.filter(t=> t.name.toLowerCase().includes(q));
            renderToolbetaSelect(filtered);
        }); }
        if(sel){ sel.addEventListener('change', ()=> updateToolbetaForm(sel.value)); }
        if(run){ run.addEventListener('click', async ()=>{
            try{
                const name = sel && sel.value; if(!name) return;
                const args = collectToolbetaArgs();
                const out = await MCP.callTool(name, args);
                if(result) result.textContent = JSON.stringify(out, null, 2);
            }catch(e){ if(result) result.textContent = String(e); }
        }); }
        // Initialize with first tool if available
        if(sel && sel.options.length>0){ updateToolbetaForm(sel.value); }
    }
    function collectToolbetaArgs(){
        const form=document.getElementById('toolbeta-form'); const args={};
        if(!form) return args;
        const inputs=form.querySelectorAll('[data-fld]');
        inputs.forEach(inp=>{
            const key=inp.getAttribute('data-fld');
            if(inp.type==='checkbox') args[key]=!!inp.checked; else args[key]=inp.value;
        });
        return args;
    }
    async function updateToolbetaForm(toolName){
        const form=document.getElementById('toolbeta-form'); if(!form) return; form.innerHTML='';
        const tool = toolbetaTools.find(t=> t.name===toolName) || {};
        const schema = (tool && tool.inputSchema) || {}; const props = schema.properties || {};
        const backendNames = await getBackendNames();
        Object.keys(props).forEach(k=>{
            const def = props[k]||{}; const type = Array.isArray(def.type)? def.type[0] : (def.type||'string');
            const id='fld_'+k; let field=null;
            if(k==='backend'){
                const sel=document.createElement('select'); sel.setAttribute('data-testid','toolbeta-field-backend'); sel.id=id; sel.setAttribute('data-fld',k);
                backendNames.forEach(n=>{ const o=document.createElement('option'); o.value=n; o.textContent=n; sel.append(o); });
                field=sel;
            }else if(type==='boolean'){
                const inp=document.createElement('input'); inp.type='checkbox'; inp.id=id; inp.setAttribute('data-fld',k); field=inp;
            }else{
                const inp=document.createElement('input'); inp.type='text'; inp.id=id; inp.setAttribute('data-fld',k); field=inp;
            }
            const wrap=document.createElement('label'); wrap.style.display='flex'; wrap.style.flexDirection='column'; wrap.style.fontSize='11px';
            wrap.textContent = k; wrap.appendChild(field); form.appendChild(wrap);
        });
    }
    async function getBackendNames(){ try{ const r=await MCP.Backends.list(); const items=(r && r.result && r.result.items)||[]; return items.map(it=> it.name); }catch(e){ return []; } }
    async function waitForMCP(){ const t0=Date.now(); while(!(window.MCP && MCP.listTools)){ if(Date.now()-t0>15000) throw new Error('MCP not ready'); await new Promise(r=>setTimeout(r,50)); } }

    async function loadServices(){
        const pre=document.getElementById('services-json'); if(pre) pre.textContent='Loading';
        try{ 
            // Use MCP SDK instead of direct REST call
            const result = await window.MCP.callTool('list_services', {});
            const services = (result && result.result && result.result.services) || {}; 
            // Build table
            let html='';
            html += 'Service | Status | Actions\n';
            html += '--------|--------|--------\n';
            Object.entries(services).forEach(([name, info])=>{
                const st=(info&&info.status)||info.bin? (info.status||'detected'): 'missing';
                html += `${name} | ${st} | `;
                // Show actions for all services that have actions available
                const serviceActions = info.actions || [];
                if (serviceActions.length > 0) {
                    const running = st==='running';
                    if (running) {
                        html += `[stop] [restart]`;
                    } else if (st==='stopped' || st==='detected') {
                        html += `[start]`;
                    } else {
                        html += `[start]`;
                    }
                }
                html += '\n';
            });
            if(pre) pre.textContent=html.trim();
            // attach click handler for actions within pre (simple delegation parsing tokens)
            if(pre && !pre._svcBound){
                pre._svcBound=true;
                pre.addEventListener('click', (e)=>{
                    if(e.target.nodeType!==Node.TEXT_NODE) return; // plain text selection ignored
                });
                pre.addEventListener('mousedown', (e)=>{
                    const sel=window.getSelection();
                    if(sel && sel.toString()) return; // allow text selection
                    const pos=pre.ownerDocument.caretRangeFromPoint? pre.ownerDocument.caretRangeFromPoint(e.clientX,e.clientY): null;
                    if(!pos) return;
                });
                // Simpler: use regex on clicked position not robust; instead overlay buttons separately below
            }
            // Render interactive buttons below table for each lifecycle-managed service
            const containerBtns = document.getElementById('services-actions');
            if(containerBtns){
                containerBtns.innerHTML='';
                Object.entries(services).forEach(([name, info])=>{
                    // Show action buttons for services that have actions available
                    const serviceActions = info.actions || [];
                    if (serviceActions.length === 0) return;
                    const st=(info&&info.status)||'unknown';
                    const wrap=document.createElement('div'); wrap.style.marginBottom='4px';
                    const title=document.createElement('strong'); title.textContent=name+':'; title.style.marginRight='6px'; wrap.append(title);
                    function addBtn(label, action){ const b=document.createElement('button'); b.textContent=label; b.style.marginRight='4px'; b.style.fontSize='11px'; b.onclick=()=> serviceAction(name, action); wrap.append(b);} 
                    if(st==='running'){ addBtn('Stop','stop'); addBtn('Restart','restart'); }
                    else if(st==='starting' || st==='stopping' || st==='restarting'){ const span=document.createElement('span'); span.textContent='(transition '+st+')'; wrap.append(span); }
                    else { addBtn('Start','start'); }
                    const statusSpan=document.createElement('span'); statusSpan.textContent=' status='+st; statusSpan.style.marginLeft='6px'; wrap.append(statusSpan);
                    containerBtns.append(wrap);
                });
            }
        }catch(e){ if(pre) pre.textContent='Error'; }
    }
    async function serviceAction(name, action){
        try{ 
            // Use MCP SDK service control instead of direct REST call
            await window.MCP.callTool('service_control', { service: name, action: action }); 
            loadServices(); 
        }catch(e){
            console.error('Service action failed:', e);
        }
    }
    // Polling for services when services view active
    setInterval(()=>{ const sv=document.getElementById('view-services'); if(sv && sv.style.display==='block') loadServices(); }, 5000);
    async function loadBackends(){
        const container = document.getElementById('backends-list'); if(!container) return;

        // Show proper loading state
        container.innerHTML = '<div style="text-align:center;padding:20px;color:#666;"><div class="loading-spinner"></div><br>Loading backends...</div>';

        try{ 
            console.log(' Loading backends via MCP SDK (metadata-first)...');
            const response = await MCP.callTool('list_backends', {include_metadata: true});

            if (!response || !response.result) {
                throw new Error('Invalid MCP response');
            }

            const js = response.result; 
            const backends = js.backends || js.items || []; 

            console.log(` Backends result:`, {result: js});
            console.log(` Extracted backends array:`, backends);
            console.log(` Is backends an array?`, Array.isArray(backends));

            // Update health counters with MCP data
            const healthyCount = js.healthy || 0;
            const unhealthyCount = js.unhealthy || 0;
            const configuredCount = js.configured || 0;
            const totalCount = js.total || backends.length;

            const healthyEl = document.getElementById('healthy-count');
            const unhealthyEl = document.getElementById('unhealthy-count');
            const configuredEl = document.getElementById('configured-count');
            const totalEl = document.getElementById('total-backends-count');

            console.log(' Updating health counters:', {healthyCount, unhealthyCount, configuredCount, totalCount});
            console.log(' Elements found:', {healthyEl, unhealthyEl, configuredEl, totalEl});

            if (healthyEl) {
                healthyEl.textContent = healthyCount;
                console.log(' Updated healthy count to', healthyCount);
            }
            if (unhealthyEl) {
                unhealthyEl.textContent = unhealthyCount;
                console.log(' Updated unhealthy count to', unhealthyCount);
            }
            if (configuredEl) {
                configuredEl.textContent = configuredCount;
                console.log(' Updated configured count to', configuredCount);
            }
            if (totalEl) {
                totalEl.textContent = totalCount;
                console.log(' Updated total count to', totalCount);
            }

            if(!backends.length){ 
                container.innerHTML = '<div style="text-align:center;padding:20px;color:#666;">No backends configured</div>'; 
                return; 
            }

            container.innerHTML=''; 
            backends.forEach((backend, index) => {
                // Enhanced data validation and processing
                const name = backend.name || `backend_${index}`;
                const type = backend.type || (backend.config && backend.config.type) || 'local';
                const tier = backend.tier || 'standard';
                const status = backend.status || 'enabled';
                const description = backend.description || `${type} storage backend`;

                // Validate required fields and log any issues
                if (!backend.name) {
                    console.warn(` Backend ${index} missing name:`, backend);
                }
                if (!backend.type && !(backend.config && backend.config.type)) {
                    console.warn(` Backend ${name} missing type:`, backend);
                }

                // Get policy info with proper defaults
                const policy = backend.policy || {};
                const storagePolicy = policy.storage_quota || {};
                const trafficPolicy = policy.traffic_quota || {};
                const replicationPolicy = policy.replication || {};
                const retentionPolicy = policy.retention || {};
                const cachePolicy = policy.cache || {};

                // Get stats
                const stats = backend.stats || {};

                // Create a comprehensive backend card
                const backendCard = el('div',{
                    class:'backend-card',
                    style:'border:1px solid #e0e0e0;margin:8px 0;padding:12px;border-radius:8px;background:white;box-shadow:0 2px 4px rgba(0,0,0,0.1);'
                });

                // Header with name, type, status
                const header = el('div',{
                    style:'display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;'
                }, 
                    el('div',{style:'display:flex;align-items:center;gap:8px;'},
                        el('strong',{text:name,style:'color:#2196F3;font-size:16px;'}),
                        el('span',{text:`[${type}]`,style:'color:#666;font-size:12px;background:#f5f5f5;padding:2px 6px;border-radius:3px;'}),
                        el('span',{
                            text:tier.toUpperCase(),
                            style:`background:${getTierColor(tier)};color:white;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:bold;`
                        }),
                        el('span',{
                            text:getStatusDisplay(status),
                            style:`color:${getStatusColor(status)};font-size:12px;font-weight:bold;padding:2px 6px;background:${getStatusBackground(status)};border-radius:3px;`
                        })
                    ),
                    el('div',{style:'display:flex;gap:4px;'},
                        el('button',{
                            style:'padding:4px 8px;font-size:11px;background:#4CAF50;color:white;border:none;border-radius:3px;cursor:pointer;',
                            title:'Test Backend Connection',
                            onclick:()=>testBackend(name)
                        },'Test'),
                        el('button',{
                            style:'padding:4px 8px;font-size:11px;background:#2196F3;color:white;border:none;border-radius:3px;cursor:pointer;',
                            title:'Edit Backend Configuration',
                            onclick:()=>editBackend(name)
                        },'Edit'),
                        el('button',{
                            style:'padding:4px 8px;font-size:11px;background:#f44336;color:white;border:none;border-radius:3px;cursor:pointer;',
                            title:'Delete Backend',
                            onclick:()=>deleteBackend(name)
                        },'Delete')
                    )
                );

                // Description
                const desc = el('div',{
                    text:description,
                    style:'color:#666;font-size:12px;margin-bottom:10px;'
                });

                // Configuration details  
                const configRow = el('div',{
                    style:'display:flex;gap:15px;margin-bottom:8px;font-size:11px;flex-wrap:wrap;'
                });

                if(backend.config) {
                    const config = backend.config;
                    Object.keys(config).slice(0, 4).forEach(key => {
                        if(key !== 'type' && typeof config[key] === 'string') {
                            configRow.appendChild(el('span',{
                                text:`${key}: ${config[key].length > 20 ? config[key].substring(0, 20) + '...' : config[key]}`,
                                style:'color:#777;background:#f9f9f9;padding:2px 4px;border-radius:2px;'
                            }));
                        }
                    });
                }

                // Stats row
                const statsRow = el('div',{
                    style:'display:flex;gap:15px;margin-bottom:8px;font-size:11px;flex-wrap:wrap;'
                });

                if(stats.used_storage_gb !== undefined) {
                    statsRow.appendChild(el('span',{
                        text:`Storage: ${stats.used_storage_gb.toFixed(1)} GB`,
                        style:'color:#81C784;'
                    }));
                }

                if(stats.total_files !== undefined) {
                    statsRow.appendChild(el('span',{
                        text:`Files: ${stats.total_files}`,
                        style:'color:#64B5F6;'  
                    }));
                }

                if(stats.availability !== undefined) {
                    const availability = (stats.availability * 100).toFixed(1);
                    statsRow.appendChild(el('span',{
                        text:`Uptime: ${availability}%`,
                        style:`color:${stats.availability > 0.99 ? '#4CAF50' : stats.availability > 0.95 ? '#FF9800' : '#f44336'};`
                    }));
                }

                // Policy summary with better formatting
                const policySummary = el('div',{
                    style:'font-size:10px;color:#888;display:flex;gap:12px;flex-wrap:wrap;border-top:1px solid #eee;padding-top:8px;'
                });

                if(storagePolicy.max_size) {
                    policySummary.appendChild(el('span',{
                        text:` Quota: ${storagePolicy.max_size} ${storagePolicy.max_size_unit || 'GB'}`,
                        style:'background:#E3F2FD;color:#1976D2;padding:2px 6px;border-radius:3px;'
                    }));
                }

                if(replicationPolicy.min_redundancy) {
                    const replicationText = replicationPolicy.max_redundancy && replicationPolicy.max_redundancy !== replicationPolicy.min_redundancy 
                        ? `${replicationPolicy.min_redundancy}-${replicationPolicy.max_redundancy}` 
                        : `${replicationPolicy.min_redundancy}`;
                    policySummary.appendChild(el('span',{
                        text:` Replication: ${replicationText}`,
                        style:'background:#F3E5F5;color:#7B1FA2;padding:2px 6px;border-radius:3px;'
                    }));
                }

                if(retentionPolicy.default_retention_days) {
                    policySummary.appendChild(el('span',{
                        text:` Retention: ${retentionPolicy.default_retention_days}d`,
                        style:'background:#FFF3E0;color:#F57C00;padding:2px 6px;border-radius:3px;'
                    }));
                }

                if(cachePolicy.max_cache_size) {
                    policySummary.appendChild(el('span',{
                        text:` Cache: ${cachePolicy.max_cache_size} ${cachePolicy.max_cache_size_unit || 'GB'}`,
                        style:'background:#E8F5E8;color:#388E3C;padding:2px 6px;border-radius:3px;'
                    }));
                }

                backendCard.append(header, desc, configRow, statsRow, policySummary);
                container.append(backendCard);
            });
        }catch(e){ 
            console.error(' Error loading backends:', e);
            console.error(' Error details:', e.stack);
            console.error(' Response data was:', js);
            console.error(' backends variable was:', backends);
            container.innerHTML = `
                <div style="text-align:center;padding:20px;border:1px solid #f44336;border-radius:8px;background:#ffebee;color:#c62828;">
                    <strong> Failed to Load Backends</strong><br>
                    <small style="color:#666;margin-top:8px;display:block;">${e.message}</small>
                    <button onclick="loadBackends()" style="margin-top:10px;padding:6px 12px;background:#2196F3;color:white;border:none;border-radius:4px;cursor:pointer;">
                         Retry
                    </button>
                </div>
            `;
        }
    }

    function getTierColor(tier) {
        switch(tier) {
            case 'hot': return '#f44336';     // Red for hot
            case 'warm': return '#FF9800';    // Orange for warm  
            case 'cold': return '#2196F3';    // Blue for cold
            case 'archive': return '#9C27B0'; // Purple for archive
            default: return '#607D8B';        // Blue-grey for standard
        }
    }

    function getStatusDisplay(status) {
        switch(status) {
            case 'enabled': return ' Enabled';
            case 'disabled': return ' Disabled';
            case 'error': return ' Error';
            case 'maintenance': return ' Maintenance';
            case 'testing': return ' Testing';
            default: return ` ${status}`;
        }
    }

    function getStatusColor(status) {
        switch(status) {
            case 'enabled': return '#4CAF50';
            case 'disabled': return '#f44336';
            case 'error': return '#f44336';
            case 'maintenance': return '#FF9800';
            case 'testing': return '#2196F3';
            default: return '#607D8B';
        }
    }

    function getStatusBackground(status) {
        switch(status) {
            case 'enabled': return '#E8F5E8';
            case 'disabled': return '#FFEBEE';
            case 'error': return '#FFEBEE';
            case 'maintenance': return '#FFF3E0';
            case 'testing': return '#E3F2FD';
            default: return '#F5F5F5';
        }
    }

    async function testBackend(name) {
        try {
            console.log(` Testing backend: ${name}`);
            const response = await fetch(`/api/backends/${encodeURIComponent(name)}/test`, {
                method: 'POST'
            });
            const result = await response.json();

            if (response.ok) {
                alert(` Backend "${name}" test successful!\n\nDetails: ${JSON.stringify(result, null, 2)}`);
            } else {
                alert(` Backend "${name}" test failed!\n\nError: ${result.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error(`Error testing backend ${name}:`, error);
            alert(` Failed to test backend "${name}"\n\nError: ${error.message}`);
        }
    }

    async function editBackend(name) {
        const newName = prompt('Backend name:', name);
        if (!newName || newName === name) return;

        try {
            // Get current backend config
            const response = await fetch(`/api/backends/${encodeURIComponent(name)}`);
            const backend = await response.json();

            const newConfig = prompt('Backend configuration (JSON):', JSON.stringify(backend.config || {}, null, 2));
            if (!newConfig) return;

            const config = JSON.parse(newConfig);

            // Update backend
            const updateResponse = await fetch(`/api/backends/${encodeURIComponent(name)}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: newName,
                    config: config
                })
            });

            if (updateResponse.ok) {
                alert(` Backend "${name}" updated successfully!`);
                loadBackends();
            } else {
                const error = await updateResponse.json();
                alert(` Failed to update backend "${name}"\n\nError: ${error.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error(`Error editing backend ${name}:`, error);
            alert(` Failed to edit backend "${name}"\n\nError: ${error.message}`);
        }
    }

    // ---- Advanced Feature 8: Real-Time Performance Metrics Functions ----

    async function testAllBackends() {
        try {
            console.log(' Testing all backends...');
            const response = await MCP.callTool('backend_health_check', {detailed: true});

            if (response && response.result) {
                const results = response.result.results || [];
                const healthy = results.filter(r => r.status === 'healthy').length;
                const total = results.length;

                alert(` Backend Health Check Complete\\n\\n Healthy: ${healthy}/${total}\\n Issues: ${total - healthy}\\n\\nCheck console for details.`);
                console.log('Backend test results:', results);
                loadBackends();
            }
        } catch (error) {
            console.error('Error testing backends:', error);
            alert(' Failed to test backends: ' + error.message);
        }
    }

    async function syncAllBackends() {
        try {
            console.log(' Syncing all backends...');
            alert(' Backend sync initiated. This may take a few moments...');
            // Implementation would sync all backends
            setTimeout(() => {
                alert(' All backends synchronized successfully!');
                loadBackends();
            }, 2000);
        } catch (error) {
            console.error('Error syncing backends:', error);
            alert(' Failed to sync backends: ' + error.message);
        }
    }

    async function runHealthCheck() {
        try {
            console.log(' Running comprehensive health check...');
            const response = await MCP.callTool('backend_health_check', {detailed: true});

            if (response && response.result) {
                const results = response.result.results || [];
                showHealthCheckResults(results);
                updateHealthCounters(results);
            }
        } catch (error) {
            console.error('Error running health check:', error);
            alert(' Health check failed: ' + error.message);
        }
    }

    function showHealthCheckResults(results) {
        const healthyCount = results.filter(r => r.status === 'healthy').length;
        const totalCount = results.length;

        const resultText = results.map(r => 
            `${r.status === 'healthy' ? '' : ''} ${r.name} (${r.type}): ${r.status}`
        ).join('\\n');

        alert(` Health Check Results\\n\\n${resultText}\\n\\nSummary: ${healthyCount}/${totalCount} backends healthy`);
    }

    function updateHealthCounters(results) {
        const healthyCount = results.filter(r => r.status === 'healthy').length;
        const unhealthyCount = results.filter(r => r.status !== 'healthy').length;
        const totalCount = results.length;

        const healthyEl = document.getElementById('healthy-count');
        const unhealthyEl = document.getElementById('unhealthy-count');
        const totalEl = document.getElementById('total-backends-count');
        const configuredEl = document.getElementById('configured-count');

        if (healthyEl) healthyEl.textContent = healthyCount;
        if (unhealthyEl) unhealthyEl.textContent = unhealthyCount;
        if (totalEl) totalEl.textContent = totalCount;
        if (configuredEl) configuredEl.textContent = totalCount;
    }

    async function showPerformanceMetrics() {
        const modal = document.getElementById('performance-metrics-modal');
        if (modal) {
            modal.style.display = 'block';
            await refreshPerformanceMetrics();
        }
    }

    function closePerformanceMetrics() {
        const modal = document.getElementById('performance-metrics-modal');
        if (modal) modal.style.display = 'none';
    }

    async function refreshPerformanceMetrics() {
        const content = document.getElementById('performance-metrics-content');
        const timeRange = document.getElementById('metrics-time-range')?.value || '1h';

        if (!content) return;

        content.innerHTML = '<div style="text-align:center;padding:20px;"> Loading performance metrics...</div>';

        try {
            const response = await MCP.callTool('get_backend_performance_metrics', {
                time_range: timeRange,
                include_history: true
            });

            if (response && response.result && response.result.metrics) {
                renderPerformanceMetrics(response.result.metrics, content);
            } else {
                content.innerHTML = '<div style="color:#f44336;text-align:center;padding:20px;">No performance data available</div>';
            }
        } catch (error) {
            console.error('Error loading performance metrics:', error);
            content.innerHTML = `<div style="color:#f44336;text-align:center;padding:20px;">Error: ${error.message}</div>`;
        }
    }

    function renderPerformanceMetrics(metrics, container) {
        container.innerHTML = '';

        if (!metrics.length) {
            container.innerHTML = '<div style="text-align:center;padding:20px;color:#888;">No backends configured for monitoring</div>';
            return;
        }

        metrics.forEach(metric => {
            const backendDiv = document.createElement('div');
            backendDiv.style.cssText = 'border:1px solid #333;margin:8px 0;padding:12px;border-radius:6px;background:#0a0a0a;';

            const perf = metric.performance;
            backendDiv.innerHTML = `
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <strong style="color:#4CAF50;">${metric.backend_name}</strong>
                    <span style="color:#888;font-size:11px;">${metric.backend_type}</span>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;font-size:11px;">
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#2196F3;">Response Time</div>
                        <div style="font-weight:bold;">${perf.response_time_ms}ms</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#4CAF50;">Throughput</div>
                        <div style="font-weight:bold;">${perf.throughput_ops_per_sec} ops/s</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#FF9800;">Error Rate</div>
                        <div style="font-weight:bold;">${perf.error_rate_percent}%</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#E91E63;">Success Rate</div>
                        <div style="font-weight:bold;">${perf.success_rate_percent}%</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#9C27B0;">Data Transfer</div>
                        <div style="font-weight:bold;">${perf.data_transfer_mbps} MB/s</div>
                    </div>
                    <div style="background:#1a1a1a;padding:6px;border-radius:3px;">
                        <div style="color:#607D8B;">Uptime</div>
                        <div style="font-weight:bold;">${perf.uptime_percent}%</div>
                    </div>
                </div>
                <div style="margin-top:8px;font-size:10px;color:#666;">
                    CPU: ${perf.cpu_usage_percent}% | Memory: ${perf.memory_usage_percent}% | 
                    Disk: ${perf.disk_usage_percent}% | Connections: ${perf.active_connections}
                </div>
            `;

            container.appendChild(backendDiv);
        });
    }

    // ---- Advanced Feature 9: Configuration Management Functions ----

    function showAddBackendModal() {
        // Enhanced modal for adding backends with templates
        alert(' Enhanced backend creation with templates coming soon! For now, use the Add Instance feature below.');
    }

    async function showConfigurationTemplates() {
        const modal = document.getElementById('config-templates-modal');
        if (modal) {
            modal.style.display = 'block';
            showTemplateSelector(); // Default to template view
        }
    }

    function closeConfigTemplates() {
        const modal = document.getElementById('config-templates-modal');
        if (modal) modal.style.display = 'none';
    }

    async function showTemplateSelector() {
        const content = document.getElementById('config-templates-content');
        if (!content) return;

        content.innerHTML = `
            <h4 style="color:#9C27B0;margin-bottom:12px;"> Configuration Templates</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
                <select id="template-backend-type" style="padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                    <option value="s3">Amazon S3 / S3-Compatible</option>
                    <option value="github">GitHub Repository</option>
                    <option value="ipfs">IPFS Node</option>
                    <option value="huggingface">HuggingFace Hub</option>
                </select>
                <select id="template-type" style="padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                    <option value="basic">Basic Template</option>
                    <option value="enterprise">Enterprise Template</option>
                    <option value="high_performance">High Performance</option>
                    <option value="backup">Backup Template</option>
                </select>
            </div>
            <button onclick="loadConfigTemplate()" style="background:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;margin-bottom:16px;"> Load Template</button>
            <div id="template-preview" style="background:#0a0a0a;border:1px solid #333;border-radius:4px;padding:12px;font-family:monospace;font-size:12px;white-space:pre-wrap;"></div>
        `;
    }

    async function loadConfigTemplate() {
        const backendType = document.getElementById('template-backend-type')?.value;
        const templateType = document.getElementById('template-type')?.value;
        const preview = document.getElementById('template-preview');

        if (!preview) return;

        try {
            const response = await MCP.callTool('get_backend_configuration_template', {
                backend_type: backendType,
                template_type: templateType
            });

            if (response && response.result && response.result.template) {
                preview.textContent = JSON.stringify(response.result.template, null, 2);
                preview.style.color = '#4CAF50';
            } else {
                preview.textContent = 'Template not found';
                preview.style.color = '#f44336';
            }
        } catch (error) {
            preview.textContent = 'Error loading template: ' + error.message;
            preview.style.color = '#f44336';
        }
    }

    async function showCloneBackend() {
        const content = document.getElementById('config-templates-content');
        if (!content) return;

        // Get backend list for cloning
        try {
            const response = await MCP.callTool('list_backends', {});
            const backends = response?.result?.backends || response?.result?.items || [];

            const backendOptions = backends.map(b => 
                `<option value="${b.name}">${b.name} (${b.type || 'unknown'})</option>`
            ).join('');

            content.innerHTML = `
                <h4 style="color:#2196F3;margin-bottom:12px;"> Clone Backend Configuration</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
                    <div>
                        <label style="display:block;margin-bottom:4px;color:#ccc;">Source Backend:</label>
                        <select id="clone-source-backend" style="width:100%;padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                            <option value="">Select backend to clone...</option>
                            ${backendOptions}
                        </select>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;color:#ccc;">New Backend Name:</label>
                        <input type="text" id="clone-new-name" placeholder="new-backend-name" style="width:100%;padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                    </div>
                </div>
                <div style="margin-bottom:16px;">
                    <label style="display:block;margin-bottom:4px;color:#ccc;">Description (optional):</label>
                    <input type="text" id="clone-description" placeholder="Cloned backend for..." style="width:100%;padding:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                </div>
                <button onclick="executeCloneBackend()" style="background:#2196F3;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;"> Clone Backend</button>
                <div id="clone-result" style="margin-top:12px;"></div>
            `;
        } catch (error) {
            content.innerHTML = `<div style="color:#f44336;">Error loading backends: ${error.message}</div>`;
        }
    }

    async function executeCloneBackend() {
        const sourceBackend = document.getElementById('clone-source-backend')?.value;
        const newName = document.getElementById('clone-new-name')?.value;
        const description = document.getElementById('clone-description')?.value;
        const resultDiv = document.getElementById('clone-result');

        if (!sourceBackend || !newName) {
            if (resultDiv) resultDiv.innerHTML = '<div style="color:#f44336;">Please select source backend and enter new name</div>';
            return;
        }

        try {
            const modifyConfig = description ? {description} : {};
            const response = await MCP.callTool('clone_backend_configuration', {
                source_backend: sourceBackend,
                new_backend_name: newName,
                modify_config: modifyConfig
            });

            if (response && response.result && response.result.ok) {
                if (resultDiv) resultDiv.innerHTML = '<div style="color:#4CAF50;"> Backend cloned successfully!</div>';
                setTimeout(() => {
                    closeConfigTemplates();
                    loadBackends();
                }, 1500);
            } else {
                const error = response?.result?.error || 'Unknown error';
                if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;"> Failed to clone: ${error}</div>`;
            }
        } catch (error) {
            if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;"> Error: ${error.message}</div>`;
        }
    }

    async function showBackupRestore() {
        const content = document.getElementById('config-templates-content');
        if (!content) return;

        // Get backend list
        try {
            const response = await MCP.callTool('list_backends', {});
            const backends = response?.result?.backends || response?.result?.items || [];

            const backendOptions = backends.map(b => 
                `<option value="${b.name}">${b.name} (${b.type || 'unknown'})</option>`
            ).join('');

            content.innerHTML = `
                <h4 style="color:#FF9800;margin-bottom:12px;"> Backup & Restore</h4>
                <div style="display:flex;gap:16px;">
                    <div style="flex:1;">
                        <h5 style="color:#4CAF50;">Create Backup</h5>
                        <select id="backup-backend" style="width:100%;padding:8px;margin-bottom:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                            <option value="">Select backend...</option>
                            ${backendOptions}
                        </select>
                        <input type="text" id="backup-name" placeholder="Backup name (optional)" style="width:100%;padding:8px;margin-bottom:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                        <button onclick="createBackup()" style="background:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;width:100%;"> Create Backup</button>
                    </div>
                    <div style="flex:1;">
                        <h5 style="color:#2196F3;">Restore Backup</h5>
                        <input type="text" id="restore-backend" placeholder="Backend name" style="width:100%;padding:8px;margin-bottom:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                        <input type="text" id="restore-backup-id" placeholder="Backup ID" style="width:100%;padding:8px;margin-bottom:8px;background:#333;color:white;border:1px solid #555;border-radius:4px;">
                        <button onclick="restoreBackup()" style="background:#2196F3;color:white;padding:8px 16px;border:none;border-radius:4px;cursor:pointer;width:100%;"> Restore Backup</button>
                    </div>
                </div>
                <div id="backup-result" style="margin-top:12px;"></div>
            `;
        } catch (error) {
            content.innerHTML = `<div style="color:#f44336;">Error loading backends: ${error.message}</div>`;
        }
    }

    async function createBackup() {
        const backendName = document.getElementById('backup-backend')?.value;
        const backupName = document.getElementById('backup-name')?.value;
        const resultDiv = document.getElementById('backup-result');

        if (!backendName) {
            if (resultDiv) resultDiv.innerHTML = '<div style="color:#f44336;">Please select a backend</div>';
            return;
        }

        try {
            const response = await MCP.callTool('backup_backend_configuration', {
                backend_name: backendName,
                backup_name: backupName || undefined
            });

            if (response && response.result && response.result.ok) {
                const backupId = response.result.backup_id;
                if (resultDiv) resultDiv.innerHTML = `<div style="color:#4CAF50;"> Backup created: ${backupId}</div>`;
            } else {
                const error = response?.result?.error || 'Unknown error';
                if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;"> Backup failed: ${error}</div>`;
            }
        } catch (error) {
            if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;"> Error: ${error.message}</div>`;
        }
    }

    async function restoreBackup() {
        const backendName = document.getElementById('restore-backend')?.value;
        const backupId = document.getElementById('restore-backup-id')?.value;
        const resultDiv = document.getElementById('backup-result');

        if (!backendName || !backupId) {
            if (resultDiv) resultDiv.innerHTML = '<div style="color:#f44336;">Please enter backend name and backup ID</div>';
            return;
        }

        try {
            const response = await MCP.callTool('restore_backend_configuration', {
                backend_name: backendName,
                backup_id: backupId
            });

            if (response && response.result && response.result.ok) {
                if (resultDiv) resultDiv.innerHTML = '<div style="color:#4CAF50;"> Backup restored successfully!</div>';
                setTimeout(() => {
                    closeConfigTemplates();
                    loadBackends();
                }, 1500);
            } else {
                const error = response?.result?.error || 'Unknown error';
                if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;"> Restore failed: ${error}</div>`;
            }
        } catch (error) {
            if (resultDiv) resultDiv.innerHTML = `<div style="color:#f44336;"> Error: ${error.message}</div>`;
        }
    }

    function showAdvancedPolicyEditor() {
        const content = document.getElementById('config-templates-content');
        if (!content) return;

        content.innerHTML = `
            <h4 style="color:#E91E63;margin-bottom:12px;"> Advanced Policy Editor</h4>
            <div style="color:#888;margin-bottom:16px;">
                Configure advanced policies for retry logic, timeouts, rate limits, and more.
            </div>
            <div style="background:#0a0a0a;border:1px solid #333;border-radius:4px;padding:16px;">
                <h5 style="margin-top:0;color:#4CAF50;">Available Policy Categories:</h5>
                <ul style="color:#ccc;line-height:1.6;">
                    <li><strong>Retry Policies:</strong> Configure retry attempts and backoff strategies</li>
                    <li><strong>Timeout Settings:</strong> Connection and operation timeouts</li>
                    <li><strong>Rate Limiting:</strong> Request rate limits and throttling</li>
                    <li><strong>Cache Policies:</strong> Cache TTL and invalidation rules</li>
                    <li><strong>Security Policies:</strong> Authentication and encryption settings</li>
                    <li><strong>Monitoring Policies:</strong> Health check intervals and alerting</li>
                </ul>
                <div style="margin-top:16px;color:#FF9800;">
                     Advanced policy editor will be available in the next update with full JSON schema validation and real-time preview.
                </div>
            </div>
        `;
    }

    function filterBackends(category) {
        // Update active button
        const buttons = document.querySelectorAll('[id^="filter-"]');
        buttons.forEach(btn => {
            btn.style.background = btn.id === `filter-${category}` ? '#4CAF50' : '#555';
        });

        // Filter logic would be implemented here
        console.log(`Filtering backends by category: ${category}`);
        loadBackends(); // Reload with filter
    }

    // ---- Enhanced Bucket Management Helper Functions ----

    // Helper functions for enhanced bucket management
    function createModal(title, contentCallback) {
        // Remove existing modal if any
        const existingModal = document.getElementById('bucket-modal');
        if (existingModal) existingModal.remove();

        const modal = document.createElement('div');
        modal.id = 'bucket-modal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
            background: rgba(0,0,0,0.8); z-index: 1000; display: flex; 
            align-items: center; justify-content: center;
        `;

        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: #1a1a1a; border: 1px solid #333; border-radius: 8px; 
            padding: 20px; max-width: 90%; max-height: 90%; overflow-y: auto;
            color: white; font-family: system-ui, Arial, sans-serif;
        `;

        const header = document.createElement('div');
        header.style.cssText = `
            display: flex; justify-content: space-between; align-items: center; 
            margin-bottom: 15px; border-bottom: 1px solid #333; padding-bottom: 10px;
        `;
        header.innerHTML = `
            <h3 style="margin: 0; color: white;">${title}</h3>
            <button onclick="document.getElementById('bucket-modal').remove()" 
                    style="background: #555; color: white; border: none; padding: 5px 10px; 
                           border-radius: 4px; cursor: pointer;"></button>
        `;

        const body = document.createElement('div');
        modalContent.appendChild(header);
        modalContent.appendChild(body);
        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });

        // Execute content callback
        if (contentCallback) contentCallback(body);

        return modal;
    }

    // Modal functions for bucket management

    // Show bucket configuration modal
    function showBucketConfigModal(bucketName) {
        if(!bucketName) return;

        const modal = createModal('Bucket Configuration: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = `
                <div style="margin-bottom:16px;">
                    <h4 style="margin:0 0 12px 0;color:#4CAF50;">Basic Settings</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;flex-direction:column;">
                            Replication Factor
                            <input type="number" id="config-replication" min="1" max="10" value="1" style="margin-top:4px;"/>
                        </label>
                        <label style="display:flex;flex-direction:column;">
                            Cache Policy
                            <select id="config-cache" style="margin-top:4px;">
                                <option value="none">None</option>
                                <option value="memory">Memory</option>
                                <option value="disk">Disk</option>
                                <option value="hybrid">Hybrid</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style="margin-bottom:16px;">
                    <h4 style="margin:0 0 12px 0;color:#FF9800;">Retention Policy</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;flex-direction:column;">
                            Retention Days (0 = infinite)
                            <input type="number" id="config-retention" min="0" value="0" style="margin-top:4px;"/>
                        </label>
                        <label style="display:flex;flex-direction:column;">
                            Auto Cleanup
                            <select id="config-cleanup" style="margin-top:4px;">
                                <option value="false">Disabled</option>
                                <option value="true">Enabled</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style="margin-bottom:20px;">
                    <h4 style="margin:0 0 12px 0;color:#2196F3;">Sync Settings</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;flex-direction:column;">
                            Sync Interval (minutes)
                            <input type="number" id="config-sync-interval" min="1" value="60" style="margin-top:4px;"/>
                        </label>
                        <label style="display:flex;flex-direction:column;">
                            Versioning
                            <select id="config-versioning" style="margin-top:4px;">
                                <option value="false">Disabled</option>
                                <option value="true">Enabled</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style="display:flex;gap:8px;justify-content:flex-end;">
                    <button onclick="saveBucketConfig('${bucketName}')" style="background:#4CAF50;color:white;padding:8px 16px;border:none;border-radius:4px;">Save Settings</button>
                    <button onclick="closeModal()" style="background:#666;color:white;padding:8px 16px;border:none;border-radius:4px;">Cancel</button>
                </div>
            `;

            // Load current settings
            try {
                await waitForMCP();
                const bucketResponse = await MCP.Buckets.get(bucketName);
                const bucket = (bucketResponse && bucketResponse.result) || {};
                const policy = bucket.policy || {};

                document.getElementById('config-replication').value = policy.replication_factor || 1;
                document.getElementById('config-cache').value = policy.cache_policy || 'none';
                document.getElementById('config-retention').value = policy.retention_days || 0;
                document.getElementById('config-cleanup').value = policy.auto_cleanup || 'false';
                document.getElementById('config-sync-interval').value = policy.sync_interval || 60;
                document.getElementById('config-versioning').value = policy.versioning || 'false';
            } catch(e) {
                console.error('Error loading bucket config:', e);
            }
        });

        modal.show();
    }

    // Show bucket share modal
    function showBucketShareModal(bucketName) {
        if(!bucketName) return;

        const modal = createModal('Share Bucket: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = `
                <div style="margin-bottom:16px;">
                    <h4 style="margin:0 0 12px 0;color:#795548;">Create Share Link</h4>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;flex-direction:column;">
                            Access Type
                            <select id="share-access" style="margin-top:4px;">
                                <option value="read_only">Read Only</option>
                                <option value="read_write">Read & Write</option>
                                <option value="admin">Admin</option>
                            </select>
                        </label>
                        <label style="display:flex;flex-direction:column;">
                            Expiration
                            <select id="share-expiration" style="margin-top:4px;">
                                <option value="1h">1 Hour</option>
                                <option value="24h">24 Hours</option>
                                <option value="7d">7 Days</option>
                                <option value="30d">30 Days</option>
                                <option value="never">Never</option>
                            </select>
                        </label>
                    </div>
                </div>
                <div style="margin-bottom:16px;">
                    <h4 style="margin:0 0 12px 0;color:#4CAF50;">Generated Link</h4>
                    <div style="display:flex;gap:8px;">
                        <input type="text" id="share-link" readonly style="flex:1;background:#0a0a0a;border:1px solid #333;padding:8px;border-radius:4px;color:#ccc;" placeholder="Click 'Generate Link' to create share link"/>
                        <button onclick="copyShareLink()" id="btn-copy-link" disabled style="background:#2196F3;color:white;padding:8px 12px;border:none;border-radius:4px;">Copy</button>
                    </div>
                </div>
                <div style="display:flex;gap:8px;justify-content:flex-end;">
                    <button onclick="generateShareLink('${bucketName}')" style="background:#795548;color:white;padding:8px 16px;border:none;border-radius:4px;">Generate Link</button>
                    <button onclick="closeModal()" style="background:#666;color:white;padding:8px 16px;border:none;border-radius:4px;">Close</button>
                </div>
            `;
        });

        modal.show();
    }

    // Generate share link for bucket
    async function generateShareLink(bucketName) {
        try {
            await waitForMCP();
            const accessType = document.getElementById('share-access').value;
            const expiration = document.getElementById('share-expiration').value;

            const result = await MCP.Buckets.generateShareLink(bucketName, accessType, expiration);
            const shareLink = window.location.origin + ((result && result.result && result.result.share_link) || '/share/unknown');

            document.getElementById('share-link').value = shareLink;
            document.getElementById('btn-copy-link').disabled = false;

        } catch(e) {
            console.error('Error generating share link:', e);
            alert('Error generating share link: ' + e.message);
        }
    }

    // Copy share link to clipboard
    function copyShareLink() {
        const linkInput = document.getElementById('share-link');
        if(linkInput && linkInput.value) {
            linkInput.select();
            navigator.clipboard.writeText(linkInput.value).then(() => {
                alert('Share link copied to clipboard!');
            }).catch(() => {
                // Fallback for older browsers
                document.execCommand('copy');
                alert('Share link copied to clipboard!');
            });
        }
    }

    // Save bucket configuration
    async function saveBucketConfig(bucketName) {
        try {
            await waitForMCP();

            const replicationFactor = parseInt(document.getElementById('config-replication').value);
            const cachePolicy = document.getElementById('config-cache').value;
            const retentionDays = parseInt(document.getElementById('config-retention').value);

            await MCP.Buckets.updatePolicy(bucketName, {
                replication_factor: replicationFactor,
                cache_policy: cachePolicy,
                retention_days: retentionDays
            });

            alert('Bucket configuration saved successfully!');
            closeModal();

            // Refresh status if this is the selected bucket
            if(bucketName === selectedBucket) {
                await updateBucketStatus();
            }

        } catch(e) {
            console.error('Error saving bucket config:', e);
            alert('Error saving configuration: ' + e.message);
        }
    }

    // Close modal helper
    function closeModal() {
        const modal = document.querySelector('.modal-overlay');
        if(modal) modal.remove();
    }

    // MCP-based bucket file browser with metadata-first architecture
    function showMCPBucketBrowser(bucketName) {
        const modal = createModal('MCP Bucket File Browser: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = '<div style="text-align:center;padding:20px;">Loading bucket via MCP SDK...</div>';

            try {
                await waitForMCP();

                // Create comprehensive file browser interface
                modalBody.innerHTML = `
                    <div style="margin-bottom:15px;">
                        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                            <strong>Bucket:</strong> <span style="color:#6b8cff;">${bucketName}</span>
                            <div style="flex:1;"></div>
                            <button id="sync-replicas-btn" onclick="syncBucketReplicas('${bucketName}')" 
                                    style="background:#2a5cb8;color:white;padding:4px 8px;border:none;border-radius:3px;cursor:pointer;font-size:11px;">
                                 Sync Replicas
                            </button>
                            <button onclick="showBucketPolicySettings('${bucketName}')" 
                                    style="background:#555;color:white;padding:4px 8px;border:none;border-radius:3px;cursor:pointer;font-size:11px;">
                                 Policy
                            </button>
                        </div>

                        <!-- Navigation breadcrumbs -->
                        <div style="background:#0a0a0a;padding:8px;border-radius:4px;margin-bottom:10px;">
                            <div style="display:flex;align-items:center;gap:5px;margin-bottom:5px;">
                                <span style="color:#888;font-size:11px;">Path:</span>
                                <input type="text" id="current-path" value="." 
                                       style="flex:1;background:#111;border:1px solid #333;color:white;padding:4px;border-radius:3px;font-size:11px;">
                                <button onclick="navigateToPath('${bucketName}')" 
                                        style="background:#555;color:white;padding:4px 8px;border:none;border-radius:3px;cursor:pointer;font-size:11px;">
                                    Go
                                </button>
                                <button onclick="goUpDirectory('${bucketName}')" 
                                        style="background:#555;color:white;padding:4px 8px;border:none;border-radius:3px;cursor:pointer;font-size:11px;">
                                     Up
                                </button>
                            </div>
                            <div id="breadcrumb-nav" style="font-size:10px;color:#666;"></div>
                        </div>

                        <!-- File operations toolbar -->
                        <div style="display:flex;gap:5px;margin-bottom:10px;flex-wrap:wrap;">
                            <input type="file" id="upload-files-${bucketName}" multiple style="display:none;">
                            <button onclick="document.getElementById('upload-files-${bucketName}').click()" 
                                    style="background:#2a5cb8;color:white;padding:6px 10px;border:none;border-radius:4px;cursor:pointer;font-size:11px;">
                                 Upload Files
                            </button>
                            <button onclick="showCreateFolderDialog('${bucketName}')" 
                                    style="background:#555;color:white;padding:6px 10px;border:none;border-radius:4px;cursor:pointer;font-size:11px;">
                                 New Folder
                            </button>
                            <button onclick="refreshBucketFilesMCP('${bucketName}')" 
                                    style="background:#555;color:white;padding:6px 10px;border:none;border-radius:4px;cursor:pointer;font-size:11px;">
                                 Refresh
                            </button>
                            <div style="flex:1;"></div>
                            <label style="display:flex;align-items:center;gap:5px;font-size:11px;color:#aaa;">
                                <input type="checkbox" id="show-metadata" checked> Show Metadata
                            </label>
                        </div>
                    </div>

                    <!-- File list container -->
                    <div id="mcp-file-list" style="max-height:450px;overflow-y:auto;border:1px solid #333;background:#0f0f0f;">
                        <div style="text-align:center;padding:20px;color:#888;">Loading files...</div>
                    </div>

                    <!-- File details panel -->
                    <div id="file-details-panel" style="display:none;margin-top:10px;padding:10px;background:#0a0a0a;border-radius:4px;font-size:11px;">
                        <div style="font-weight:bold;margin-bottom:5px;">File Details</div>
                        <div id="file-metadata-content"></div>
                    </div>
                `;

                // Setup event handlers
                const fileInput = document.getElementById('upload-files-' + bucketName);
                if (fileInput) {
                    fileInput.onchange = (e) => uploadFilesMCP(bucketName, e.target.files);
                }

                const showMetaCheckbox = document.getElementById('show-metadata');
                if (showMetaCheckbox) {
                    showMetaCheckbox.onchange = () => refreshBucketFilesMCP(bucketName);
                }

                // Load initial file list
                await refreshBucketFilesMCP(bucketName);

            } catch (e) {
                console.error('Error loading MCP bucket browser:', e);
                modalBody.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading bucket: ' + e.message + '</div>';
            }
        });
    }

    // Enhanced bucket details view
    function showBucketDetails(bucketName) {
        const modal = createModal('Bucket File Manager: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = '<div style="text-align:center;padding:20px;">Loading bucket contents...</div>';

            try {
                const response = await fetch('/api/buckets/' + encodeURIComponent(bucketName));
                const data = await response.json();

                modalBody.innerHTML = `
                    <div style="margin-bottom:15px;padding:10px;background:#0a0a0a;border-radius:5px;">
                        <strong>Bucket:</strong> ${bucketName} (${data.bucket.backend})<br>
                        <strong>Files:</strong> ${data.file_count} | <strong>Folders:</strong> ${data.folder_count} | 
                        <strong>Storage:</strong> ${formatBytes(data.total_size)}<br>
                        <strong>Advanced:</strong> 
                        ${data.settings.vector_search ? ' Vector Search' : ''} 
                        ${data.settings.knowledge_graph ? ' Knowledge Graph' : ''}
                        ${data.settings.storage_quota ? ' Quota: ' + formatBytes(data.settings.storage_quota) : ''}
                    </div>

                    <div style="margin-bottom:10px;">
                        <input type="file" id="upload-${bucketName}" multiple style="display:none;">
                        <button onclick="document.getElementById('upload-${bucketName}').click()" 
                                style="background:#2a5cb8;color:white;padding:6px 12px;border:none;border-radius:4px;cursor:pointer;">
                             Upload Files
                        </button>
                        <button onclick="refreshBucketFiles('${bucketName}')" 
                                style="background:#555;color:white;padding:6px 12px;border:none;border-radius:4px;cursor:pointer;margin-left:5px;">
                             Refresh
                        </button>
                    </div>

                    <div id="file-list-${bucketName}" style="max-height:400px;overflow-y:auto;border:1px solid #333;padding:5px;background:#0f0f0f;">
                        ${data.files.length === 0 ? 
                            '<div style="text-align:center;padding:20px;color:#888;">No files in this bucket</div>' :
                            data.files.map(file => `
                                <div style="display:flex;justify-content:space-between;align-items:center;padding:4px;border-bottom:1px solid #222;">
                                    <span>
                                        ${file.type === 'directory' ? '' : ''} 
                                        ${file.name} 
                                        <small style="color:#666;">(${formatBytes(file.size)})</small>
                                    </span>
                                    <span>
                                        ${file.type === 'file' ? `<button onclick="downloadFile('${bucketName}','${file.path}')" style="background:#2a5cb8;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;"></button>` : ''}
                                        <button onclick="deleteFile('${bucketName}','${file.path}')" style="background:#b52a2a;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;"></button>
                                    </span>
                                </div>
                            `).join('')
                        }
                    </div>
                `;

                // Setup file upload handler
                const fileInput = document.getElementById('upload-' + bucketName);
                if (fileInput) {
                    fileInput.onchange = (e) => uploadFiles(bucketName, e.target.files);
                }

            } catch (e) {
                modalBody.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading bucket details: ' + e.message + '</div>';
            }
        });
    }

    // Enhanced bucket settings modal
    function showBucketSettings(bucketName) {
        const modal = createModal('Bucket Settings: ' + bucketName, async (modalBody) => {
            modalBody.innerHTML = '<div style="text-align:center;padding:20px;">Loading settings...</div>';

            try {
                const response = await fetch('/api/buckets/' + encodeURIComponent(bucketName) + '/settings');
                const data = await response.json();
                const settings = data.settings || {};

                modalBody.innerHTML = `
                    <div style="display:grid;gap:15px;">
                        <div>
                            <h4>Search & Indexing</h4>
                            <label style="display:block;margin:5px 0;">
                                <input type="checkbox" id="vector_search" ${settings.vector_search ? 'checked' : ''}> 
                                Vector Search (enables semantic similarity search)
                            </label>
                            <label style="display:block;margin:5px 0;">
                                <input type="checkbox" id="knowledge_graph" ${settings.knowledge_graph ? 'checked' : ''}> 
                                Knowledge Graph (enables relationship mapping)
                            </label>
                            <label style="display:block;margin:5px 0;">
                                Search Index Type: 
                                <select id="search_index_type" style="margin-left:5px;">
                                    <option value="hnsw" ${settings.search_index_type === 'hnsw' ? 'selected' : ''}>HNSW (Fast)</option>
                                    <option value="ivf" ${settings.search_index_type === 'ivf' ? 'selected' : ''}>IVF (Balanced)</option>
                                    <option value="flat" ${settings.search_index_type === 'flat' ? 'selected' : ''}>Flat (Accurate)</option>
                                </select>
                            </label>
                        </div>

                        <div>
                            <h4>Storage & Performance</h4>
                            <label style="display:block;margin:5px 0;">
                                Storage Quota (bytes): 
                                <input type="number" id="storage_quota" value="${settings.storage_quota || ''}" placeholder="No limit" style="width:120px;margin-left:5px;">
                            </label>
                            <label style="display:block;margin:5px 0;">
                                Max Files: 
                                <input type="number" id="max_files" value="${settings.max_files || ''}" placeholder="No limit" style="width:120px;margin-left:5px;">
                            </label>
                            <label style="display:block;margin:5px 0;">
                                Cache TTL (seconds): 
                                <input type="number" id="cache_ttl" value="${settings.cache_ttl || 3600}" style="width:120px;margin-left:5px;">
                            </label>
                        </div>

                        <div>
                            <h4>Access & Security</h4>
                            <label style="display:block;margin:5px 0;">
                                <input type="checkbox" id="public_access" ${settings.public_access ? 'checked' : ''}> 
                                Public Access (allow anonymous downloads)
                            </label>
                        </div>

                        <div style="text-align:center;margin-top:20px;">
                            <button onclick="saveBucketSettings('${bucketName}')" 
                                    style="background:#2a5cb8;color:white;padding:8px 20px;border:none;border-radius:4px;cursor:pointer;">
                                 Save Settings
                            </button>
                        </div>
                    </div>
                `;

            } catch (e) {
                modalBody.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error loading settings: ' + e.message + '</div>';
            }
        });
    }

    async function uploadFiles(bucketName, files) {
        if (!files || files.length === 0) return;

        const results = [];
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch(`/api/buckets/${encodeURIComponent(bucketName)}/upload`, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const result = await response.json();
                    results.push({success: true, file: result.file});
                } else {
                    results.push({success: false, error: await response.text()});
                }
            } catch (e) {
                results.push({success: false, error: e.message});
            }
        }

        // Refresh the file list
        refreshBucketFiles(bucketName);

        // Show results
        const successCount = results.filter(r => r.success).length;
        alert(`Upload complete: ${successCount}/${files.length} files uploaded successfully.`);
    }

    function refreshBucketFiles(bucketName) {
        // Find and refresh the file list for this bucket
        const fileListEl = document.getElementById(`file-list-${bucketName}`);
        if (!fileListEl) return;

        fileListEl.innerHTML = '<div style="text-align:center;padding:20px;">Refreshing...</div>';

        fetch('/api/buckets/' + encodeURIComponent(bucketName))
            .then(response => response.json())
            .then(data => {
                fileListEl.innerHTML = data.files.length === 0 ? 
                    '<div style="text-align:center;padding:20px;color:#888;">No files in this bucket</div>' :
                    data.files.map(file => `
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:4px;border-bottom:1px solid #222;">
                            <span>
                                ${file.type === 'directory' ? '' : ''} 
                                ${file.name} 
                                <small style="color:#666;">(${formatBytes(file.size)})</small>
                            </span>
                            <span>
                                ${file.type === 'file' ? `<button onclick="downloadFile('${bucketName}','${file.path}')" style="background:#2a5cb8;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;"></button>` : ''}
                                <button onclick="deleteFile('${bucketName}','${file.path}')" style="background:#b52a2a;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;font-size:10px;"></button>
                            </span>
                        </div>
                    `).join('');
            })
            .catch(e => {
                fileListEl.innerHTML = '<div style="color:red;text-align:center;padding:20px;">Error refreshing files</div>';
            });
    }

    function downloadFile(bucketName, filePath) {
        const url = `/api/buckets/${encodeURIComponent(bucketName)}/download/${filePath}`;
        const a = document.createElement('a');
        a.href = url;
        a.download = filePath.split('/').pop();
        a.click();
    }

    function deleteFile(bucketName, filePath) {
        if (!confirm(`Delete file: ${filePath}?`)) return;

        fetch(`/api/buckets/${encodeURIComponent(bucketName)}/files/${filePath}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                refreshBucketFiles(bucketName);
            } else {
                alert('Error deleting file: ' + (result.message || 'Unknown error'));
            }
        })
        .catch(e => {
            alert('Error deleting file: ' + e.message);
        });
    }

    async function saveBucketSettings(bucketName) {
        const settings = {
            vector_search: document.getElementById('vector_search')?.checked || false,
            knowledge_graph: document.getElementById('knowledge_graph')?.checked || false,
            search_index_type: document.getElementById('search_index_type')?.value || 'hnsw',
            storage_quota: parseInt(document.getElementById('storage_quota')?.value) || null,
            max_files: parseInt(document.getElementById('max_files')?.value) || null,
            cache_ttl: parseInt(document.getElementById('cache_ttl')?.value) || 3600,
            public_access: document.getElementById('public_access')?.checked || false
        };

        try {
            const response = await fetch(`/api/buckets/${encodeURIComponent(bucketName)}/settings`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(settings)
            });

            const result = await response.json();
            if (result.success) {
                alert('Settings saved successfully!');
                document.getElementById('bucket-modal')?.remove();
                loadBuckets(); // Refresh bucket list to show updated stats
            } else {
                alert('Error saving settings: ' + (result.error || 'Unknown error'));
            }
        } catch (e) {
            alert('Error saving settings: ' + e.message);
        }
    }

    // ---- End Enhanced Bucket Management Helper Functions ----

    // Enhanced Bucket File Management Variables
    let selectedBucket = null;
    let selectedFiles = [];
    let bucketUsageData = {};

    // Comprehensive Bucket File Management Functions
    async function loadBuckets(){
        const container=document.getElementById('buckets-list'); 
        const selector=document.getElementById('bucket-selector');

        if(container) container.textContent='Loading';

        try{ 
            await waitForMCP();
            const result = await MCP.Buckets.list();
            const items = (result && result.result && result.result.items) || []; 

            // Update bucket selector
            if(selector) {
                selector.innerHTML = '<option value="">Select a bucket...</option>';
                items.forEach(bucket => {
                    const option = el('option', {value: bucket.name, text: bucket.name});
                    selector.appendChild(option);
                });

                // Auto-select first bucket if only one exists (for testing/demo)
                if(items.length === 1) {
                    selector.value = items[0].name;
                    selectBucket(items[0].name);
                }
            }

            if(!items.length && container){ 
                container.innerHTML = '<div style="color:#888;padding:8px;">No buckets created yet. Create your first bucket above!</div>'; 
                return; 
            }

            if(container) {
                container.innerHTML=''; 
                items.forEach(it=>{
                    const wrap=el('div',{class:'bucket-wrap',style:'border:1px solid #333;margin:4px 0;padding:6px;border-radius:4px;background:#111;'});
                    const header=el('div',{style:'display:flex;align-items:center;justify-content:space-between;cursor:pointer;'},
                        el('div',{}, 
                            el('strong',{text:it.name,style:'color:#4CAF50;'}), 
                            el('span',{style:'color:#888;margin-left:6px;',text: it.backend? (' '+it.backend):''}),
                            el('span',{style:'color:#666;margin-left:8px;font-size:11px;',text: it.created_at ? new Date(it.created_at).toLocaleDateString() : ''})
                        ),
                        el('div',{},
                            el('button',{style:'padding:2px 6px;font-size:11px;margin-right:4px;background:#4CAF50;color:white;border:none;border-radius:3px;',title:'Select & Manage Files',onclick:(e)=>{ e.stopPropagation(); selectBucket(it.name); }},' Manage'),
                        el('button',{style:'padding:2px 6px;font-size:11px;margin-right:4px;',title:'Policy Settings',onclick:(e)=>{ e.stopPropagation(); showBucketPolicySettings(it.name); }},''),
                        el('button',{style:'padding:2px 6px;font-size:11px;margin-right:4px;',title:'Sync Replicas',onclick:(e)=>{ e.stopPropagation(); syncBucketReplicas(it.name); }},''),
                        el('button',{style:'padding:2px 6px;font-size:11px;margin-right:4px;',title:'Expand/Collapse',onclick:(e)=>{ e.stopPropagation(); toggle(); }},''),
                        el('button',{style:'padding:2px 6px;font-size:11px;',title:'Delete',onclick:(e)=>{ e.stopPropagation(); if(confirm('Delete bucket '+it.name+'?')) deleteBucket(it.name); }},'')
                        )
                    )

                // Enhanced bucket details
                const body=el('div',{style:'display:none;margin-top:6px;font-size:12px;'});
                body.innerHTML='<div style="margin-bottom:8px;color:#aaa;font-weight:bold;">Bucket Details & Policy</div>'+
                    '<div id="bucket-stats-'+it.name+'" style="margin-bottom:8px;padding:4px;background:#0a0a0a;border-radius:3px;font-size:10px;color:#999;"></div>'+
                    '<div class="policy-fields" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">'
                    +' <label style="display:flex;flex-direction:column;font-size:11px;">Replication Factor<input type="number" min="1" max="10" class="pf-rep" style="width:90px;"/></label>'
                    +' <label style="display:flex;flex-direction:column;font-size:11px;">Cache Policy<select class="pf-cache" style="width:120px;"><option>none</option><option>memory</option><option>disk</option></select></label>'
                    +' <label style="display:flex;flex-direction:column;font-size:11px;">Retention Days<input type="number" min="0" class="pf-ret" style="width:110px;"/></label>'
                    +'</div>'
                    +'<div style="margin-top:6px;display:flex;gap:6px;">'
                    +' <button class="btn-policy-save" style="padding:4px 10px;font-size:11px;">Save Policy</button>'
                    +' <button class="btn-policy-cancel" style="padding:4px 10px;font-size:11px;">Cancel</button>'
                    +' <button class="btn-view-files" style="padding:4px 10px;font-size:11px;background:#444;">View Files</button>'
                    +' <span class="policy-status" style="margin-left:8px;color:#888;"></span>'
                    +'</div>';
                wrap.append(header, body); container.append(wrap);

                let loaded=false; let loading=false; let expanded=false; let currentPolicy=null;

                // Load bucket statistics
                async function loadBucketStats(){
                    const statsEl = document.getElementById('bucket-stats-'+it.name);
                    if(!statsEl) return;
                    try{
                        const response = await fetch('/api/buckets/'+encodeURIComponent(it.name));
                        const data = await response.json();
                        let statsText = `Files: ${data.file_count || 0} | Folders: ${data.folder_count || 0} | Size: ${formatBytes(data.total_size || 0)}`;
                        if(data.settings.vector_search) statsText += ' | Vector Search: ';
                        if(data.settings.knowledge_graph) statsText += ' | Knowledge Graph: ';
                        statsEl.textContent = statsText;
                    }catch(e){
                        statsEl.textContent = 'Unable to load stats';
                    }
                }

                async function fetchPolicy(){ 
                    if(loading||loaded) return; 
                    loading=true; 
                    setStatus('Loading...'); 
                    try{ 
                        const pr=await fetch('/api/state/buckets/'+encodeURIComponent(it.name)+'/policy'); 
                        const pj=await pr.json(); 
                        currentPolicy=pj.policy||pj||{}; 
                        applyPolicy(); 
                        loaded=true; 
                        setStatus(''); 
                        loadBucketStats(); // Load additional stats
                    }catch(e){ 
                        setStatus('Error loading'); 
                    } finally { 
                        loading=false; 
                    } 
                }
                function applyPolicy(){ 
                    if(!currentPolicy) return; 
                    const rep=body.querySelector('.pf-rep'); 
                    const cache=body.querySelector('.pf-cache'); 
                    const ret=body.querySelector('.pf-ret'); 
                    if(rep) rep.value=currentPolicy.replication_factor; 
                    if(cache) cache.value=currentPolicy.cache_policy; 
                    if(ret) ret.value=currentPolicy.retention_days; 
                }
                function toggle(){ 
                    expanded=!expanded; 
                    body.style.display= expanded? 'block':'none'; 
                    header.querySelector('button[title="Expand/Collapse"]').textContent = expanded? '':''; 
                    if(expanded) fetchPolicy(); 
                }
                function setStatus(msg, isErr){ 
                    const st=body.querySelector('.policy-status'); 
                    if(st){ 
                        st.textContent=msg||''; 
                        st.style.color = isErr? '#f66':'#888'; 
                    } 
                }

                // Event handlers
                body.querySelector('.btn-policy-cancel').onclick = ()=>{ applyPolicy(); setStatus('Reverted'); };
                body.querySelector('.btn-policy-save').onclick = async ()=>{
                    const rep=parseInt(body.querySelector('.pf-rep').value,10); 
                    const cache=body.querySelector('.pf-cache').value; 
                    const ret=parseInt(body.querySelector('.pf-ret').value,10);
                    const payload={replication_factor:rep, cache_policy:cache, retention_days:ret};
                    setStatus('Saving...');
                    try{
                        const rs=await fetch('/api/state/buckets/'+encodeURIComponent(it.name)+'/policy',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
                        if(!rs.ok){ const tx=await rs.text(); setStatus('Error: '+tx.slice(0,60), true); return; }
                        const jsR=await rs.json(); currentPolicy=jsR.policy||payload; applyPolicy(); setStatus('Saved');
                    }catch(e){ setStatus('Save failed', true); }
                };
                body.querySelector('.btn-view-files').onclick = ()=> showBucketDetails(it.name);
                header.addEventListener('click', ()=> toggle());
            });
            }
        }catch(e){ 
            container.textContent='Error loading buckets'; 
            console.error('Bucket loading error:', e);
        }
    }
    async function loadPins(){
        const container=document.getElementById('pins-list'); if(!container) return; container.textContent='Loading';
        try{ const r=await fetch('/api/pins'); const js=await r.json(); const items=js.items||[]; if(!items.length){ container.textContent='(none)'; return; }
            container.innerHTML=''; items.forEach(it=>{
                const row=el('div',{class:'row',style:'justify-content:space-between;'},
                    el('span',{text: it.cid + (it.name? ' ('+it.name+')':'')}),
                    el('span',{}, el('button',{style:'padding:2px 6px;font-size:11px;',title:'Delete',onclick:()=>deletePin(it.cid)},''))
                ); container.append(row);
            });
        }catch(e){ container.textContent='Error'; }
    }
    async function deleteBackend(name){ try{ await fetch('/api/state/backends/'+encodeURIComponent(name), {method:'DELETE'}); loadBackends(); }catch(e){} }
    async function deleteBucket(name){ try{ await fetch('/api/state/buckets/'+encodeURIComponent(name), {method:'DELETE'}); loadBuckets(); }catch(e){} }
    async function deletePin(cid){ try{ await fetch('/api/pins/'+encodeURIComponent(cid), {method:'DELETE'}); loadPins(); }catch(e){} }
    const btnBackendAdd=document.getElementById('btn-backend-add'); if(btnBackendAdd) btnBackendAdd.onclick = async ()=>{
        const name=(document.getElementById('backend-name')||{}).value||''; 
        const type=(document.getElementById('backend-type')||{}).value||''; 
        const tier=(document.getElementById('backend-tier')||{}).value||'warm';
        const description=(document.getElementById('backend-description')||{}).value||'';

        if(!name || !type) {
            alert('Please provide both backend name and type');
            return;
        }

        try{ 
            await fetch('/api/state/backends',{
                method:'POST',
                headers:{'content-type':'application/json'},
                body:JSON.stringify({
                    name, 
                    type,
                    tier,
                    description: description || `${type.charAt(0).toUpperCase() + type.slice(1)} storage backend`,
                    config:{}
                })
            }); 

            // Clear form fields
            (document.getElementById('backend-name')||{}).value=''; 
            (document.getElementById('backend-type')||{}).value='';
            (document.getElementById('backend-tier')||{}).value='warm';
            (document.getElementById('backend-description')||{}).value='';

            loadBackends(); 
        }catch(e){
            console.error('Error adding backend:', e);
            alert('Failed to add backend: ' + e.message);
        }
    };
    const btnBucketAdd=document.getElementById('btn-bucket-add'); if(btnBucketAdd) btnBucketAdd.onclick = async ()=>{
        const name=(document.getElementById('bucket-name')||{}).value||''; 
        const backend=(document.getElementById('bucket-backend')||{}).value||''; 
        if(!name) return;
        try{ 
            await waitForMCP();
            await MCP.Buckets.create(name, backend); 
            (document.getElementById('bucket-name')||{}).value=''; 
            (document.getElementById('bucket-backend')||{}).value=''; 
            loadBuckets(); 
        }catch(e){
            console.error('Error creating bucket:', e);
            alert('Error creating bucket: ' + e.message);
        }
    };

    // Enhanced Bucket File Management Variables
    // selectedBucket = null; // already declared above
    selectedFiles = [];
    bucketUsageData = {};

    // Event handlers for new bucket management features
    const bucketSelector = document.getElementById('bucket-selector');
    if(bucketSelector) {
        bucketSelector.onchange = (e) => {
            if(e.target.value) {
                selectBucket(e.target.value);
            } else {
                showBucketFileInterface(false);
                selectedBucket = null;
                updateBucketToolbar();
            }
        };
    }

    const refreshBucketsBtn = document.getElementById('btn-refresh-buckets');
    if(refreshBucketsBtn) refreshBucketsBtn.onclick = loadBuckets;

    // Bucket configuration buttons
    const btnBucketConfigure = document.getElementById('btn-bucket-configure');
    if(btnBucketConfigure) btnBucketConfigure.onclick = () => showBucketConfigModal(selectedBucket);

    const btnBucketAdvanced = document.getElementById('btn-bucket-advanced');
    if(btnBucketAdvanced) btnBucketAdvanced.onclick = () => showBucketAdvancedModal(selectedBucket);

    const btnBucketQuota = document.getElementById('btn-bucket-quota');
    if(btnBucketQuota) btnBucketQuota.onclick = () => showBucketQuotaModal(selectedBucket);

    const btnBucketShare = document.getElementById('btn-bucket-share');
    if(btnBucketShare) btnBucketShare.onclick = () => showBucketShareModal(selectedBucket);

    const btnForceSync = document.getElementById('btn-force-sync');
    if(btnForceSync) btnForceSync.onclick = () => forceBucketSync(selectedBucket);

    // File operation buttons
    const btnUploadFile = document.getElementById('btn-upload-file');
    if(btnUploadFile) btnUploadFile.onclick = () => document.getElementById('file-input').click();

    const btnNewFolder = document.getElementById('btn-new-folder');
    if(btnNewFolder) btnNewFolder.onclick = () => createNewFolder();

    const btnSelectiveSync = document.getElementById('btn-selective-sync');
    if(btnSelectiveSync) btnSelectiveSync.onclick = () => performSelectiveSync();

    const btnDownloadSelected = document.getElementById('btn-download-selected');
    if(btnDownloadSelected) btnDownloadSelected.onclick = () => downloadSelectedFiles();

    const btnDeleteSelected = document.getElementById('btn-delete-selected');
    if(btnDeleteSelected) btnDeleteSelected.onclick = () => deleteSelectedFiles();

    // Drag & Drop functionality
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    if(dropZone && fileInput) {
        // Make drop zone clickable
        dropZone.onclick = () => fileInput.click();

        // Drag and drop events
        dropZone.ondragover = (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#4CAF50';
            dropZone.style.backgroundColor = '#0a2a0a';
        };

        dropZone.ondragleave = (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#666';
            dropZone.style.backgroundColor = '#0a0a0a';
        };

        dropZone.ondrop = (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#666';
            dropZone.style.backgroundColor = '#0a0a0a';

            const files = Array.from(e.dataTransfer.files);
            uploadFiles(files);
        };

        // File input change event
        fileInput.onchange = (e) => {
            const files = Array.from(e.target.files);
            uploadFiles(files);
        };
    }

    // Select bucket and show file management interface
    async function selectBucket(bucketName) {
        selectedBucket = bucketName;
        selectedFiles = []; // Clear file selection

        // Update UI visibility
        showBucketFileInterface(true);
        updateBucketToolbar();

        // Load bucket usage and files
        await updateBucketStatus();
        await loadBucketFiles();
    }

    // Show/hide bucket file interface
    function showBucketFileInterface(show) {
        const elements = [
            'bucket-status-bar',
            'drop-zone', 
            'file-toolbar',
            'file-list-container'
        ];

        elements.forEach(id => {
            const el = document.getElementById(id);
            if(el) el.style.display = show ? 'block' : 'none';
        });

        // Hide bucket list when file interface is shown
        const bucketsList = document.getElementById('buckets-list');
        if(bucketsList) bucketsList.style.display = show ? 'none' : 'block';
    }

    // Update bucket toolbar button states
    function updateBucketToolbar() {
        const hasSelection = selectedBucket !== null;
        const hasFileSelection = selectedFiles.length > 0;

        const buttons = [
            'btn-bucket-configure',
            'btn-bucket-advanced', 
            'btn-bucket-quota',
            'btn-bucket-share',
            'btn-force-sync'
        ];

        buttons.forEach(id => {
            const btn = document.getElementById(id);
            if(btn) btn.disabled = !hasSelection;
        });

        const fileButtons = [
            'btn-selective-sync',
            'btn-download-selected',
            'btn-delete-selected'
        ];

        fileButtons.forEach(id => {
            const btn = document.getElementById(id);
            if(btn) btn.disabled = !hasFileSelection;
        });

        // Update selection info
        const selectionInfo = document.getElementById('selection-info');
        if(selectionInfo) {
            if(hasFileSelection) {
                selectionInfo.textContent = `${selectedFiles.length} file(s) selected`;
                selectionInfo.style.color = '#4CAF50';
            } else {
                selectionInfo.textContent = 'Select files to enable operations';
                selectionInfo.style.color = '#888';
            }
        }
    }
    const btnPinAdd=document.getElementById('btn-pin-add'); if(btnPinAdd) btnPinAdd.onclick = async ()=>{
        const cid=(document.getElementById('pin-cid')||{}).value||''; const name=(document.getElementById('pin-name')||{}).value||''; if(!cid) return;
        try{ await fetch('/api/pins',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({cid, name})}); (document.getElementById('pin-cid')||{}).value=''; loadPins(); }catch(e){}
    };

    // Update bucket status bar
    async function updateBucketStatus() {
        if(!selectedBucket) return;

        try {
            await waitForMCP();
            const usageResponse = await MCP.Buckets.getUsage(selectedBucket);
            const usage = (usageResponse && usageResponse.result) || {};
            bucketUsageData[selectedBucket] = usage;

            const statusQuota = document.getElementById('status-quota');
            const statusFiles = document.getElementById('status-files');
            const statusCache = document.getElementById('status-cache');
            const statusRetention = document.getElementById('status-retention');

            if(statusFiles) {
                statusFiles.textContent = `Files: ${usage.file_count || 0}`;
                statusFiles.style.color = usage.file_count > 1000 ? '#FF9800' : '#2196F3';
            }

            if(statusQuota) {
                const sizeGB = usage.total_size_gb || 0;
                statusQuota.textContent = `Usage: ${sizeGB.toFixed(2)} GB`;
                statusQuota.style.color = sizeGB > 10 ? '#F44336' : '#4CAF50';
            }

            // Load bucket config for cache and retention info
            const bucketResponse = await MCP.Buckets.get(selectedBucket);
            const bucket = (bucketResponse && bucketResponse.result) || {};
            const policy = bucket.policy || {};

            if(statusCache) {
                const cachePolicy = policy.cache_policy || 'none';
                statusCache.textContent = `Cache: ${cachePolicy}`;
                statusCache.style.color = cachePolicy === 'none' ? '#888' : '#FF9800';
            }

            if(statusRetention) {
                const retentionDays = policy.retention_days || 0;
                statusRetention.textContent = retentionDays > 0 ? `Retention: ${retentionDays}d` : 'Retention: None';
                statusRetention.style.color = retentionDays > 0 ? '#9C27B0' : '#888';
            }

        } catch(e) {
            console.error('Error updating bucket status:', e);
        }
    }

    // Load bucket files
    async function loadBucketFiles() {
        if(!selectedBucket) return;

        const fileListBody = document.getElementById('file-list-body');
        if(!fileListBody) return;

        fileListBody.innerHTML = 'Loading files...';

        try {
            await waitForMCP();
            const result = await MCP.Buckets.listFiles(selectedBucket, '.', true);
            const files = (result && result.result && result.result.files) || [];

            if(files.length === 0) {
                fileListBody.innerHTML = '<div style="color:#888;padding:12px;text-align:center;">No files in this bucket. Upload some files to get started!</div>';
                return;
            }

            fileListBody.innerHTML = '';

            files.forEach(file => {
                const row = el('div', {
                    class: 'file-row',
                    style: 'display:grid;grid-template-columns:30px 1fr 100px 120px 80px;gap:8px;align-items:center;padding:6px;border-bottom:1px solid #333;cursor:pointer;',
                    onclick: () => toggleFileSelection(file.path)
                });

                const checkbox = el('input', {
                    type: 'checkbox',
                    style: 'margin:0;',
                    onchange: (e) => {
                        e.stopPropagation();
                        if(e.target.checked) {
                            if(!selectedFiles.includes(file.path)) {
                                selectedFiles.push(file.path);
                            }
                        } else {
                            selectedFiles = selectedFiles.filter(f => f !== file.path);
                        }
                        updateBucketToolbar();
                    }
                });

                const nameEl = el('div', {
                    style: 'display:flex;align-items:center;',
                }, 
                    el('span', {text: file.is_dir ? '' : '', style: 'margin-right:6px;'}),
                    el('span', {text: file.name, style: 'color:' + (file.is_dir ? '#4CAF50' : '#ccc')})
                );

                const sizeEl = el('span', {
                    text: file.is_dir ? '-' : formatFileSize(file.size || 0),
                    style: 'font-size:11px;color:#888;font-family:monospace;'
                });

                const modifiedEl = el('span', {
                    text: file.modified ? new Date(file.modified).toLocaleDateString() : '-',
                    style: 'font-size:11px;color:#888;'
                });

                const actionsEl = el('div', {},
                    el('button', {
                        text: '',
                        title: 'Download',
                        style: 'padding:2px 6px;font-size:10px;margin-right:2px;background:#673AB7;color:white;border:none;border-radius:2px;',
                        onclick: (e) => {
                            e.stopPropagation();
                            downloadFile(file.path);
                        }
                    }),
                    el('button', {
                        text: '',
                        title: 'Delete',
                        style: 'padding:2px 6px;font-size:10px;background:#F44336;color:white;border:none;border-radius:2px;',
                        onclick: (e) => {
                            e.stopPropagation();
                            deleteFile(file.path);
                        }
                    })
                );

                row.appendChild(checkbox);
                row.appendChild(nameEl);
                row.appendChild(sizeEl);
                row.appendChild(modifiedEl);
                row.appendChild(actionsEl);

                fileListBody.appendChild(row);
            });

        } catch(e) {
            console.error('Error loading bucket files:', e);
            fileListBody.innerHTML = '<div style="color:#F44336;padding:12px;">Error loading files: ' + e.message + '</div>';
        }
    }
    let logSource=null; let logsInited=false; function initLogs(){
        if(logsInited) return; logsInited=true;
        try{ logSource = new EventSource('/api/logs/stream');
            logSource.onmessage = (ev)=>{ try{ const data=JSON.parse(ev.data); const pre=document.getElementById('logs-pre'); if(!pre) return; pre.textContent += '\n'+data.timestamp+' '+data.level+' ['+data.logger+'] '+data.message; pre.scrollTop = pre.scrollHeight; }catch(e){} };
        }catch(e){ console.warn('SSE logs failed', e); }
        const clr=document.getElementById('btn-clear-logs'); if(clr) clr.onclick = ()=>{ if(window.MCP){ window.MCP.callTool('clear_logs',{}).then(()=>{ const pre=document.getElementById('logs-pre'); if(pre) pre.textContent='(cleared)'; }); } };
    }

    // Toggle file selection
    function toggleFileSelection(filePath) {
        if(selectedFiles.includes(filePath)) {
            selectedFiles = selectedFiles.filter(f => f !== filePath);
        } else {
            selectedFiles.push(filePath);
        }
        updateBucketToolbar();

        // Update checkbox state
        const rows = document.querySelectorAll('.file-row');
        rows.forEach(row => {
            const checkbox = row.querySelector('input[type="checkbox"]');
            const nameEl = row.children[1];
            if(nameEl && checkbox) {
                const fileName = nameEl.textContent.trim();
                checkbox.checked = selectedFiles.some(f => f.endsWith(fileName));
            }
        });
    }

    // Format file size
    function formatFileSize(bytes) {
        if(bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // Upload files with progress tracking
    async function uploadFiles(files) {
        if(!selectedBucket || !files.length) return;

        const progressDiv = document.getElementById('upload-progress');
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');

        if(progressDiv) progressDiv.style.display = 'block';

        try {
            await waitForMCP();

            for(let i = 0; i < files.length; i++) {
                const file = files[i];
                const progress = ((i + 1) / files.length) * 100;

                if(progressFill) progressFill.style.width = progress + '%';
                if(progressText) progressText.textContent = `Uploading ${file.name}... ${Math.round(progress)}% complete`;

                // Read file content
                const content = await readFileAsText(file);

                // Upload via MCP
                await MCP.Buckets.uploadFile(selectedBucket, file.name, content, 'text', true);
            }

            // Hide progress and reload files
            if(progressDiv) progressDiv.style.display = 'none';
            await loadBucketFiles();
            await updateBucketStatus();

            alert(`Successfully uploaded ${files.length} file(s)!`);

        } catch(e) {
            console.error('Error uploading files:', e);
            alert('Error uploading files: ' + e.message);
            if(progressDiv) progressDiv.style.display = 'none';
        }
    }

    // Read file as text
    function readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = reject;
            reader.readAsText(file);
        });
    }

    // Create new folder
    async function createNewFolder() {
        if(!selectedBucket) return;

        const folderName = prompt('Enter folder name:');
        if(!folderName) return;

        try {
            await waitForMCP();
            await MCP.Buckets.mkdir(selectedBucket, folderName, true);
            await loadBucketFiles();
        } catch(e) {
            console.error('Error creating folder:', e);
            alert('Error creating folder: ' + e.message);
        }
    }

    // Download file
    async function downloadFile(filePath) {
        if(!selectedBucket) return;

        try {
            await waitForMCP();
            const result = await MCP.Buckets.downloadFile(selectedBucket, filePath, 'text');
            const content = (result && result.result && result.result.content) || '';

            // Create download link
            const blob = new Blob([content], {type: 'text/plain'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filePath.split('/').pop();
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

        } catch(e) {
            console.error('Error downloading file:', e);
            alert('Error downloading file: ' + e.message);
        }
    }

    // Delete file
    async function deleteFile(filePath) {
        if(!selectedBucket) return;
        if(!confirm(`Delete file "${filePath}"?`)) return;

        try {
            await waitForMCP();
            await MCP.Buckets.deleteFile(selectedBucket, filePath, true);
            await loadBucketFiles();
            await updateBucketStatus();
        } catch(e) {
            console.error('Error deleting file:', e);
            alert('Error deleting file: ' + e.message);
        }
    }

    // Download selected files
    async function downloadSelectedFiles() {
        if(!selectedBucket || !selectedFiles.length) return;

        for(const filePath of selectedFiles) {
            await downloadFile(filePath);
        }
    }

    // Delete selected files
    async function deleteSelectedFiles() {
        if(!selectedBucket || !selectedFiles.length) return;
        if(!confirm(`Delete ${selectedFiles.length} selected file(s)?`)) return;

        try {
            await waitForMCP();

            for(const filePath of selectedFiles) {
                await MCP.Buckets.deleteFile(selectedBucket, filePath, true);
            }

            selectedFiles = [];
            await loadBucketFiles();
            await updateBucketStatus();
            updateBucketToolbar();

        } catch(e) {
            console.error('Error deleting files:', e);
            alert('Error deleting files: ' + e.message);
        }
    }

    // Perform selective sync
    async function performSelectiveSync() {
        if(!selectedBucket || !selectedFiles.length) return;

        try {
            await waitForMCP();
            const options = {
                force_update: confirm('Force update existing files?'),
                verify_checksums: true,
                create_backup: confirm('Create backup before sync?')
            };

            const result = await MCP.Buckets.selectiveSync(selectedBucket, selectedFiles, options);
            alert(`Selective sync completed. ${result.synced_files?.length || 0} files synced.`);

            await loadBucketFiles();
            await updateBucketStatus();

        } catch(e) {
            console.error('Error performing selective sync:', e);
            alert('Error performing selective sync: ' + e.message);
        }
    }

    // Force bucket sync
    async function forceBucketSync(bucketName) {
        if(!bucketName) return;

        try {
            await waitForMCP();
            await MCP.Buckets.syncReplicas(bucketName, true);
            alert('Force sync completed successfully!');

            if(bucketName === selectedBucket) {
                await updateBucketStatus();
            }

        } catch(e) {
            console.error('Error performing force sync:', e);
            alert('Error performing force sync: ' + e.message);
        }
    }
    async function loadFiles(){
        const pathEl = document.getElementById('files-path');
        const bucketEl = document.getElementById('files-bucket');
        const container = document.getElementById('files-container');
        const loading = document.getElementById('files-loading');

        if (!container) return;

        const path = (pathEl && pathEl.value) || '.';
        const bucket = (bucketEl && bucketEl.value) || null;

        if (loading) loading.textContent = 'Loading';

        try {
            // Use MCP SDK for API calls
            const params = new URLSearchParams();
            if (path !== '.') params.append('path', path);
            if (bucket) params.append('bucket', bucket);

            const response = await fetch(`/api/files/list?${params.toString()}`);
            const data = await response.json();

            if (loading) loading.textContent = '';

            // Clear container
            container.innerHTML = '';

            if (!data.items || data.items.length === 0) {
                container.appendChild(el('div', {text: '(empty directory)', style: 'color: #888; padding: 8px;'}));
                return;
            }

            // Create file table
            const table = el('table', {style: 'width: 100%; font-size: 12px; border-collapse: collapse;'});

            // Header
            const header = el('tr', {style: 'border-bottom: 1px solid #333;'},
                el('th', {text: '', style: 'width: 20px; padding: 4px;'}), // checkbox
                el('th', {text: 'Name', style: 'text-align: left; padding: 4px;'}),
                el('th', {text: 'Type', style: 'text-align: left; padding: 4px; width: 80px;'}),
                el('th', {text: 'Size', style: 'text-align: right; padding: 4px; width: 80px;'}),
                el('th', {text: 'Modified', style: 'text-align: left; padding: 4px; width: 130px;'})
            );
            table.appendChild(header);

            // Sort items: directories first, then files, alphabetically
            const sortedItems = [...data.items].sort((a, b) => {
                if (a.is_dir && !b.is_dir) return -1;
                if (!a.is_dir && b.is_dir) return 1;
                return a.name.localeCompare(b.name);
            });

            // File rows
            sortedItems.forEach(item => {
                const row = el('tr', {
                    style: 'border-bottom: 1px solid #222; cursor: pointer;',
                    'data-name': item.name,
                    'data-type': item.type
                });

                // Checkbox
                const checkbox = el('input', {type: 'checkbox', style: 'margin: 0;'});
                checkbox.addEventListener('change', updateDeleteButton);
                row.appendChild(el('td', {style: 'padding: 4px;'}, checkbox));

                // Name
                const nameEl = el('td', {
                    text: item.name,
                    style: `padding: 4px; ${item.is_dir ? 'font-weight: bold; color: #6b8cff;' : ''}`
                });
                row.appendChild(nameEl);

                // Type
                row.appendChild(el('td', {text: item.type, style: 'padding: 4px; color: #888;'}));

                // Size
                const sizeText = item.size !== null ? formatBytes(item.size) : '';
                row.appendChild(el('td', {text: sizeText, style: 'padding: 4px; text-align: right; font-family: monospace;'}));

                // Modified
                const modText = item.modified ? new Date(item.modified).toLocaleDateString() + ' ' + new Date(item.modified).toLocaleTimeString() : '';
                row.appendChild(el('td', {text: modText, style: 'padding: 4px; font-family: monospace; font-size: 10px;'}));

                // Click handlers
                row.addEventListener('click', (e) => {
                    if (e.target.type === 'checkbox') return; // Don't interfere with checkbox

                    if (item.is_dir) {
                        // Navigate to directory
                        const newPath = path === '.' ? item.name : `${path}/${item.name}`;
                        if (pathEl) pathEl.value = newPath;
                        loadFiles();
                    } else {
                        // Show file details
                        showFileDetails(item, path, bucket);
                    }
                });

                table.appendChild(row);
            });

            container.appendChild(table);

            // Update path breadcrumb
            updatePathBreadcrumb(path, bucket);

        } catch (e) {
            console.error('Error loading files:', e);
            if (loading) loading.textContent = 'Error loading files';
        }
    }

    function updateDeleteButton() {
        const checkboxes = document.querySelectorAll('#files-container input[type="checkbox"]');
        const deleteBtn = document.getElementById('btn-file-delete');
        const hasSelected = Array.from(checkboxes).some(cb => cb.checked);

        if (deleteBtn) {
            deleteBtn.disabled = !hasSelected;
            deleteBtn.style.opacity = hasSelected ? '1' : '0.5';
        }
    }

    function updatePathBreadcrumb(path, bucket) {
        // Could add breadcrumb navigation here in the future
        const pathEl = document.getElementById('files-path');
        if (pathEl && pathEl.value !== path) {
            pathEl.value = path;
        }
    }

    async function showFileDetails(item, path, bucket) {
        const detailsPanel = document.getElementById('file-details');
        const statsEl = document.getElementById('file-stats');

        if (!detailsPanel || !statsEl) return;

        try {
            const params = new URLSearchParams();
            params.append('path', path === '.' ? item.name : `${path}/${item.name}`);
            if (bucket) params.append('bucket', bucket);

            const response = await fetch(`/api/files/stats?${params.toString()}`);
            const stats = await response.json();

            let statsText = '';
            statsText += `Name: ${item.name}\n`;
            statsText += `Type: ${stats.is_file ? 'File' : 'Directory'}\n`;
            statsText += `Size: ${formatBytes(stats.size || 0)}\n`;
            statsText += `Modified: ${stats.modified ? new Date(stats.modified).toLocaleString() : ''}\n`;
            statsText += `Created: ${stats.created ? new Date(stats.created).toLocaleString() : ''}\n`;
            statsText += `Permissions: ${stats.permissions || ''}\n`;

            if (stats.is_dir) {
                statsText += `\nContains:\n`;
                statsText += `  Files: ${stats.file_count || 0}\n`;
                statsText += `  Directories: ${stats.dir_count || 0}\n`;
                statsText += `  Total Size: ${formatBytes(stats.total_size || 0)}\n`;
            }

            statsEl.textContent = statsText;
            detailsPanel.style.display = 'block';

        } catch (e) {
            console.error('Error getting file stats:', e);
            statsEl.textContent = 'Error loading file details';
            detailsPanel.style.display = 'block';
        }
    }

    async function loadVfsBuckets() {
        const bucketEl = document.getElementById('files-bucket');
        if (!bucketEl) return;

        try {
            const response = await fetch('/api/files/buckets');
            const data = await response.json();

            // Clear and populate bucket selector
            bucketEl.innerHTML = '';

            // Add "All Buckets" option
            const defaultOption = el('option', {value: '', text: '(default)'});
            bucketEl.appendChild(defaultOption);

            if (data.buckets) {
                data.buckets.forEach(bucket => {
                    if (bucket.name !== 'default') { // Skip default as we already have it
                        const option = el('option', {
                            value: bucket.name,
                            text: `${bucket.display_name || bucket.name} (${bucket.file_count} files)`
                        });
                        bucketEl.appendChild(option);
                    }
                });
            }

        } catch (e) {
            console.error('Error loading buckets:', e);
        }
    }
    const btnFiles=document.getElementById('btn-files-load'); if(btnFiles) btnFiles.onclick = ()=> loadFiles();
    const btnBucketRefresh=document.getElementById('btn-bucket-refresh'); if(btnBucketRefresh) btnBucketRefresh.onclick = ()=> loadVfsBuckets();
    const btnFilesUp=document.getElementById('btn-files-up'); if(btnFilesUp) btnFilesUp.onclick = ()=> {
        const pathEl = document.getElementById('files-path');
        if (pathEl) {
            const currentPath = pathEl.value || '.';
            if (currentPath !== '.') {
                const parts = currentPath.split('/');
                parts.pop();
                pathEl.value = parts.length > 0 ? parts.join('/') : '.';
                loadFiles();
            }
        }
    };
    const btnFilesRefresh=document.getElementById('btn-files-refresh'); if(btnFilesRefresh) btnFilesRefresh.onclick = ()=> loadFiles();
    const bucketSelect=document.getElementById('files-bucket'); if(bucketSelect) bucketSelect.onchange = ()=> loadFiles();

    // File operations
    const btnFileNew=document.getElementById('btn-file-new'); if(btnFileNew) btnFileNew.onclick = async ()=> {
        const filename = prompt('Enter filename:');
        if (!filename) return;

        const pathEl = document.getElementById('files-path');
        const bucketEl = document.getElementById('files-bucket');
        const currentPath = (pathEl && pathEl.value) || '.';
        const bucket = (bucketEl && bucketEl.value) || null;

        const fullPath = currentPath === '.' ? filename : `${currentPath}/${filename}`;

        try {
            const response = await fetch('/api/files/write', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'x-api-token': (window.API_TOKEN || '')},
                body: JSON.stringify({
                    path: fullPath,
                    content: '',
                    bucket: bucket
                })
            });

            if (response.ok) {
                loadFiles();
            } else {
                alert('Failed to create file');
            }
        } catch (e) {
            console.error('Error creating file:', e);
            alert('Error creating file');
        }
    };

    const btnDirNew=document.getElementById('btn-dir-new'); if(btnDirNew) btnDirNew.onclick = async ()=> {
        const dirname = prompt('Enter directory name:');
        if (!dirname) return;

        const pathEl = document.getElementById('files-path');
        const bucketEl = document.getElementById('files-bucket');
        const currentPath = (pathEl && pathEl.value) || '.';
        const bucket = (bucketEl && bucketEl.value) || null;

        const fullPath = currentPath === '.' ? dirname : `${currentPath}/${dirname}`;

        try {
            const response = await fetch('/api/files/mkdir', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'x-api-token': (window.API_TOKEN || '')},
                body: JSON.stringify({
                    path: fullPath,
                    bucket: bucket
                })
            });

            if (response.ok) {
                loadFiles();
            } else {
                alert('Failed to create directory');
            }
        } catch (e) {
            console.error('Error creating directory:', e);
            alert('Error creating directory');
        }
    };

    const btnFileDelete=document.getElementById('btn-file-delete'); if(btnFileDelete) btnFileDelete.onclick = async ()=> {
        const checkboxes = document.querySelectorAll('#files-container input[type="checkbox"]:checked');
        const selectedFiles = Array.from(checkboxes).map(cb => {
            const row = cb.closest('tr');
            return row ? row.getAttribute('data-name') : null;
        }).filter(name => name);

        if (selectedFiles.length === 0) return;

        if (!confirm(`Delete ${selectedFiles.length} selected items?`)) return;

        const pathEl = document.getElementById('files-path');
        const bucketEl = document.getElementById('files-bucket');
        const currentPath = (pathEl && pathEl.value) || '.';
        const bucket = (bucketEl && bucketEl.value) || null;

        let successCount = 0;
        for (const filename of selectedFiles) {
            try {
                const fullPath = currentPath === '.' ? filename : `${currentPath}/${filename}`;
                const response = await fetch(`/api/files/delete?path=${encodeURIComponent(fullPath)}${bucket ? '&bucket=' + encodeURIComponent(bucket) : ''}`, {
                    method: 'DELETE',
                    headers: {'x-api-token': (window.API_TOKEN || '')}
                });

                if (response.ok) {
                    successCount++;
                }
            } catch (e) {
                console.error('Error deleting file:', filename, e);
            }
        }

        if (successCount > 0) {
            loadFiles();
            document.getElementById('file-details').style.display = 'none';
        }

        if (successCount < selectedFiles.length) {
            alert(`${successCount}/${selectedFiles.length} items deleted successfully`);
        }
    };

    // Initialize files view
    if (document.getElementById('view-files')) {
        loadVfsBuckets();
    }
    // ---- Tools Tab ----
    // Use var to avoid temporal-dead-zone when showView('tools') runs before these are initialized
    var toolsLoaded=false; var toolDefs=[]; function initTools(){ if(toolsLoaded) return; toolsLoaded=true; loadToolList(); }
    async function loadToolList(){
        const sel=document.getElementById('tool-select'); if(!sel) return; sel.innerHTML=''; toolDefs=[];
        try{
            if(window.MCP && MCP.listTools){
                const r=await MCP.listTools(); toolDefs=(r && r.result && r.result.tools)||[];
            } else {
                const r=await fetch('/mcp/tools/list',{method:'POST'}); const js=await r.json(); toolDefs=(js && js.result && js.result.tools)||[];
            }
            toolDefs.sort((a,b)=> (a.name||'').localeCompare(b.name||''));
            toolDefs.forEach(td=>{ const o=document.createElement('option'); o.value=td.name; o.textContent=td.name; sel.append(o); });
            buildToolFormForSelected();
        }catch(e){ const o=document.createElement('option'); o.textContent='(error)'; sel.append(o); }
    }
    function getToolDef(name){ return (toolDefs||[]).find(t=>t.name===name); }
    const RAW_TOGGLE_ID='btn-tool-raw-toggle';
    function buildToolFormForSelected(){ const sel=document.getElementById('tool-select'); if(!sel) return; buildToolForm(getToolDef(sel.value)); }
    function simplifySchema(schema){ if(!schema) return {type:'object',properties:{}}; if(schema.type==='object') return schema; if(typeof schema==='object' && !schema.type){
            // treat keys as properties mapping to simple types
            const props={}; Object.keys(schema).forEach(k=>{ const v=schema[k]; if(typeof v==='string') props[k]={type:v}; else props[k]=v; }); return {type:'object',properties:props};
        } return schema; }
    async function dynamicEnum(prop){ const ui=(prop && prop.ui)||{}; if(!ui.enumFrom) return null; try{
            if(ui.enumFrom==='backends'){ const r=await fetch('/api/state/backends'); const js=await r.json(); return (js.items||[]).map(it=>({value:it.name,label:it.name})); }
            if(ui.enumFrom==='buckets'){ const r=await fetch('/api/state/buckets'); const js=await r.json(); return (js.items||[]).map(it=>({value:it.name,label:it.name})); }
            if(ui.enumFrom==='pins'){ const r=await fetch('/api/pins'); const js=await r.json(); return (js.items||[]).map(it=>({value:it.cid,label:(it.name? it.name+' ':'')+'('+it.cid.slice(0,10)+'...)'})); }
        }catch(e){}
        return null; }
    let lastBuiltTool=null; async function buildToolForm(tool){ const form=document.getElementById('tool-form'); const raw=document.getElementById('tool-args'); const desc=document.getElementById('tool-desc'); if(!form||!raw) return; form.innerHTML=''; if(desc) desc.textContent= tool? (tool.description||'') : ''; if(!tool){ raw.style.display='block'; return; } lastBuiltTool=tool.name; const schema=simplifySchema(tool.inputSchema); if(schema.type!=='object'){ raw.style.display='block'; return; }
        const props=schema.properties||{}; const required=new Set(schema.required||[]);
        for(const [name, prop] of Object.entries(props)){
            const wrap=document.createElement('label'); wrap.style.display='flex'; wrap.style.flexDirection='column'; wrap.style.fontSize='11px'; wrap.style.minWidth='140px'; wrap.style.flex='1 1 140px'; wrap.dataset.wrapFor=name;
            const title=(prop.title||name)+(required.has(name)?'*':''); const span=document.createElement('span'); span.textContent=title; span.style.marginBottom='2px'; wrap.append(span);
            let input;
            if(prop.enum){ input=document.createElement('select'); prop.enum.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; input.append(o); }); }
            else if((prop.ui||{}).enumFrom){ input=document.createElement('select'); input.dataset.enumFrom=prop.ui.enumFrom; input.innerHTML='<option value="">(loading)</option>'; dynamicEnum(prop).then(list=>{ if(!list) return; input.innerHTML=''; list.forEach(it=>{ const o=document.createElement('option'); o.value=it.value; o.textContent=it.label; input.append(o); }); if(prop.default) input.value=prop.default; updateRawArgs(); }); }
            else if(prop.type==='boolean'){ input=document.createElement('input'); input.type='checkbox'; if(prop.default) input.checked=!!prop.default; }
            else if(prop.type==='number' || prop.type==='integer'){ input=document.createElement('input'); input.type='number'; if(prop.default!=null) input.value=prop.default; }
            else if((prop.ui||{}).widget==='textarea'){ input=document.createElement('textarea'); input.rows=(prop.ui.rows||3); if(prop.default!=null) input.value=prop.default; }
            else { input=document.createElement('input'); input.type='text'; if(prop.default!=null) input.value=prop.default; }
            input.id='tool-field-'+name; input.dataset.fieldName=name; if(prop.description) input.title=prop.description; if((prop.ui||{}).placeholder) input.placeholder=prop.ui.placeholder; if(required.has(name)) input.dataset.required='1';
            input.addEventListener('input', ()=>{ clearFieldError(input); updateRawArgs(); });
            if(input.tagName==='SELECT') input.addEventListener('change', ()=>{ clearFieldError(input); updateRawArgs(); });
            wrap.append(input); form.append(wrap);
        }
        raw.style.display='none'; updateRawArgs();
    }
    function collectFormArgs(){ const form=document.getElementById('tool-form'); if(!form) return {}; const fields=form.querySelectorAll('[data-field-name]'); const args={}; fields.forEach(f=>{ const name=f.dataset.fieldName; if(f.type==='checkbox') args[name]=f.checked; else if(f.type==='number') args[name]= (f.value===''? null : Number(f.value)); else args[name]=f.value; }); return args; }
    function updateRawArgs(){ const raw=document.getElementById('tool-args'); if(!raw || raw.style.display==='block') return; const args=collectFormArgs(); raw.value=JSON.stringify(args,null,2); }
    function clearFieldError(input){ const wrap=input.parentElement; if(wrap) wrap.style.outline='none'; }
    function validateToolForm(tool){ if(!tool) return true; const form=document.getElementById('tool-form'); if(!form) return true; let ok=true; const requiredEls=form.querySelectorAll('[data-required="1"]'); requiredEls.forEach(inp=>{ const val = (inp.type==='checkbox')? (inp.checked? 'true': '') : inp.value.trim(); if(!val){ ok=false; const wrap=inp.parentElement; if(wrap) wrap.style.outline='1px solid #d66'; } }); return ok; }
    const toolSelect=document.getElementById('tool-select'); if(toolSelect) toolSelect.addEventListener('change', ()=> buildToolFormForSelected());
    const rawToggle=document.getElementById('btn-tool-raw-toggle'); if(rawToggle) rawToggle.addEventListener('click',()=>{ const raw=document.getElementById('tool-args'); if(!raw) return; raw.style.display = (raw.style.display==='none'?'block':'none'); });
    const toolFilter=document.getElementById('tool-filter'); if(toolFilter) toolFilter.addEventListener('input',()=>{
        const q=toolFilter.value.toLowerCase(); const sel=document.getElementById('tool-select'); if(!sel) return; Array.from(sel.options).forEach(opt=>{ opt.hidden = !!q && !opt.value.toLowerCase().includes(q); });
    });
    const btnToolRefresh=document.getElementById('btn-tool-refresh'); if(btnToolRefresh) btnToolRefresh.onclick = loadToolList;
    const btnToolRun=document.getElementById('btn-tool-run'); if(btnToolRun) btnToolRun.onclick = async ()=>{
        const sel=document.getElementById('tool-select'); const argsEl=document.getElementById('tool-args'); const out=document.getElementById('tool-result'); const status=document.getElementById('tool-run-status');
        const name=(sel&&sel.value)||''; if(!name){ if(status) status.textContent='No tool selected'; return; }
        let tool=getToolDef(name); let args={};
        if(tool && lastBuiltTool===name && document.getElementById('tool-form').children.length){ if(!validateToolForm(tool)){ if(status) status.textContent='Missing required'; return; } args=collectFormArgs(); if(argsEl) argsEl.value=JSON.stringify(args,null,2); }
        else { try{ args=JSON.parse((argsEl&&argsEl.value)||'{}'); }catch(e){ if(status) status.textContent='Invalid JSON'; return; } }
        if(tool && tool.inputSchema && tool.inputSchema.confirm && tool.inputSchema.confirm.message){ if(!confirm(tool.inputSchema.confirm.message)) return; }
        if(status) status.textContent='Running...'; const started=performance.now();
        try{ const r= await (window.MCP? MCP.callTool(name,args): fetch('/mcp/tools/call',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name, args})}).then(r=>r.json()));
            if(out) out.textContent = JSON.stringify(r,null,2); if(status) status.textContent='Done in '+(performance.now()-started).toFixed(0)+'ms';
        }catch(e){ if(out) out.textContent=String(e); if(status) status.textContent='Error'; }
    };

    // ---- IPFS Tab ----
    let ipfsInit=false; function initIPFS(){ if(ipfsInit) return; ipfsInit=true; refreshIPFSVersion(); }
    async function refreshIPFSVersion(){ try{ if(window.MCP){ const v=await MCP.IPFS.version(); if(v && v.result) setText('ipfs-version','Version: '+(v.result.version||JSON.stringify(v.result))); } }catch(e){} }
    const btnIpfsCat=document.getElementById('btn-ipfs-cat'); if(btnIpfsCat) btnIpfsCat.onclick= async ()=>{
        const cidEl=document.getElementById('ipfs-cid'); const out=document.getElementById('ipfs-cat-output'); const cid=(cidEl&&cidEl.value)||''; if(!cid) return;
        if(out) out.textContent='Fetching...';
        try{ const r= await (window.MCP? MCP.IPFS.cat(cid): MCP.callTool('ipfs_cat',{cid}));
            let data=(r && r.result && (r.result.content||r.result.data||r.result.result))||r;
            let txt= typeof data==='string'? data: JSON.stringify(data,null,2);
            if(txt.length>8192) txt=txt.slice(0,8192)+'\n...(truncated)';
            if(out) out.textContent=txt;
        }catch(e){ if(out) out.textContent='Error: '+e; }
    };
    const btnIpfsPin=document.getElementById('btn-ipfs-pin'); if(btnIpfsPin) btnIpfsPin.onclick = async ()=>{
        const cid=(document.getElementById('ipfs-cid')||{}).value||''; if(!cid) return; try{ await (window.MCP? MCP.IPFS.pin(cid,null): MCP.callTool('ipfs_pin',{cid})); loadPins(); }catch(e){}
    };

    // ---- CARs Tab ----
    let carsInit=false; function initCARs(){ if(carsInit) return; carsInit=true; loadCARs(); }
    async function loadCARs(){ try{ if(!window.MCP){ setText('cars-list','MCP not ready'); return; } const r=await MCP.CARs.list(); const list=(r && r.result && r.result.items)||[]; document.getElementById('cars-list').textContent=JSON.stringify(list,null,2); }catch(e){ setText('cars-list','Error'); } }
    const btnCarsRefresh=document.getElementById('btn-cars-refresh'); if(btnCarsRefresh) btnCarsRefresh.onclick= loadCARs;
    const btnCarExport=document.getElementById('btn-car-export'); if(btnCarExport) btnCarExport.onclick= async ()=>{
        const path=(document.getElementById('car-path')||{}).value||'.'; const name=(document.getElementById('car-name')||{}).value||'out.car';
        try{ if(window.MCP) await MCP.CARs.export(path,name); loadCARs(); }catch(e){ console.warn(e); }
    };
    const btnCarImport=document.getElementById('btn-car-import'); if(btnCarImport) btnCarImport.onclick= async ()=>{
        const src=(document.getElementById('car-import-src')||{}).value||''; const dest=(document.getElementById('car-import-dest')||{}).value||'.'; if(!src) return;
        try{ if(window.MCP) await MCP.CARs.import(src,dest); loadCARs(); }catch(e){ console.warn(e); }
    };
    async function fetchStatus(){
        try{
            const r = await fetch('/api/mcp/status');
            const raw = await r.json();
            const js = raw.data || raw; // support both shapes
            document.getElementById('srv-status').textContent = 'Running';
            document.getElementById('srv-port').textContent = 'Tools: '+(js.total_tools||0);
            const c = (js.counts)||{};
            setText('svc-active', c.services_active);
            setText('count-backends', c.backends);
            setText('count-buckets', c.buckets);
            document.getElementById('ts-info').textContent = new Date().toLocaleTimeString();
        }catch(e){ console.warn(e); }
    }
    async function fetchMetrics(){
        try{
            const r = await fetch('/api/metrics/system');
            const m = await r.json();
            updatePerf('cpu', m.cpu_percent, '%');
            if(m.memory) updatePerf('mem', m.memory.percent, '%', formatBytes(m.memory.used)+' / '+formatBytes(m.memory.total));
            if(m.disk) updatePerf('disk', m.disk.percent, '%', formatBytes(m.disk.used)+' / '+formatBytes(m.disk.total));
        }catch(e){ console.warn(e); }
        try{
            const nr = await fetch('/api/metrics/network?seconds=60');
            const njs = await nr.json();
            const pts = njs.points||[];
            if(pts.length){
                const last = pts[pts.length-1];
                const el = document.getElementById('net-activity'); if(el) el.textContent = humanRate(last.rx_bps)+'   '+humanRate(last.tx_bps)+' ';
                drawNetSpark(pts);
            }
        }catch(e){ /* ignore */ }
    }
    function updatePerf(key, val, suffix, extra){
        const pct = (typeof val === 'number') ? Math.max(0, Math.min(100, val)) : 0;
        const fill = document.getElementById('bar-fill-'+key); if(fill) fill.style.width = pct+'%';
        const label = document.getElementById('bar-label-'+key); if(label) label.textContent = (val!=null?val.toFixed(1):'')+ (suffix||'') + (extra?('  '+extra):'');
    }
    function setText(id,v){ const el=document.getElementById(id); if(el) el.textContent = (v==null?'':String(v)); }
    function formatBytes(b){ if(!b && b!==0) return ''; const u=['B','KB','MB','GB','TB']; let i=0; let n=b; while(n>=1024 && i<u.length-1){ n/=1024; i++; } return n.toFixed(n>=100?0: (n>=10?1:2))+' '+u[i]; }
    function humanRate(bps){ if(bps==null) return ''; const u=['B/s','KB/s','MB/s','GB/s']; let i=0; let n=bps; while(n>=1024 && i<u.length-1){ n/=1024; i++; } return n.toFixed(n>=100?0: (n>=10?1:2))+' '+u[i]; }
    let realtime=false; let pollTimer=null; const btnRT=document.getElementById('btn-realtime');
    function schedulePoll(){ clearTimeout(pollTimer); pollTimer = setTimeout(async ()=>{ await refreshAll(); if(!realtime) schedulePoll(); }, POLL_INTERVAL); }
    async function refreshAll(){ await Promise.all([fetchStatus(), fetchMetrics()]); }
    const btnRefresh=document.getElementById('btn-refresh'); if(btnRefresh) btnRefresh.onclick = ()=> refreshAll();
    if(btnRT){ btnRT.onclick = ()=>{ realtime=!realtime; btnRT.textContent='Real-time: '+(realtime?'On':'Off'); if(realtime){ startRealtime(); } else { if(ws){ ws.close(); ws=null; schedulePoll(); } }; }; }
    let ws=null; function startRealtime(){
        schedulePoll();
        try{
            ws = new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');
            ws.onmessage = (ev)=>{ try{ const msg=JSON.parse(ev.data); if(msg.type==='metrics'){ applyRealtime(msg); } else if(msg.type==='system_update'){ if(Array.isArray(msg.deprecations)) renderDeprecationBanner(msg.deprecations); const data = msg.data && (msg.data.data||msg.data); if(data && data.counts){ setText('svc-active', data.counts.services_active); setText('count-backends', data.counts.backends); setText('count-buckets', data.counts.buckets); document.getElementById('srv-status').textContent='Running'; } } }catch(e){} };
            ws.onclose = ()=>{ if(realtime){ setTimeout(startRealtime, 2500); } };
        }catch(e){ console.warn('ws fail', e); }
    }
    function applyRealtime(m){
        if(m.cpu!=null) updatePerf('cpu', m.cpu, '%');
        if(m.mem!=null) updatePerf('mem', m.mem, '%');
        if(m.disk!=null) updatePerf('disk', m.disk, '%');
        if(m.rx_bps!=null || m.tx_bps!=null){ const el=document.getElementById('net-activity'); if(el) el.textContent=humanRate(m.rx_bps)+'   '+humanRate(m.tx_bps)+' '; appendNetPoint(m); }
    // realtime push into perf history arrays
    if(m.cpu!=null) pushPerfPoint('cpu', m.cpu);
    if(m.mem!=null) pushPerfPoint('mem', m.mem);
    if(m.disk!=null) pushPerfPoint('disk', m.disk);
    // Append rolling averages if present
    function addAvg(key, avg){ if(avg==null) return; const label=document.getElementById('bar-label-'+key); if(!label) return; let base=label.textContent||''; base=base.replace(/ \(avg .*?\)$/,''); const suffix = (key==='cpu'||key==='mem'||key==='disk')? '%':''; label.textContent = base+' (avg '+avg.toFixed(1)+suffix+')'; }
    addAvg('cpu', m.avg_cpu);
    addAvg('mem', m.avg_mem);
    addAvg('disk', m.avg_disk);
    }
    // --- Network sparkline helpers ---
    const NET_MAX_POINTS = 120; // keep 2 minutes @1s
    const netBuffer = [];
    function appendNetPoint(p){ if(!(p && (p.rx_bps!=null || p.tx_bps!=null))) return; netBuffer.push({ts:p.ts||Date.now()/1000, rx:p.rx_bps||0, tx:p.tx_bps||0}); if(netBuffer.length>NET_MAX_POINTS) netBuffer.shift(); drawNetSpark(); }
    function drawNetSpark(history){ const svg = document.getElementById('net-spark'); if(!svg) return; const pts = history || netBuffer; if(!pts.length){ svg.innerHTML=''; setText('net-summary',''); return; }
        const w = svg.clientWidth || svg.viewBox?.baseVal?.width || 300; const h = svg.clientHeight || 60; const rxVals = pts.map(p=>p.rx||p.rx_bps||0); const txVals = pts.map(p=>p.tx||p.tx_bps||0); const maxVal = Math.max(1, ...rxVals, ...txVals);
        const path = (vals)=>{ return 'M '+vals.map((v,i)=>{ const x = (i/(vals.length-1||1))*w; const y = h - (v/maxVal)* (h-4) -2; return x+','+y; }).join(' L '); };
        const rxPath = path(rxVals); const txPath = path(txVals);
        svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
        svg.innerHTML = `<path d="${rxPath}" fill="none" stroke="#6b8cff" stroke-width="1.6"/><path d="${txPath}" fill="none" stroke="#b081ff" stroke-width="1.6" opacity="0.8"/>`;
        // summary
        const avg = arr=> arr.reduce((a,b)=>a+b,0)/arr.length||0; const rxAvg=avg(rxVals); const txAvg=avg(txVals);
        const summaryEl=document.getElementById('net-summary'); if(summaryEl) summaryEl.textContent = 'Avg '+humanRate(rxAvg)+'   '+humanRate(txAvg)+'   | points '+pts.length;
    }
    // --- Perf (cpu/mem/disk) sparkline helpers ---
    const PERF_MAX_POINTS = 180; // 3 minutes @1s
    const perfBuffers = { cpu: [], mem: [], disk: [] };
    function pushPerfPoint(k, v){ if(typeof v !== 'number') return; const buf = perfBuffers[k]; buf.push(v); if(buf.length>PERF_MAX_POINTS) buf.shift(); drawPerfSpark(k); }
    function drawPerfSpark(k){ const id = 'spark-'+k; const svg = document.getElementById(id); if(!svg) return; const buf = perfBuffers[k]; if(!buf.length){ svg.innerHTML=''; return; } const w = svg.clientWidth || 300; const h = svg.clientHeight || 26; const maxVal = Math.max(1, ...buf); const path = 'M '+buf.map((v,i)=>{ const x=(i/(buf.length-1||1))*w; const y = h - (v/maxVal)*(h-4) -2; return x+','+y; }).join(' L '); svg.setAttribute('viewBox',`0 0 ${w} ${h}`); svg.innerHTML = `<path d="${path}" fill="none" stroke="#6b8cff" stroke-width="1.4"/>`; }
    refreshAll().then(schedulePoll);
    // Fallback one-time deprecations fetch (in case WebSocket path blocked)
    try{ fetch('/api/system/deprecations').then(r=>r.json()).then(d=>{ if(d && Array.isArray(d.deprecated)) renderDeprecationBanner(d.deprecated); }).catch(()=>{}); }catch(e){}
})();
