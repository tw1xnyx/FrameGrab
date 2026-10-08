"""Universal Downloader v5. Browser-only UI, Windows portable launch, stdlib local server."""
import copy
import logging
from logging.handlers import RotatingFileHandler
import platform
import ctypes
import sys
import traceback
import secrets
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote, quote
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
TOOLS = Path(os.environ.get('FRAMEGRAB_TOOLS_DIR', str((ROOT.parent / 'tools') if (ROOT.parent / 'tools').is_dir() else (ROOT / 'tools'))))
APP_DATA = Path(os.environ.get('FRAMEGRAB_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FrameGrab'))
APP_DATA.mkdir(parents=True, exist_ok=True)
WORK = APP_DATA / 'work'
LOG_DIR = APP_DATA / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG = APP_DATA / 'settings.json'
HISTORY = APP_DATA / 'history.json'
BUILD = '8.0.0-desktop-source'
DEFAULT_PORT = int(os.environ.get('FRAMEGRAB_SERVICE_PORT', '8181'))
SESSION_TOKEN = os.environ.get('FRAMEGRAB_API_TOKEN', '')
PARENT_PID = int(os.environ.get('FRAMEGRAB_PARENT_PID', '0'))
LOG = logging.getLogger('framegrab')
LOG.setLevel(logging.INFO)
_handler = RotatingFileHandler(LOG_DIR / 'framegrab.log', maxBytes=2_000_000, backupCount=4, encoding='utf-8')
_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
LOG.addHandler(_handler)
YTDLP = TOOLS / 'yt-dlp.exe'
DENO = TOOLS / 'deno.exe'
FFMPEG = TOOLS / 'ffmpeg.exe'
FFPROBE = TOOLS / 'ffprobe.exe'
COOKIE_BROWSERS = {'none', 'chrome', 'edge', 'brave', 'firefox', 'vivaldi'}
VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.mov', '.m4v', '.mp3', '.m4a', '.aac', '.opus'}
DEFAULT_FOLDER = Path(os.environ.get('USERPROFILE') or str(Path.home())) / 'Downloads'
if not DEFAULT_FOLDER.is_dir():
    DEFAULT_FOLDER = ROOT / 'downloads'
DEFAULT_FOLDER.mkdir(parents=True, exist_ok=True)
WORK.mkdir(exist_ok=True)

LOCK = threading.RLock()
JOBS = {}
PROCESSES = {}
CANCEL = {}
RESERVED = set()
SETTINGS = {'download_dir': str(DEFAULT_FOLDER)}
HIST = []
POOL = ThreadPoolExecutor(max_workers=3)


def load_state():
    global HIST
    # Migrate from an earlier portable service directory only when present.
    for fn, target in (('settings.json', CONFIG), ('history.json', HISTORY)):
        previous = ROOT / fn
        if not target.exists() and previous.is_file():
            try: shutil.copy2(previous, target)
            except OSError: pass
    try:
        s = json.loads(CONFIG.read_text(encoding='utf-8'))
        p = Path(s.get('download_dir', ''))
        if p.is_absolute() and p.is_dir(): SETTINGS['download_dir'] = str(p)
    except (ValueError, OSError, TypeError): pass
    try:
        data = json.loads(HISTORY.read_text(encoding='utf-8'))
        if isinstance(data, list): HIST = data[:300]
    except (ValueError, OSError, TypeError): pass


