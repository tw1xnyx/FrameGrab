'use strict';
const {app, BrowserWindow, dialog, ipcMain, shell, clipboard, nativeTheme, session, Tray, Menu, nativeImage} = require('electron');
const {spawn, spawnSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const net = require('node:net');
const http = require('node:http');
const os = require('node:os');
const {isValidUpdateFeed, safeReport, readJSON, writeAtomic} = require('./update-utils.cjs');
const {ReleaseUpdater} = require('./release-updater.cjs');
const BUILTIN_UPDATE_FEED='https://github.com/tw1xnyx/FrameGrab-Updates/releases';

app.setAppUserModelId('com.framegrab.desktop');
const persistentPath = process.env.FRAMEGRAB_QA==='1' && process.env.FRAMEGRAB_QA_DATA ? path.resolve(process.env.FRAMEGRAB_QA_DATA) : path.join(app.getPath('appData'), 'FrameGrab');
fs.mkdirSync(persistentPath,{recursive:true});
app.setPath('userData', persistentPath);
const dataDir = app.getPath('userData');
const autoUpdater = new ReleaseUpdater({app,dataDir,allowLocal:process.env.FRAMEGRAB_ALLOW_LOCAL_UPDATE_TEST==='1'});
const logDir = path.join(dataDir, 'logs');
const sessionKey = crypto.randomBytes(32).toString('hex');
const updateCfg = path.join(dataDir, 'update-source.json');
const windowState = path.join(dataDir, 'window.json');
const isDev = !app.isPackaged;
const allowLocalUpdates = isDev || process.env.FRAMEGRAB_ALLOW_LOCAL_UPDATE_TEST==='1';
let mainWindow = null;
let engine = null;
let servicePort = 0;
let quitting = false;
let updateState = {status: 'not-configured', version:app.getVersion(), available:null, progress:0, releaseNotes:'', updateSize:null};

function log(message) {
  fs.mkdirSync(logDir, {recursive:true});
  const file = path.join(logDir, 'desktop.log');
  try {
    if (fs.existsSync(file) && fs.statSync(file).size > 2_000_000) fs.renameSync(file, file + '.previous');
    fs.appendFileSync(file, `${new Date().toISOString()} ${safeReport(message)}\n`);
  } catch {}
}
function roots() {
  return {
    service: isDev ? path.join(__dirname, '..', 'service') : path.join(process.resourcesPath, 'service'),
    tools: isDev ? path.join(__dirname, '..', 'tools') : path.join(process.resourcesPath, 'tools'),
    runtime: isDev ? path.join(__dirname, '..', 'runtime') : path.join(process.resourcesPath, 'runtime')
  };
}
function findEngine() {
  const dirs = roots();
  const binary = path.join(dirs.runtime, process.platform==='win32'?'pythonw.exe':'python3');
  const script = path.join(dirs.service, 'app.py');
  for (const file of [binary,script,path.join(dirs.tools,'yt-dlp.exe'),path.join(dirs.tools,'ffmpeg.exe'),path.join(dirs.tools,'ffprobe.exe'),path.join(dirs.tools,'deno.exe')]) {
    if(!fs.existsSync(file)) throw new Error('Required bundled component missing: ' + file);
  }
  return {binary, script, dirs};
}
function openPort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen({port:0,host:'127.0.0.1'}, () => {
      const port=server.address().port;
      server.close(err => err ? reject(err) : resolve(port));
    });
  });
}
function engineGet(urlPath, timeout = 1400) {
  return new Promise((resolve,reject) => {
    const req=http.request({hostname:'127.0.0.1',port:servicePort,path:urlPath,method:'GET',timeout,headers:{'X-FrameGrab-Token':sessionKey}},res=>{
      let body='';res.on('data',d=>body+=d);res.on('end',()=>res.statusCode===200?resolve(body):reject(new Error(`Health check HTTP ${res.statusCode}`)));
    });
    req.once('timeout',()=>req.destroy(new Error('Local engine timed out')));
    req.once('error', reject);
    req.end();
  });
}
async function waitEngine() {
  for(let i=0; i<65; i++) {
    if(!engine || engine.exitCode!==null) throw new Error('Hidden media engine exited before becoming ready. Check diagnostics.');
    try { await engineGet('/api/state'); return; } catch {}
    await new Promise(r=>setTimeout(r,220));
  }
  throw new Error('Hidden media engine did not start in time. Check logs and packaged dependencies.');
}
async function startEngine() {
  const {binary, script, dirs}=findEngine();
  servicePort=await openPort();
  engine=spawn(binary, ['-u',script], {
    cwd:dirs.service, windowsHide:true, detached:false,
    env:{...process.env, PYTHONUTF8:'1', PYTHONIOENCODING:'utf-8', FRAMEGRAB_DATA_DIR:dataDir,
      FRAMEGRAB_TOOLS_DIR:dirs.tools, FRAMEGRAB_API_TOKEN:sessionKey,
      FRAMEGRAB_SERVICE_PORT:String(servicePort), FRAMEGRAB_PARENT_PID:String(process.pid)},
    stdio:['ignore','pipe','pipe']
  });
  engine.stdout.on('data',d=>log('engine: '+d.toString().slice(-500)));
  engine.stderr.on('data',d=>log('engine error: '+d.toString().slice(-900)));
  engine.once('exit',(code,signal)=>{
    log(`engine exited code=${code} signal=${signal}`);
    if(!quitting && mainWindow && !mainWindow.isDestroyed()) dialog.showMessageBox(mainWindow,{type:'error',title:'Media engine stopped',message:'The downloader engine has stopped.',detail:'Open Diagnostics for details. Restart the application to recover.'});
  });
  await waitEngine();
}
function stopEngine() {
  if (!engine || engine.exitCode !== null) return;
  try {
    if(process.platform==='win32') spawn('taskkill',['/PID',String(engine.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
    else engine.kill('SIGTERM');
  } catch(e) { log('cleanup error '+e.message); }
}
function stopEngineForUpdate() {
  return new Promise(resolve => {
    if(!engine || engine.exitCode !== null) return resolve();
    if(process.platform !== 'win32') { engine.kill('SIGTERM'); return resolve(); }
    const child=spawn('taskkill',['/PID',String(engine.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
    const t=setTimeout(resolve,4000);
    child.once('exit',()=>{clearTimeout(t);resolve();});
    child.once('error',()=>{clearTimeout(t);resolve();});
  });
}
function emitUpdate(payload) {
  updateState={...updateState,...payload};
  if(mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('framegrab:update-progress',updateState);
}
function setupUpdater() {
  autoUpdater.autoDownload=false;
  autoUpdater.autoInstallOnAppQuit=false;
  autoUpdater.on('checking-for-update',()=>emitUpdate({status:'checking',error:null,progress:0}));
  autoUpdater.on('update-available',info=>emitUpdate({status:'available',available:info.version,releaseNotes:typeof info.releaseNotes==='string'?info.releaseNotes:JSON.stringify(info.releaseNotes||''),updateSize:info.files?.[0]?.size||null}));
  autoUpdater.on('update-not-available',()=>emitUpdate({status:'current',available:null}));
  autoUpdater.on('download-progress',p=>emitUpdate({status:'downloading',progress:p.percent||0,bytesPerSecond:p.bytesPerSecond,transferred:p.transferred,total:p.total}));
  autoUpdater.on('update-downloaded',info=>emitUpdate({status:'downloaded',available:info.version,progress:100}));
  autoUpdater.on('error',err=>{log('Update error: '+err.message);emitUpdate({status:'error',error:safeReport(err.message)});});
  const saved=readJSON(updateCfg).url;const feed=(saved&&isValidUpdateFeed(saved,allowLocalUpdates)&&!saved.includes('example.invalid')&&!saved.includes('tw1xnyx.github.io'))?saved:BUILTIN_UPDATE_FEED;
  if(isValidUpdateFeed(feed,allowLocalUpdates)) {
    setFeed(feed);
    if(app.isPackaged) {
      setTimeout(()=>autoUpdater.checkForUpdates().catch(e=>log('Update check: '+e.message)),15000).unref();
      setInterval(()=>autoUpdater.checkForUpdates().catch(e=>log('Update check: '+e.message)),6*60*60*1000).unref();
      
    }
  }
}
function setFeed(url) {
  if(!isValidUpdateFeed(url,allowLocalUpdates)) throw new Error('Use an HTTPS update URL (or localhost only in development).');
  autoUpdater.setFeedURL(url===BUILTIN_UPDATE_FEED?{provider:'github'}:{provider:'generic',url:url.replace(/\/$/,'')});
  emitUpdate({status:'configured',feed:url});
}
async function installUpdate() {
  if(updateState.status!=='downloaded') throw new Error('No downloaded verified update is ready.');
  const current=JSON.parse(await engineGet('/api/state'));if(current.jobs.some(j=>j.items.some(i=>['queued','analyzing','downloading','paused'].includes(i.status))))throw Error('Finish or cancel active downloads before installing an update.');
  writeAtomic(path.join(dataDir,'pending-update.json'),{version:updateState.available});
  quitting=true;
  await stopEngineForUpdate();
  autoUpdater.quitAndInstall(false,true);
  return true;
}
function createWindow() {
  const ws=readJSON(windowState,{});
  const bounds=Object.fromEntries(['width','height','x','y'].filter(k=>Number.isInteger(ws[k])).map(k=>[k,ws[k]]));
  mainWindow = new BrowserWindow({
    width:Math.max(900,bounds.width||1300),height:Math.max(640,bounds.height||820),
    ...(Number.isInteger(bounds.x)&&Number.isInteger(bounds.y)?{x:bounds.x,y:bounds.y}:{}),
    minWidth:780,minHeight:560,show:false,backgroundColor:'#e8eef9',
    title:'FrameGrab',autoHideMenuBar:true, titleBarStyle:'hidden',titleBarOverlay:{color:'#171c29',symbolColor:'#ffffff',height:41},
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true,
      webSecurity:true,devTools:isDev}
  });
  mainWindow.once('ready-to-show',()=>mainWindow.show());
  mainWindow.webContents.on('will-navigate',(e,url)=>{
    if(!url.startsWith(`http://127.0.0.1:${servicePort}/`)) {e.preventDefault();if(/^https?:\/\//.test(url))shell.openExternal(url);}
  });
  mainWindow.webContents.setWindowOpenHandler(({url})=>{
    if(/^https?:\/\//.test(url)) shell.openExternal(url);
    return {action:'deny'};
  });
  mainWindow.on('close',()=>{
    const b=mainWindow.getBounds();
    if(!mainWindow.isMinimized()) writeAtomic(windowState,{x:b.x,y:b.y,width:b.width,height:b.height});
  });
  mainWindow.loadURL(`http://127.0.0.1:${servicePort}/`);
}
function setupIpc() {
  const handle=(name,fn)=>ipcMain.handle(name,(event,...args)=>{if(!mainWindow||event.sender!==mainWindow.webContents||event.senderFrame!==mainWindow.webContents.mainFrame)throw Error('Untrusted application frame');return fn(event,...args);});
  ipcMain.on('framegrab:session-token',(event)=>{
    if(mainWindow && event.sender===mainWindow.webContents) event.returnValue=sessionKey;
    else event.returnValue='';
  });
  handle('framegrab:appearance-load',()=>readJSON(path.join(dataDir,'appearance.json'),{}));
  handle('framegrab:appearance-save',(_event,value)=>{
    const out={};const choices={palette:['clean','red','navy','graphite','emerald','purple','sand'],theme:['light','dark','system'],preset:['aurora','silk','lagoon']};
    for(const [k,list] of Object.entries(choices))if(list.includes(value?.[k]))out[k]=value[k];
    for(const k of ['motion','optics','thumbs'])if(typeof value?.[k]==='boolean')out[k]=value[k];
    if(Number.isFinite(value?.intensity))out.intensity=Math.max(0,Math.min(100,value.intensity));
    writeAtomic(path.join(dataDir,'appearance.json'),out);return out;
  });
  handle('framegrab:version',()=>{const marker=path.join(dataDir,'pending-update.json');const justUpdated=readJSON(marker,{}).version===app.getVersion();if(justUpdated)fs.unlinkSync(marker);return {version:app.getVersion(),justUpdated,isPackaged:app.isPackaged,platform:process.platform};});
  handle('framegrab:choose-folder',async()=>{
    const d=await dialog.showOpenDialog(mainWindow,{title:'Choose download destination',properties:['openDirectory','createDirectory']});
    return d.canceled ? null : d.filePaths[0];
  });
  handle('framegrab:open-folder',async()=>{const info=JSON.parse(await engineGet('/api/state'));return shell.openPath(info.folder);});
  handle('framegrab:reveal-file',async(_event,p)=>{
    if(typeof p!=='string'||!path.isAbsolute(p)) throw new Error('Invalid file path');
    if(!fs.existsSync(p)) throw new Error('File no longer exists');
    shell.showItemInFolder(p);
    return true;
  });
  handle('framegrab:clipboard-read',()=>clipboard.readText().slice(0,150000));
  handle('framegrab:clipboard-write',(_event,value)=>{clipboard.writeText(String(value));return true;});
  handle('framegrab:update-status',()=>({...updateState,feed:updateState.feed||BUILTIN_UPDATE_FEED,isPackaged:app.isPackaged}));
  handle('framegrab:update-set-feed',(_event,url)=>{
    if(!isValidUpdateFeed(url,allowLocalUpdates)) throw new Error('A secure HTTPS update hosting URL is required.');
    setFeed(url);
    writeAtomic(updateCfg,{url});
    return updateState;
  });
  handle('framegrab:update-check',async()=>{
    if(!app.isPackaged) throw new Error('Update checking must run in an installed application. Build and install a Windows release to test it.');

    await autoUpdater.checkForUpdates();
    return updateState;
  });
  handle('framegrab:update-download',async()=>{
    if(updateState.status!=='available') throw new Error('No available update to download.');
    await autoUpdater.downloadUpdate();
    return updateState;
  });
  handle('framegrab:update-install',()=>installUpdate());
  handle('framegrab:diagnostics',async()=>({desktop:app.getVersion(),os:`${os.type()} ${os.release()}`,arch:os.arch(),
    appData:dataDir,logs:logDir,resources:roots(),update:updateState,engineReady:!!(engine&&engine.exitCode===null)}));
  handle('framegrab:open-logs',()=>shell.openPath(logDir));
}
app.whenReady().then(async()=>{
  try {
    setupIpc();
    await startEngine();
    const url=`http://127.0.0.1:${servicePort}/`;
    await session.defaultSession.cookies.set({url,name:'fg_session',value:sessionKey,path:'/',httpOnly:true,sameSite:'strict',secure:false});
    setupUpdater();
    createWindow();
  } catch(error) {
    log('startup failure: '+error.stack);
    dialog.showErrorBox('FrameGrab could not start',`${safeReport(error.message)}\n\nLogs: ${logDir}`);
    app.quit();
  }
});
app.on('window-all-closed',()=>{quitting=true;app.quit();});
app.on('before-quit',()=>{quitting=true;stopEngine();});
app.on('activate',()=>{if(BrowserWindow.getAllWindows().length===0 && engine?.exitCode===null)createWindow();});
process.on('uncaughtException',e=>log('fatal: '+safeReport(e.stack||e.message)));
process.on('unhandledRejection',e=>log('rejection: '+safeReport(e?.stack||e)));
