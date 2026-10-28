"""Conecta la preparación de ingeniería a las rutas y formularios existentes."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def change(name,old,new):
    p=root/name;text=p.read_text(encoding='utf-8')
    if new in text:return
    assert text.count(old)==1,(name,text.count(old))
    p.write_text(text.replace(old,new),encoding='utf-8')
app='draft2model/revision_visual.py'
change(app,"'reconstruccion.js','etapas.js'","'reconstruccion.js','preparacion_configuracion.js','etapas.js'")
change(app,'self._reconstruccion = None','self._reconstruccion = None\n        self._preparacion_configuracion = None')
change(app,'    @property\n    def reconstruccion(self):','''    @property
    def preparacion_configuracion(self):
        with self.lock:
            if self._preparacion_configuracion is None:
                from .preparacion_configuracion import ServicioPreparacionConfiguracion
                self._preparacion_configuracion = ServicioPreparacionConfiguracion(self)
            return self._preparacion_configuracion

    @property
    def reconstruccion(self):''')
change(app,"            if route.path == '/api/reconstruccion/cuota':",'''            if route.path == '/api/configuracion/preparaciones':
                return self.responder(200,{'versiones':app.preparacion_configuracion.listar(arg('caso'),arg('expediente_sha256'))})
            if route.path == '/api/configuracion/preparacion':
                return self.responder(200,app.preparacion_configuracion.consultar(arg('caso'),arg('expediente_sha256'),arg('version')))
            if route.path == '/api/reconstruccion/cuota':''')
change(app,"        config_operation = {'/api/configuracion/importar'",'''        config_preparation_operation={'/api/configuracion/preparacion/crear':'crear','/api/configuracion/preparacion/guardar':'guardar','/api/configuracion/preparacion/registrar':'registrar'}.get(self.path)
        config_operation = {'/api/configuracion/importar\'''')
change(app,'        operation = reconstruction_operation or ','        operation = config_preparation_operation or reconstruction_operation or ')
change(app,'            if reconstruction_operation:\n                result=', '''            if config_preparation_operation:
                result=getattr(self.server.revision.preparacion_configuracion,config_preparation_operation)(body)
            elif reconstruction_operation:
                result=''')
change('draft2model/revision_web/index.html','<script src="/editor_ingenieria.js"></script>',
       '<script src="/editor_ingenieria.js"></script><script src="/preparacion_configuracion.js"></script>')
change('draft2model/revision_web/configuracion.js',' clear();\n})();', ''' window.addEventListener('d2m-config-created',event=>{
  const value=event.detail;
  if(!docs||value?.caso!==docs.caso||value.expediente_sha256!==docs.expediente_sha256||value.aprueba_ingenieria!==false||value.registrada!==true)return;
  listing(value.configuracion).catch(error=>message(error.message,true));
 });
 clear();
})();''')
print('Preparación de ingeniería348 integrada en rutas y editor web.')