def save_json(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

load_state()


def sanitize_log(text):
    # Redact cookie, bearer, authentication header, tokens in URLs/logs.
    text = re.sub(r'(?i)(authorization\s*[:=]\s*bearer\s+)\S+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)(cookie\s*[:=]\s*)[^\r\n]+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)([?&](?:token|auth|key|api_key|signature|sig|password|access_token)=)[^&\s]+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)(--cookies(?:-from-browser)?\s+)([^\s]+)', r'\1[REDACTED]', text)
    return text[-12000:]

def hidden():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0


def valid_url(url):
    try:
        p = urlparse(str(url).strip())
        return p.scheme in ('http', 'https') and bool(p.hostname)
    except ValueError: return False


def host_is(host, domain):
    return host == domain or host.endswith('.' + domain)


def platform_for(url):
    h = (urlparse(url).hostname or '').lower()
    domains = [('youtube.com', 'YouTube'), ('youtu.be', 'YouTube'),
               ('instagram.com', 'Instagram'), ('tiktok.com', 'TikTok'),
               ('x.com', 'X'), ('twitter.com', 'X'), ('facebook.com', 'Facebook'),
               ('fb.watch', 'Facebook'), ('reddit.com', 'Reddit'), ('redd.it', 'Reddit'),
               ('vimeo.com', 'Vimeo'), ('twitch.tv', 'Twitch'),
               ('pinterest.com', 'Pinterest'), ('dailymotion.com', 'Dailymotion')]
    return next((label for domain, label in domains if host_is(h, domain)), 'Website')


def cmd_base(browser='none'):
    if not YTDLP.is_file(): raise RuntimeError('A bundled media component is missing. Repair the FrameGrab installation.')
    args = [str(YTDLP), '--ignore-config']
    if DENO.is_file(): args += ['--js-runtimes', 'deno:' + str(DENO)]
    if browser != 'none': args += ['--cookies-from-browser', browser]
    return args


def run_capture(args, timeout=160):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          encoding='utf-8', errors='replace', timeout=timeout, creationflags=hidden())
    return proc.returncode, proc.stdout, proc.stderr


def cookie_error(msg):
    s = str(msg).lower()
    return ('could not copy chrome cookie database' in s or
            ('permission denied' in s and 'cookie' in s) or
            'failed to decrypt with dpapi' in s)


def metadata(url, browser):
    args = cmd_base(browser) + ['--no-playlist', '--dump-single-json', '--skip-download',
                                 '--no-warnings', '--ffmpeg-location', str(TOOLS), url]
    rc, out, err = run_capture(args)
    if rc: raise RuntimeError((err or out or 'Could not analyze the link')[-1800:].strip())
    d = json.loads(out)
    return {'title': str(d.get('title') or 'Untitled video'),
            'uploader': str(d.get('channel') or d.get('uploader') or ''),
            'duration': d.get('duration'), 'thumbnail': str(d.get('thumbnail') or ''), 'id': str(d.get('id') or ''),
            'has_audio': any(str(fmt.get('acodec', 'none')).lower() not in ('none', '') for fmt in (d.get('formats') or [])),
            'width': d.get('width'), 'height': d.get('height'),
            'estimated_size': d.get('filesize') or d.get('filesize_approx'),
            'is_live': bool(d.get('is_live'))}


def parse_time(raw):
    value = str(raw or '').strip()
    if not value: return None
    parts = value.split(':')
    try:
        if len(parts) == 1: result = float(parts[0])
        elif len(parts) == 2: result = int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3: result = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else: raise ValueError()
        if not 0 <= result < 24*3600*20: raise ValueError()
        return result
    except ValueError: raise ValueError('Use a time like 90, 02:15, or 01:02:15.')


def quality_format(q):
    if q == 'best': return 'bv*+ba/b/best'
    if q not in {'2160', '1440', '1080', '720', '480', '360'}: q = '1080'
    # /best fallbacks for single-format posts like Instagram Reels and TikTok.
    return f'bv*[height<={q}]+ba/b[height<={q}]/best'


def name_key(title):
    """Approximate Windows name normalization used for COLLISION planning only."""
    x = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip(' .')[:165]
    return x or 'Video'


def collision_template(target, title, mode='rename'):
    """Reserve basename across active processes, prevent replacing completed files."""
    name = name_key(title)
    with LOCK:
        existing = {p.stem.casefold() for p in target.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS}
        suffix = 1
        while True:
            text = name if suffix == 1 else f'{name} ({suffix})'
            key = (str(target).lower(), text.casefold())
            if key not in RESERVED and text.casefold() not in existing:
                if mode == 'skip' and suffix > 1: return None, None
                RESERVED.add(key)
                # Use the actual video title via yt-dlp, not a generated ID.
                output = '%(title).165B' + (f' ({suffix})' if suffix > 1 else '') + '.%(ext)s'
                return output, key
            suffix += 1


def snapshot_media(folder):
    """Capture preexisting outputs so post-download fallback never selects a stale file."""
    try:
        return {str(p.resolve()).casefold(): (p.stat().st_size, p.stat().st_mtime_ns)
                for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS}
    except OSError:
        return {}


