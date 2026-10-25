"""Contabilidad declarada de contenido; no crea cargas ni configura un motor."""
import math


class ErrorContabilidad(ValueError):
    pass


def _numero(value, name, minimo=None, positivo=False):
    if type(value) not in (int, float):
        raise ErrorContabilidad(name + ': número finito, no booleano, requerido')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (minimo is not None and value < minimo) or (positivo and value <= 0):
        raise ErrorContabilidad(name + ': número fuera de dominio')
    return value


def _texto(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ErrorContabilidad(name + ': referencia explícita requerida')
    return value


def _lista(value, name):
    if not isinstance(value, list):
        raise ErrorContabilidad(name + ': lista explícita requerida')
    return value


def _factores(rows, key):
    out = {}
    for row in _lista(rows, 'factores'):
        ident = _texto(row[key], key)
        if ident in out:
            raise ErrorContabilidad('Referencia repetida: ' + ident)
        out[ident] = _numero(row['factor'], 'factor')
    return out


def _cerca(a, b):
    return abs(a-b) <= 1e-9 * max(1, abs(a), abs(b))


def auditar(escenarios, *, masa, patrones, hosts, casos, combinaciones):
    """Una evaluación contiene un estado explícito por depósito.

    hosts: registros conservados de preparar_liquidos, no resultados de un solver.
    casos/combinaciones: listas completas con formato de configuración 0.5.
    Las referencias de fuente son declaradas, no autenticadas aquí.
    """
    try:
        return _auditar(escenarios, masa, patrones, hosts, casos, combinaciones)
    except ErrorContabilidad:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ErrorContabilidad('Entrada incompleta o no representable: ' + str(exc)) from None


def _auditar(escenarios, masa, patrones, hosts, casos, combinaciones):
    escenarios = _lista(escenarios, 'escenarios')
    if not escenarios:
        raise ErrorContabilidad('Declare al menos un escenario')
    if masa['metodo'] != 'patrones' or _lista(masa['masas_puntos'], 'masas_puntos'):
        raise ErrorContabilidad('Solo patrones; no mezclar masas explícitas y patrones')
    gravity = _numero(masa['gravedad_m_s2'], 'gravedad fuente masa', positivo=True)
    factores = _factores(masa['factores_patrones'], 'patron')
    existentes = {}
    for p in _lista(patrones, 'patrones'):
        ident = _texto(p['id'], 'patron.id')
        if ident in existentes:
            raise ErrorContabilidad('Patrón repetido: ' + ident)
        existentes[ident] = _numero(p['multiplicador_peso_propio'], 'peso propio', 0)
    if set(factores) - set(existentes):
        raise ErrorContabilidad('Fuente de masa referencia patrón inexistente')
    case_patterns = {}
    for c in _lista(casos, 'casos'):
        ident = _texto(c['id'], 'caso.id')
        if ident in case_patterns:
            raise ErrorContabilidad('Caso repetido')
        kind = c['tipo']
        if kind not in ('estatico_lineal', 'modal_eigen', 'espectro_respuesta'):
            raise ErrorContabilidad('Tipo de caso desconocido')
        f = _factores(c['parametros']['patrones'], 'patron') if kind == 'estatico_lineal' else {}
        if set(f) - set(existentes):
            raise ErrorContabilidad('Caso referencia patrón inexistente')
        case_patterns[ident] = {p for p, factor in f.items() if factor != 0}
    contexts = list(case_patterns.values())
    combo_ids = set()
    for c in _lista(combinaciones, 'combinaciones'):
        ident = _texto(c['id'], 'combinacion.id')
        if ident in combo_ids or c['tipo'] not in ('lineal', 'envolvente'):
            raise ErrorContabilidad('Combinación repetida o tipo desconocido')
        combo_ids.add(ident)
        f = _factores(c['casos'], 'caso')
        if set(f) - set(case_patterns):
            raise ErrorContabilidad('Combinación referencia caso inexistente')
        contexts.append(set().union(*(case_patterns[k] for k, v in f.items() if v != 0)))
    hosts = _lista(hosts, 'hosts')
    report, deposits, declarations, patterns_used, host_keys = [], set(), set(), set(), set()
    claimed_hosts = set()
    for s in escenarios:
        deposito = _texto(s['deposito'], 'deposito')
        estado = _texto(s['estado'], 'estado')
        fuente = _texto(s['fuente'], 'fuente')
        declaration = _texto(s['declaracion'], 'declaracion')
        if deposito in deposits or declaration in declarations:
            raise ErrorContabilidad('Depósito/estado alternativo o declaración duplicados en una evaluación')
        deposits.add(deposito); declarations.add(declaration)
        volume = _numero(s['volumen_m3'], 'volumen', 0)
        gamma = _numero(s['peso_especifico_kn_m3'], 'gamma', positivo=True)
        g = _numero(s['gravedad_m_s2'], 'gravedad', positivo=True)
        if g != gravity:
            raise ErrorContabilidad('Gravedad de escenario distinta de fuente de masa')
        h = _numero(s['nivel_libre_z_m'], 'nivel libre')
        weight = _numero(volume*gamma, 'gammaV', 0)
        mass = _numero(weight/g, 'masa calculada', 0)
        pressure = _texto(s['patron_presion'], 'patron_presion')
        alternative = s['patron_masa_exclusivo']
        if alternative is not None:
            _texto(alternative, 'patron_masa_exclusivo')
        declared = {pressure} | ({alternative} if alternative is not None else set())
        if alternative == pressure or declared & patterns_used:
            raise ErrorContabilidad('Representaciones/patrones compartidos o duplicados')
        patterns_used.update(declared)
        for p in declared:
            if p not in existentes or existentes[p] != 0:
                raise ErrorContabilidad('Patrón de contenido inexistente o con peso propio')
        mode = s['modo']
        if mode == 'patron_presion':
            selected = pressure
            if s['peso_vertical_referencia_kn'] is not None:
                raise ErrorContabilidad('Modo presión no admite segunda representación de peso')
        elif mode == 'patron_masa_exclusivo':
            if alternative is None:
                raise ErrorContabilidad('Declare patrón exclusivo')
            selected = alternative
            reference = _numero(s['peso_vertical_referencia_kn'], 'peso vertical referencia', 0)
            if not _cerca(reference, weight):
                raise ErrorContabilidad('Peso vertical de referencia distinto de gammaV')
            if any(alternative in context for context in contexts):
                raise ErrorContabilidad('Patrón solo masa no admite uso en caso/combinación estática')
        else:
            raise ErrorContabilidad('Modo explícito no admitido')
        if factores.get(selected) != 1:
            raise ErrorContabilidad('Contenido100% exige factor exactamente 1 del patrón elegido')
        if any(factores.get(p, 0) != 0 for p in declared - {selected}):
            raise ErrorContabilidad('Representación alternativa también incluida en masa')
        selected_hosts = []
        for i, host in enumerate(hosts):
            if host['declaracion'] != declaration and host['patron'] != pressure:
                continue
            if host['declaracion'] != declaration or host['patron'] != pressure:
                raise ErrorContabilidad('Host ligado a otra declaración/patrón')
            if (_numero(host['peso_especifico_kn_m3'], 'host.gamma', positivo=True) != gamma
                    or _numero(host['nivel_libre_z_m'], 'host.nivel') != h):
                raise ErrorContabilidad('Host ligado a otro gamma/nivel')
            key = (declaration, pressure, _texto(host['superficie'], 'host.superficie'))
            if key in host_keys:
                raise ErrorContabilidad('Host duplicado')
            host_keys.add(key); claimed_hosts.add(i)
            a, b = host['fuerza_kn'], host['fuerza_fuente_kn']
            if not isinstance(a, list) or not isinstance(b, list) or len(a) != 3 or len(b) != 3:
                raise ErrorContabilidad('Fuerzas XYZ requeridas')
            for x, y in zip(a, b):
                if not _cerca(_numero(x, 'fuerza'), _numero(y, 'fuerza fuente')):
                    raise ErrorContabilidad('Fuerza no conservada en host')
            if _numero(host['error_relativo_max'], 'error conservación', 0) > 1e-9:
                raise ErrorContabilidad('Host no conserva integral')
            selected_hosts.append(host)
        if not selected_hosts:
            raise ErrorContabilidad('Faltan hosts de presión conservada para la declaración')
        fz = _numero(math.fsum(host['fuerza_kn'][2] for host in selected_hosts), 'Fz')
        if mode == 'patron_presion' and not _cerca(fz, -weight):
            raise ErrorContabilidad('Integral Fz no equivale a -gammaV: falta fondo/cobertura o signo incorrecto')
        report.append({'deposito': deposito, 'estado': estado, 'fuente': fuente,
                       'declaracion': declaration, 'modo': mode, 'patron_masa': selected,
                       'volumen_m3': volume, 'peso_kn': weight, 'masa_kn_s2_m': mass,
                       'factor_contenido': 1, 'fz_presion_kn': fz})
    if claimed_hosts != set(range(len(hosts))):
        raise ErrorContabilidad('Hosts de contenido sin escenario contabilizado')
    return {'estado': 'contabilidad_declarada_coherente', 'escenarios': report,
            'peso_total_kn': _numero(math.fsum(r['peso_kn'] for r in report), 'peso total', 0),
            'masa_total_kn_s2_m': _numero(math.fsum(r['masa_kn_s2_m'] for r in report), 'masa total', 0),
            'aprueba_ingenieria': False, 'crea_cargas': False, 'ejecutable': False}
