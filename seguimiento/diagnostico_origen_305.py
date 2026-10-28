"""Eco local de cabeceras de navegación; sin cookies, tokens, archivos ni claves."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == '/prueba':
            raw = b'''<!doctype html><meta charset="utf-8"><title>Diagnostico local de conexion</title>
<h1>Conexion local sin datos privados</h1><button id="probar">Comprobar solicitud de esta pagina</button><pre id="estado">Sin consultar</pre>
<script>document.getElementById('probar').onclick=async()=>{const out=document.getElementById('estado');out.textContent='Consultando';try{const r=await fetch('/eco',{headers:{'X-Revision-Session':'diagnostico-sin-credencial'}});out.textContent=await r.text();}catch(e){out.textContent=String(e);}};</script>'''
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        keys = ('Host', 'Origin', 'Sec-Fetch-Site', 'Sec-Fetch-Mode', 'Sec-Fetch-Dest')
        raw = json.dumps({key: self.headers.get(key) for key in keys}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 18304), Handler).serve_forever()
