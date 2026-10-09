'use strict';
const {EventEmitter}=require('node:events');
const fs=require('node:fs'),path=require('node:path'),https=require('node:https'),http=require('node:http'),crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const publicKey=fs.readFileSync(path.join(__dirname,'publisher-public.pem'),'utf8');
function version(v){if(!/^\d+\.\d+\.\d+$/.test(v))throw Error('Invalid update version');return v.split('.').map(Number);}
function compare(a,b){a=version(a);b=version(b);for(let i=0;i<3;i++)if(a[i]!==b[i])return Math.sign(a[i]-b[i]);return 0;}
function verifyFeed(envelope,currentVersion,allowLocal=false){
 if(!envelope||typeof envelope.signed!=='string'||typeof envelope.signature!=='string')throw Error('Missing update signature');
 const bytes=Buffer.from(envelope.signed,'base64');
 if(!crypto.verify('RSA-SHA256',bytes,publicKey,Buffer.from(envelope.signature,'base64')))throw Error('Update publisher signature is invalid');
 const info=JSON.parse(bytes.toString('utf8'));const u=new URL(info.url);
 if(u.username||u.password||u.hash||!(u.protocol==='https:'||(allowLocal&&u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname))))throw Error('Update download requires HTTPS');
 if(info.schema!==1||!Number.isSafeInteger(info.size)||info.size<1024||info.size>50*1024*1024||!/^[a-f0-9]{64}$/.test(info.sha256))throw Error('Invalid incremental package metadata');
 if(!Number.isFinite(Date.parse(info.expires))||Date.parse(info.expires)<Date.now())throw Error('Update manifest has expired');
 version(info.version);version(info.minVersion);
 if(compare(currentVersion,info.minVersion)<0)throw Error('This patch requires FrameGrab '+info.minVersion+' or newer');
 return info;
}
function request(url,allowLocal,handler,redirects=0){return new Promise((resolve,reject)=>{
 const u=new URL(url);if(u.username||u.password||!(u.protocol==='https:'||(allowLocal&&u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname))))return reject(Error('Insecure update URL'));
 const r=(u.protocol==='https:'?https:http).get(u,{timeout:30000,headers:{'User-Agent':'FrameGrab-Incremental-Updater'}},res=>{
  if([301,302,303,307,308].includes(res.statusCode)){res.resume();if(redirects>=4)return reject(Error('Too many update redirects'));return request(new URL(res.headers.location,url).href,allowLocal,handler,redirects+1).then(resolve,reject);}
  if(res.statusCode!==200){res.resume();return reject(Error('Update server returned HTTP '+res.statusCode));}
  Promise.resolve().then(()=>handler(res)).then(resolve,reject);
 });r.on('error',reject);r.on('timeout',()=>r.destroy(Error('Update request timed out')));
});}
class PatchUpdater extends EventEmitter {
 constructor({app,dataDir,allowLocal=false}){super();this.app=app;this.dir=path.join(dataDir,'updates');this.allowLocal=allowLocal;this.info=null;this.downloaded=null;this.busy=false;}
 setFeedURL({url}){this.url=url.replace(/\/$/,'');this.info=null;this.downloaded=null;}
 async checkForUpdates(){if(this.busy)return;this.busy=true;this.emit('checking-for-update');try{
  if(!this.url)throw Error('No incremental update feed configured');
  const url=this.url.endsWith('.json')?this.url:this.url+'/patch-feed.json';
  const data=await request(url,this.allowLocal,async res=>{let chunks=[],size=0;for await(const c of res){size+=c.length;if(size>128*1024){res.destroy();throw Error('Update manifest too large');}chunks.push(c);}return Buffer.concat(chunks);});
  const info=verifyFeed(JSON.parse(data),this.app.getVersion(),this.allowLocal);
  if(compare(info.version,this.app.getVersion())<=0){this.info=null;this.emit('update-not-available');return;}
  this.info=info;this.emit('update-available',{...info,files:[{size:info.size}]});
 }catch(e){this.emit('error',e);throw e;}finally{this.busy=false;}}
 async downloadUpdate(){if(this.busy)throw Error('An update operation is already running');if(!this.info)throw Error('Check for an update first');this.busy=true;this.downloaded=null;
  fs.mkdirSync(this.dir,{recursive:true});const info=this.info;const target=path.join(this.dir,'FrameGrab_Update_'+info.version+'.exe');const tmp=target+'.part';
  try{await request(info.url,this.allowLocal,async res=>{const hash=crypto.createHash('sha256');let transferred=0;const stream=fs.createWriteStream(tmp,{flags:'w'});
   let streamError=null;stream.on('error',e=>{streamError=e;res.destroy(e);});
   try{for await(const c of res){transferred+=c.length;if(transferred>info.size)throw Error('Update exceeds signed size');hash.update(c);if(!stream.write(c))await new Promise((ok,bad)=>{const done=()=>{stream.off('error',fail);ok();};const fail=e=>{stream.off('drain',done);bad(e);};stream.once('drain',done);stream.once('error',fail);});this.emit('download-progress',{percent:transferred/info.size*100,transferred,total:info.size});}
    await new Promise((ok,bad)=>{stream.once('error',bad);stream.end(ok);});if(streamError)throw streamError;
    if(transferred!==info.size||hash.digest('hex')!==info.sha256)throw Error('Update hash or size verification failed');
   }finally{stream.destroy();}
  });fs.renameSync(tmp,target);this.downloaded=target;this.emit('update-downloaded',info);return [target];
  }catch(e){try{fs.unlinkSync(tmp);}catch{}this.emit('error',e);throw e;}finally{this.busy=false;}}
 quitAndInstall(){if(!this.downloaded||!this.info)throw Error('No verified patch is ready');const data=fs.readFileSync(this.downloaded);if(data.length!==this.info.size||crypto.createHash('sha256').update(data).digest('hex')!==this.info.sha256)throw Error('Downloaded patch changed after verification');
  const child=spawn(this.downloaded,[],{detached:true,stdio:'ignore',windowsHide:false});child.once('error',e=>this.emit('error',e));child.once('spawn',()=>{child.unref();this.app.quit();});}
}
module.exports={PatchUpdater,verifyFeed,compare};
