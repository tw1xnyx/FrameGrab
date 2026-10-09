"""Local Premiere preparation. No network services; original is retained until validation."""
import json
import math
import time
import os
import re
import subprocess
import threading
import uuid
from collections import deque, Counter
from fractions import Fraction
from pathlib import Path

class MediaError(RuntimeError):
    pass

def _flags():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0)

def probe(path, ffprobe):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise MediaError('The downloaded file is missing or empty.')
    p = subprocess.run([str(ffprobe), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120, creationflags=_flags())
    if p.returncode:
        raise MediaError('Media inspection failed: ' + p.stderr[-1500:])
    try:
        info = json.loads(p.stdout)
        info['duration'] = float(info.get('format', {}).get('duration') or 0)
    except (ValueError, TypeError) as exc:
        raise MediaError('Media inspection returned invalid duration or metadata.') from exc
    info['video'] = [s for s in info.get('streams', []) if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')]
    info['audio'] = [s for s in info.get('streams', []) if s.get('codec_type') == 'audio']
    if info['duration'] <= 0:
        raise MediaError('The media has no valid duration.')
    return info

def _run(args, duration, phase, progress, cancel, telemetry=lambda data: None):
    """Drain both pipes, report timestamp-based progress and honor cancellation."""
    err = deque(maxlen=100)
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding='utf-8', errors='replace', creationflags=_flags())
    def read_errors():
        for line in p.stderr:
            err.append(line.rstrip())
    t = threading.Thread(target=read_errors, daemon=True)
    t.start()
    def watch_cancel():
        while p.poll() is None:
            if cancel and cancel.wait(.2):
                try: p.kill()
                except OSError: pass
                return
            if not cancel:
                return
    watcher = threading.Thread(target=watch_cancel, daemon=True)
    watcher.start()
    try:
        for line in p.stdout:
            key, _, value = line.strip().partition('=')
            if key == 'speed' and value != 'N/A':
                telemetry({'processing_speed': value})
            if key == 'out_time_us':
                try: progress(phase, min(99.0, max(0.0, float(value) / 1_000_000 / duration * 100)))
                except ValueError: pass
        rc = p.wait()
        t.join(timeout=5)
        if cancel and cancel.is_set():
            raise MediaError('Media processing canceled.')
        if rc:
            raise MediaError(phase + ' failed: ' + '\n'.join(err)[-3000:])
        progress(phase, 100)
        return '\n'.join(err)
    finally:
        if p.poll() is None:
            p.kill(); p.wait()
        p.stdout.close(); p.stderr.close()

def decode(path, info, ffmpeg, progress=lambda *a: None, cancel=None, check_vfr=True):
    args = [str(ffmpeg), '-hide_banner', '-nostdin', '-xerror', '-err_detect', 'explode', '-v', 'info', '-i', str(path)]
    if info['video']:
        args += ['-map', '0:' + str(info['video'][0]['index'])]
    args += ['-map', '0:a?', '-sn', '-dn']
    if info['video'] and check_vfr:
        args += ['-vf', 'vfrdet']
    args += ['-progress', 'pipe:1', '-nostats', '-f', 'null', '-']
    log = _run(args, info['duration'], 'Verifying', progress, cancel)
    if info['video'] and check_vfr:
        m = re.search(r'VFR:([0-9.]+)\s*\((\d+)/(\d+)\)', log)
        if not m:
            raise MediaError('Frame timing could not be verified.')
        # FFmpeg's VFR statistic flags differing time-base intervals. Exact zero is required.
        different = float(m.group(1)) > 0 or int(m.group(2)) > 0
        # Matroska/WebM often use millisecond timestamps: CFR 24/30 fps then
        # alternates neighboring ticks. This quantization is not true VFR.
        span = re.search(r'min:\s*(-?\d+) max:\s*(-?\d+)', log)
        if different and span and int(span.group(1)) > 0 and int(span.group(2))-int(span.group(1)) <= 1:
            return False
        return different
    return False

def frame_rate(video):
    for key in ('avg_frame_rate', 'r_frame_rate'):
        try:
            rate = Fraction(video.get(key, '0/1'))
            if 1 <= rate <= 240:
                # Restore standard NTSC rates where source averaging introduces rounding.
                for standard in (Fraction(24000,1001),Fraction(30000,1001),Fraction(60000,1001),Fraction(120000,1001)):
                    if abs(float(rate-standard)) < .015:
                        return str(standard)
                return str(rate.limit_denominator(1001))
        except (ValueError, ZeroDivisionError):
            pass
    raise MediaError('A usable source frame rate could not be determined.')

def compatible(info, vfr):
    v = info['video'][0]
    video_ok = v.get('codec_name') == 'h264' and v.get('pix_fmt') == 'yuv420p' and not vfr and v.get('field_order', 'progressive') in ('progressive', 'unknown')
    audio_ok = all(a.get('codec_name') == 'aac' and a.get('profile') in ('LC', None) and int(a.get('sample_rate') or 0) == 48000 for a in info['audio'])
    return video_ok, audio_ok

_NVENC_CACHE = {}
_NVENC_LOCK = threading.Lock()

def nvenc_status(ffmpeg):
    """Capability requires both the encoder and an actual driver-backed encode."""
    key=(str(ffmpeg),Path(ffmpeg).stat().st_mtime_ns)
    with _NVENC_LOCK:
        if key in _NVENC_CACHE: return dict(_NVENC_CACHE[key])
        try:
            listing=subprocess.run([str(ffmpeg),'-hide_banner','-encoders'],capture_output=True,timeout=20,creationflags=_flags())
            if b'h264_nvenc' not in listing.stdout: raise MediaError('Bundled FFmpeg has no h264_nvenc encoder.')
            test=subprocess.run([str(ffmpeg),'-v','error','-nostdin','-f','lavfi','-i','color=size=320x240:rate=30','-frames:v','8','-c:v','h264_nvenc','-preset','p5','-tune','hq','-profile:v','high','-pix_fmt','yuv420p','-f','null','-'],capture_output=True,timeout=25,creationflags=_flags())
            if test.returncode: raise MediaError(test.stderr.decode('utf-8','replace')[-700:])
            result={'available':True,'encoder':'GPU · NVIDIA NVENC','reason':'Real NVENC encode succeeded.'}
        except (OSError,subprocess.TimeoutExpired,MediaError) as exc:
            result={'available':False,'encoder':'CPU · x264','reason':str(exc)}
        _NVENC_CACHE[key]=result
        return dict(result)

def analyze_frames(path, info, ffprobe, progress=lambda *a: None, cancel=None):
    """Stream frame timing/keyframe metadata; memory does not grow with video length."""
    progress('Inspecting',0)
    args=[str(ffprobe),'-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time,key_frame','-of','compact=p=0:nk=0',str(path)]
    intervals=Counter(); last=None; first=None; key_last=None; max_gop=0.; broken=0; count=0
    p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',errors='replace',creationflags=_flags())
    try:
        for line in p.stdout:
            if cancel and cancel.is_set(): raise MediaError('Media analysis canceled.')
            row=dict(part.split('=',1) for part in line.strip().split('|') if '=' in part)
            if 'key_frame' not in row: continue
            count+=1
            try: stamp=float(row['best_effort_timestamp_time'])
            except (KeyError,ValueError): broken+=1;continue
            if not math.isfinite(stamp): broken+=1;continue
            if first is None:first=stamp
            if last is not None:
                delta=stamp-last
                if delta<=0:broken+=1
                else:intervals[round(delta,5)]+=1
            last=stamp
            if row.get('key_frame')=='1':
                if key_last is not None:max_gop=max(max_gop,stamp-key_last)
                key_last=stamp
            if count%90==0:progress('Inspecting',min(99,max(0,(stamp-first)/info['duration']*100)))
        if p.wait():raise MediaError('Frame metadata analysis failed.')
        if count<2 or not intervals:raise MediaError('Video has no usable frame timing.')
        max_gop=max(max_gop,(last-key_last) if key_last is not None else info['duration'])
        # Adjacent millisecond intervals from Matroska/WebM are quantization, not VFR.
        total=sum(intervals.values()); typical,n=intervals.most_common(1)[0]
        close=sum(c for d,c in intervals.items() if abs(d-typical)<=.0011)
        measured=1/typical
        if close/total>.8: measured=total/sum(d*c for d,c in intervals.items())
        else:
            try:nominal=Fraction(info['video'][0].get('r_frame_rate') or '0/1')
            except (ValueError,ZeroDivisionError):nominal=Fraction(0)
            if 1<=nominal<=240 and abs(float(nominal)-measured)/measured<.02:measured=float(nominal)
        rate=Fraction(measured).limit_denominator(1001)
        standards=[Fraction(24000,1001),Fraction(24),Fraction(25),Fraction(30000,1001),Fraction(30),Fraction(50),Fraction(60000,1001),Fraction(60),Fraction(120)]
        nearest=min(standards,key=lambda common:abs(float(common)-measured)/float(common))
        if abs(float(nearest)-measured)/float(nearest)<.001:rate=nearest
        if not 1<=rate<=240:rate=Fraction(frame_rate(info['video'][0]))
        progress('Inspecting',100)
        return {'frames':count,'rate':str(rate),'broken_timestamps':broken,'max_gop_seconds':max_gop,'intervals':dict(intervals)}
    finally:
        if p.poll() is None:p.kill();p.wait()
        p.stdout.close()

def validate_stream_timing(info):
    v=info['video'][0]
    vd=float(v.get('duration') or info['duration']); vs=float(v.get('start_time') or 0)
    for a in info['audio']:
        ad=float(a.get('duration') or info['duration']);ast=float(a.get('start_time') or 0)
        if abs(ast-vs)>.25 or abs((ast+ad)-(vs+vd))>max(.35,info['duration']*.005):
            raise MediaError('Audio/video timing differs unexpectedly; original retained for recovery.')

def _output_name(source):
    stem=source.stem if source.stem.endswith('_Premiere') else source.stem+'_Premiere'
    target=source.with_name(stem+'.mp4')
    if target==source:return target
    for n in range(1,10000):
        candidate=target if n==1 else source.with_name(stem+' ('+str(n)+').mp4')
        try:
            # Reserve the name across simultaneous conversions, without overwriting files.
            with candidate.open('xb'):pass
            return candidate
        except FileExistsError:continue
    raise MediaError('Cannot reserve a free output filename.')

def prepare(path, ffmpeg, ffprobe, require_audio=False, premiere=True, progress=lambda *a: None, cancel=None, log=lambda *a: None, telemetry=lambda data: None, force_cpu=False, proxy=False):
    source=Path(path)
    if source.suffix.lower() in ('.avif','.webp','.heic','.heif','.png','.jpg','.jpeg'):
        result=prepare_image(source,ffmpeg,ffprobe)
        return result,{'action':'image-png','duration':0,'streams':[],'size':result.stat().st_size}
    info=probe(source,ffprobe)
    if not info['video']:raise MediaError('The download has no usable video stream.')
    if require_audio and not info['audio']:raise MediaError('The download is missing expected audio; retry the source download.')
    vfr=decode(source,info,ffmpeg,lambda phase,pct:progress('Inspecting',pct),cancel)
    if not premiere:
        return source,{'action':'validated-original','duration':info['duration'],'streams':info['streams'],'size':source.stat().st_size,'encoder':'Original streams'}
    timing=analyze_frames(source,info,ffprobe,progress,cancel)
    v_ok,a_ok=compatible(info,vfr)
    v=info['video'][0];hdr=v.get('color_transfer') in ('smpte2084','arib-std-b67')
    # Compatibility alone is not enough for editing: constrain keyframe gaps and complexity.
    refs=int(v.get('refs') or 0);bitrate=int(v.get('bit_rate') or 0)
    ceiling=max(8000000,min(160000000,int(v['width']*v['height']*float(Fraction(timing['rate']))*.16)))
    v_ok=v_ok and not hdr and not timing['broken_timestamps'] and timing['max_gop_seconds']<=2.05 and refs<=4 and (not bitrate or bitrate<=ceiling*1.25)
    container_ok='mp4' in info.get('format',{}).get('format_name','').split(',') and source.suffix.lower()=='.mp4'
    target=_output_name(source); reserved=target!=source;committed=False
    temp=source.parent/('.framegrab-'+uuid.uuid4().hex+'.mp4')
    try:
        if v_ok and a_ok and container_ok:
            validate_stream_timing(info)
            if target!=source:
                os.replace(source,target)
            committed=True;result={'action':'unchanged','duration':info['duration'],'streams':info['streams'],'size':target.stat().st_size,'encoder':'Original streams','timing':timing}
            progress('Verifying',100)
            log('Optimization passed: original compressed streams retained; editing-friendly GOP and CFR verified.')
        else:
            gpu=nvenc_status(ffmpeg) if not force_cpu and not v_ok else {'available':False,'reason':'CPU selected or video copied.'}
            attempts=['copy','cpu'] if v_ok else (['gpu','cpu'] if gpu['available'] else ['cpu','cpu'])
            if not gpu['available'] and not v_ok:log('CPU x264 selected: '+gpu['reason'])
            for attempt,encoder in enumerate(attempts):
                try:
                    rate=Fraction(timing['rate']);fps=float(rate);gop=max(1,round(fps*2))
                    args=[str(ffmpeg),'-hide_banner','-nostdin','-y','-fflags','+genpts','-noautorotate','-i',str(source),'-map','0:'+str(v['index']),'-map','0:a?','-map_metadata','0','-sn','-dn']
                    if encoder=='copy':
                        timing_filter='setts=time_base=1/'+str(rate.numerator*1000)+':prescale=1:pts=round(PTS*TB*'+str(fps)+')/'+str(fps)+'/TB:dts=round(DTS*TB*'+str(fps)+')/'+str(fps)+'/TB:duration=1/'+str(fps)+'/TB'
                        args+=['-c:v','copy','-bsf:v',timing_filter];label='Original video · lossless remux'
                    else:
                        filters=[]
                        if v.get('field_order','progressive') not in ('progressive','unknown'):filters.append('bwdif=mode=send_frame')
                        if hdr:
                            if v.get('color_primaries') not in ('bt2020',) or v.get('color_space') not in ('bt2020nc','bt2020c'):
                                raise MediaError('HDR color primaries/matrix are missing or ambiguous; refusing an unverified color conversion.')
                            filters+=['zscale=t=linear:npl=100','format=gbrpf32le','tonemap=tonemap=hable:desat=0','zscale=p=bt709:t=bt709:m=bt709:r=tv']
                            log('HDR tone-mapped explicitly to SDR BT.709 for the 8-bit MP4 profile.')
                        filters+=['pad=ceil(iw/2)*2:ceil(ih/2)*2','fps='+str(rate),'format=yuv420p']
                        sar=Fraction(v.get('sample_aspect_ratio','1:1').replace(':','/')) if v.get('sample_aspect_ratio') not in (None,'N/A','0:1') else Fraction(1)
                        dar=Fraction(int(v['width']),int(v['height']))*sar;outw=int(v['width'])+int(v['width'])%2;outh=int(v['height'])+int(v['height'])%2
                        filters+=['setsar='+str(dar*Fraction(outh,outw))]
                        if encoder=='gpu':
                            args+=['-c:v','h264_nvenc','-preset','p5','-tune','hq','-rc','vbr','-cq','19','-b:v','0','-spatial-aq','1','-rc-lookahead','16','-forced-idr','1'];label='GPU · NVIDIA NVENC'
                        else:
                            args+=['-c:v','libx264','-preset','medium','-crf','18','-threads','4','-x264-params','open-gop=0:scenecut=0'];label='CPU · x264'
                        args+=['-profile:v','high','-pix_fmt','yuv420p','-g',str(gop),'-keyint_min',str(max(1,round(fps))),'-bf','2','-refs','3','-force_key_frames','expr:gte(t,n_forced*2)','-maxrate',str(ceiling),'-bufsize',str(ceiling*2),'-vf',','.join(filters),'-fps_mode','cfr']
                        colors={'color_primaries':'bt709','color_trc':'bt709','colorspace':'bt709','color_range':'tv'} if hdr else {'color_primaries':v.get('color_primaries'),'color_trc':v.get('color_transfer'),'colorspace':v.get('color_space'),'color_range':v.get('color_range')}
                        for name,value in colors.items():
                            if value and value not in ('unknown','unspecified'):args+=['-'+name,value]
                    if a_ok and attempt==0:args+=['-c:a','copy']
                    else:args+=['-c:a','aac','-profile:a','aac_low','-b:a','256k','-ar','48000']
                    args+=['-avoid_negative_ts','make_zero','-movflags','+faststart','-max_muxing_queue_size','4096','-progress','pipe:1','-nostats','-f','mp4',str(temp)]
                    telemetry({'encoder':label,'processing_speed':''});progress('Converting',0)
                    _run(args,info['duration'],'Converting',progress,cancel,telemetry)
                    final=probe(temp,ffprobe)
                    if not final['video'] or (require_audio and not final['audio']):raise MediaError('Processed output is missing expected streams.')
                    final_vfr=decode(temp,final,ffmpeg,progress,cancel)
                    if not all(compatible(final,final_vfr)) or 'mp4' not in final['format']['format_name']:raise MediaError('Final output fails H.264/AAC/CFR MP4 profile.')
                    validate_stream_timing(final)
                    final_timing=analyze_frames(temp,final,ffprobe,lambda phase,pct:progress('Verifying',pct),cancel)
                    if final_timing['broken_timestamps'] or final_timing['max_gop_seconds']>2.10:raise MediaError('Final timestamps/keyframe intervals failed verification.')
                    if abs(final['duration']-info['duration'])>max(.30,2/fps):raise MediaError('Processed duration differs unexpectedly from source.')
                    after=final['video'][0]
                    if (after['width'],after['height'])!=(int(v['width'])+int(v['width'])%2,int(v['height'])+int(v['height'])%2):raise MediaError('Processed dimensions changed unexpectedly.')
                    out_sar=Fraction(after.get('sample_aspect_ratio','1:1').replace(':','/')) if after.get('sample_aspect_ratio') not in (None,'N/A','0:1') else Fraction(1)
                    src_sar=Fraction(v.get('sample_aspect_ratio','1:1').replace(':','/')) if v.get('sample_aspect_ratio') not in (None,'N/A','0:1') else Fraction(1)
                    if abs(float(Fraction(after['width'],after['height'])*out_sar/(Fraction(v['width'],v['height'])*src_sar))-1)>.002:raise MediaError('Display aspect ratio changed unexpectedly.')
                    if hdr and any(after.get(k)!=val for k,val in [('color_primaries','bt709'),('color_transfer','bt709'),('color_space','bt709')]):raise MediaError('Tone-mapped color metadata failed validation.')
                    os.replace(temp,target);committed=True
                    if target!=source:
                        try:source.unlink()
                        except OSError:log('Output ready; source retained because cleanup is unavailable.')
                    result={'action':'remux' if encoder=='copy' else 'transcode','duration':final['duration'],'streams':final['streams'],'size':target.stat().st_size,'encoder':label,'timing':final_timing}
                    log('Verified Premiere MP4: '+result['action']+' using '+label);break
                except (MediaError,subprocess.SubprocessError) as exc:
                    temp.unlink(missing_ok=True)
                    if (cancel and cancel.is_set()) or attempt==len(attempts)-1:raise
                    log('Processing failed; retrying safely with CPU x264: '+str(exc)[-800:]);telemetry({'encoder':'CPU · x264 fallback','processing_speed':''})
        if proxy:
            try:result['proxy_path']=str(create_proxy(target,ffmpeg,ffprobe,progress,cancel))
            except (MediaError,subprocess.SubprocessError,OSError) as exc:log('Main MP4 verified; optional proxy failed: '+str(exc));result['proxy_error']=str(exc)
        return target,result
    finally:
        temp.unlink(missing_ok=True)
        if reserved and not committed:target.unlink(missing_ok=True)

def create_proxy(source,ffmpeg,ffprobe,progress=lambda *a:None,cancel=None):
    """Optional intraframe editing proxy alongside (never instead of) the verified MP4."""
    source=Path(source);info=probe(source,ffprobe);dest=source.with_name(source.stem+'_Proxy.mov')
    for n in range(1,10000):
        candidate=dest if n==1 else dest.with_name(dest.stem+' ('+str(n)+').mov')
        try:
            with candidate.open('xb'):pass
            dest=candidate;break
        except FileExistsError:continue
    else:raise MediaError('Cannot reserve proxy filename.')
    temp=source.parent/('.framegrab-'+uuid.uuid4().hex+'.mov');committed=False
    try:
        args=[str(ffmpeg),'-hide_banner','-nostdin','-y','-i',str(source),'-map','0:v:0','-map','0:a?','-vf',"scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",'-c:v','prores_ks','-profile:v','0','-pix_fmt','yuv422p10le','-vendor','apl0','-threads','4','-c:a','pcm_s16le','-ar','48000','-progress','pipe:1','-nostats',str(temp)]
        _run(args,info['duration'],'Creating editing proxy',progress,cancel)
        final=probe(temp,ffprobe);decode(temp,final,ffmpeg,progress,cancel)
        if final['video'][0]['codec_name']!='prores' or abs(final['duration']-info['duration'])>.3:raise MediaError('Proxy verification failed.')
        os.replace(temp,dest);committed=True;return dest
    finally:
        temp.unlink(missing_ok=True)
        if not committed:dest.unlink(missing_ok=True)

def prepare_image(path, ffmpeg, ffprobe):
    """Convert a still image and decode the result before committing it."""
    source=Path(path)
    if not source.is_file() or not source.stat().st_size:
        raise MediaError('The still image is missing or empty.')
    same=source.suffix.lower() in ('.png','.jpg','.jpeg')
    target=source if same else source.with_suffix('.png')
    if not same and target.exists():
        target=source.with_name(source.stem+'-'+uuid.uuid4().hex[:8]+'.png')
    temp=source.parent/('.framegrab-'+uuid.uuid4().hex+'.png')
    try:
        if not same:
            converted=subprocess.run([str(ffmpeg),'-v','error','-nostdin','-y','-i',str(source),'-frames:v','1',str(temp)],capture_output=True,creationflags=_flags())
            if converted.returncode or not temp.is_file() or not temp.stat().st_size:
                raise MediaError('Still image conversion failed: '+converted.stderr.decode('utf-8','replace')[-500:])
        checked=temp if not same else source
        meta=subprocess.run([str(ffprobe),'-v','error','-show_streams','-of','json',str(checked)],capture_output=True,creationflags=_flags())
        streams=json.loads(meta.stdout or b'{}').get('streams',[])
        if meta.returncode or not any(x.get('codec_type')=='video' and x.get('width',0)>0 for x in streams):
            raise MediaError('Still image probe verification failed.')
        decoded=subprocess.run([str(ffmpeg),'-v','error','-nostdin','-xerror','-i',str(checked),'-frames:v','1','-f','null','-'],capture_output=True,creationflags=_flags())
        if decoded.returncode:
            raise MediaError('Still image decode verification failed.')
        if not same: os.replace(temp,target)
        return target
    finally:
        temp.unlink(missing_ok=True)
