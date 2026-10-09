import sys,json,time,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from test_windows_real import WindowsPipeline
class UpgradeAPI(WindowsPipeline):
 def wait(self,jid):
  for _ in range(600):
   j=next(j for j in self.call('/api/state')['jobs'] if j['id']==jid)
   if j['status']=='finished':return j
   time.sleep(.1)
  self.fail('Processing timed out')
 def test_mode_and_unknown_settings_preserved(self):
  config=json.loads(self.mod.CONFIG.read_text());config['legacy_custom_preference']={'keep':True};self.mod.CONFIG.write_text(json.dumps(config));self.mod.load_state()
  self.call('/api/preferences',{'download_mode':'standard','create_proxy':True});self.mod.load_state()
  state=self.call('/api/state');self.assertEqual(state['preferences'],{'download_mode':'standard','create_proxy':True})
  self.assertEqual(json.loads(self.mod.CONFIG.read_text())['legacy_custom_preference'],{'keep':True})
  p=self.download({'download_mode':'standard'});self.assertNotIn('_Premiere',p.stem)
  self.call('/api/preferences',{'download_mode':'premiere','create_proxy':False})
 def test_retry_conversion_without_redownload(self):
  with patch.object(self.mod.media_compat,'prepare',side_effect=self.mod.media_compat.MediaError('Injected processing fault')):
   jid=self.call('/api/start',{'urls':[self.url],'options':{'download_mode':'premiere'}})['job_id'];j=self.wait(jid)
  item=j['items'][0];self.assertEqual(item['status'],'error');self.assertTrue(item['can_retry_conversion']);self.assertNotIn('conversion_source',item)
  with patch.object(self.mod,'metadata',side_effect=AssertionError('Retry attempted a new download')):
   self.call('/api/retry-conversion',{'job_id':jid,'index':0});j=self.wait(jid)
  self.assertEqual(j['done'],1,json.dumps(j));self.assertIn('_Premiere.mp4',j['items'][0]['file_name'])
 def test_retry_rejects_modified_original(self):
  with patch.object(self.mod.media_compat,'prepare',side_effect=self.mod.media_compat.MediaError('Injected processing fault')):
   jid=self.call('/api/start',{'urls':[self.url],'options':{'download_mode':'premiere'}})['job_id'];self.wait(jid)
  from pathlib import Path
  p=Path(self.mod.JOBS[jid]['items'][0]['conversion_source']);p.write_bytes(p.read_bytes()+b'changed')
  with self.assertRaises(HTTPError) as cm:self.call('/api/retry-conversion',{'job_id':jid,'index':0})
  self.assertEqual(cm.exception.code,400)
if __name__=='__main__':
 suite=unittest.TestSuite(UpgradeAPI(n) for n in ['test_mode_and_unknown_settings_preserved','test_retry_conversion_without_redownload','test_retry_rejects_modified_original'])
 result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())
