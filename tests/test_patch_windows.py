import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];INSTALL=ROOT.parent/'patch-test';BUILD=ROOT/'patch/build';DATA=ROOT.parent/'patch-user-data';DATA.mkdir(exist_ok=True)
manifest=json.loads((BUILD/'manifest.json').read_text()); paths=[x['path'] for x in manifest['files']]
def hashes():return {p:hashlib.sha256((INSTALL/p).read_bytes()).hexdigest() if (INSTALL/p).exists() else None for p in paths}
(DATA/'settings.json').write_text(json.dumps({'download_dir':str(DATA),'preserved_custom':'unchanged'}));(DATA/'history.json').write_text(json.dumps([{'title':'Preserved previous download','file_path':str(DATA/'previous.mp4'),'timestamp':'2026-10-09'}]));(DATA/'update-source.json').write_text('{}')
preserved={p:(DATA/p).read_bytes() for p in ['settings.json','history.json','update-source.json']}
env=dict(os.environ,FRAMEGRAB_QA='1',FRAMEGRAB_QA_DATA=str(DATA))
def invoke(*args,production=False):return subprocess.run([str(BUILD/('FrameGrab_Update.exe' if production else 'FrameGrab_Update_Test.exe')),'--target',str(INSTALL),'--silent',*args],env=env,timeout=85).returncode
before=hashes();results=[]
assert invoke('--fail-after','2','--no-restart')==1;assert hashes()==before;results.append('Injected replacement failure: all baseline file hashes restored')
assert invoke('--crash-after','2','--no-restart')==71;assert hashes()!=before
assert invoke('--fail-after','1','--no-restart')==1;assert hashes()==before;results.append('Abrupt interrupted update: journal recovered originals before next update; rollback passed')
p=INSTALL/'resources/service/web/app.js';old=p.read_bytes();p.write_bytes(old+b'\n// unexpected local modification\n');snapshot=hashes();assert invoke('--no-restart')==1;assert hashes()==snapshot;p.write_bytes(old);results.append('Unexpected installed file rejected before any replacement')
assert invoke(production=True)==0;assert hashes()=={x['path']:x['sha256'] for x in manifest['files']};results.append('Production updater: real existing installation copy patched and restarted; bundled backend ready')
assert invoke(production=True)==0;results.append('Re-running production updater: safely recognizes already installed version')
for p,b in preserved.items():assert (DATA/p).read_bytes()==b,p
results.append('Settings, prior history, saved directory, custom preference and update configuration byte-identical')
(BUILD/'patch-test-results.json').write_text(json.dumps(results,indent=2));print('\n'.join(results))
