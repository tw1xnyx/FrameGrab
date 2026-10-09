import hashlib, json, os, shutil, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'service'))
import media_compat as m
T=ROOT/'.qa-compat';T.mkdir(exist_ok=True)
FF=ROOT/'tools/ffmpeg.exe'; FP=ROOT/'tools/ffprobe.exe'

def run(*args):
    p=subprocess.run([str(FF),'-v','error','-nostdin','-y',*map(str,args)],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))

def fixture(name,v='libx264',a='aac',rate=48000,extra=()):
    p=T/name
    run('-f','lavfi','-i','testsrc2=size=160x90:rate=24','-f','lavfi','-i',f'sine=frequency=440:sample_rate={rate}','-t','3','-c:v',v,'-g','48','-c:a',a,*extra,p)
    return p

class Compatibility(unittest.TestCase):
    def check(self,p,require_audio=True):
        events=[];out,result=m.prepare(p,FF,FP,require_audio,progress=lambda *x:events.append(x))
        info=m.probe(out,FP)
        self.assertEqual(out.suffix,'.mp4');self.assertTrue(all(m.compatible(info,m.decode(out,info,FF))))
        self.assertEqual(info['video'][0]['width'],160);self.assertEqual(info['video'][0]['height'],90)
        self.assertAlmostEqual(info['duration'],3,delta=.2)
        self.assertFalse(list(T.glob('.framegrab-*')))
        return out,result,events
    def test_01_h264_aac_cfr_unchanged(self):
        p=fixture('compatible.mp4');before=hashlib.sha256(p.read_bytes()).hexdigest();out,r,e=self.check(p)
        self.assertEqual(r['action'],'unchanged');self.assertEqual(before,hashlib.sha256(out.read_bytes()).hexdigest())
        self.assertFalse(any(x[0]=='Converting' for x in e))
    def test_02_vp9_webm_opus(self):
        out,r,e=self.check(fixture('vp9.webm','libvpx-vp9','libopus'))
        self.assertEqual(r['action'],'transcode');self.assertTrue(any(x[0]=='Converting' for x in e))
    def test_03_av1(self):
        self.check(fixture('av1.webm','libaom-av1','libopus',extra=('-cpu-used','8')))
    def test_04_mkv_lossless_remux(self):
        p=fixture('remux.mkv');before=T/'before.h264';run('-i',p,'-map','0:v:0','-c','copy',before)
        out,r,e=self.check(p);after=T/'after.h264';run('-i',out,'-map','0:v:0','-c','copy',after)
        self.assertEqual(r['action'],'remux');self.assertEqual(before.read_bytes(),after.read_bytes())
    def test_05_variable_frame_rate(self):
        p=fixture('vfr.mp4',extra=('-vf',"select='if(lt(t,1),not(mod(n,2)),1)'",'-fps_mode','vfr'))
        info=m.probe(p,FP);self.assertTrue(m.decode(p,info,FF));self.check(p)
    def test_06_audio_pcm_resample(self):
        self.check(fixture('pcm.mkv',a='pcm_s16le',rate=44100))
    def test_07_wrong_extension(self):
        p=fixture('wrong.mkv','libvpx-vp9','libopus');q=T/'wrong.mp4';p.replace(q);self.check(q)
    def test_08_corrupted_retained(self):
        p=fixture('broken.mp4',extra=('-movflags','+faststart'));data=p.read_bytes();p.write_bytes(data[:len(data)//2]);before=p.read_bytes()
        with self.assertRaises(m.MediaError):m.prepare(p,FF,FP,True)
        self.assertEqual(before,p.read_bytes())
    def test_09_missing_audio(self):
        p=T/'silent.mp4';run('-f','lavfi','-i','testsrc2=size=160x90:rate=24','-t','3','-c:v','libx264',p)
        with self.assertRaisesRegex(m.MediaError,'audio'):m.prepare(p,FF,FP,True)
    def test_10_image_webp(self):
        p=T/'image.webp';run('-f','lavfi','-i','color=c=red:size=160x90','-frames:v','1',p)
        out=m.prepare_image(p,FF,FP);self.assertEqual(out.suffix,'.png');self.assertTrue(out.is_file())
    def test_11_high_bit_depth(self):
        self.check(fixture('ten-bit.mkv',extra=('-pix_fmt','yuv420p10le')))
if __name__=='__main__':unittest.main(verbosity=2)
