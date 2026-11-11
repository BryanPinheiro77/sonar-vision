#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""USB camera bench, Python stdlib only; frames remain in memory, localhost only."""
import argparse
import datetime
import json
import math
import os
import pathlib
import select
import termios
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sonar Vision · Câmera USB</title>
<style>
:root{color-scheme:dark}body{font:17px/1.5 system-ui;margin:30px auto;padding:0 20px;
max-width:1000px;background:#17191d;color:#eee}h1{font-size:1.7rem;margin:0 0 8px}
p{max-width:72ch}img{display:block;max-width:100%;height:auto;margin:20px 0}
.controls{display:flex;flex-wrap:wrap;gap:12px 20px;align-items:end;margin:24px 0}
label{display:flex;flex-direction:column;gap:4px}button,select{font:inherit;
padding:9px 12px;border:1px solid #858c96;border-radius:6px;background:#252a31;color:#eee}
button{cursor:pointer}button:hover,select:hover{background:#343c47}
button:disabled,select:disabled{opacity:.55;cursor:wait}
:focus-visible{outline:3px solid #91c8ff;outline-offset:3px}
#status{min-height:3em;font-variant-numeric:tabular-nums}
small{color:#c2c9d2}::selection{background:#a3d1ff;color:#122032}
</style>
<h1>Sonar Vision · Câmera USB</h1>
<p>Compare detalhe e fluidez. As imagens ficam somente na memória.</p>
<div class="controls">
<label>Resolução<select id="resolution" disabled>
<option value="0">320 × 240</option><option value="1">640 × 480</option>
<option value="2">800 × 600</option><option value="3">1024 × 768</option>
<option value="4">1600 × 1200</option></select></label>
<label>Qualidade JPEG<select id="quality" disabled><option value="a">60 · mais compressão</option>
<option value="b" selected>80 · padrão</option><option value="c">90 · menos compressão</option></select></label>
<button id="pause" disabled>Pausar</button><button id="mirror" disabled>Espelhar</button>
<button id="flip" disabled>Inverter verticalmente</button></div>
<p id="status" role="status">Conectando à câmera…</p>
<img id="camera" alt="Imagem ao vivo da câmera do ESP32-S3" hidden>
<small>O FPS considera os frames exibidos nesta aba. Outras abas podem reduzir a fluidez.
Mais resolução exige mais processamento. FPS local: envio e inferência na AWS ainda não estão nesta medida. USB → Mac → navegador local.
Este firmware executa somente a câmera, sem alerta tátil, sensores ou áudio.</small>
<script>
let paused=false,busy=false,changing=false,previous=null,timer=null,arrivals=[];
const status=document.querySelector('#status'),camera=document.querySelector('#camera');
const resolution=document.querySelector('#resolution'),quality=document.querySelector('#quality');
const controls=[...document.querySelectorAll('button,select')];
function enable(value){for(const control of controls)control.disabled=!value}
async function synchronize(){
 const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw Error(await r.text());
 const s=await r.json();const widths=[320,640,800,1024,1600];
 resolution.value=String(widths.indexOf(Number(s.width)));
 quality.value=({60:'a',80:'b',90:'c'})[Number(s.quality)];
}
async function frame(){
 if(paused||busy||changing)return;busy=true;const start=performance.now();
 try{
 const r=await fetch('/frame.jpg',{cache:'no-store'});if(!r.ok)throw Error(await r.text());
 const blob=await r.blob(),url=URL.createObjectURL(blob);
 try{await new Promise((resolve,reject)=>{camera.onload=resolve;camera.onerror=reject;camera.src=url})}
 catch(e){URL.revokeObjectURL(url);throw Error('O navegador não conseguiu decodificar a imagem')}
 if(previous)URL.revokeObjectURL(previous);previous=url;camera.hidden=false;
 const now=performance.now();arrivals.push(now);while(arrivals.length>2&&arrivals[0]<now-3000)arrivals.shift();
 const fps=arrivals.length>1?((arrivals.length-1)*1000/(now-arrivals[0])).toFixed(1):'…';
 status.textContent=`Ao vivo · ${camera.naturalWidth} × ${camera.naturalHeight} · ${fps} FPS · ${(blob.size/1024).toFixed(1)} KiB · leitura ${(now-start).toFixed(0)} ms · conversão ${Number(r.headers.get('X-Encode-Ms')).toFixed(0)} ms · USB ${Number(r.headers.get('X-Transfer-Ms')).toFixed(0)} ms`;
 }catch(e){camera.hidden=true;arrivals=[];status.textContent='Falha na captura: '+e.message+'. Confira a USB e tente 320 × 240.'}
 finally{busy=false;
 if(paused&&!changing)status.textContent='Pausado · a imagem exibida não está ao vivo';
 if(!paused&&!changing)timer=setTimeout(frame,camera.hidden?1000:0)}
}
async function control(command){
 if(changing)return;changing=true;enable(false);clearTimeout(timer);
 try{
 while(busy)await new Promise(resolve=>setTimeout(resolve,10));
 status.textContent='Aplicando ajuste à câmera…';
 const r=await fetch('/control?'+command,{method:'POST'});if(!r.ok)throw Error(await r.text());
 await synchronize();arrivals=[];
 status.textContent=paused?'Pausado · ajuste aplicado. Clique em Retomar para ver.':'Ajuste aplicado.';
 }catch(e){status.textContent='Não foi possível aplicar: '+e.message+'. Selecione 320 × 240 para recuperar.'}
 finally{changing=false;enable(true);if(!paused)frame()}
}
resolution.onchange=()=>control(resolution.value);quality.onchange=()=>control(quality.value);
document.querySelector('#mirror').onclick=()=>control('H');
document.querySelector('#flip').onclick=()=>control('V');
document.querySelector('#pause').onclick=()=>{paused=!paused;clearTimeout(timer);arrivals=[];
 document.querySelector('#pause').textContent=paused?'Retomar':'Pausar';
 if(paused)status.textContent='Pausado · a imagem exibida não está ao vivo';else frame()};
(async()=>{try{await synchronize();enable(true);frame()}
 catch(e){status.textContent='Câmera indisponível: '+e.message+'. Confira a USB e recarregue a página.'}})();
</script></html>"""


class Metrics:
    """Observe the existing preview; never request an extra camera frame."""
    def __init__(self, path, device_status):
        self.file = pathlib.Path(path).open('x', encoding='utf-8')
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.samples = []
        self.errors = []
        self.started = self.window_started = time.monotonic()
        self.frames = self.failures = 0
        self.last_report = {'state': 'aguardando_primeira_janela'}
        self.write({'event': 'session', 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'device': device_status, 'interval_seconds': 5,
                    'measurement': 'USB frames requested by preview; not browser render or AWS',
                    'motion': 'user-controlled; not automatically classified',
                    'images_saved': False, 'cloud_tested': False})
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def write(self, record):
        self.file.write(json.dumps(record, ensure_ascii=False)+'\n')
        self.file.flush()

    def frame(self, meta, size):
        with self.lock:
            self.samples.append(dict(meta, jpeg_bytes=size))
            self.frames += 1

    def error(self, error):
        with self.lock:
            self.failures += 1
            self.errors.append(str(error)[:200])

    def report(self):
        with self.lock:
            now = time.monotonic()
            elapsed = now-self.window_started
            rows = self.samples
            record = {'event': 'window', 'elapsed_seconds': now-self.started,
                      'window_seconds': elapsed, 'frames': len(rows),
                      'fps': len(rows)/elapsed, 'capture_failures': len(self.errors),
                      'total_frames': self.frames, 'total_capture_failures': self.failures,
                      'state': 'capturando' if rows else 'sem_frames_recebidos'}
            if rows:
                times = sorted(row['total_ms'] for row in rows)
                record.update(resolutions=sorted({(r['width'], r['height']) for r in rows}),
                              frame_ms_median=times[len(times)//2],
                              frame_ms_p95=times[math.ceil(.95*len(times))-1],
                              frame_ms_max=max(times),
                              jpeg_bytes_mean=sum(r['jpeg_bytes'] for r in rows)/len(rows),
                              jpeg_bytes_max=max(r['jpeg_bytes'] for r in rows),
                              mean_ms={k:sum(r[k] for r in rows)/len(rows)
                                       for k in ('capture_ms', 'encode_ms', 'transfer_ms')})
            if self.errors:
                record['errors'] = self.errors[-5:]
            self.last_report = record
            self.write(record)
            self.samples = []; self.errors = []; self.window_started = now
            print(f"MOTION_METRICS {record['fps']:.2f} FPS; {len(rows)} frames; "
                  f"{record['capture_failures']} failures; elapsed={now-self.started:.0f}s", flush=True)

    def run(self):
        while not self.stop_event.wait(5):
            self.report()

    def latest(self):
        with self.lock:
            return dict(self.last_report)

    def close(self):
        self.stop_event.set(); self.thread.join()
        self.report(); self.file.close()


class Camera:
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        settings = termios.tcgetattr(self.fd)
        settings[0] = settings[1] = settings[3] = 0
        settings[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        settings[4] = settings[5] = termios.B115200
        settings[6][termios.VMIN] = 0
        settings[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, settings)
        self.lock = threading.Lock()

    def read(self, size, deadline):
        data = bytearray()
        while len(data) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                raise TimeoutError('ESP não respondeu pela USB em 15 s')
            part = os.read(self.fd, size - len(data))
            if not part:
                raise OSError('USB desconectada')
            data.extend(part)
        return bytes(data)

    def line(self, deadline):
        data = bytearray()
        while len(data) < 1024:
            data.extend(self.read(1, deadline))
            if data.endswith(b'\n'):
                return data.decode('ascii', errors='replace').strip()
        raise ValueError('Linha serial excedeu o limite')

    def capture(self):
        return self.request('C', with_meta=True)

    def request(self, command, with_meta=False):
        with self.lock:
            termios.tcflush(self.fd, termios.TCIFLUSH)
            start = time.monotonic()
            os.write(self.fd, command.encode('ascii'))
            deadline = time.monotonic() + 15
            # Boot diagnostics can still arrive when the host opens USB.
            # Ignore complete non-protocol lines, within the same deadline.
            while True:
                header = self.line(deadline)
                if header.startswith(('SVSTATUS ', 'SVJPEG ', 'SVERROR ', 'SVOK')):
                    break
            if command != 'C':
                if not header.startswith(('SVSTATUS ', 'SVOK')):
                    raise ValueError(header)
                return header
            if not header.startswith('SVJPEG '):
                raise ValueError(header)
            fields = header.split()
            size = int(fields[1])
            if not 4 <= size <= 2 * 1024 * 1024:
                raise ValueError('Tamanho JPEG inválido')
            data = self.read(size, deadline)
            if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
                raise ValueError(f'JPEG incompleto ({len(data)} bytes)')
            if len(fields) != 6:
                raise ValueError('Firmware não corresponde à ponte de resolução (protocolo 2)')
            end = self.line(deadline)
            if not end:
                end = self.line(deadline)
            if not end.startswith('SVEND '):
                raise ValueError('Medição USB ausente')
            meta = dict(capture_ms=int(fields[2])/1000, encode_ms=int(fields[3])/1000,
                        width=int(fields[4]), height=int(fields[5]),
                        transfer_ms=int(end.split()[1])/1000,
                        total_ms=(time.monotonic()-start)*1000)
            return (data, meta) if with_meta else data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', default='/dev/cu.usbmodem101')
    parser.add_argument('--port', type=int, default=8087)
    parser.add_argument('--profile', choices=('fast', 'baseline'), default='fast')
    parser.add_argument('--resolution', choices=range(5), type=int, default=1)
    parser.add_argument('--metrics-log', help='JSONL numeric metrics only; must be a new file')
    args = parser.parse_args()
    camera = Camera(args.device)
    # Explicit bench profile. Baseline remains available without DMA/double buffer.
    for command in ('0', 'L', 'M' if args.profile == 'fast' else 'N',
                    'E' if args.profile == 'fast' else 'G', 'b', str(args.resolution)):
        camera.request(command)
    info = camera.request('P')
    first = camera.request('C')
    print(f'{info}; first_jpeg_bytes={len(first)}', flush=True)
    metrics = Metrics(args.metrics_log, info) if args.metrics_log else None

    class Handler(BaseHTTPRequestHandler):
        def send(self, code, kind, body, meta=None):
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if meta:
                for key in ('capture', 'encode', 'transfer'):
                    self.send_header(f'X-{key.title()}-Ms', str(meta[key+'_ms']))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                if self.path.split('?', 1)[0] == '/':
                    self.send(200, 'text/html; charset=utf-8', PAGE.encode())
                elif self.path.startswith('/frame.jpg'):
                    try:
                        data, meta = camera.capture()
                    except (OSError, ValueError) as error:
                        if metrics:
                            metrics.error(error)
                        raise
                    if metrics:
                        metrics.frame(meta, len(data))
                    self.send(200, 'image/jpeg', data, meta)
                elif self.path == '/metrics':
                    report = metrics.latest() if metrics else {'state': 'metrics_disabled'}
                    self.send(200, 'application/json', json.dumps(report).encode())
                elif self.path == '/status':
                    status = camera.request('P')
                    fields = dict(item.split('=', 1) for item in status.split()[1:])
                    self.send(200, 'application/json', json.dumps(fields).encode())
                else:
                    self.send(404, 'text/plain', b'Not found')
            except (OSError, ValueError) as error:
                self.send(503, 'text/plain; charset=utf-8', str(error).encode())

        def do_POST(self):
            if self.headers.get('Origin') != f'http://127.0.0.1:{args.port}':
                self.send(403, 'text/plain', b'Local origin required')
                return
            if self.path not in tuple('/control?'+c for c in '01234abcHV'):
                self.send(404, 'text/plain', b'Not found')
                return
            try:
                camera.request(self.path[-1])
                if metrics:
                    with metrics.lock:
                        metrics.write({'event': 'control', 'command': self.path[-1],
                                       'elapsed_seconds': time.monotonic()-metrics.started})
                self.send(200, 'text/plain', b'OK')
            except (OSError, ValueError) as error:
                self.send(503, 'text/plain; charset=utf-8', str(error).encode())

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if metrics:
            metrics.close()
        os.close(camera.fd)


if __name__ == '__main__':
    main()
