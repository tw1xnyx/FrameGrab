import sys,time,threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from test_windows_real import WindowsPipeline
class PauseResume(WindowsPipeline):
 def test_pause_resume_and_cancel(self):
  data=(self.media/'owned-test.mp4').read_bytes();ranges=[]
  class Slow(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_HEAD(self):self.send_response(200);self.send_header('Content-Length',len(data));self.send_header('Content-Type','video/mp4');self.end_headers()
   def do_GET(self):
    start=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0]);ranges.append(start);self.send_response(206 if start else 200);self.send_header('Content-Type','video/mp4');self.send_header('Content-Length',len(data)-start);self.send_header('Accept-Ranges','bytes')
    if start:self.send_header('Content-Range',f'bytes {start}-{len(data)-1}/{len(data)}')
    self.end_headers()
    try:
     for off in range(start,len(data),2048):self.wfile.write(data[off:off+2048]);self.wfile.flush();time.sleep(.04)
    except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
  host=ThreadingHTTPServer(('127.0.0.1',0),Slow);threading.Thread(target=host.serve_forever,daemon=True).start()
  try:
   url=f'http://127.0.0.1:{host.server_port}/slow.mp4'
   for cancel in [False,True]:
    jid=self.call('/api/start',{'urls':[url],'options':{'destination':str(self.dest),'download_mode':'premiere'}})['job_id']
    def item():return self.mod.JOBS[jid]['items'][0]
    for _ in range(400):
     if item()['phase']=='Downloading Video' and (jid,0) in self.mod.PROCESSES and item().get('progress',0)>15:break
     time.sleep(.05)
    self.call('/api/pause',{'job_id':jid,'index':0})
    for _ in range(200):
     if item()['status']=='paused':break
     time.sleep(.05)
    self.assertEqual(item()['status'],'paused',str(item()))
    if cancel:
     self.call('/api/cancel',{'job_id':jid,'index':0});self.assertEqual(item()['status'],'canceled');continue
    self.assertTrue(any((self.mod.WORK/f'{jid}-0').rglob('*.part')))
    self.call('/api/resume',{'job_id':jid,'index':0})
    for _ in range(1000):
     if item()['status'] in ['done','error']:break
     time.sleep(.05)
    self.assertEqual(item()['status'],'done',str(item()));self.mod.verify_media(self.dest/item()['file_name'],require_audio=True)
   self.assertTrue(any(n>0 for n in ranges),str(ranges))
  finally:host.shutdown();host.server_close()
if __name__=='__main__':
 import unittest
 unittest.main(defaultTest='PauseResume.test_pause_resume_and_cancel',verbosity=2)
