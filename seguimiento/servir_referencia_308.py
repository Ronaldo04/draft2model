"""Vista temporal de QA, limitada al kit y al origen local; sin API."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'referencia_humana_308'
ORIGIN='http://127.0.0.1:18308'
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        if (self.headers.get('Host')!='127.0.0.1:18308'
                or self.headers.get('Origin') not in (None,ORIGIN)
                or self.headers.get('Sec-Fetch-Site') not in (None,'none','same-origin')):
            self.send_error(403,'Acceso local no autorizado');return
        super().do_GET()

if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',18308),partial(Handler,directory=str(ROOT))).serve_forever()
