import sys,json,subprocess,unittest,shutil
from pathlib import Path
from fractions import Fraction
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'service'));import media_compat as m
FF=ROOT/'tools/ffmpeg.exe';FP=ROOT/'tools/ffprobe.exe';T=ROOT/'.qa-optimized';T.mkdir(exist_ok=True)
RESULTS=[]
def run(*args):
 p=subprocess.run([str(FF),'-v','error','-nostdin','-y',*map(str,args)],capture_output=True,creationflags=m._flags())
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
def sample(name,size='640x360',rate='30',extra=(),codec='libx264',duration=3):
 p=T/name;run('-f','lavfi','-i',f'testsrc2=size={size}:rate={rate}','-f','lavfi','-i','sine=frequency=600:sample_rate=48000','-t',duration,'-c:v',codec,'-threads','4','-g','300','-c:a','aac',*extra,p);return p
class Optimized(unittest.TestCase):
 def check(self,p,rate=None,**kw):
  events=[];telemetry=[];out,r=m.prepare(p,FF,FP,True,progress=lambda *e:events.append(e),telemetry=telemetry.append,**kw)
  info=m.probe(out,FP);self.assertTrue(all(m.compatible(info,m.decode(out,info,FF))));self.assertLessEqual(r['timing']['max_gop_seconds'],2.1)
  self.assertIn('_Premiere',out.stem);m.validate_stream_timing(info)
  if rate:self.assertAlmostEqual(float(Fraction(info['video'][0]['avg_frame_rate'])),float(Fraction(rate)),delta=.01)
  RESULTS.append({'source':p.name,'output':str(out.resolve()),'action':r['action'],'encoder':r['encoder'],'resolution':[info['video'][0]['width'],info['video'][0]['height']],'fps':info['video'][0]['avg_frame_rate'],'max_gop_seconds':r['timing']['max_gop_seconds'],'duration':info['duration'],'telemetry':telemetry})
  return out,r,events
 def test_rates_and_high_resolution(self):
  for size,rate in [('640x360','24000/1001'),('640x360','25'),('640x360','30000/1001'),('1920x1080','30'),('1920x1080','60'),('2560x1440','60000/1001'),('3840x2160','30')]:
   with self.subTest(size=size,rate=rate):
    out,r,e=self.check(sample('resolution-'+size+'-'+rate.replace('/','-')+'.mp4',size,rate),rate)
    self.assertTrue(r['encoder'].startswith('GPU'),r['encoder'])
 def test_gpu_failure_cpu_fallback(self):
  p=sample('gpu-failure.mp4');real=m._run
  def fail_gpu(args,*a,**k):
   if 'h264_nvenc' in args:raise m.MediaError('Injected device failure')
   return real(args,*a,**k)
  with patch.object(m,'_run',fail_gpu):out,r,e=self.check(p,'30')
  self.assertIn('CPU',r['encoder'])
 def test_cpu_only(self):
  out,r,e=self.check(sample('cpu-only.mp4'),force_cpu=True);self.assertIn('CPU',r['encoder'])
 def test_vfr_intended_rate(self):
  self.check(sample('vfr-irregular.mp4',extra=('-vf',"select='if(lt(t,1),not(mod(n,2)),1)'",'-fps_mode','vfr')),'30')
 def test_timestamp_offset(self):
  self.check(sample('offset.mp4',extra=('-output_ts_offset','7')),'30')
 def test_proxy(self):
  out,r,e=self.check(sample('with-proxy.mp4'),proxy=True);proxy=Path(r['proxy_path']);info=m.probe(proxy,FP)
  self.assertEqual(info['video'][0]['codec_name'],'prores');self.assertTrue(out.is_file());m.decode(proxy,info,FF,check_vfr=False)
 def test_hdr_tone_mapping(self):
  self.check(sample('hdr.mkv',extra=('-pix_fmt','yuv420p10le','-color_primaries','bt2020','-color_trc','smpte2084','-colorspace','bt2020nc')))
 def test_standard_no_conversion(self):
  p=sample('standard.mkv');original=p.read_bytes();out,r=m.prepare(p,FF,FP,True,premiere=False)
  self.assertEqual(out,p);self.assertEqual(out.read_bytes(),original)
 def test_collision(self):
  p=sample('collision.mp4');q=T/'collision_Premiere.mp4';q.write_bytes(b'preserved existing file');self.check(p)
  self.assertEqual(q.read_bytes(),b'preserved existing file')
 def test_separate_stream_merge(self):
  p=sample('separate-input.mp4');v=T/'video-only.mp4';a=T/'audio-only.m4a';merged=T/'separate-merged.mkv'
  run('-i',p,'-map','0:v','-c','copy',v);run('-i',p,'-map','0:a','-c','copy',a)
  run('-i',v,'-i',a,'-map','0:v','-map','1:a','-c','copy',merged);self.check(merged)
if __name__=='__main__':
 try:unittest.main(verbosity=2)
 finally:(T/'results.json').write_text(json.dumps(RESULTS,indent=2),encoding='utf-8')
