"""Conecta el servicio de reconstrucción a las rutas y al espacio por etapas."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def change(path,old,new):
    p=root/path;s=p.read_text(encoding='utf-8')
    if new in s:return
    assert s.count(old)==1,(path,s.count(old),old)
    p.write_text(s.replace(old,new),encoding='utf-8')
app='draft2model/revision_visual.py'
change(app,"'etapas.js','etapas.css'","'reconstruccion.js','etapas.js','etapas.css'")
change(app,'self._explicaciones = None','self._explicaciones = None\n        self._reconstruccion = None')
change(app,'    def tabular_version(self, caso, version, expediente_sha256):',
'''    @property
    def reconstruccion(self):
        with self.lock:
            if self._reconstruccion is None:
                from .revision_reconstruccion import ServicioReconstruccion
                self._reconstruccion = ServicioReconstruccion(self)
            return self._reconstruccion

    def tabular_version(self, caso, version, expediente_sha256):''')
change(app,"            if route.path == '/api/casos':",'''            if route.path == '/api/reconstruccion/cuota':
                return self.responder(200,app.reconstruccion.estado_cuota())
            if route.path == '/api/reconstruccion/historial':
                return self.responder(200,{'trabajos':app.reconstruccion.listar(arg('caso'),arg('expediente_sha256'))})
            if route.path == '/api/reconstruccion/estado':
                return self.responder(200,app.reconstruccion.consultar(arg('caso'),arg('expediente_sha256'),arg('trabajo')))
            if route.path == '/api/casos':''')
change(app,"        config_operation = {'/api/configuracion/importar'", "        reconstruction_operation={'/api/reconstruccion/preparar':'preparar_originales','/api/reconstruccion/ejecutar':'ejecutar'}.get(self.path)\n        config_operation = {'/api/configuracion/importar'")
change(app,"        operation = ('controles'", "        operation = reconstruction_operation or ('controles'")
change(app,'            if controls_operation:\n                result=',
'''            if reconstruction_operation:
                result=getattr(self.server.revision.reconstruccion,reconstruction_operation)(body)
            elif controls_operation:
                result=''')
change('draft2model/revision_web/index.html','<script src="/etapas.js"></script>',
       '<script src="/etapas.js"></script><script src="/reconstruccion.js"></script>')
print('Rutas y panel de reconstrucción345 integrados; requiere reiniciar el servidor de UI sin trabajos activos.')