def resolve_output(target, record, reported, before, started, expected_name=None):
    """Prefer yt-dlp's after_move filepath; scan changed files only as recovery."""
    candidates = []
    if record.exists():
        try:
            candidates += [Path(p.strip().strip('"')) for p in record.read_text(encoding='utf-8-sig').splitlines() if p.strip() and p.strip() != 'NA']
        except (OSError, UnicodeError):
            pass
    if reported is not None:
        candidates.insert(0, reported)
    seen = set()
    for p in candidates:
        if not p.is_absolute(): p = target / p
        key = str(p).casefold()
        if key in seen: continue
        seen.add(key)
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS and p.stat().st_size > 0:
            return p.resolve(), 'reported'
    # Recovery: only files NEW or MODIFIED after this command, never arbitrary old files.
    changed = []
    for p in target.iterdir():
        if not p.is_file() or p.suffix.lower() not in VIDEO_EXTS or p.name.endswith(('.part', '.ytdl')): continue
        stat = p.stat()
        if stat.st_size <= 0: continue
        if before.get(str(p.resolve()).casefold()) == (stat.st_size, stat.st_mtime_ns): continue
        if stat.st_mtime < started - 3: continue
        changed.append(p)
    if expected_name:
        prefix = name_key(expected_name).casefold()
        matching = [p for p in changed if p.stem.casefold().startswith(prefix[:min(32,len(prefix))])]
        if matching: changed = matching
    if len(changed) == 1: return changed[0].resolve(), 'directory recovery'
    if not changed:
        raise RuntimeError('yt-dlp exited, but there is no new finished media file in your selected folder. Check permissions and merge logs.')
    raise RuntimeError('Several output files changed and yt-dlp did not report its final filename. Cannot safely guess which file belongs to this video.')


def verify_media(path, media_type='mp4', require_audio=False):
    """Require a real decodable container with video, or audio when MP3 was requested."""
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError('The final output is missing or empty.')
    if not FFPROBE.is_file():
        raise RuntimeError('FFprobe is missing, so the saved video cannot be verified.')
    args = [str(FFPROBE), '-v', 'error', '-show_entries',
            'format=duration,size:stream=codec_type,codec_name,width,height',
            '-of', 'json', str(path)]
    rc, out, err = run_capture(args, timeout=90)
    if rc:
        raise RuntimeError('The saved file cannot be read by FFprobe: ' + (err or 'unknown error')[-500:])
    try: info = json.loads(out)
    except ValueError: raise RuntimeError('FFprobe returned invalid file inspection data.')
    streams = info.get('streams') or []
    needed = 'audio' if media_type == 'mp3' else 'video'
    if not any(st.get('codec_type') == needed for st in streams):
        raise RuntimeError(f'The saved file is missing a usable {needed} stream.')
    if media_type != 'mp3' and require_audio and not any(st.get('codec_type') == 'audio' for st in streams):
        raise RuntimeError('The saved video is missing its audio track.')
    try: duration = float(info.get('format', {}).get('duration') or 0)
    except (ValueError, TypeError): duration = 0
    if duration <= 0: raise RuntimeError('The saved file has no valid media duration.')
    return {'duration': duration, 'streams': streams, 'size': path.stat().st_size}


def item_set(jid, ix, **kwargs):
    with LOCK:
        job = JOBS.get(jid)
        if job and 0 <= ix < len(job['items']):
            job['items'][ix].update(kwargs)


def item_log(jid, ix, value):
    text = sanitize_log(str(value)).rstrip()
    if not text: return
    with LOCK:
        job = JOBS.get(jid)
        if job:
            logs = job['items'][ix]['logs']
            logs.append(text[-900:])
            del logs[:-50]


def finish_counts(jid):
    with LOCK:
        job = JOBS[jid]
        items = job['items']
        job['done'] = sum(x['status'] == 'done' for x in items)
        job['failed'] = sum(x['status'] == 'error' for x in items)
        job['canceled'] = sum(x['status'] == 'canceled' for x in items)
        job['skipped'] = sum(x['status'] == 'skipped' for x in items)
        job['progress'] = round(sum(float(x.get('progress') or 0) for x in items) / len(items), 1)
        if all(x['status'] in {'done', 'error', 'canceled', 'skipped'} for x in items):
            job['status'] = 'finished'


def remember(item):
    entry = {key: item.get(key) for key in ('id', 'url', 'platform', 'title', 'path', 'file_name', 'size')}
    entry['completed_at'] = datetime.now(timezone.utc).isoformat()
    with LOCK:
        HIST.insert(0, entry)
        del HIST[300:]
        save_json(HISTORY, HIST)


