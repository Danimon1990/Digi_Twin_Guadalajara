from __future__ import annotations
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from ..experiments import CONFIG, run_experiment


def make_server(output: Path, port: int = 8765) -> ThreadingHTTPServer:
    output=output.resolve(); output.mkdir(parents=True,exist_ok=True)
    jobs={}; lock=threading.Lock(); token=secrets.token_urlsafe(32)
    page=Path(__file__).with_name('index.html').read_text().replace('__TOKEN__',token)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def reply(self,status,body,kind='application/json'):
            data=body.encode() if isinstance(body,str) else json.dumps(body,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass  # browser navigated away
        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        def do_GET(self):
            if not self.valid_host():return self.reply(403,{'error':'Local host only'})
            path=urlparse(self.path).path
            if path=='/':return self.reply(200,page,'text/html')
            if path=='/api/catalog':return self.reply(200,json.loads((CONFIG/'product_catalog.json').read_text()))
            match=re.fullmatch(r'/api/jobs/([a-f0-9]{32})',path)
            if match:
                job=jobs.get(match[1]);return self.reply(200,job) if job else self.reply(404,{'error':'Unknown run'})
            match=re.fullmatch(r'/runs/([a-f0-9]{32})/(replay.html|summary.json)',path)
            if match:
                file=output/match[1]/match[2]
                if file.is_file():return self.reply(200,file.read_text(),'text/html' if file.suffix=='.html' else 'application/json')
            return self.reply(404,{'error':'Not found'})
        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-Experiment-Token')!=token:
                return self.reply(403,{'error':'Local session token required'})
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:
                return self.reply(403,{'error':'Same-origin only'})
            if self.path!='/api/run':return self.reply(404,{'error':'Not found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=65536:raise ValueError('Invalid request size')
                options=json.loads(self.rfile.read(length))
                if not isinstance(options,dict):raise ValueError('Expected options object')
            except (ValueError,json.JSONDecodeError) as e:return self.reply(400,{'error':str(e)})
            if not lock.acquire(blocking=False):return self.reply(409,{'error':'A simulation is already running'})
            id=uuid4().hex;jobs[id]={'id':id,'status':'running'}
            def compute():
                try:
                    summary=run_experiment(options,output/id)
                    jobs[id]={'id':id,'status':'done','summary':summary,'replay_url':f'/runs/{id}/replay.html','summary_url':f'/runs/{id}/summary.json'}
                except Exception as e:
                    jobs[id]={'id':id,'status':'error','error':f'{type(e).__name__}: {e}'}
                finally:lock.release()
            threading.Thread(target=compute,daemon=True).start()
            self.reply(202,{'id':id,'status':'running'})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def serve(output:Path,port:int=8765):
    server=make_server(output,port)
    print(f'Local simulation UI: http://127.0.0.1:{server.server_port}',flush=True)
    print(f'Each run is saved separately under {output.resolve()}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
