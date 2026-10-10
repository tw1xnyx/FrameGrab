'use strict';
const {_electron:electron}=require('./qa-playwright.cjs')();
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const root=path.resolve(__dirname,'..'),data=path.join(root,'.qa-installed-feed');fs.mkdirSync(data,{recursive:true});let app;
 try{
  app=await electron.launch({executablePath:path.resolve(root,'../patch-test/FrameGrab.exe'),env:{...process.env,FRAMEGRAB_QA:'1',FRAMEGRAB_QA_DATA:data}});
  const page=await app.firstWindow();await page.waitForFunction(()=>!!window.framegrabNative,{timeout:45000});
  const version=await page.evaluate(()=>window.framegrabNative.version());assert.equal(version.version,'8.3.0');assert(version.isPackaged);
  await page.evaluate(()=>window.framegrabNative.updateCheck());
  await page.waitForFunction(async()=>['current','error'].includes((await window.framegrabNative.updateStatus()).status),{timeout:60000});
  const result=await page.evaluate(()=>window.framegrabNative.updateStatus());assert.equal(result.status,'current',JSON.stringify(result));
  fs.writeFileSync(path.join(data,'results.json'),JSON.stringify({version,result,installerExecuted:false},null,2));console.log('PASS packaged updated app: native Check for Updates reaches live public feed and reports current version');
 }finally{if(app)await app.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
