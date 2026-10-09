"""Real Windows pipeline verification with bundled tools and owned synthetic media."""
import functools, importlib.util, json, os, subprocess, threading, time, unittest, urllib.request
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'service'))
QA=ROOT/'.qa'
QA.mkdir(exist_ok=True)
os.environ['FRAMEGRAB_DATA_DIR']=str(QA/'data')
os.environ['FRAMEGRAB_TOOLS_DIR']=str(ROOT/'tools')
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
class WindowsPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media=QA/'media'; cls.media.mkdir(exist_ok=True)
        cls.dest=QA/'Downloads with spaces'; cls.dest.mkdir(exist_ok=True)
        args=[str(ROOT/'tools/ffmpeg.exe'),'-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=25','-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','12','-c:v','libx264','-c:a','aac','-movflags','+faststart',str(cls.media/'owned-test.mp4')]
        subprocess.run(args,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        cls.host=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(cls.media)))
        threading.Thread(target=cls.host.serve_forever,daemon=True).start()
        cls.url=f'http://127.0.0.1:{cls.host.server_port}/owned-test.mp4'
        spec=importlib.util.spec_from_file_location('fg',ROOT/'service/app.py')
        cls.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.mod)
        cls.mod.set_folder(str(cls.dest))
        cls.mod.SESSION_TOKEN='qa-token'
        cls.api=ThreadingHTTPServer(('127.0.0.1',0),cls.mod.H)
        threading.Thread(target=cls.api.serve_forever,daemon=True).start()
        cls.base=f'http://127.0.0.1:{cls.api.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.api.shutdown();cls.api.server_close();cls.host.shutdown();cls.host.server_close();cls.mod.POOL.shutdown(wait=True)
    def call(self,route,body=None):
        req=urllib.request.Request(self.base+route,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-FrameGrab-Token':'qa-token'})
        with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
    def download(self,opts):
        jid=self.call('/api/start',{'urls':[self.url],'options':opts})['job_id']
        for i in range(600):
            j=next(x for x in self.call('/api/state')['jobs'] if x['id']==jid)
            if j['status']=='finished':
                self.assertEqual(j['done'],1,json.dumps(j,indent=2));return self.dest/j['items'][0]['file_name']
            time.sleep(.2)
        self.fail('Timeout')
    def test_full(self):
        p=self.download({}); info=self.mod.verify_media(p,require_audio=True)
        self.assertAlmostEqual(info['duration'],12,delta=.3)
        self.assertEqual(p.parent,self.dest)
    def test_exact_clip(self):
        p=self.download({'clip':True,'start':'00:00:03','end':'00:00:07','exact':True})
        self.assertAlmostEqual(self.mod.verify_media(p,require_audio=True)['duration'],4,delta=.35)
    def test_mp3(self):
        p=self.download({'kind':'mp3'});self.assertEqual(p.suffix,'.mp3');self.mod.verify_media(p,'mp3')
    def test_auth_and_settings(self):
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as e:urllib.request.urlopen(self.base+'/api/state')
        self.assertEqual(e.exception.code,403)
        self.assertEqual(json.loads(self.mod.CONFIG.read_text())['download_dir'],str(self.dest.resolve()))
        self.assertTrue(all(t['ready'] for t in self.call('/api/diagnostics')['tools'].values()))
    def test_invalid_clip(self):
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as e:self.call('/api/start',{'urls':[self.url],'options':{'clip':True,'start':'00:00:07','end':'00:00:03'}})
        self.assertEqual(e.exception.code,400)
    def test_zero_output_rejected(self):
        with self.assertRaises(RuntimeError):self.mod.verify_media(self.dest/'nonexistent.mp4')
if __name__=='__main__':unittest.main(verbosity=2)


