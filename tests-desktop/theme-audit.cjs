'use strict';
const {chromium}=require('./qa-playwright.cjs')();
const cp=require('child_process'),path=require('path'),fs=require('fs'),assert=require('assert');
(async()=>{
 const root=path.resolve(__dirname,'..'),out=path.join(root,'.qa-theme-audit');fs.mkdirSync(out,{recursive:true});
 const server=cp.spawn('python',[path.join(root,'service/app.py')],{env:{...process.env,FRAMEGRAB_DATA_DIR:path.join(out,'data'),FRAMEGRAB_TOOLS_DIR:path.join(root,'tools'),FRAMEGRAB_SERVICE_PORT:'8291',FRAMEGRAB_API_TOKEN:'theme-audit'},windowsHide:true,stdio:'ignore'});
 let browser;try{
  for(let i=0;i<100;i++){try{const r=await fetch('http://127.0.0.1:8291/api/state',{headers:{'X-FrameGrab-Token':'theme-audit'}});if(r.ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({channel:'msedge',headless:true});const context=await browser.newContext({viewport:{width:1440,height:1040},extraHTTPHeaders:{'X-FrameGrab-Token':'theme-audit'}});
  await context.addInitScript(()=>{window.framegrabNative={sessionToken:'theme-audit',clipboardRead:async()=>'',clipboardWrite:async()=>true,version:async()=>({version:'8.3.0',isPackaged:true}),appearanceLoad:async()=>JSON.parse(localStorage.getItem('audit-native')||'{}'),appearanceSave:async p=>localStorage.setItem('audit-native',JSON.stringify(p)),updateStatus:async()=>({status:'downloading',progress:42,feed:'https://github.com/tw1xnyx/FrameGrab-Updates/releases',available:'8.4.0'}),onUpdate:f=>{window.auditUpdate=f;},chooseFolder:async()=>null,diagnostics:async()=>({desktop:'8.3.0',engineReady:true}),openLogs:async()=>true};});
  const items=[['downloading','Downloading Video',42],['downloading','Converting - H.264 NVENC',65],['downloading','Verifying output',null],['done','Ready',100],['error','Failed',0],['paused','Paused - resume when ready',18],['queued','Queued',0]].map(([status,phase,progress],index)=>({index,id:'fixture-'+index,url:'https://example.org/owned-qa-media',title:['Mountain light - 4K documentary','Night city - compatible MP4','Studio interview - verifying','Coastal aerial - ready','Unavailable source - error details','Road trip - paused','Next download - queued'][index],status,phase,progress,file_name:'Owned QA '+index+'.mp4',platform:'QA',duration:125,width:3840,height:2160,size:285000000,destination:'D:\\Editing Projects\\Final Media',speed:status==='downloading'?'8.4 MiB/s':'',eta:'00:21',download_mode:'premiere',logs:index===4?['ERROR: Destination unavailable. Reconnect the drive and retry.']:[],error:index===4?'Destination unavailable':'',can_retry_conversion:index===4}));
  const fixture={folder:'D:\\Editing Projects\\Final Media',jobs:[{id:'qa-job',items,options:{kind:'mp4'}}],history:[{...items[3],completed_at:'2026-10-10T00:00:00Z',path:'D:\\Editing Projects\\Final Media\\Owned QA 3.mp4'}],preferences:{download_mode:'premiere'},tools:{yt_dlp:true,ffmpeg:true,deno:true}};
  let emptyState=false;const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/api/state',r=>r.fulfill({json:emptyState?{...fixture,jobs:[],history:[]}:fixture}));await page.goto('http://127.0.0.1:8291/');await page.waitForSelector('.task-card');
  const results=[];
  async function audit(theme,variant,screen,scope='body'){
   await page.waitForTimeout(280);if(screen==='settings')await page.locator('#saveFolder').hover();if(screen==='tasks')await page.locator('.card-btn').first().hover();if(['tasks','settings'].includes(screen))await page.waitForTimeout(240);
   const result=await page.evaluate(({scope})=>{
    const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d',{willReadFrequently:true});
    const rgba=value=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=value;ctx.fillRect(0,0,1,1);const a=ctx.getImageData(0,0,1,1).data;return [a[0],a[1],a[2],a[3]/255];};
    const blend=(a,b)=>[0,1,2].map(i=>a[i]*a[3]+b[i]*(1-a[3])).concat(1);
    const lum=c=>c.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
    const background=e=>{let list=[],n=e;while(n){const s=getComputedStyle(n),c=rgba(s.backgroundColor);if(c[3])list.push(c);if(c[3]===1)break;n=n.parentElement;}let base=[255,255,255,1];for(const c of list.reverse())base=blend(c,base);return base;};
    const candidates=e=>{const segment=e.closest('.segment.active');if(segment){const thumb=segment.parentElement.querySelector('.segment-thumb'),a=e.getBoundingClientRect(),b=thumb.getBoundingClientRect();if(a.left+a.width/2>=b.left&&a.left+a.width/2<=b.right)return candidates(thumb);}let n=e;while(n){const s=getComputedStyle(n);if(s.backgroundImage.includes('gradient')){const stops=s.backgroundImage.match(/rgba?\([^)]*\)|color\([^)]*\)/g)||[];if(stops.length)return stops.map(v=>blend(rgba(v),background(n)));}if(rgba(s.backgroundColor)[3]===1)break;n=n.parentElement;}return [background(e)];};
    const failures=[],measured=[];const check=(el,text,color)=>{const fg=rgba(color),bgs=candidates(el);let ratio=Infinity;for(const bg of bgs){const f=lum(blend(fg,bg)),b=lum(bg);ratio=Math.min(ratio,(Math.max(f,b)+.05)/(Math.min(f,b)+.05));}const item={tag:el.tagName,id:el.id,cls:typeof el.className==='string'?el.className:'',text:text.slice(0,90),ratio:+ratio.toFixed(2),color};measured.push(item);if(ratio<4.5)failures.push(item);};
    const root=document.querySelector(scope),walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);while(walker.nextNode()){const t=walker.currentNode,el=t.parentElement,s=getComputedStyle(el);if(!t.textContent.trim()||['SCRIPT','STYLE','OPTION','SVG'].includes(el.tagName)||!el.getClientRects().length||s.visibility==='hidden'||s.display==='none')continue;let n=el,hidden=false;while(n){if(n.hidden||getComputedStyle(n).opacity==='0'){hidden=true;break;}n=n.parentElement;}if(!hidden)check(el,t.textContent.trim(),s.color);}
    for(const el of root.querySelectorAll('input,textarea,select')){if(!el.getClientRects().length)continue;const s=getComputedStyle(el);check(el,el.value||el.placeholder||el.id,s.color);if(el.placeholder)check(el,el.placeholder,getComputedStyle(el,'::placeholder').color);}
    return {failures,count:measured.length,min:Math.min(...measured.map(x=>x.ratio))};
   },{scope});results.push({theme,variant,screen,...result});
   if(variant==='native'||screen==='tasks'||screen==='settings')await page.screenshot({path:path.join(out,theme+'-'+(variant==='alternate'?'dark-':'')+screen+'.png'),fullPage:true});
  }
  for(const theme of ['prismatic','neon','aurora','tangerine','matcha','titanium','rose']){
   await page.locator('[data-page="settings"]').first().click();await page.selectOption('#paletteSelect',theme);
   await page.selectOption('#themeMode','light');for(const variant of ['native','alternate']){
    if(variant==='alternate')await page.locator('#themeButton').click();
    for(const screen of ['tasks','history','files','queue','settings']){await page.locator('[data-page="'+screen+'"]').first().click();if(screen==='settings')await page.locator('#runDiagnostics').click();await audit(theme,variant,screen);}
    await page.locator('#wallpaperButton').click();await audit(theme,variant,'popover','#wallpaperPopover');await page.keyboard.press('Escape');
    await page.locator('#newButton').click();await audit(theme,variant,'download','.download-modal');
    await page.locator('#advancedButton').click();await page.locator('#modeClip').click();await audit(theme,variant,'clipping','.download-modal');
    await page.locator('#closeModal').click();await page.evaluate(()=>window.FrameGrabDesktopUI.showError('Theme audit','The selected destination is unavailable. Reconnect the drive, then retry.','Owned QA fixture: Error 53. Original media remains available.'));
    await page.locator('#errorOverlay details').evaluate(e=>e.open=true);await audit(theme,variant,'error','#errorOverlay');await page.locator('#closeError').click();
    emptyState=true;await page.waitForTimeout(1300);await page.locator('[data-page="tasks"]').first().click();await audit(theme,variant,'empty');emptyState=false;await page.waitForTimeout(1300);
    // Restore dialog defaults for the next palette without saving media/download settings.
    await page.locator('#newButton').click();await page.locator('#modeFull').click();if(await page.locator('#advancedButton').getAttribute('aria-expanded')==='true')await page.locator('#advancedButton').click();await page.locator('#closeModal').click();
   }
  }
  await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>document.documentElement.dataset.motion==='off');assert.equal(await page.evaluate(()=>document.documentElement.dataset.motion),'off');assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({fixture:true,results,errors,reducedMotion:true},null,2));const failed=results.filter(x=>x.failures.length);console.log(JSON.stringify({views:results.length,textChecks:results.reduce((n,x)=>n+x.count,0),failed:failed.map(x=>({theme:x.theme,variant:x.variant,screen:x.screen,failures:x.failures})),errors},null,2));assert.equal(failed.length,0,'Rendered text contrast must pass on every screen');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