def job_copy(job):
    out = copy.deepcopy(job)
    for item in out['items']:
        item.pop('path', None)
        item['download_url'] = '/download/' + item['id'] if item['status'] == 'done' else None
    return out


def download_one(jid, ix, url, opts, limiter):
    key = (jid, ix)
    ev = CANCEL[key]
    if ev.is_set(): item_set(jid, ix, status='canceled', phase='Canceled'); finish_counts(jid); return
    with limiter:
        reserved = None
        item_temp = WORK / f'{jid}-{ix}'
        item_temp.mkdir(parents=True, exist_ok=True)
        try:
            if ev.is_set(): item_set(jid, ix, status='canceled', phase='Canceled'); return
            browser = str(opts.get('browser', 'none')).lower()
            if browser not in COOKIE_BROWSERS: browser = 'none'
            target = Path(SETTINGS['download_dir'])
            if not target.is_dir(): raise RuntimeError('Selected download folder no longer exists. Choose it again.')
            item_set(jid, ix, status='analyzing', phase='Reading video details', progress=2)
            try:
                meta = metadata(url, browser)
            except Exception as exc:
                if browser != 'none' and cookie_error(exc):
                    item_log(jid, ix, 'Browser cookies unavailable. Retrying public access without cookies.')
                    browser = 'none'
                    meta = metadata(url, browser)
                else: raise
            item_set(jid, ix, title=meta['title'], uploader=meta['uploader'], thumbnail=meta['thumbnail'], duration=meta['duration'], width=meta.get('width'), height=meta.get('height'), estimated_size=meta.get('estimated_size'))
            if ev.is_set(): item_set(jid, ix, status='canceled', phase='Canceled'); return
            start, end = (parse_time(opts.get('start')), parse_time(opts.get('end'))) if opts.get('clip') else (None, None)
            if opts.get('clip'):
                if meta['is_live']: raise RuntimeError('Time range download is not supported for an active live stream.')
                if start is None or end is None or end <= start: raise RuntimeError('Enter a valid start and end time.')
                if meta['duration'] and end > float(meta['duration']) + 1: raise RuntimeError('End time exceeds video duration.')
            def stamp(n):
                return f'{int(n//3600):02d}-{int(n%3600//60):02d}-{int(n%60):02d}'
            clip_title = meta['title'] + (f' - Clip {stamp(start)} to {stamp(end)}' if start is not None else '')
            output, reserved = collision_template(target, clip_title, opts.get('duplicate', 'rename'))
            if output is None:
                item_set(jid, ix, status='skipped', phase='Already in destination', progress=100)
                return
            before = snapshot_media(target)
            started = time.time()
            report = WORK / f'after-move-{jid}-{ix}-{uuid.uuid4().hex}.txt'
            args = cmd_base(browser) + [
                '--no-playlist', '--newline', '--progress', '--windows-filenames',
                '--no-overwrites', '--continue', '--ffmpeg-location', str(TOOLS),
                '--paths', 'home:' + str(target), '--paths', 'temp:' + str(item_temp),
                '--output', output, '--print', 'after_move:__UVD_DONE__%(filepath)s',
                '--print-to-file', 'after_move:%(filepath)s', str(report)
            ]
            if opts.get('kind') == 'mp3':
                args += ['-f', 'ba/b', '--extract-audio', '--audio-format', 'mp3', '--audio-quality', '0']
            else:
                args += ['-f', quality_format(str(opts.get('quality') or 'best')),
                         '--merge-output-format', 'mkv' if opts.get('kind') == 'mkv' else 'mp4']
            if opts.get('subtitles'):
                args += ['--write-subs', '--write-auto-subs', '--sub-langs', 'en.*,en', '--convert-subs', 'srt']
            if opts.get('clip'):
                args += ['--download-sections', f'*{start:g}-{end:g}']
                if opts.get('exact', True): args += ['--force-keyframes-at-cuts']
                # Rename the section using a literal filename suffix in the template.
                # The original yt-dlp title remains in the prefix.
                suffix = f' - Clip {stamp(start)} to {stamp(end)}'
                args[args.index('--output') + 1] = output.replace('.%(ext)s', suffix + '.%(ext)s') if suffix not in output else output
            args.append(url)  # Avoid the original no-URL bug.
            item_set(jid, ix, status='downloading', phase='Downloading source', progress=5)
            item_log(jid, ix, 'Saving directly to: ' + str(target))
            final_path = None
            rx = re.compile(r'\[download\]\s+(\d+(?:\.\d+)?)%')
            speed_rx = re.compile(r' at\s+([^ ]+)\s+ETA\s+(\S+)')

            def run_dl(argv):
                nonlocal final_path
                seen_cookie_err = False
                process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, encoding='utf-8', errors='replace', bufsize=1,
                                           creationflags=hidden())
                with LOCK: PROCESSES[key] = process
                for line in process.stdout:
                    if ev.is_set():
                        stop_proc(process)
                        break
                    line = line.rstrip('\r\n')
                    if line.startswith('__UVD_DONE__'):
                        final_path = Path(line[len('__UVD_DONE__'):].strip())
                        continue
                    if cookie_error(line): seen_cookie_err = True
                    if line.startswith('[download]') and '%' in line:
                        m = rx.search(line)
                        if m:
                            pct = 5 + min(100, float(m.group(1))) * .83
                            with LOCK:
                                item = JOBS[jid]['items'][ix]
                                if pct > item['progress']: item['progress'] = round(pct, 1)
                        s = speed_rx.search(line)
                        if s: item_set(jid, ix, speed=s.group(1), eta=s.group(2))
                    elif 'Merging formats' in line or '[Merger]' in line: item_set(jid, ix, phase='Merging video + audio', progress=92)
                    elif 'ExtractAudio' in line: item_set(jid, ix, phase='Converting to MP3', progress=94)
                    elif 'Post-process' in line or 'Fixup' in line: item_set(jid, ix, phase='Finishing file', progress=96)
                    else: item_log(jid, ix, line)
                code = process.wait()
                if process.stdout: process.stdout.close()
                with LOCK: PROCESSES.pop(key, None)
                return code, seen_cookie_err

            rc, cookie_problem = run_dl(args)
            if ev.is_set(): item_set(jid, ix, status='canceled', phase='Canceled'); return
            if rc and cookie_problem and browser != 'none':
                item_log(jid, ix, 'Chrome cookie database locked. Automatically retrying as a public link.')
                retry = []
                skip_next = False
                for a in args:
                    if skip_next: skip_next = False; continue
                    if a == '--cookies-from-browser': skip_next = True; continue
                    retry.append(a)
                rc, _ = run_dl(retry)
            if rc: raise RuntimeError('Download or FFmpeg processing failed. Open technical details for the exact yt-dlp error.')
            item_set(jid, ix, phase='Locating finished file', progress=97)
            final_path, how = resolve_output(target, report, final_path, before, started, clip_title)
            item_log(jid, ix, 'Final file path (' + how + '): ' + str(final_path))
            # Ensure yt-dlp did not leave the only copy outside the chosen directory.
            if final_path.parent.resolve() != target.resolve():
                raise RuntimeError('Output was found outside your selected Downloads folder: ' + str(final_path))
            item_set(jid, ix, phase='Verifying saved media', progress=98)
            verified = verify_media(final_path, str(opts.get('kind') or 'mp4'), require_audio=bool(meta.get('has_audio')))
            if start is not None:
                selected = end-start
                if verified['duration'] > selected + max(5,selected*.05):
                    raise RuntimeError('The output duration exceeds the selected clip range. Section extraction may have downloaded the full video.')
            item_log(jid, ix, f'VERIFIED: {final_path.name} ({verified["size"]} bytes, {verified["duration"]:.2f}s)')
            data = {'id': uuid.uuid4().hex[:14], 'url': url, 'platform': platform_for(url),
                    'title': meta['title'], 'path': str(final_path), 'file_name': final_path.name,
                    'size': final_path.stat().st_size}
            item_set(jid, ix, **data, status='done', phase='Saved to folder', progress=100, speed='', eta='')
            remember(data)
            shutil.rmtree(item_temp, ignore_errors=True)
            try: report.unlink(missing_ok=True)
            except OSError: pass
        except Exception as exc:
            if ev.is_set(): item_set(jid, ix, status='canceled', phase='Canceled')
            else:
                item_log(jid, ix, 'ERROR: ' + str(exc))
                LOG.error('Download failed: %s', sanitize_log(str(exc)))
                item_set(jid, ix, status='error', phase='Failed', error=str(exc))
        finally:
            if reserved is not None:
                with LOCK: RESERVED.discard(reserved)
            finish_counts(jid)


