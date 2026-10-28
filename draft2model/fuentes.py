"""Recuperación local de fragmentos aprobados y citas verificables, sin LLM/red."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .gestion_extraccion import json_desde_bytes


def huella_corpus(corpus):
    data = {k: v for k, v in corpus.items() if k != 'aprobacion'}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def _texto(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label}: se requiere texto no vacío.')
    return value


def cargar_corpus(manifiesto: Path) -> dict:
    """Verificar rutas relativas, hashes y aprobación exacta antes de recuperar."""
    manifiesto = Path(manifiesto).resolve()
    corpus = json_desde_bytes(manifiesto.read_bytes(), manifiesto.name)
    if not isinstance(corpus, dict) or set(corpus) != {'contrato', 'version', 'datos_sinteticos', 'documentos', 'fragmentos', 'aprobacion'}:
        raise ValueError('Manifiesto de corpus inválido.')
    if corpus['contrato'] != 'draft2model.corpus' or corpus['version'] != '0.1.0' or type(corpus['datos_sinteticos']) is not bool:
        raise ValueError('Contrato o naturaleza de corpus inválidos.')
    approval = corpus['aprobacion']
    if not isinstance(approval, dict) or set(approval) != {'huella', 'revisor_declarado', 'fecha', 'alcance'}:
        raise ValueError('Corpus requiere aprobación declarada explícita.')
    for key in ('revisor_declarado', 'fecha', 'alcance'):
        _texto(approval[key], key)
    from datetime import date
    date.fromisoformat(approval['fecha'])
    if approval['huella'] != huella_corpus(corpus):
        raise ValueError('Aprobación de corpus desactualizada.')
    if not isinstance(corpus['documentos'], list) or not corpus['documentos']:
        raise ValueError('Corpus sin documentos.')
    documents = {}
    for doc in corpus['documentos']:
        if not isinstance(doc, dict) or set(doc) != {'id', 'titulo', 'edicion', 'archivo', 'sha256'}:
            raise ValueError('Documento de corpus inválido.')
        for key in doc:
            _texto(doc[key], key)
        if doc['id'] in documents:
            raise ValueError('Documento duplicado.')
        relative = Path(doc['archivo'])
        target = manifiesto.parent / relative
        if relative.is_absolute() or '..' in relative.parts or target.resolve() != target or not target.resolve().is_relative_to(manifiesto.parent):
            raise ValueError('Documento fuera del corpus o enlazado.')
        if hashlib.sha256(target.read_bytes()).hexdigest() != doc['sha256']:
            raise ValueError('Documento fuente alterado.')
        documents[doc['id']] = doc
    if not isinstance(corpus['fragmentos'], list) or not corpus['fragmentos']:
        raise ValueError('Corpus sin fragmentos.')
    ids = set()
    for fragment in corpus['fragmentos']:
        if not isinstance(fragment, dict) or set(fragment) != {'id', 'documento', 'pagina', 'apartado', 'texto'}:
            raise ValueError('Fragmento inválido.')
        for key in ('id', 'documento', 'apartado', 'texto'):
            _texto(fragment[key], key)
        if fragment['id'] in ids or fragment['documento'] not in documents:
            raise ValueError('Fragmento duplicado o documento inexistente.')
        if type(fragment['pagina']) is not int or fragment['pagina'] < 1:
            raise ValueError('Página de fragmento inválida.')
        ids.add(fragment['id'])
    return copy.deepcopy(corpus)


def _tokens(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')
    return set(re.findall(r'[a-z0-9]{3,}', text))


def recuperar(manifiesto: Path, consulta: str, limite: int = 5) -> dict:
    """Ranking léxico determinístico. Sin coincidencia se abstiene explícitamente."""
    _texto(consulta, 'consulta')
    if type(limite) is not int or not 1 <= limite <= 20:
        raise ValueError('Límite entre 1 y 20.')
    corpus = cargar_corpus(manifiesto)
    terms = _tokens(consulta)
    docs = {d['id']: d for d in corpus['documentos']}
    matches = []
    for item in corpus['fragmentos']:
        score = len(terms & _tokens(item['texto'] + ' ' + item['apartado']))
        if score:
            matches.append({**copy.deepcopy(item), 'coincidencias': score,
                            'titulo': docs[item['documento']]['titulo'],
                            'edicion': docs[item['documento']]['edicion'],
                            'sha256_documento': docs[item['documento']]['sha256']})
    matches.sort(key=lambda item: (-item['coincidencias'], item['id']))
    return {'huella_corpus': huella_corpus(corpus), 'datos_sinteticos': corpus['datos_sinteticos'],
            'metodo': 'recuperacion_lexica_local', 'fragmentos': matches[:limite],
            'abstencion': not matches, 'identidad_revisor': 'declarada_no_verificada'}


def verificar_citas(manifiesto: Path, citas: list[dict], huella_esperada: str):
    corpus = cargar_corpus(manifiesto)
    if huella_corpus(corpus) != huella_esperada:
        raise ValueError('El corpus cambió; regenerar explicación.')
    if not isinstance(citas, list):
        raise ValueError('Citas deben ser una lista.')
    fragments = {f['id']: f for f in corpus['fragmentos']}
    for citation in citas:
        if not isinstance(citation, dict) or set(citation) != {'fragmento_id', 'texto'}:
            raise ValueError('Cita inválida.')
        fragment = fragments.get(citation['fragmento_id'])
        if fragment is None or citation['texto'] != fragment['texto']:
            raise ValueError('Cita inexistente o texto alterado.')
    return True
