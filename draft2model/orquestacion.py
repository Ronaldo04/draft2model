"""Corridas locales persistentes; exclusión de motor e invalidación por entradas."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from datetime import datetime, timezone


class ErrorCorrida(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


class RegistroCorridas:
    """No ejecuta comandos ni reintenta ETABS; el adaptador solicita cada transición."""
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz).resolve()
        self.raiz.mkdir(parents=True, exist_ok=True)
        self.db = self.raiz / 'corridas.sqlite3'
        if self.db.resolve() != self.db:
            raise ErrorCorrida('Base de corridas enlazada.')
        with self._conexion() as db:
            db.execute('CREATE TABLE IF NOT EXISTS corridas (id TEXT PRIMARY KEY, caso TEXT NOT NULL, etapa TEXT NOT NULL, estado TEXT NOT NULL, entradas TEXT NOT NULL, salidas TEXT NOT NULL, creado TEXT NOT NULL, actualizado TEXT NOT NULL, motivo TEXT)')
            # Una sola operación de motor, incluso si dos procesos usan distintas etapas.
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS motor_unico ON corridas((1)) WHERE estado='en_ejecucion'")

    def _conexion(self):
        if self.db.resolve() != self.db:
            raise ErrorCorrida('Base de corridas enlazada.')
        return sqlite3.connect(self.db, timeout=10)

    def _huellas(self, caso, rutas):
        if not isinstance(caso,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',caso):
            raise ErrorCorrida('Caso inválido.')
        case = self.raiz / caso
        if case.resolve()!=case or not case.is_dir():
            raise ErrorCorrida('Caso ausente o enlazado.')
        if not isinstance(rutas,list) or not rutas or not all(isinstance(p,str) for p in rutas) or len(set(rutas))!=len(rutas):
            raise ErrorCorrida('Se requieren rutas relativas distintas y explícitas.')
        result={}
        for name in rutas:
            if not isinstance(name,str): raise ErrorCorrida('Ruta inválida.')
            relative=Path(name); target=case/relative
            if relative.is_absolute() or '..' in relative.parts or target.resolve()!=target or not target.is_file():
                raise ErrorCorrida('Entrada/salida ausente, enlazada o fuera del caso.')
            result[name]=hashlib.sha256(target.read_bytes()).hexdigest()
        return result

    def crear(self, caso, etapa, entradas):
        if etapa not in ('preparacion','vision','geometria','modelo','analisis','evaluacion','informe'):
            raise ErrorCorrida('Etapa desconocida.')
        hashes=self._huellas(caso,entradas); ident=uuid4().hex; now=_now()
        with self._conexion() as db:
            db.execute('INSERT INTO corridas VALUES (?,?,?,?,?,?,?,?,?)',
                       (ident,caso,etapa,'preparada',json.dumps(hashes),'{}',now,now,None))
        return ident

    def consultar(self, ident):
        if not isinstance(ident,str) or not re.fullmatch(r'[0-9a-f]{32}',ident):
            raise ErrorCorrida('Identificador inválido.')
        with self._conexion() as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT * FROM corridas WHERE id=?',(ident,)).fetchone()
        if row is None: raise ErrorCorrida('Corrida inexistente.')
        data=dict(row)
        for key in ('entradas','salidas'): data[key]=json.loads(data[key])
        problems=[]
        for key in ('entradas','salidas'):
            if data[key]:
                try:
                    if self._huellas(data['caso'],list(data[key]))!=data[key]:
                        problems.append(f'{key}: contenido cambió; regenerar derivados.')
                except (ValueError,OSError) as exc: problems.append(f'{key}: {exc}')
        data['vigente']=not problems;data['problemas']=problems
        return data

    def iniciar(self, ident):
        data=self.consultar(ident)
        if not data['vigente'] or data['estado']!='preparada':
            raise ErrorCorrida('Solo se inicia una corrida preparada con entradas vigentes.')
        try:
            with self._conexion() as db:
                cursor=db.execute("UPDATE corridas SET estado='en_ejecucion',actualizado=? WHERE id=? AND estado='preparada'",(_now(),ident))
                if cursor.rowcount!=1: raise ErrorCorrida('La corrida cambió en otro proceso.')
        except sqlite3.IntegrityError as exc:
            raise ErrorCorrida('Existe otra corrida activa. No se duplica la operación del motor.') from exc
        return self.consultar(ident)

    def finalizar(self, ident, salidas):
        data=self.consultar(ident)
        if data['estado']!='en_ejecucion' or not data['vigente']:
            raise ErrorCorrida('Corrida no activa o entradas cambiadas; registrar fallo y revisar.')
        hashes=self._huellas(data['caso'],salidas)
        if set(hashes)&set(data['entradas']):
            raise ErrorCorrida('Una salida no puede sustituir una entrada de la corrida.')
        with self._conexion() as db:
            cursor=db.execute("UPDATE corridas SET estado='completada',salidas=?,actualizado=? WHERE id=? AND estado='en_ejecucion'",(json.dumps(hashes),_now(),ident))
            if cursor.rowcount!=1: raise ErrorCorrida('La corrida cambió en otro proceso.')
        return self.consultar(ident)

    def fallar(self, ident, motivo):
        self.consultar(ident)
        if not isinstance(motivo,str) or not motivo.strip(): raise ErrorCorrida('Motivo requerido.')
        with self._conexion() as db:
            cursor=db.execute("UPDATE corridas SET estado='fallida',motivo=?,actualizado=? WHERE id=? AND estado='en_ejecucion'",(motivo,_now(),ident))
            if cursor.rowcount!=1: raise ErrorCorrida('Solo una corrida activa puede registrar fallo.')
        return self.consultar(ident)

    def recuperar(self, ident, *, motor_detenido_declarado, motivo):
        """No presume que matar un cliente haya detenido ETABS; requiere comprobación externa."""
        self.consultar(ident)
        if motor_detenido_declarado is not True or not isinstance(motivo,str) or not motivo.strip():
            raise ErrorCorrida('Comprobar motor detenido y declarar motivo antes de liberar.')
        with self._conexion() as db:
            cursor=db.execute("UPDATE corridas SET estado='interrumpida',motivo=?,actualizado=? WHERE id=? AND estado='en_ejecucion'",(motivo,_now(),ident))
            if cursor.rowcount!=1: raise ErrorCorrida('Solo recuperar una corrida activa.')
        return self.consultar(ident)
