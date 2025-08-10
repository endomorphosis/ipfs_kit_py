// Static app.js override to avoid string literal formatting issues
(function(){
  function ensureMcp(){ if(!window.mcpClient) throw new Error('MCP client not initialized'); return window.mcpClient; }
  async function rpcTool(name, args){ const c=ensureMcp(); if(c.toolsCall) return c.toolsCall(name,args||{}); if(c.callTool) return c.callTool(name,args||{}); throw new Error('MCP client missing toolsCall'); }
  async function rpcToolsList(){
    const c=ensureMcp();
    var res;
    if(c.toolsList) res = await c.toolsList(); else if(c.listTools) res = await c.listTools(); else throw new Error('MCP client missing toolsList');
    // Normalize to array of tool defs
    if (Array.isArray(res)) return res;
    if (res && Array.isArray(res.tools)) return res.tools;
    if (res && typeof res === 'object') return Object.values(res);
    return [];
  }

  async function refreshLogs(){ try{ const res = await rpcTool('get_logs', {limit:50}); var el=document.getElementById('logs'); if(el){ var lines=(res.logs||[]).map(function(l){return '['+l.timestamp+'] ('+l.component+') '+l.message}); el.textContent = lines.join('\n'); } } catch(e){ console.warn('refreshLogs failed', e); } }
  async function clearLogs(){ try{ await rpcTool('clear_logs', {}); await refreshLogs(); } catch(e){ console.warn('clearLogs failed', e); } }

  var _logsAutoTimer=null; function logsAutoToggle(){ var cb=document.getElementById('logs-auto'); if(!cb) return; if(cb.checked){ if(_logsAutoTimer) return; _logsAutoTimer=setInterval(function(){ refreshLogs(); },1500); } else { if(_logsAutoTimer){ clearInterval(_logsAutoTimer); _logsAutoTimer=null; } } }

  var _logTailTimer=null; function logsSetTail(text){ var el=document.getElementById('log-file-tail'); if(el) el.textContent=text; }
  function logsSelectedPath(){ var sel=document.getElementById('log-file-select'); if(!sel) return null; var opt=sel.options[sel.selectedIndex]; return opt ? (opt.value||opt.textContent) : null; }
  async function logsListFiles(){ try{ var res=await rpcTool('list_log_files', {}); var sel=document.getElementById('log-file-select'); if(!sel) return; sel.innerHTML=''; var files=(res.files||[]).slice().sort(function(a,b){ var ta=a.modified?Date.parse(a.modified):0; var tb=b.modified?Date.parse(b.modified):0; return tb-ta; }); files.forEach(function(f){ var o=document.createElement('option'); o.textContent=f.path; o.value=f.path; sel.appendChild(o); }); if(sel.options.length>0){ sel.selectedIndex=0; try{ await logsTailOnce(); }catch(e){} } } catch(e){ console.warn('logsListFiles', e); } }
  async function logsTailOnce(){ try{ var p=logsSelectedPath(); var _limEl=document.getElementById('log-tail-limit'); var limit=parseInt((_limEl&&_limEl.value)?_limEl.value:'200',10); if(!p){ logsSetTail('No file selected'); return; } var res=await rpcTool('tail_file', {path:p, limit:limit}); if(res && res.lines){ logsSetTail(res.lines.join('\n')); } else { logsSetTail(JSON.stringify(res,null,2)); } } catch(e){ console.warn('logsTailOnce', e); } }
  function logsTailStart(){ if(_logTailTimer) return; _logTailTimer=setInterval(function(){ logsTailOnce(); },1500); }
  function logsTailStop(){ if(_logTailTimer){ clearInterval(_logTailTimer); _logTailTimer=null; } }

  function showPanel(name){ var panels=document.querySelectorAll('.panel'); panels.forEach(function(p){ p.classList.remove('active'); }); var el=document.getElementById('panel-'+name); if(el) el.classList.add('active'); }
  // Expose functions for inline onclick handlers
  window.showPanel = showPanel;
  window.loadTools = loadTools;
  window.callSelectedTool = callSelectedTool;
  window.refreshLogs = refreshLogs;
  window.clearLogs = clearLogs;
  window.logsListFiles = logsListFiles;
  window.logsTailOnce = logsTailOnce;
  window.logsTailStart = logsTailStart;
  window.logsTailStop = logsTailStop;
  window.filesList = filesList;
  window.filesRead = filesRead;
  window.filesWrite = filesWrite;
  window.filesResolveBucket = filesResolveBucket;
  window.carsList = carsList;
  window.backendCreate = backendCreate;
  window.backendUpdate = backendUpdate;
  window.backendRemove = backendRemove;
  window.backendShow = backendShow;
  window.backendTest = backendTest;
  window.loadBackends = loadBackends;
  window.loadServices = loadServices;
  window.serviceControl = serviceControl;
  window.carImport = carImport;
  window.carExport = carExport;
  window.carRemove = carRemove;
  window.carImportToBucket = carImportToBucket;
  window.bucketsList = bucketsList;
  window.bucketsCreate = bucketsCreate;
  window.bucketsDelete = bucketsDelete;
  window.pinsList = pinsList;
  window.pinsCreate = pinsCreate;
  window.pinsDelete = pinsDelete;
  window.integrationsLoad = integrationsLoad;
  window.integrationsTestType = integrationsTestType;
  window.integrationsTestName = integrationsTestName;

  var selectedTool=null; async function loadTools(){ try{ var tools=await rpcToolsList(); var ul=document.getElementById('tools-list'); if(!ul) return; ul.innerHTML=''; if(!Array.isArray(tools)) tools=[]; tools.forEach(function(t){ var name=(t&&t.name)?t.name:String(t); var li=document.createElement('li'); li.textContent=name; li.style.cursor='pointer'; li.onclick=function(){ selectedTool=name; var tn=document.getElementById('tool-name'); if(tn) tn.textContent=name; }; ul.appendChild(li); }); } catch(e){ console.warn('loadTools failed', e); } }
  async function callSelectedTool(){ if(!selectedTool) return; var args={}; try{ args=JSON.parse(document.getElementById('tool-args').value||'{}'); }catch(e){} try{ var res=await rpcTool(selectedTool, args); document.getElementById('tool-result').textContent=JSON.stringify(res,null,2); } catch(e){ document.getElementById('tool-result').textContent='Error: '+e; } }

  async function loadBackends(){ try{ var r=await fetch('/api/state/backends'); var j=await r.json(); document.getElementById('backends').textContent=JSON.stringify(j,null,2); } catch(e){ console.warn('loadBackends failed', e); } }
  async function loadServices(){ try{ var r=await fetch('/api/services'); var j=await r.json(); document.getElementById('services').textContent=JSON.stringify(j,null,2); } catch(e){ console.warn('loadServices failed', e); } }

  function getEl(id){ return document.getElementById(id); }
  async function filesList(){ try{ var _fb=getEl('files-bucket'); var bucket=((_fb&&_fb.value)?_fb.value:'').trim(); var _fp=getEl('files-path'); var path=((_fp&&_fp.value)?_fp.value:'').trim(); var res=await rpcTool('list_files', {bucket:bucket, path:path}); getEl('files-list').textContent=JSON.stringify(res,null,2); } catch(e){ console.warn('filesList', e); } }
  async function filesRead(){ try{ var _fb=getEl('files-bucket'); var bucket=((_fb&&_fb.value)?_fb.value:'').trim(); var _fp=getEl('files-path'); var path=((_fp&&_fp.value)?_fp.value:'').trim(); var res=await rpcTool('read_file', {bucket:bucket, path:path}); getEl('files-read').textContent=(res&&res.content)?res.content:JSON.stringify(res,null,2); } catch(e){ console.warn('filesRead', e); } }
  async function filesWrite(){ try{ var _fb=getEl('files-bucket'); var bucket=((_fb&&_fb.value)?_fb.value:'').trim(); var _fp=getEl('files-path'); var path=((_fp&&_fp.value)?_fp.value:'').trim(); var _fc=getEl('files-content'); var content=(_fc&&_fc.value)?_fc.value:''; var res=await rpcTool('write_file', {bucket:bucket, path:path, content:content}); await filesList(); } catch(e){ console.warn('filesWrite', e); } }
  async function filesResolveBucket(){ try{ var _fb=getEl('files-bucket'); var bucket=((_fb&&_fb.value)?_fb.value:'').trim(); if(!bucket){ getEl('files-resolved').textContent='No bucket provided'; return; } var res=await rpcTool('resolve_bucket_path', {bucket:bucket}); getEl('files-resolved').textContent=JSON.stringify(res,null,2); } catch(e){ console.warn('filesResolveBucket', e); } }

  async function carsList(){ try{ var res=await rpcTool('list_cars', {}); getEl('cars-list').textContent=JSON.stringify(res,null,2); } catch(e){ console.warn('carsList', e); } }
  async function backendCreate(){ try{ var _ben=getEl('be-name'); var name=((_ben&&_ben.value)?_ben.value:'').trim(); var _bet=getEl('be-type'); var type=((_bet&&_bet.value)?_bet.value:'').trim(); var _bec=getEl('be-config'); var cfgText=(_bec&&_bec.value)?_bec.value:'{}'; var config={}; try{ config=JSON.parse(cfgText);}catch(e){} var res=await rpcTool('backend_create', {name:name, type:type, config:config}); getEl('backend-op').textContent=JSON.stringify(res,null,2); await loadBackends(); } catch(e){ console.warn('backendCreate', e); } }
  async function backendUpdate(){ try{ var _ben=getEl('be-name'); var name=((_ben&&_ben.value)?_ben.value:'').trim(); var _bec=getEl('be-config'); var cfgText=(_bec&&_bec.value)?_bec.value:'{}'; var config={}; try{ config=JSON.parse(cfgText);}catch(e){} var res=await rpcTool('backend_update', {name:name, config:config}); getEl('backend-op').textContent=JSON.stringify(res,null,2); await loadBackends(); } catch(e){ console.warn('backendUpdate', e); } }
  async function backendRemove(){ try{ var _ben=getEl('be-name'); var name=((_ben&&_ben.value)?_ben.value:'').trim(); var res=await rpcTool('backend_remove', {name:name}); getEl('backend-op').textContent=JSON.stringify(res,null,2); await loadBackends(); } catch(e){ console.warn('backendRemove', e); } }
  async function backendShow(){ try{ var _ben=getEl('be-name'); var name=((_ben&&_ben.value)?_ben.value:'').trim(); var res=await rpcTool('backend_show', {name:name}); getEl('backend-op').textContent=JSON.stringify(res,null,2); } catch(e){ console.warn('backendShow', e); } }
  async function backendTest(){ try{ var _ben=getEl('be-name'); var name=((_ben&&_ben.value)?_ben.value:'').trim(); var res=await fetch('/api/state/backends/'+encodeURIComponent(name)+'/test', {method:'POST'}); var j=await res.json(); getEl('backend-op').textContent=JSON.stringify(j,null,2); } catch(e){ console.warn('backendTest', e); } }

  async function serviceControl(){ try{ var _svn=getEl('svc-name'); var service=((_svn&&_svn.value)?_svn.value:'').trim(); var _sva=getEl('svc-action'); var action=((_sva&&_sva.value)?_sva.value:'start').trim(); var res=await rpcTool('control_service', {service:service, action:action}); getEl('svc-op').textContent=JSON.stringify(res,null,2); await loadServices(); } catch(e){ console.warn('serviceControl', e); } }

  async function carImport(){ try{ var _can=getEl('car-name'); var name=((_can&&_can.value)?_can.value:'').trim(); var _cab=getEl('car-b64'); var b64=(_cab&&_cab.value)?_cab.value:''; var res=await rpcTool('import_car', {name:name, content_b64:b64}); await carsList(); } catch(e){ console.warn('carImport', e); } }
  async function carExport(){ try{ var _can=getEl('car-name'); var name=((_can&&_can.value)?_can.value:'').trim(); var res=await rpcTool('export_car', {name:name}); getEl('cars-export').textContent=JSON.stringify(res,null,2); } catch(e){ console.warn('carExport', e); } }
  async function carRemove(){ try{ var _can=getEl('car-name'); var name=((_can&&_can.value)?_can.value:'').trim(); var res=await rpcTool('remove_car', {name:name}); await carsList(); } catch(e){ console.warn('carRemove', e); } }
  async function carImportToBucket(){ try{ var _can=getEl('car-name'); var name=((_can&&_can.value)?_can.value:'').trim(); var _cbu=getEl('car-bucket'); var bucket=((_cbu&&_cbu.value)?_cbu.value:'').trim(); var _cab=getEl('car-b64'); var b64=(_cab&&_cab.value)?_cab.value:''; var res=await rpcTool('import_car_to_bucket', {name:name, bucket:bucket, content_b64:b64}); getEl('cars-export').textContent=JSON.stringify(res,null,2); } catch(e){ console.warn('carImportToBucket', e); } }

  // Buckets
  async function bucketsList(){ try{ var res=await rpcTool('list_buckets', {}); var el=getEl('buckets-list'); if(el) el.textContent=JSON.stringify(res,null,2); } catch(e){ console.warn('bucketsList', e); } }
  async function bucketsCreate(){ try{ var _bn=getEl('bucket-name'); var name=((_bn&&_bn.value)?_bn.value:'').trim(); var _bb=getEl('bucket-backend'); var backend=((_bb&&_bb.value)?_bb.value:'').trim(); var res=await rpcTool('create_bucket', {name:name, backend:backend}); var op=getEl('buckets-op'); if(op) op.textContent=JSON.stringify(res,null,2); await bucketsList(); } catch(e){ console.warn('bucketsCreate', e); } }
  async function bucketsDelete(){ try{ var _bdn=getEl('bucket-del-name'); var name=((_bdn&&_bdn.value)?_bdn.value:'').trim(); var res=await rpcTool('delete_bucket', {name:name}); var op=getEl('buckets-op'); if(op) op.textContent=JSON.stringify(res,null,2); await bucketsList(); } catch(e){ console.warn('bucketsDelete', e); } }

  // Pins
  async function pinsList(){ try{ var res=await rpcTool('list_pins', {}); var el=getEl('pins-list'); if(el) el.textContent=JSON.stringify(res,null,2); } catch(e){ console.warn('pinsList', e); } }
  async function pinsCreate(){ try{ var _pc=getEl('pin-cid'); var cid=((_pc&&_pc.value)?_pc.value:'').trim(); var _pn=getEl('pin-name'); var name=((_pn&&_pn.value)?_pn.value:'').trim(); var res=await rpcTool('create_pin', {cid:cid, name:name}); var op=getEl('pins-op'); if(op) op.textContent=JSON.stringify(res,null,2); await pinsList(); } catch(e){ console.warn('pinsCreate', e); } }
  async function pinsDelete(){ try{ var _pdc=getEl('pin-del-cid'); var cid=((_pdc&&_pdc.value)?_pdc.value:'').trim(); var res=await rpcTool('delete_pin', {cid:cid}); var op=getEl('pins-op'); if(op) op.textContent=JSON.stringify(res,null,2); await pinsList(); } catch(e){ console.warn('pinsDelete', e); } }

  // Integrations (group backends by type)
  async function integrationsLoad(){
    try{
      var res = await fetch('/api/state/backends');
      var j = await res.json();
      var byType = {};
      var list = (j && j.backends) ? j.backends : [];
      (list||[]).forEach(function(b){
        var t = (b && b.type) ? String(b.type).toLowerCase() : 'unknown';
        if(!byType[t]) byType[t] = [];
        byType[t].push(b.name||b.file||'unknown');
      });
      var el = getEl('integrations-list');
      if(el) el.textContent = JSON.stringify(byType, null, 2);
    }catch(e){ console.warn('integrationsLoad', e); }
  }
  async function integrationsTestType(){
    try{
      var _it=getEl('intg-type'); var t=(_it&&_it.value)?_it.value.trim().toLowerCase():'';
      if(!t){ var op=getEl('integrations-op'); if(op) op.textContent='Type required'; return; }
      var res = await fetch('/api/state/backends'); var j = await res.json();
      var list = (j && j.backends) ? j.backends : [];
      var matches = list.filter(function(b){ return String(b.type||'').toLowerCase()===t; });
      var results = [];
      for (var i=0;i<matches.length;i++){
        try{
          var name = matches[i].name || '';
          var r = await fetch('/api/state/backends/'+encodeURIComponent(name)+'/test', {method:'POST'});
          results.push(await r.json());
        }catch(e){ results.push({success:false,error:String(e)}); }
      }
      var op=getEl('integrations-op'); if(op) op.textContent=JSON.stringify(results,null,2);
    }catch(e){ console.warn('integrationsTestType', e); }
  }
  async function integrationsTestName(){
    try{
      var _in=getEl('intg-name'); var name=(_in&&_in.value)?_in.value.trim():'';
      if(!name){ var op=getEl('integrations-op'); if(op) op.textContent='Name required'; return; }
      var r = await fetch('/api/state/backends/'+encodeURIComponent(name)+'/test', {method:'POST'});
      var j = await r.json();
      var op=getEl('integrations-op'); if(op) op.textContent=JSON.stringify(j,null,2);
    }catch(e){ console.warn('integrationsTestName', e); }
  }

  (async function(){
    try{
      await rpcToolsList();
      await refreshLogs();
      try{ var cb=document.getElementById('logs-auto'); if(cb){ cb.addEventListener('change', logsAutoToggle); } }catch(e){}
      try{ await logsListFiles(); }catch(e){}
      try{ var out=document.getElementById('logs-sse'); if(out && typeof EventSource!=='undefined'){ var es=new EventSource('/api/logs/stream'); es.onmessage=function(ev){ try{ var j=JSON.parse(ev.data); var line='['+((j&&j.timestamp)||'')+'] '+((j&&j.message)||'')+' (count: '+(((j&&j.log_count)!==undefined && (j&&j.log_count)!==null)? j.log_count : '')+')'; out.textContent=(out.textContent? out.textContent+'\n' : '') + line; out.scrollTop=out.scrollHeight; }catch(e){} }; es.onerror=function(){}; } }catch(e){}
      try{ var r=await fetch('/api/mcp/status'); var j=await r.json(); var el=document.getElementById('overview'); if(el) el.textContent=JSON.stringify(j.data||j,null,2); }catch(e){}
      try{ var a=await rpcTool('get_system_analytics', {}); var ela=document.getElementById('overview-analytics'); if(ela) ela.textContent=JSON.stringify(a,null,2); }catch(e){}
      try{ var p=await rpcTool('get_parquet_summary', {}); var elp=document.getElementById('overview-parquet'); if(elp) elp.textContent=JSON.stringify(p,null,2); }catch(e){}
      console.log('MCP ready');
    }catch(e){ console.warn('MCP not ready', e); }
  })();
})();
