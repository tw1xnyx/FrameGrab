'use strict';
// Explicit live release QA. Uses isolated cache and an older app adapter version;
// downloads the real installer without executing it or altering an installation.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const {NsisUpdater}=require('electron-updater');
const {NodeHttpExecutor}=require('builder-util/out/nodeHttpExecutor');
const {ReleaseUpdater}=require('../desktop/release-updater.cjs');
NodeHttpExecutor.prototype.download=require('electron-updater/out/electronHttpExecutor').ElectronHttpExecutor.prototype.download;
(async()=>{
 const dir=path.resolve(__dirname,'../.qa-public-feed');fs.mkdirSync(dir,{recursive:true});
 const config=path.join(dir,'app-update.yml');fs.writeFileSync(config,'provider: github\nowner: tw1xnyx\nrepo: FrameGrab-Updates\nprivate: false\nupdaterCacheDirName: cache\n');
 const app={name:'FrameGrab',version:'8.2.0',isPackaged:true,userDataPath:dir,baseCachePath:dir,appUpdateConfigPath:config,whenReady:async()=>{},onQuit:()=>{},quit:()=>{throw Error('Live transport QA must never install');}};
 const n=new NsisUpdater(null,app);n.httpExecutor=new NodeHttpExecutor();
 const u=new ReleaseUpdater({engine:n});let last=0,events=0;
 u.on('download-progress',p=>{last=p.percent;events++;});
 const result=await u.checkForUpdates();assert.equal(result.updateInfo.version,'8.3.0');
 const files=await u.downloadUpdate();const bytes=fs.readFileSync(files[0]);
 assert.equal(bytes.subarray(0,2).toString(),'MZ');
 assert.equal(crypto.createHash('sha512').update(bytes).digest('base64'),result.updateInfo.files[0].sha512);
 assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),'f51820222dce305e7626f3b5e45bdccf0b4006b96002bc6b0bc4479f37434d08');
 assert(events>0);assert(last>=99);
 const report={version:result.updateInfo.version,bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),progressEvents:events,lastProgress:last,installerExecuted:false,adapterVersion:app.version};
 fs.writeFileSync(path.join(dir,'results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