def stop_proc(proc):
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True,
                           timeout=10, creationflags=hidden())
        else: proc.terminate()
    except (OSError, subprocess.TimeoutExpired):
        try: proc.kill()
        except OSError: pass


def create_batch(urls, opts):
    jid = uuid.uuid4().hex[:12]
    with LOCK:
        JOBS[jid] = {'id': jid, 'created': time.time(), 'status': 'running', 'progress': 0,
                     'options': copy.deepcopy(opts), 'total': len(urls), 'done': 0, 'failed': 0, 'skipped': 0, 'canceled': 0,
                     'items': [{'index': i, 'url': url, 'platform': platform_for(url),
                                'title': 'Waiting in queue', 'status': 'queued', 'phase': 'Queued',
                                'progress': 0, 'logs': [], 'id': ''} for i, url in enumerate(urls)]}
        for i in range(len(urls)): CANCEL[(jid, i)] = threading.Event()
    n = max(1, min(3, int(opts.get('parallel') or 2)))
    limiter = threading.Semaphore(n)
    for i, url in enumerate(urls):
        # The shared global pool is bounded to avoid resource spikes across jobs.
        POOL.submit(download_one, jid, i, url, opts, limiter)
    return jid


def choose_folder():
    if os.name != 'nt':
        raise RuntimeError('Folder chooser requires Windows. Enter the folder path in Settings instead.')
    # No tkinter dependency in Python embeddable distribution.
    script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog=New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description='Choose a folder for all downloaded videos'
