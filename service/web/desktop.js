/* Native-only settings, diagnostics, installer updates and error reporting. */
(() => {
 'use strict';
 const $ = id => document.getElementById(id);
 const native = window.framegrabNative;
 let errorData = '';
 let diagnostics = {};
 const redact = s => String(s ?? '')
  .replace(/(authorization\s*[:=]\s*bearer\s+)\S+/ig,'$1[REDACTED]')
  .replace(/(cookie\s*[:=]\s*)[^\r\n]+/ig,'$1[REDACTED]')
  .replace(/([?&](?:token|auth|password|api_key|signature|sig|access_token)=)[^&\s]+/ig,'$1[REDACTED]');
 const showError = (operation, simple, technical='') => {
   const body = [`FrameGrab v${native ? '8.3.0' : 'web'}`,`Time: ${new Date().toISOString()}`,
       `Operation: ${operation}`,`Error: ${simple}`,`Technical details: ${technical}`].join('\n');
   errorData = redact(body);
   $('errorSummary').textContent = simple || 'The operation could not be completed';
   $('errorTechnical').textContent = redact(technical || simple);
   $('errorOverlay').hidden = false;
   $('closeError').focus();
 };
 const closeError = () => { $('errorOverlay').hidden = true; };
 window.FrameGrabDesktopUI = {showError, closeError};
 $('closeError').onclick = closeError;
 $('copyError').onclick = async () => {
   try { if(native) await native.clipboardWrite(errorData); else await navigator.clipboard.writeText(errorData); }
   catch(e) { $('errorSummary').textContent = 'Clipboard unavailable: ' + e.message; }
 };
 $('errorLogs').onclick = async () => {
   try { if(native) await native.openLogs(); else $('errorTechnical').parentElement.open = true; }
   catch(e) {showError('Open logs',e.message);}
 };
 $('errorOverlay').addEventListener('click',e=>{if(e.target===$('errorOverlay'))closeError();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape' && !$('errorOverlay').hidden){e.preventDefault();closeError();}});
 if(!native) {
   $('desktopSettings').hidden = true;
   $('diagnosticSettings').hidden = true;
   return;
 }
 document.documentElement.classList.add('native-desktop');
 let lastUpdate={};
 const applyUpdate = state => {
   if(state.status!==lastUpdate.status&&['available','downloaded'].includes(state.status))window.dispatchEvent(new CustomEvent('framegrab-toast',{detail:state.status==='available'?'Update available: '+state.available:'Update downloaded - ready to install'}));
   lastUpdate=state;
   $('updateStatus').textContent=(state.status||'unconfigured').replace(/-/g,' ');
   $('downloadUpdate').disabled=state.status!=='available';
   $('installUpdate').disabled=state.status!=='downloaded';
   $('updateProgress').hidden=state.status!=='downloading';$('updateProgress').value=state.progress||0;
   $('updateDetails').textContent=[state.available && ('Available: '+state.available),
     state.progress && ('Download: '+Math.round(state.progress)+'%'),
     state.releaseNotes, state.error].filter(Boolean).join(' · ');
 };
 native.version().then(info=>{if(info.justUpdated)window.dispatchEvent(new CustomEvent('framegrab-toast',{detail:'FrameGrab updated to '+info.version}));$('desktopVersion').textContent=info.version+(info.isPackaged?' · Installed':' · Development');});
 native.updateStatus().then(state=>{$('updateFeed').value=state.feed||'';applyUpdate(state);});
 native.onUpdate(applyUpdate);
 $('saveUpdateFeed').onclick=async()=>{
   try { applyUpdate(await native.updateSetFeed($('updateFeed').value.trim())); }
   catch(e){showError('Configure updates',e.message);}
 };
 $('checkUpdates').onclick=async()=>{
   try {applyUpdate(await native.updateCheck());}
   catch(e){showError('Check for Updates',e.message);}
 };
 $('downloadUpdate').onclick=async()=>{
   try {applyUpdate(await native.updateDownload());await native.updateInstall();}
   catch(e){showError('Download update',e.message);}
 };
 $('installUpdate').onclick=async()=>{
   try {await native.updateInstall();}
   catch(e){showError('Install update',e.message);}
 };
 async function runDiagnostics(){
   const head=await native.diagnostics();
   const r=await fetch('/api/diagnostics',{headers:{'X-FrameGrab-Token':native.sessionToken}});
   if(!r.ok)throw Error('Media diagnostics HTTP '+r.status);
   diagnostics={desktop:head,media:await r.json(),timestamp:new Date().toISOString()};
   $('diagnosticsText').textContent=JSON.stringify(diagnostics,null,2);
 }
 $('runDiagnostics').onclick=()=>runDiagnostics().catch(e=>showError('Check Dependencies',e.message));
 $('copyDiagnostics').onclick=async()=>{
   try {if(!Object.keys(diagnostics).length)await runDiagnostics();await native.clipboardWrite(redact(JSON.stringify(diagnostics,null,2)));}
   catch(e){showError('Copy Diagnostics',e.message);}
 };
 $('openLogFolder').onclick=()=>native.openLogs().catch(e=>showError('Open Logs',e.message));
 // Clipboard detection is opt-in: only suggest video URLs when the app gains focus.
 let lastSuggested='';
 window.addEventListener('focus', async()=>{
   try {
     const text=(await native.clipboardRead()).trim();
     if(text===lastSuggested || !/^https?:\/\/\S+$/i.test(text) || !/(youtube|youtu\.be|instagram|tiktok|facebook|twitter|x\.com|vimeo|reddit)/i.test(text))return;
     lastSuggested=text;
     const yes=confirm('A video link is on your clipboard. Paste it into a new download?');
     if(yes){$('newButton').click();$('urlInput').value=text;$('urlInput').dispatchEvent(new Event('input',{bubbles:true}));}
   }catch{}
 });
})();
