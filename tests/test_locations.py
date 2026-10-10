import sys,json,time,unittest,os
from pathlib import Path
from unittest.mock import patch
from test_windows_real import WindowsPipeline
class Locations(WindowsPipeline):
 def test_distinct_destinations(self):
  a=self.dest/'Alpha spaces';b=self.dest/'Unicode \u0648\u06cc\u0688\u06cc\u0648';a.mkdir(exist_ok=True);b.mkdir(exist_ok=True)
  jobs=[self.call('/api/start',{'urls':[self.url],'options':{'destination':str(folder),'download_mode':'premiere'}})['job_id'] for folder in [a,b]]
  self.mod.set_folder(str(self.dest))
  for jid,folder in zip(jobs,[a,b]):
   for _ in range(600):
    j=next(j for j in self.call('/api/state')['jobs'] if j['id']==jid)
    if j['status']=='finished':break
    time.sleep(.1)
   self.assertEqual(j['done'],1,json.dumps(j));p=folder/j['items'][0]['file_name'];self.assertTrue(p.is_file());self.mod.verify_media(p,require_audio=True)
   entry=next(h for h in self.mod.HIST if h['id']==j['items'][0]['id']);self.assertEqual(Path(entry['path']).parent,folder)
 def test_actual_d_drive(self):
  import uuid
  if not Path('D:/').is_dir():self.skipTest('D drive unavailable')
  folder=Path('D:/')/('FrameGrab-QA-'+uuid.uuid4().hex[:8]);folder.mkdir()
  try:
   jid=self.call('/api/start',{'urls':[self.url],'options':{'destination':str(folder),'download_mode':'premiere'}})['job_id']
   for _ in range(600):
    j=next(j for j in self.call('/api/state')['jobs'] if j['id']==jid)
    if j['status']=='finished':break
    time.sleep(.1)
   self.assertEqual(j['done'],1,json.dumps(j));file=folder/j['items'][0]['file_name'];self.assertTrue(file.is_file());self.mod.verify_media(file,require_audio=True)
  finally:
   assert folder.parent==Path('D:/') and folder.name.startswith('FrameGrab-QA-')
   for file in folder.iterdir():
    if file.is_file():file.unlink()
   folder.rmdir()
 def test_unavailable_no_fallback(self):
  with self.assertRaises(ValueError):self.mod.create_batch([self.url],{'destination':str(self.dest/'missing-folder')})
  cfg=json.loads(self.mod.CONFIG.read_text());cfg['download_dir']=str(self.dest/'disconnected-drive');self.mod.CONFIG.write_text(json.dumps(cfg));self.mod.load_state();self.assertEqual(self.mod.SETTINGS['download_dir'],cfg['download_dir']);self.mod.set_folder(str(self.dest))
 def test_disk_space_rejection(self):
  from collections import namedtuple
  Usage=namedtuple('Usage','total used free')
  with patch.object(self.mod.shutil,'disk_usage',return_value=Usage(1000,999,1)):
   with self.assertRaisesRegex(ValueError,'Insufficient'):self.mod.validate_destination(self.dest)
 def test_write_failure_rejection(self):
  real=Path.open
  def reject(p,*a,**kw):
   if p.name.startswith('.framegrab-writecheck-'):raise PermissionError('Read-only test destination')
   return real(p,*a,**kw)
  with patch.object(Path,'open',reject):
   with self.assertRaisesRegex(ValueError,'not writable'):self.mod.validate_destination(self.dest)
if __name__=='__main__':
 suite=unittest.TestSuite(Locations(n) for n in ['test_actual_d_drive','test_distinct_destinations','test_unavailable_no_fallback','test_disk_space_rejection','test_write_failure_rejection'])
 result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())