$dialog.ShowNewFolderButton=$true
if($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){Write-Output $dialog.SelectedPath}
'''
    proc = subprocess.run(['powershell.exe', '-NoProfile', '-STA', '-Command', script],
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=240,
                          creationflags=hidden())
    if proc.returncode: raise RuntimeError((proc.stderr or 'Folder dialog failed').strip()[:600])
    result = proc.stdout.strip().splitlines()
    if not result: return None
    return result[-1].strip()


def set_folder(path):
    p = Path(str(path or '')).expanduser()
    if not p.is_absolute() or not p.is_dir(): raise ValueError('Choose an existing, absolute folder path.')
    if not os.access(str(p), os.W_OK): raise ValueError('The selected folder is not writable.')
    with LOCK:
        SETTINGS['download_dir'] = str(p.resolve())
        save_json(CONFIG, SETTINGS)
    return SETTINGS['download_dir']


def reveal_file(path):
    p = Path(path)
    if not p.exists(): raise FileNotFoundError('The downloaded file no longer exists.')
    if os.name == 'nt':
        subprocess.Popen(['explorer.exe', '/select,', str(p)], creationflags=hidden())
    else:
        webbrowser.open(p.parent.as_uri())


class H(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def authorized(self):
        if not SESSION_TOKEN: return True
        token = self.headers.get('X-FrameGrab-Token', '')
        cookie = self.headers.get('Cookie', '')
        return secrets.compare_digest(token, SESSION_TOKEN) or any(secrets.compare_digest(part.strip(), 'fg_session=' + SESSION_TOKEN) for part in cookie.split(';'))


    def data(self, payload, status=200):
        b = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def static(self, name, mime):
        p = WEB / name
        if not p.is_file(): return self.data({'error': 'Missing static resource'}, 404)
        b = p.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 0 or size > 150_000: raise ValueError('Request is too large.')
            return json.loads(self.rfile.read(size).decode('utf-8')) if size else {}
        except (ValueError, UnicodeDecodeError): return {}

    def do_GET(self):
        path = unquote(self.path.split('?', 1)[0])
        if (path.startswith('/api/') or path.startswith('/download/')) and not self.authorized():
            return self.data({'error': 'Unauthorized local request'}, 403)

        if path == '/': return self.static('index.html', 'text/html; charset=utf-8')
        if path == '/styles.css': return self.static('styles.css', 'text/css; charset=utf-8')
        if path == '/app.js': return self.static('app.js', 'text/javascript; charset=utf-8')
        if path == '/background.js': return self.static('background.js', 'text/javascript; charset=utf-8')
        if path == '/glass.js': return self.static('glass.js', 'text/javascript; charset=utf-8')
        if path == '/desktop.js': return self.static('desktop.js', 'text/javascript; charset=utf-8')
        if path == '/api/diagnostics':
            results = {}
            for name, candidate in (('yt-dlp',YTDLP), ('FFmpeg',FFMPEG), ('FFprobe',FFPROBE), ('Deno',DENO)):
                if not candidate.is_file():
                    results[name] = {'ready': False, 'error': 'Not bundled with installation'}
                    continue
                try:
                    rc, out, err = run_capture([str(candidate), '-version' if name in ('FFmpeg','FFprobe') else '--version'], timeout=15)
                    results[name] = {'ready': rc == 0, 'version': sanitize_log((out or err).splitlines()[0])[:180] if (out or err) else ''}
                except Exception as e: results[name] = {'ready': False, 'error': sanitize_log(str(e))}
            folder=Path(SETTINGS['download_dir'])
            try: free=shutil.disk_usage(folder).free
            except OSError: free=None
            return self.data({'build': BUILD, 'os': platform.platform(), 'tools':results, 'folder': str(folder),
                              'folder_writable': folder.is_dir() and os.access(folder,os.W_OK),
                              'free_bytes':free, 'log_dir':str(LOG_DIR), 'update_system':'Managed by desktop updater'})
        if path == '/api/state':
            with LOCK:
                state = {'build': BUILD, 'folder': SETTINGS['download_dir'],
                         'jobs': [job_copy(x) for x in sorted(JOBS.values(), key=lambda j: j['created'], reverse=True)[:8]],
                         'history': copy.deepcopy(HIST[:120]),
                         'tools': {'yt_dlp': YTDLP.is_file(), 'ffmpeg': FFMPEG.is_file(), 'deno': DENO.is_file()}}
            return self.data(state)
        if path.startswith('/download/'):
            id_ = path.split('/')[-1]
            with LOCK:
                entry = next((x for x in HIST if x['id'] == id_), None)
            if not entry: return self.data({'error': 'File not found'}, 404)
            p = Path(entry['path'])
            if not p.is_file(): return self.data({'error': 'File was moved or deleted'}, 404)
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(p.stat().st_size))
            self.send_header('Content-Disposition', f"attachment; filename=\"download{p.suffix}\"; filename*=UTF-8''{quote(p.name)}")
            self.end_headers()
            try:
                with p.open('rb') as f: shutil.copyfileobj(f, self.wfile, 1024 * 1024)
            except (BrokenPipeError, ConnectionResetError): pass
            return
        return self.data({'error': 'Not found'}, 404)

    def do_POST(self):
        path = self.path.split('?', 1)[0]
        if not self.authorized():
            return self.data({'error': 'Unauthorized local request'}, 403)

        origin = self.headers.get('Origin', '')
        if origin:
            netloc = urlparse(origin).hostname
            if netloc not in ('127.0.0.1', 'localhost'):
                return self.data({'error': 'Request origin not allowed'}, 403)
        d = self.body()
        if path == '/api/analyze':
            url = str(d.get('url') or '').strip()
            if not valid_url(url): return self.data({'error': 'Enter a valid video URL.'}, 400)
            browser = str(d.get('browser') or 'none').lower()
            if browser not in COOKIE_BROWSERS: browser = 'none'
            try:
                try: meta = metadata(url, browser)
                except Exception as ex:
                    if browser != 'none' and cookie_error(ex): meta = metadata(url, 'none')
                    else: raise
                meta['platform'] = platform_for(url)
                return self.data(meta)
            except Exception as ex: return self.data({'error': str(ex)[:1200]}, 400)
        if path == '/api/start':
            raw = d.get('urls') if isinstance(d.get('urls'), list) else []
            urls = list(dict.fromkeys(str(x).strip() for x in raw[:60] if valid_url(x)))
            if not urls: return self.data({'error': 'Paste one or more valid video URLs.'}, 400)
            opts = d.get('options') if isinstance(d.get('options'), dict) else {}
            if opts.get('clip'):
                try:
                    a, b = parse_time(opts.get('start')), parse_time(opts.get('end'))
                    if a is None or b is None or b <= a: raise ValueError()
                except ValueError: return self.data({'error': 'Enter valid start and end times.'}, 400)
            try: jid = create_batch(urls, opts)
            except Exception as e: return self.data({'error': str(e)}, 400)
            return self.data({'job_id': jid, 'count': len(urls)})
        if path == '/api/history/clear':
            with LOCK:
                HIST.clear()
                save_json(HISTORY, HIST)
            return self.data({'ok': True, 'files_deleted': False})
        if path == '/api/file/open':
            with LOCK: entry = next((x for x in HIST if x['id'] == d.get('id')), None)
            if not entry: return self.data({'error': 'File not found in download history'}, 404)
            try:
                file = Path(entry['path'])
                if not file.is_file(): raise FileNotFoundError('File was moved or deleted')
                if os.name == 'nt': os.startfile(str(file))
                else: webbrowser.open(file.as_uri())
                return self.data({'ok': True})
            except OSError as exc: return self.data({'error': sanitize_log(str(exc))}, 400)
        if path == '/api/folder/pick':
            try:
                p = choose_folder()
                return self.data({'folder': set_folder(p) if p else SETTINGS['download_dir'], 'changed': bool(p)})
            except Exception as e: return self.data({'error': str(e)}, 400)
        if path == '/api/folder/set':
            try: return self.data({'folder': set_folder(d.get('folder'))})
            except (ValueError, OSError) as e: return self.data({'error': str(e)}, 400)
        if path == '/api/folder/open':
            try:
                folder = Path(SETTINGS['download_dir'])
                if os.name == 'nt': subprocess.Popen(['explorer.exe', str(folder)], creationflags=hidden())
                else: webbrowser.open(folder.as_uri())
                return self.data({'ok': True})
            except OSError as e: return self.data({'error': str(e)}, 400)
        if path == '/api/reveal':
            with LOCK: entry = next((x for x in HIST if x['id'] == d.get('id')), None)
            if not entry: return self.data({'error': 'File not found in download history'}, 404)
            try: reveal_file(entry['path']); return self.data({'ok': True})
            except OSError as e: return self.data({'error': str(e)}, 400)
        if path == '/api/cancel':
            jid, ix = d.get('job_id'), d.get('index')
            with LOCK:
                if not isinstance(ix, int) or (jid, ix) not in CANCEL: return self.data({'error': 'Item not found'}, 404)
                ev = CANCEL[(jid, ix)]
                ev.set()
                proc = PROCESSES.get((jid, ix))
                item_set(jid, ix, phase='Canceling…')
            if proc: stop_proc(proc)
            return self.data({'ok': True})
        if path == '/api/retry':
            jid, ix = d.get('job_id'), d.get('index')
            with LOCK:
                old = JOBS.get(jid)
                if not old or not isinstance(ix, int) or not 0 <= ix < len(old['items']): return self.data({'error':'Item not found'},404)
                if old['items'][ix]['status'] not in ('error','canceled'): return self.data({'error':'Only failed/canceled items can retry'},400)
                url = old['items'][ix]['url']
                opts = old.get('options', {})
            return self.data({'job_id': create_batch([url], opts)})
        return self.data({'error': 'Not found'}, 404)


def parent_alive():
    if not PARENT_PID or os.name != 'nt': return True
    # Query the Electron parent handle; if it exited, kill our yt-dlp tree.
    import ctypes
    SYNCHRONIZE=0x00100000
    k=ctypes.windll.kernel32
    k.OpenProcess.restype=ctypes.c_void_p
    k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
    k.WaitForSingleObject.restype=ctypes.c_ulong
    k.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=k.OpenProcess(SYNCHRONIZE,False,PARENT_PID)
    if not handle: return False
    try: return k.WaitForSingleObject(handle,0)==0x102
    finally: k.CloseHandle(handle)

def watchdog(server):
    if not PARENT_PID: return
    while True:
        time.sleep(2)
        if not parent_alive():
            LOG.warning('Desktop parent exited. Stopping child downloads.')
            with LOCK:
                for e in CANCEL.values(): e.set()
                procs=list(PROCESSES.values())
            for p in procs: stop_proc(p)
            server.shutdown()
            return

def main():
    missing=[p.name for p in (YTDLP,FFMPEG,FFPROBE,DENO) if not p.is_file()]
    if missing:
        LOG.error('Missing packaged tools: %s', ', '.join(missing))
        raise SystemExit('Missing packaged tools: '+', '.join(missing))
    server=ThreadingHTTPServer(('127.0.0.1',DEFAULT_PORT),H)
    LOG.info('FrameGrab engine ready on loopback port %s', server.server_port)
    threading.Thread(target=watchdog,args=(server,),daemon=True).start()
    try: server.serve_forever()
    finally:
        with LOCK:
            for e in CANCEL.values(): e.set()
            procs=list(PROCESSES.values())
        for p in procs: stop_proc(p)
        server.server_close()

if __name__=='__main__': main()
