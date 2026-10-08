const assert=require('node:assert/strict');
const test=require('node:test');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const {safeReport,isValidUpdateFeed,writeAtomic,readJSON,sha512}=require('../desktop/update-utils.cjs');
const os=require('node:os');
test('strict hosted HTTPS update source, local HTTP only for explicit test',()=>{
 assert.equal(isValidUpdateFeed('https://updates.example.org/releases/'),true);
 assert.equal(isValidUpdateFeed('http://example.org/releases'),false);
 assert.equal(isValidUpdateFeed('https://user:pass@updates.example.org/'),false);
 assert.equal(isValidUpdateFeed('http://127.0.0.1:8990/',false),false);
 assert.equal(isValidUpdateFeed('http://127.0.0.1:8990/',true),true);
});
test('sensitive tokens are removed from diagnostics',()=>{
 const msg='Authorization: Bearer verysecret Cookie: id=abc\nhttps://x.test/?token=123&other=ok';
 const clean=safeReport(msg);
 assert(!clean.includes('verysecret'));
 assert(!clean.includes('123'));
 assert(clean.includes('[REDACTED]'));
});
test('update/settings persistence uses atomic JSON files',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'framegrab-native-'));
 try{const p=path.join(dir,'state.json');writeAtomic(p,{theme:'dark',installed:'8.0.0'});assert.deepEqual(readJSON(p),{theme:'dark',installed:'8.0.0'});assert.equal(readJSON(path.join(dir,'missing.json')).length,undefined);}finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('native packaging manifest contains installer and stable app identifier',()=>{
 const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
 assert.equal(pkg.build.appId,'com.framegrab.desktop');
 assert.equal(pkg.build.nsis.allowToChangeInstallationDirectory,true);
 assert.equal(pkg.build.nsis.deleteAppDataOnUninstall,false);
 assert(pkg.build.extraResources.some(x=>x.to==='runtime'));
 assert(pkg.build.extraResources.some(x=>x.to==='tools'));
 assert(pkg.build.extraResources.some(x=>x.to==='service'));
});
test('UI exposes download, selected-part editor and Copy Error',()=>{
 const html=fs.readFileSync(path.join(root,'service/web/index.html'),'utf8');
 const js=fs.readFileSync(path.join(root,'service/web/app.js'),'utf8');
 for(const id of ['modeClip','trimHandleStart','trimHandleEnd','startDownload','errorOverlay','copyError','checkUpdates','runDiagnostics'])assert(html.includes(`id="${id}"`));
 assert(js.includes('copy-error'));
 assert(js.includes('window.framegrabNative'));
});
