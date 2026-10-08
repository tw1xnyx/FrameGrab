"""Integration tests. Synthetic H264/AAC MP4 & MP3 made by local FFmpeg; fake yt-dlp only simulates network/extraction."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
FAKE = '''#!/usr/bin/env python3
import sys,shutil,re,json,os
from pathlib import Path
args=sys.argv[1:]
url=args[-1]
if '--dump-single-json' in args:
    if '--cookies-from-browser' in args:
        print('ERROR: Could not copy Chrome cookie database',file=sys.stderr); sys.exit(1)
    print(json.dumps({'id':'testid00001','title':'Great Summer Video','channel':'Studio','duration':20,'is_live':False,'thumbnail':''}))
    sys.exit(0)
if '--output' not in args: sys.exit(9)
if 'missing' in url:
    # yt-dlp's incorrect success case. The application MUST flag it.
    sys.exit(0)
name=args[args.index('--output')+1].replace('%(title).165B','Great Summer Video')
section='--download-sections' in args
media='mp3' if '--extract-audio' in args else 'mp4'
name=name.replace('%(ext)s',media)
folder=Path(args[args.index('--paths')+1].split(':',1)[1]);folder.mkdir(parents=True,exist_ok=True)
out=folder/name
if 'special' in url:
    # Output name unexpectedly rewritten by yt-dlp; rely on machine-reported filepath.
    out=folder/'Sanitized by downloader [different filename].mp4'
sample=Path(os.environ['FRAMEGRAB_TEST_SAMPLE_DIR'])/('sample.mp3' if media=='mp3' else 'sample.mp4')
shutil.copyfile(sample,out)
print('[download] 100.0% of 1.20 MiB at 3.00 MiB/s ETA 00:00',flush=True)
if media=='mp4': print('[Merger] Merging formats into "'+str(out)+'"',flush=True)
if '--print-to-file' in args:
    i=args.index('--print-to-file')
    path=Path(args[i+2]);path.parent.mkdir(parents=True,exist_ok=True)
    if 'unreported' not in url: path.write_text(str(out)+'\\n',encoding='utf-8')
if 'unreported' not in url: print('__UVD_DONE__'+str(out),flush=True)
sys.exit(0)
'''

class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='framegrab-v7-')
        cls.root=Path(cls.tmp.name)
        shutil.copy2(PROJECT/'service'/'app.py', cls.root/'app.py')
        shutil.copytree(PROJECT/'service'/'web', cls.root/'web')
        tools=cls.root/'tools';tools.mkdir()
        fake=tools/'yt-dlp.exe';fake.write_text(FAKE,encoding='utf-8');fake.chmod(0o755)
        for fn,real in [('ffmpeg.exe','ffmpeg'),('ffprobe.exe','ffprobe')]:
            (tools/fn).symlink_to(shutil.which(real))
        (tools/'deno.exe').write_text('placeholder')
        cls.folder=cls.root/'Downloads with spaces';cls.folder.mkdir()
        # Real video+audio container and a real MP3, both approximately 2 seconds.
        code=subprocess.run(['ffmpeg','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=25','-f','lavfi','-i','sine=frequency=440:sample_rate=44100', '-t','2','-c:v','mpeg4','-q:v','3','-c:a','aac','-shortest',str(cls.root/'sample.mp4')],capture_output=True)
        if code.returncode: raise RuntimeError(code.stderr.decode())
        code=subprocess.run(['ffmpeg','-loglevel','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','2','-c:a','libmp3lame',str(cls.root/'sample.mp3')],capture_output=True)
        if code.returncode: raise RuntimeError(code.stderr.decode())
        os.environ['FRAMEGRAB_TEST_SAMPLE_DIR']=str(cls.root)
        os.environ['FRAMEGRAB_DATA_DIR']=str(cls.root/'appdata')
        os.environ['FRAMEGRAB_TOOLS_DIR']=str(tools)
        spec=importlib.util.spec_from_file_location('framegrab_v7_test',cls.root/'app.py')
        cls.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.mod)
        cls.mod.SETTINGS['download_dir']=str(cls.folder)
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),cls.mod.H)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.mod.POOL.shutdown(wait=True)
        cls.tmp.cleanup();os.environ.pop('FRAMEGRAB_TEST_SAMPLE_DIR',None)
        os.environ.pop('FRAMEGRAB_DATA_DIR',None)
        os.environ.pop('FRAMEGRAB_TOOLS_DIR',None)

    def api(self,route,payload=None):
        body=json.dumps(payload).encode() if payload is not None else None
        req=urllib.request.Request(self.base+route,data=body,headers={'Content-Type':'application/json'} if body else {})
        with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read())

    def finished(self,jid):
        for _ in range(120):
            j=next(x for x in self.api('/api/state')['jobs'] if x['id']==jid)
            if j['status']=='finished':return j
            time.sleep(.1)
        raise AssertionError('Timed out waiting for job')

    def start(self,url,options=None):
        return self.finished(self.api('/api/start',{'urls':[url], 'options':options or {}})['job_id'])

    def test_01_machine_reported_path_even_when_filename_changes(self):
        j=self.start('https://example.com/special')
        self.assertEqual(j['done'],1,j)
        self.assertEqual(j['items'][0]['file_name'],'Sanitized by downloader [different filename].mp4')
        self.assertEqual(self.mod.verify_media(self.folder/j['items'][0]['file_name'])['duration'],2)
        print('PASS actual after_move path resolves a differently sanitized Windows filename')

    def test_02_no_report_directory_fallback(self):
        j=self.start('https://example.com/unreported')
        self.assertEqual(j['done'],1,j)
        self.assertTrue((self.folder/'Great Summer Video.mp4').exists())
        print('PASS changed-file recovery when yt-dlp omits final path event')

    def test_03_real_clip_with_audio_and_name(self):
        j=self.start('https://example.com/clip',{'clip':True,'start':'00:00:00','end':'00:00:02','exact':True})
        self.assertEqual(j['done'],1,j)
        f=self.folder/j['items'][0]['file_name']
        self.assertIn('Clip 00-00-00 to 00-00-02',f.name)
        streams=self.mod.verify_media(f)['streams']
        self.assertTrue(any(x['codec_type']=='audio' for x in streams))
        self.assertTrue(any(x['codec_type']=='video' for x in streams))
        print('PASS selected clip saved directly, audio+video verified and unique clip filename')

    def test_04_zero_output_must_fail(self):
        j=self.start('https://example.com/missing')
        self.assertEqual(j['failed'],1,j)
        self.assertNotEqual(j['items'][0]['status'],'done')
        print('PASS no fake success for zero output')

    def test_05_compatible_mp3(self):
        j=self.start('https://example.com/mp3',{'kind':'mp3'})
        self.assertEqual(j['done'],1,j)
        path=self.folder/j['items'][0]['file_name']
        self.assertEqual(path.suffix,'.mp3')
        self.assertGreater(path.stat().st_size,100)
        print('PASS audio extraction MP3 passes real ffprobe check')

    def test_06_metadata_api_and_assets(self):
        info=self.api('/api/analyze',{'url':'https://www.youtube.com/watch?v=testid00001'})
        self.assertEqual(info['duration'],20)
        for url in ('/','/styles.css','/app.js','/background.js','/glass.js','/desktop.js'):
            with urllib.request.urlopen(self.base+url,timeout=6) as r:self.assertEqual(r.status,200)
        print('PASS metadata Analyze endpoint and all app assets')

    def test_07_auth_required_when_desktop_token_present(self):
        from urllib.error import HTTPError
        old=self.mod.SESSION_TOKEN
        self.mod.SESSION_TOKEN='temporary-test-secret'
        try:
            try: self.api('/api/state')
            except HTTPError as e: self.assertEqual(e.code,403)
            else: self.fail('Unexpectedly accepted missing token')
            req=urllib.request.Request(self.base+'/api/state',headers={'X-FrameGrab-Token':'temporary-test-secret'})
            with urllib.request.urlopen(req) as r:
                self.assertEqual(json.load(r)['build'],'8.0.0-desktop-source')
            print('PASS localhost API denies unauthenticated requests')
        finally: self.mod.SESSION_TOKEN=old

    def test_08_diagnostics_response(self):
        d=self.api('/api/diagnostics')
        self.assertIn('FFprobe',d['tools'])
        self.assertTrue(Path(d['log_dir']).is_dir())
        print('PASS diagnostics tool checks and persistent log folder')

if __name__=='__main__':unittest.main(verbosity=2)
