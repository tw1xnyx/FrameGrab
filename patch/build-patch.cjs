'use strict';
// Builds only the incremental updater. Never rebuilds or packages Electron/runtime/tools.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process'),asar=require('@electron/asar');
(async()=>{
 const root=path.resolve(__dirname,'..'),baseline=path.resolve(process.argv[2]||'C:/Games/APP TEST/FrameGrab'),patch=__dirname,build=path.join(patch,'build'),stage=path.join(patch,'asar-stage');
 const keyFile=process.env.FRAMEGRAB_SIGNING_KEY||path.join(patch,'publisher-private.pem');
 if(!fs.existsSync(keyFile))throw Error('Supply the local publisher signing key via FRAMEGRAB_SIGNING_KEY. Never commit the private key.');
 fs.mkdirSync(build,{recursive:true});fs.mkdirSync(stage,{recursive:true});
 asar.extractAll(path.join(baseline,'resources/app.asar'),stage);
 for(const name of fs.readdirSync(path.join(root,'desktop')))fs.copyFileSync(path.join(root,'desktop',name),path.join(stage,'desktop',name));
 const pkg=JSON.parse(fs.readFileSync(path.join(stage,'package.json')));pkg.version='8.3.0';fs.writeFileSync(path.join(stage,'package.json'),JSON.stringify(pkg,null,2));
 await asar.createPackage(stage,path.join(build,'app.asar'));
 const hash=b=>crypto.createHash('sha256').update(b).digest('hex');const fh=p=>hash(fs.readFileSync(p));
 const relative=['resources/app.asar','resources/service/app.py','resources/service/media_compat.py','resources/service/web/index.html','resources/service/web/app.js','resources/service/web/desktop.js','resources/service/web/styles.css','resources/service/web/themes.js','resources/service/web/premium.css'];
 const files=[];const payload=path.join(build,'payload');fs.mkdirSync(payload,{recursive:true});
 for(const name of relative){const source=name==='resources/app.asar'?path.join(build,'app.asar'):path.join(root,name.replace(/^resources\//,''));const target=path.join(payload,name);fs.mkdirSync(path.dirname(target),{recursive:true});fs.copyFileSync(source,target);
  const oldHashes=[];for(const base of [baseline,path.join(root,'dist/win-unpacked'),path.join(root,'../v8.1-release-baseline/payload'),path.join(root,'../v8.2-release-baseline/payload')]){const old=path.join(base,name);if(fs.existsSync(old))oldHashes.push(fh(old));}
  const archived=path.join(root,'../v8.1-release-baseline/manifest.json');const previous=fs.existsSync(archived)?archived:path.join(patch,'baselines/v8.1.json');const prior=fs.existsSync(previous)?JSON.parse(fs.readFileSync(previous)).files.find(f=>f.path===name):null;if(prior)oldHashes.push(...prior.oldHashes);const lastFile=path.join(patch,'baselines/v8.2.json');if(fs.existsSync(lastFile)){const last=JSON.parse(fs.readFileSync(lastFile)).files.find(f=>f.path===name);if(last)oldHashes.push(last.sha256,...last.oldHashes);}
  files.push({path:name,sha256:fh(source),oldHashes:[...new Set(oldHashes)],allowAbsent:['resources/service/media_compat.py','resources/service/web/themes.js','resources/service/web/premium.css'].includes(name)});}
 const exeHashes=[...new Set([baseline,path.join(root,'dist/win-unpacked')].map(b=>fh(path.join(b,'FrameGrab.exe'))))];
 const manifest=Buffer.from(JSON.stringify({schema:1,version:'8.3.0',minimumVersion:'8.0.0',exeHashes,files}));fs.writeFileSync(path.join(build,'manifest.json'),manifest);fs.writeFileSync(path.join(build,'manifest.sig'),crypto.sign('RSA-SHA256',manifest,fs.readFileSync(keyFile)));
 cp.execFileSync('python',['-c','import pathlib,zipfile; b=pathlib.Path(__import__("sys").argv[1]); z=zipfile.ZipFile(b/"payload.zip","w",zipfile.ZIP_DEFLATED,compresslevel=9); [(z.write(p,p.relative_to(b/"payload").as_posix())) for p in (b/"payload").rglob("*") if p.is_file()]; z.close()',build]);
 const csc='C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe';const args=['/nologo','/target:winexe','/platform:x64','/optimize+','/r:System.Windows.Forms.dll','/r:System.Drawing.dll','/r:System.Web.Extensions.dll','/r:System.IO.Compression.dll','/r:System.IO.Compression.FileSystem.dll','/win32icon:'+path.join(root,'assets/framegrab.ico'),'/resource:'+path.join(build,'manifest.json')+',manifest.json','/resource:'+path.join(build,'manifest.sig')+',manifest.sig','/resource:'+path.join(patch,'publisher-public.xml')+',publisher.xml','/resource:'+path.join(build,'payload.zip')+',payload.zip',];
 for(const test of [false,true])cp.execFileSync(csc,[...args,'/out:'+path.join(build,test?'FrameGrab_Update_Test.exe':'FrameGrab_Update.exe'),...(test?['/define:TESTING']:[]),path.join(patch,'Updater.cs')],{stdio:'inherit'});
 const exe=path.join(build,'FrameGrab_Update.exe');fs.writeFileSync(path.join(build,'build-result.json'),JSON.stringify({version:'8.3.0',bytes:fs.statSync(exe).size,sha256:fh(exe),files},null,2));console.log(JSON.stringify({bytes:fs.statSync(exe).size,sha256:fh(exe),files:files.map(f=>f.path)}));
})().catch(e=>{console.error(e);process.exitCode=1;});
