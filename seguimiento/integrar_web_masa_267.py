"""Edición localizada de los puntos de propagación documental de masa267."""
from pathlib import Path

p=Path('draft2model/revision_entregables.py')
s=p.read_text(encoding='utf-8')
def cambiar(a,b,n=1):
    global s
    if s.count(a)!=n:
        raise RuntimeError((a[:90],s.count(a),n))
    s=s.replace(a,b)
cambiar('relectura_source=None):','relectura_source=None,masa_sources=None):')
cambiar('        if refs_data is None:\n            return crear_informe', '        masa_sources=masa_sources or {}\n        if refs_data is None:\n            return crear_informe')
cambiar('fuente_relectura_modelo=relectura_source)', 'fuente_relectura_modelo=relectura_source,**masa_sources)',4)
cambiar("{'referencias','revision_resultados','controles_analisis','relectura_modelo'}", "{'referencias','revision_resultados','controles_analisis','relectura_modelo','contenido_masa','masa_nativa'}",2)
cambiar("            checked,geometry,source,_=self._fuente(caso,body['resultado'],fingerprint,body['analisis'])", "            masa_sources=self._fuentes_masa(caso,fingerprint,body,body['analisis'])\n            checked,geometry,source,_=self._fuente(caso,body['resultado'],fingerprint,body['analisis'])")
cambiar('refs_data,revision_source,controles_source,relectura_source)', 'refs_data,revision_source,controles_source,relectura_source,masa_sources)',2)
cambiar("                if refs:meta['referencias']=refs", "                for key in ('contenido_masa','masa_nativa'):\n                    if key in body:meta[key]=body[key]\n                if refs:meta['referencias']=refs",1) if False else None
# Las dos ramas de creación y aprobación tienen el mismo texto; se editan por contexto.
cambiar("                if revision_source:meta['revision_resultados']=body['revision_resultados']", "                for key in ('contenido_masa','masa_nativa'):\n                    if key in body:meta[key]=body[key]\n                if revision_source:meta['revision_resultados']=body['revision_resultados']")
cambiar("        contents={name:self._seguro(target/name).read_bytes() for name in meta['archivos']}", "        masa_sources=self._fuentes_masa(caso,expediente_sha256,meta,meta['analisis'])\n        contents={name:self._seguro(target/name).read_bytes() for name in meta['archivos']}")
cambiar('        refs_data=None\n', "        masa_actual=self._masa_actual(masa_sources,checked,ev)\n        if any(report.get(k)!=v for k,v in masa_actual.items()):\n            raise ValueError('La masa del informe no corresponde a las fuentes vigentes.')\n        refs_data=None\n")
cambiar("                    or pm.get('relectura_modelo_seleccionada')!=meta.get('relectura_modelo')", "                    or pm.get('contenido_masa_seleccionado')!=meta.get('contenido_masa')\n                    or pm.get('masa_nativa_seleccionada')!=meta.get('masa_nativa')\n                    or pm.get('relectura_modelo_seleccionada')!=meta.get('relectura_modelo')")
cambiar("        if refs is not None and self._referencias", "        if self._masa_actual(masa_sources,current,current_ev)!=masa_actual:\n            raise ValueError('Las fuentes de masa cambiaron durante la consulta.')\n        if refs is not None and self._referencias")
cambiar("        return ({**meta,**extra,'evidencia_analisis':ev", "        return ({**meta,**extra,**masa_actual,\n                 'contenido_masa_seleccionado':meta.get('contenido_masa'),\n                 'masa_nativa_seleccionada':meta.get('masa_nativa'),'evidencia_analisis':ev")
cambiar("            refs_data=self._referencias(caso,fp,before['resultado']", "            seleccion_masa={}\n            if before.get('contenido_masa_seleccionado') is not None:seleccion_masa['contenido_masa']=before['contenido_masa_seleccionado']\n            if before.get('masa_nativa_seleccionada') is not None:seleccion_masa['masa_nativa']=before['masa_nativa_seleccionada']\n            masa_sources=self._fuentes_masa(caso,fp,seleccion_masa,before['analisis'])\n            refs_data=self._referencias(caso,fp,before['resultado']")
cambiar("                if relectura_ref is not None:meta['relectura_modelo']=relectura_ref", "                meta.update(seleccion_masa)\n                if relectura_ref is not None:meta['relectura_modelo']=relectura_ref")
p.write_bytes(s.encode('utf-8'))
