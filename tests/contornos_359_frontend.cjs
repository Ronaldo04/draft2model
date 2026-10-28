'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const ROOT = path.resolve(__dirname, '..');
const SCRIPT_PATH = path.join(ROOT, 'draft2model', 'revision_web', 'contornos.js');
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, 'utf8');

class FakeEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail !== undefined ? init.detail : null;
    this.defaultPrevented = false;
  }
  preventDefault() {
    this.defaultPrevented = true;
  }
}

class FakeCustomEvent extends FakeEvent {
  constructor(type, init = {}) {
    super(type, init);
  }
}

class FakeTextNode {
  constructor(text) {
    this.nodeType = 3;
    this._text = String(text ?? '');
    this.parentNode = null;
  }
  get textContent() {
    return this._text;
  }
  set textContent(v) {
    this._text = String(v ?? '');
  }
}

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.nodeType = 1;
    this.tagName = String(tagName).toUpperCase();
    this.ownerDocument = ownerDocument;
    this.parentNode = null;
    this.childNodes = [];
    this.attributes = new Map();
    this.dataset = {};
    this.listeners = new Map();
    this.id = '';
    this.className = '';
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.required = false;
    this.type = '';
    this.htmlFor = '';
    this.min = '';
    this.max = '';
    this.step = '';
    this.maxLength = -1;
    this._value = '';
  }

  get children() {
    return this.childNodes.filter(n => n.nodeType === 1);
  }

  get options() {
    if (this.tagName !== 'SELECT') return [];
    return this.children.filter(c => c.tagName === 'OPTION');
  }

  get value() {
    if (this.tagName === 'SELECT') {
      const opts = this.options;
      if (!opts.length) return '';
      if (opts.some(o => o.value === this._value)) return this._value;
      return opts[0].value;
    }
    return this._value;
  }

  set value(v) {
    const str = String(v ?? '');
    if (this.tagName === 'SELECT') {
      const opts = this.options;
      this._value = (!opts.length || opts.some(o => o.value === str)) ? str : '';
      return;
    }
    this._value = str;
  }

  get textContent() {
    return this.childNodes.map(n => n.textContent).join('');
  }

  set textContent(v) {
    this.replaceChildren();
    if (v !== '' && v !== null && v !== undefined) {
      this.append(new FakeTextNode(String(v)));
    }
  }

  setAttribute(name, val) {
    const s = String(val);
    this.attributes.set(name, s);
    if (name === 'id') this.id = s;
    if (name === 'class') this.className = s;
    if (name.startsWith('data-')) {
      const camel = name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      this.dataset[camel] = s;
    }
  }

  getAttribute(name) {
    if (name === 'id') return this.id || null;
    if (name === 'class') return this.className || null;
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  append(...nodes) {
    for (const raw of nodes) {
      const node = typeof raw === 'string' ? new FakeTextNode(raw) : raw;
      if (!node) continue;
      if (node.parentNode) node.remove?.();
      node.parentNode = this;
      this.childNodes.push(node);
      if (this.tagName === 'SELECT' && node.tagName === 'OPTION' && this.options.length === 1 && !this._value) {
        this._value = node.value;
      }
    }
  }

  replaceChildren(...nodes) {
    for (const c of this.childNodes) c.parentNode = null;
    this.childNodes = [];
    if (this.tagName === 'SELECT') this._value = '';
    if (nodes.length) this.append(...nodes);
  }

  after(node) {
    if (!this.parentNode) return;
    if (node.parentNode) node.remove?.();
    const idx = this.parentNode.childNodes.indexOf(this);
    node.parentNode = this.parentNode;
    this.parentNode.childNodes.splice(idx + 1, 0, node);
  }

  remove() {
    if (!this.parentNode) return;
    const idx = this.parentNode.childNodes.indexOf(this);
    if (idx >= 0) this.parentNode.childNodes.splice(idx, 1);
    this.parentNode = null;
  }

  addEventListener(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(fn);
  }

  dispatchEvent(ev) {
    const fns = [...(this.listeners.get(ev.type) || [])];
    for (const fn of fns) fn.call(this, ev);
    return !ev.defaultPrevented;
  }

  click() {
    if (this.disabled) return;
    if (this.tagName === 'INPUT' && this.type === 'checkbox') {
      this.checked = !this.checked;
      this.dispatchEvent(new FakeEvent('change'));
      return;
    }
    const ev = new FakeEvent('click');
    const proceed = this.dispatchEvent(ev);
    if (proceed && this.tagName === 'BUTTON' && this.type === 'submit') {
      let p = this.parentNode;
      while (p) {
        if (p.tagName === 'FORM') {
          p.dispatchEvent(new FakeEvent('submit'));
          break;
        }
        p = p.parentNode;
      }
    }
  }

  matchesSelector(sel) {
    const s = sel.trim();
    if (s.startsWith('#')) return this.id === s.slice(1);
    if (s.startsWith('.')) return this.className.split(/\s+/).includes(s.slice(1));
    const mAttr = /^([a-z0-9]+)?\[([a-z0-9_-]+)="([^"]*)"\]$/i.exec(s);
    if (mAttr) {
      const [, tag, attr, expected] = mAttr;
      if (tag && this.tagName !== tag.toUpperCase()) return false;
      const actual = attr.startsWith('data-')
        ? this.dataset[attr.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())]
        : (attr === 'type' ? this.type : this.getAttribute(attr));
      return actual === expected;
    }
    return this.tagName === s.toUpperCase();
  }

  querySelector(sel) {
    for (const child of this.children) {
      if (child.matchesSelector(sel)) return child;
      const found = child.querySelector(sel);
      if (found) return found;
    }
    return null;
  }

  querySelectorAll(sel) {
    const out = [];
    for (const child of this.children) {
      if (child.matchesSelector(sel)) out.push(child);
      out.push(...child.querySelectorAll(sel));
    }
    return out;
  }
}

class FakeDocument {
  constructor() {
    this.body = new FakeElement('body', this);
  }
  createElement(tag) {
    return new FakeElement(tag, this);
  }
  createTextNode(txt) {
    return new FakeTextNode(txt);
  }
  getElementById(id) {
    if (this.body.id === id) return this.body;
    return this.body.querySelector('#' + id);
  }
}

function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function flushMicrotasks(rounds = 24) {
  for (let i = 0; i < rounds; i++) {
    await Promise.resolve();
  }
}

const SHA_EXP_1 = '1'.repeat(64);
const SHA_EXP_2 = '2'.repeat(64);
const GEO_ORIG = 'a'.repeat(32);
const GEO_HUELLA_ORIG = 'b'.repeat(64);
const GEO_SHA_ORIG = 'c'.repeat(64);
const GEO_DERIV = 'd'.repeat(32);
const GEO_HUELLA_DERIV = 'e'.repeat(64);
const GEO_SHA_DERIV = 'f'.repeat(64);
const GEO_OTRA = '9'.repeat(32);

const PREP_1 = '11'.repeat(16);
const PREP_SHA_1 = '3'.repeat(64);
const PREP_2 = '22'.repeat(16);
const PREP_SHA_2 = '4'.repeat(64);
const PREP_DERIV = '33'.repeat(16);
const PREP_SHA_DERIV = '5'.repeat(64);
const JOB_1 = '44'.repeat(16);
const JOB_2 = '55'.repeat(16);

function makeGeoRecord(versionId, huella, sha, unidad = 'm') {
  const datos = {
    id: 'edificio-prueba',
    version_contrato: '0.3.0',
    unidad_longitud: unidad,
    revision: { estado: 'borrador', aprobacion: null },
    vertices: [{ id: 'V1', x: 0, y: 0, z: 0 }, { id: 'V2', x: 4, y: 0, z: 0 }, { id: 'V3', x: 0, y: 3, z: 0 }],
    superficies: [],
    aberturas: [],
    faltantes: []
  };
  return {
    huella,
    sha256_geometria: sha,
    datos,
    comprobacion: {
      correcta: true,
      huella_contenido: huella,
      sha256_geometria: sha,
      validacion: { consistente: true, datos_sinteticos: true, faltantes: [] }
    }
  };
}

function makePreconfig(id, sha, geoId = GEO_ORIG, geoHuella = GEO_HUELLA_ORIG, geoSha = GEO_SHA_ORIG, caso = 'edificio-prueba', expSha = SHA_EXP_1) {
  const geoOrig = { version_id: geoId, huella_contenido: geoHuella, sha256_geometria: geoSha };
  return {
    id,
    caso,
    expediente_sha256: expSha,
    sha256_configuracion: sha,
    datos: { caso, geometria_origen: geoOrig, revision: { estado: 'borrador', aprobacion: null } },
    registro: { id, caso, expediente_sha256: expSha, geometria_origen: geoOrig, sha256_configuracion: sha },
    puede_registrar: false,
    aprueba_ingenieria: false,
    ejecuta_etabs: false
  };
}

function makeSampleResultado({ conHijo = true } = {}) {
  const dibujos = [
    {
      id: 'DIB_PLANTA_1',
      archivo_id: 'LAM01',
      pagina: 1,
      bbox_pagina: [0, 0, 1, 1],
      plano_id: 'PL_Z_0',
      fuente: {
        original_id: 'LAM01',
        sha256: '7'.repeat(64),
        pagina: 1,
        dibujo_id: 'DIB_PLANTA_1',
        bbox_pagina: [0, 0, 1, 1]
      },
      plano: {
        id: 'PL_Z_0',
        ejes: ['x', 'y'],
        eje_constante: 'z',
        valor_constante: 0,
        unidad_longitud: 'm'
      },
      anclas: [
        { id: 'A1', punto_resuelto: 'V1', uv_local: [0.1, 0.9], evidencias: ['EV1'] },
        { id: 'A2', punto_resuelto: 'V2', uv_local: [0.9, 0.9], evidencias: ['EV2'] },
        { id: 'A3', punto_resuelto: 'V3', uv_local: [0.1, 0.1], evidencias: ['EV3'] }
      ],
      controles: [
        { id: 'C1', punto_resuelto: 'V4', uv_local: [0.5, 0.5], evidencias: ['EV4'] }
      ],
      puntos: [
        { id: 'PN_1', uv_local: [0.5, 0.9], relacionados: ['V1', 'V2', 'V3'], evidencias: ['EV5'] }
      ]
    }
  ];

  const avisoRepetido = 'Dibujo DIB_PLANTA_1: sin exactitud contrastada en al menos tres controles independientes.';
  return {
    lectura: {
      datos: {
        dibujos,
        elementos: [
          { id: 'M_ESTE', tipo: 'muro', accion: 'nuevo', vertices: ['V1', 'V2', 'PN_1'], dibujos: ['DIB_PLANTA_1'], evidencias: ['EV5'] }
        ],
        aberturas: [
          { id: 'AB_1', host: 'M_ESTE', vertices: ['V1', 'V2', 'PN_1'], dibujos: ['DIB_PLANTA_1'], evidencias: ['EV5'] }
        ],
        faltantes: ['Cota de coronación del parapeto no indicada en lámina.']
      },
      contexto: {
        geometria: {
          version_id: GEO_ORIG,
          huella_contenido: GEO_HUELLA_ORIG,
          sha256_geometria: GEO_SHA_ORIG,
          sha256_geometria_canonica: '8'.repeat(64),
          unidad_longitud: 'm',
          datos_sinteticos: true
        }
      },
      advertencias: [avisoRepetido, 'Colisión de punto propuesto: P_DUP'],
      faltantes: ['Cota de coronación del parapeto no indicada en lámina.']
    },
    digitizaciones: conHijo ? { DIB_PLANTA_1: '66'.repeat(16) } : {},
    errores_digitizacion: conHijo ? [] : [{ dibujo: 'DIB_NORTE', motivo: 'Tres anclas colineales en el plano.' }],
    incorporacion: {
      aplicado: conHijo,
      agregados: conHijo
        ? { vertices: ['PN_1'], superficies: ['M_ESTE'], aberturas: ['AB_1'], frames: ['VIG_1'] }
        : { vertices: [], superficies: [], aberturas: [], frames: [] },
      pendientes: conHijo
        ? []
        : [
            { tipo: 'digitizacion_ausente', id: 'DIB_NORTE', motivo: 'Falta registro comprobado del dibujo.' },
            { tipo: 'topologia_sin_metricas', id: 'M_ESTE', motivo: 'Entidad sin puntos/dibujos reproducibles.' }
          ],
      conflictos: conHijo
        ? []
        : [{ tipo: 'colision_id', id: 'V1', motivo: 'ID nuevo colisiona; no se sobrescribe ni mueve el existente.' }],
      advertencias: [avisoRepetido],
      faltantes: [
        { descripcion: 'Cota de coronación del parapeto no indicada en lámina.' },
        { descripcion: avisoRepetido },
        { descripcion: 'Entidad sin puntos/dibujos reproducibles.' },
        { descripcion: 'ID nuevo colisiona; no se sobrescribe ni mueve el existente.' },
        { descripcion: 'Falta definir condiciones de cimentación del edificio.' }
      ],
      validacion: { consistente: true, errores: [] }
    },
    geometria_version: conHijo ? GEO_DERIV : null,
    configuracion_preparacion: conHijo ? PREP_DERIV : null,
    sha256_configuracion: conHijo ? PREP_SHA_DERIV : null,
    frames_propuestos: conHijo ? [{ id: 'VIG_1', tipo: 'viga', puntos: ['V1', 'PN_1'] }] : [],
    faltantes: [
      { descripcion: 'Cota de coronación del parapeto no indicada en lámina.' },
      { descripcion: 'Falta definir condiciones de cimentación del edificio.' }
    ],
    aprueba_ingenieria: false,
    ejecutable_etabs: false
  };
}

function createHarness(apiHandler) {
  const document = new FakeDocument();
  const stageGeo = document.createElement('div');
  const stageGuide = document.createElement('section');
  stageGuide.className = 'stage-guide';
  stageGeo.append(stageGuide);

  const geoSelect = document.createElement('select');
  geoSelect.id = 'geoVersion';
  const optEmpty = document.createElement('option');
  optEmpty.value = '';
  optEmpty.textContent = 'Sin geometría';
  geoSelect.append(optEmpty);

  const geoJson = document.createElement('textarea');
  geoJson.id = 'geoJson';

  document.body.append(geoSelect, geoJson, stageGeo);

  const winListeners = new Map();
  const emittedEvents = [];
  const apiCalls = [];
  const timers = [];

  const windowObj = {
    crypto: crypto.webcrypto,
    URLSearchParams,
    Event: FakeEvent,
    CustomEvent: FakeCustomEvent,
    document,
    D2MEtapas: {
      containers: new Map([['geometria', stageGeo]])
    },
    addEventListener(type, fn) {
      if (!winListeners.has(type)) winListeners.set(type, []);
      winListeners.get(type).push(fn);
    },
    dispatchEvent(ev) {
      emittedEvents.push({ type: ev.type, detail: ev.detail ? JSON.parse(JSON.stringify(ev.detail)) : null });
      const fns = [...(winListeners.get(ev.type) || [])];
      for (const fn of fns) fn.call(windowObj, ev);
      return !ev.defaultPrevented;
    },
    setTimeout(fn, ms) {
      const item = { id: timers.length + 1, fn, ms, cleared: false };
      timers.push(item);
      return item.id;
    },
    clearTimeout(id) {
      const found = timers.find(t => t.id === id);
      if (found) found.cleared = true;
    }
  };

  const sandbox = {
    window: windowObj,
    document,
    crypto: crypto.webcrypto,
    URLSearchParams,
    Event: FakeEvent,
    CustomEvent: FakeCustomEvent,
    setTimeout: windowObj.setTimeout,
    clearTimeout: windowObj.clearTimeout,
    docs: null,
    geoRecord: null,
    $: id => document.getElementById(id),
    message: () => {},
    api: async (url, body) => {
      const clonedBody = body !== undefined ? JSON.parse(JSON.stringify(body)) : undefined;
      apiCalls.push({ url, method: body !== undefined ? 'POST' : 'GET', body: clonedBody });
      const payload = await apiHandler(url, clonedBody);
      return {
        ok: true,
        json: async () => JSON.parse(JSON.stringify(payload))
      };
    }
  };

  vm.createContext(sandbox);
  vm.runInContext(SCRIPT_SOURCE, sandbox, { filename: 'contornos.js' });

  function setCase(caso, expSha = SHA_EXP_1) {
    sandbox.docs = caso ? { caso, expediente_sha256: expSha, documentos: [{ id: 'LAM01', paginas: 1 }] } : null;
    sandbox.geoRecord = null;
    geoSelect.replaceChildren();
    const empty = document.createElement('option');
    empty.value = '';
    geoSelect.append(empty);
    geoJson.value = '';
    windowObj.dispatchEvent(new FakeEvent('d2m-case'));
  }

  function openGeo(versionId, record) {
    if (!Array.from(geoSelect.options).some(o => o.value === versionId)) {
      const opt = document.createElement('option');
      opt.value = versionId;
      opt.textContent = versionId;
      geoSelect.append(opt);
    }
    geoSelect.value = versionId;
    sandbox.geoRecord = record;
    geoJson.value = record ? JSON.stringify(record.datos, null, 2) : '';
    windowObj.dispatchEvent(new FakeEvent('d2m-geometry-opened'));
  }

  return {
    document,
    window: windowObj,
    sandbox,
    panel: document.getElementById('cntPanel'),
    geoSelect,
    geoJson,
    apiCalls,
    emittedEvents,
    timers,
    setCase,
    openGeo,
    el: id => document.getElementById(id)
  };
}

function assertSinJergaInternaVisible(texto) {
  const patronesProhibidos = [
    /\bd2m-[a-z0-9-]+\b/i,
    /draft2model\.[a-z0-9_.-]+/i,
    /\bsha256_configuracion\b/i,
    /\bconfirmacion_explicita\b/i,
    /\blimites_digitizacion\b/i,
    /\bcontornos_borrador\b/i,
    /\bfallido_no_reintentar\b/i,
    /\ben_ejecucion\b/i,
    /\bresiduo_ajuste_max_m\b/i,
    /\buv_local\b/i,
    /\[object Object\]/
  ];
  for (const re of patronesProhibidos) {
    assert.equal(re.test(texto), false, `Se filtró jerga interna prohibida (${re}) en texto visible: ${texto}`);
  }
}

async function runTests() {
  let passed = 0;

  // --- BLOQUE 1: Montaje, higiene DOM/seguridad, valores predeterminados y ausencia de nombres internos ---
  {
    const h = createHarness(async () => ({}));
    assert.ok(h.panel, 'El panel de contornos debe montarse en la etapa 3 (geometria).');

    for (const bad of ['innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function']) {
      assert.equal(SCRIPT_SOURCE.includes(bad), false, `No se permite usar ${bad} en contornos.js`);
    }
    assert.equal(h.panel.querySelectorAll('textarea').length, 0, 'No debe pedir JSON en textarea.');
    assert.equal(h.panel.querySelectorAll('input[type="file"]').length, 0, 'No debe pedir subida manual de archivos.');

    assert.equal(h.el('cntProveedor').value, 'openai');
    assert.equal(h.el('cntModelo').value, 'gpt-6.1-sol');
    assert.equal(h.el('cntTokens').value, '32768');

    const defaultsEsperados = {
      cntCritResiduo: '0.02',
      cntCritControl: '0.03',
      cntCritIncertidumbre: '0.08',
      cntCritLocalizacion: '0.005',
      cntCritReferencia: '0.005',
      cntCritCondicion: '50',
      cntCritEscalaMin: '0.1',
      cntCritEscalaMax: '500',
      cntCritCoordMax: '1000'
    };
    for (const [id, expected] of Object.entries(defaultsEsperados)) {
      assert.equal(h.el(id).value, expected, `Valor predeterminado incorrecto en ${id}`);
    }

    const textoEtapas = h.el('cntEtapas').textContent.toLowerCase();
    for (const etapa of ['leyendo', 'calibrando', 'comprobando geometría', 'guardando']) {
      assert.ok(textoEtapas.includes(etapa), `Falta etapa clara "${etapa}" en el indicador.`);
    }
    assertSinJergaInternaVisible(h.panel.textContent);
    passed++;
  }

  // --- BLOQUE 2: Vínculo geometría-preparación, ramas múltiples, dirty/desvínculo y preparar local sin API ---
  {
    let modoRamas = 'crear';
    const h = createHarness(async (url, body) => {
      if (url === '/api/reconstruccion/cuota') {
        return {
          openai: { configurada: true, limite: 5, usadas: 1, restantes: 4, credencial_configurada: true },
          gemini: { configurada: true, limite: 5, usadas: 0, restantes: 5, credencial_configurada: false }
        };
      }
      if (url.startsWith('/api/contornos/historial?')) return { trabajos: [] };
      if (url.startsWith('/api/configuracion/preparacion/para-geometria?')) {
        if (modoRamas === 'crear') return { versiones: [], reutilizable: null, crear: true };
        if (modoRamas === 'multiple') return { versiones: [PREP_1, PREP_2], reutilizable: null, crear: false };
        return { versiones: [PREP_1], reutilizable: PREP_1, crear: false };
      }
      if (url.startsWith('/api/configuracion/preparacion?')) {
        const ver = new URL('http://local' + url).searchParams.get('version');
        return makePreconfig(ver, ver === PREP_2 ? PREP_SHA_2 : PREP_SHA_1);
      }
      if (url === '/api/contornos/preparar') {
        return {
          id: body.clave_solicitud,
          caso: body.caso,
          expediente_sha256: body.expediente_sha256,
          estado: 'preparado',
          paso: 'Preparación local terminada; sin envío.',
          tiene_respuesta_conservada: false,
          simulado: false,
          resultado: null,
          origen_preparacion: body.configuracion_preparacion,
          origen_sha256_configuracion: body.sha256_configuracion,
          criterios_calculo: body.limites_digitizacion
        };
      }
      throw new Error('Ruta no esperada en bloque 2: ' + url);
    });

    // 2a. Sin preparación creada: no llama a /crear ni habilita preparar
    h.setCase('edificio-prueba', SHA_EXP_1);
    await flushMicrotasks();
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();

    assert.equal(h.apiCalls.some(c => c.url.includes('/crear')), false, 'No debe crear preparaciones manualmente.');
    assert.equal(h.el('cntPreparar').disabled, true);
    assert.ok(h.el('cntVinculoEstado').textContent.includes('aún no tiene una preparación'));

    // 2b. Varias ramas: muestra selector sin elegir silenciosamente ninguna
    modoRamas = 'multiple';
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();
    assert.equal(h.el('cntRamasWrap').hidden, false, 'Debe mostrar selector de ramas cuando existen varias.');
    assert.equal(h.apiCalls.some(c => c.url.startsWith('/api/configuracion/preparacion?')), false, 'No debe abrir una rama silenciosamente.');
    assert.equal(h.el('cntPreparar').disabled, true);

    // Selección explícita de rama PREP_2
    h.el('cntRamaPreparacion').value = PREP_2;
    h.el('cntRamaPreparacion').dispatchEvent(new FakeEvent('change'));
    h.el('cntAbrirRama').click();
    await flushMicrotasks();

    // Sigue bloqueado hasta confirmar expresamente criterios de calibración
    assert.equal(h.el('cntPreparar').disabled, true, 'Debe exigir confirmación expresa de criterios antes de preparar.');
    h.el('cntConfirmarCriterios').click();
    assert.equal(h.el('cntPreparar').disabled, false);

    // 2c. Estado dirty bloquea y no se pierde aunque se reabra geometría
    h.window.dispatchEvent(new FakeCustomEvent('d2m-preconfig-edited', {
      detail: { caso: 'edificio-prueba', expediente_sha256: SHA_EXP_1, id: PREP_2, sin_guardar: true }
    }));
    assert.equal(h.el('cntPreparar').disabled, true, 'Dirty debe bloquear preparación.');
    modoRamas = 'unica';
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();
    assert.equal(h.el('cntPreparar').disabled, true, 'Reconsultar geometría no debe limpiar dirty sin guardar.');

    // Al abrir preparación limpia de OTRA geometría por evento, sigue bloqueado por desvínculo
    h.window.dispatchEvent(new FakeCustomEvent('d2m-preconfig-opened', {
      detail: makePreconfig(PREP_1, PREP_SHA_1, GEO_OTRA)
    }));
    assert.equal(h.el('cntPreparar').disabled, true, 'Preparación de otra geometría debe bloquear por desvínculo.');

    // Al abrir preparación válida de LA MISMA geometría, desbloquea
    h.window.dispatchEvent(new FakeCustomEvent('d2m-preconfig-opened', {
      detail: makePreconfig(PREP_1, PREP_SHA_1, GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG)
    }));
    assert.equal(h.el('cntPreparar').disabled, false, 'Preparación válida de la geometría actual debe habilitar preparar.');

    // 2d. Preparar es local y envía las 9 claves exactas sin llamar a /ejecutar
    h.el('cntPreparar').click();
    await flushMicrotasks();
    const prepCall = h.apiCalls.find(c => c.url === '/api/contornos/preparar');
    assert.ok(prepCall, 'Debe invocar POST /api/contornos/preparar.');
    assert.deepEqual(Object.keys(prepCall.body).sort(), [
      'caso',
      'clave_solicitud',
      'configuracion_preparacion',
      'expediente_sha256',
      'limites_digitizacion',
      'max_tokens',
      'modelo',
      'proveedor',
      'sha256_configuracion'
    ]);
    assert.equal(prepCall.body.configuracion_preparacion, PREP_1);
    assert.equal(prepCall.body.sha256_configuracion, PREP_SHA_1);
    assert.equal(Object.keys(prepCall.body.limites_digitizacion).length, 9);
    assert.equal(h.apiCalls.some(c => c.url.includes('/ejecutar')), false, 'Preparar jamás debe llamar a ejecutar.');
    assertSinJergaInternaVisible(h.panel.textContent);
    passed++;
  }

  // --- BLOQUE 3: Cuota 0, invalidación al editar proveedor/modelo/criterios, 1 envío y fallo sin reintento ---
  {
    let cuotaRestante = 0;
    let estadoTrabajo = 'en_ejecucion';
    let pasoTrabajo = 'Calibrando dibujo DIB_PLANTA_1 desde las referencias geométricas; sin otra API.';

    const h = createHarness(async (url, body) => {
      if (url === '/api/reconstruccion/cuota') {
        return {
          openai: { configurada: true, limite: 5, usadas: 5 - cuotaRestante, restantes: cuotaRestante, credencial_configurada: true },
          gemini: { configurada: true, limite: 5, usadas: 0, restantes: 5, credencial_configurada: true }
        };
      }
      if (url.startsWith('/api/contornos/historial?')) return { trabajos: [JOB_1] };
      if (url.startsWith('/api/configuracion/preparacion/para-geometria?')) {
        return { versiones: [PREP_1], reutilizable: PREP_1, crear: false };
      }
      if (url.startsWith('/api/configuracion/preparacion?')) {
        return makePreconfig(PREP_1, PREP_SHA_1);
      }
      if (url === '/api/contornos/preparar') {
        return {
          id: JOB_1,
          caso: body.caso,
          expediente_sha256: body.expediente_sha256,
          estado: 'preparado',
          paso: 'Preparación local terminada; sin envío.',
          tiene_respuesta_conservada: false,
          simulado: false,
          resultado: null,
          origen_preparacion: body.configuracion_preparacion,
          origen_sha256_configuracion: body.sha256_configuracion,
          criterios_calculo: body.limites_digitizacion
        };
      }
      if (url === '/api/contornos/ejecutar') {
        assert.deepEqual(body, {
          caso: 'edificio-prueba',
          expediente_sha256: SHA_EXP_1,
          trabajo: JOB_1,
          confirmacion_explicita: true
        });
        return { id: JOB_1, estado: 'en_ejecucion', aprueba_ingenieria: false };
      }
      if (url.startsWith('/api/contornos/estado?')) {
        return {
          id: JOB_1,
          caso: 'edificio-prueba',
          expediente_sha256: SHA_EXP_1,
          estado: estadoTrabajo,
          paso: pasoTrabajo,
          tiene_respuesta_conservada: false,
          simulado: false,
          resultado: null,
          origen_preparacion: PREP_1,
          origen_sha256_configuracion: PREP_SHA_1,
          criterios_calculo: {}
        };
      }
      throw new Error('Ruta no esperada en bloque 3: ' + url);
    });

    h.setCase('edificio-prueba', SHA_EXP_1);
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();

    h.el('cntConfirmarCriterios').click();
    h.el('cntPreparar').click();
    await flushMicrotasks();

    // Con cuota 0: bloquea consentimiento y envío, y NO cambia a Gemini automáticamente
    assert.equal(h.el('cntProveedor').value, 'openai', 'No debe cambiar de proveedor sin decisión del ingeniero.');
    assert.equal(h.el('cntConfirmarEnvio').disabled, true, 'Con cuota 0 debe bloquear confirmación de envío.');
    assert.equal(h.el('cntEjecutar').disabled, true, 'Con cuota 0 debe bloquear ejecutar.');

    // Con cuota > 0 disponible: editar criterio invalida preparación y desmarca confirmaciones
    cuotaRestante = 2;
    h.setCase('edificio-prueba', SHA_EXP_1);
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();
    h.el('cntConfirmarCriterios').click();
    h.el('cntPreparar').click();
    await flushMicrotasks();
    assert.equal(h.el('cntConfirmarEnvio').disabled, false);
    h.el('cntConfirmarEnvio').click();
    assert.equal(h.el('cntEjecutar').disabled, false);

    // Editar criterio invalida preparación y ambas casillas
    h.el('cntCritResiduo').value = '0.025';
    h.el('cntCritResiduo').dispatchEvent(new FakeEvent('input'));
    assert.equal(h.el('cntConfirmarCriterios').checked, false);
    assert.equal(h.el('cntConfirmarEnvio').checked, false);
    assert.equal(h.el('cntEjecutar').disabled, true);

    // Reconfirmar criterios, preparar y editar modelo -> también invalida preparación
    h.el('cntConfirmarCriterios').click();
    h.el('cntPreparar').click();
    await flushMicrotasks();
    h.el('cntConfirmarEnvio').click();
    assert.equal(h.el('cntEjecutar').disabled, false);
    h.el('cntModelo').value = 'gpt-6-astra';
    h.el('cntModelo').dispatchEvent(new FakeEvent('input'));
    assert.equal(h.el('cntConfirmarEnvio').checked, false);
    assert.equal(h.el('cntEjecutar').disabled, true);

    // Preparar y ejecutar 1 vez -> pasa por calibrando y termina en fallido_no_reintentar sin reintentar
    h.el('cntPreparar').click();
    await flushMicrotasks();
    h.el('cntConfirmarEnvio').click();
    h.el('cntEjecutar').click();
    await flushMicrotasks();

    assert.equal(h.apiCalls.filter(c => c.url === '/api/contornos/ejecutar').length, 1);
    assert.ok(h.el('cntEtapas').querySelector('[data-etapa="calibrando"]').textContent.toLowerCase().includes('calibrando'));

    // Siguiente sondeo de 2s devuelve fallo terminal -> detiene sondeo y prohíbe reintento
    estadoTrabajo = 'fallido_no_reintentar';
    pasoTrabajo = 'El proveedor devolvió una respuesta incompleta.';
    const activeTimer = h.timers.filter(t => !t.cleared).pop();
    assert.ok(activeTimer, 'Debe programar sondeo de 2s mientras está en ejecución.');
    activeTimer.fn();
    await flushMicrotasks();

    assert.equal(h.el('cntEjecutar').disabled, true, 'Ante fallo no debe permitir reintento.');
    assert.equal(h.el('cntProveedor').value, 'openai', 'Ante fallo no debe cambiar proveedor.');
    assert.equal(h.apiCalls.filter(c => c.url === '/api/contornos/ejecutar').length, 1, 'Cero reintentos automáticos.');
    assertSinJergaInternaVisible(h.panel.textContent);
    passed++;
  }

  // --- BLOQUE 4: Publicación idempotente de hijos (2 IDs + SHA + origen), respeto de rama/dirty y recuperar sin API ---
  {
    const sampleRes = makeSampleResultado({ conHijo: true });
    const h = createHarness(async (url, body) => {
      if (url === '/api/reconstruccion/cuota') {
        return {
          openai: { configurada: true, limite: 5, usadas: 1, restantes: 4, credencial_configurada: true },
          gemini: { configurada: true, limite: 5, usadas: 0, restantes: 5, credencial_configurada: true }
        };
      }
      if (url.startsWith('/api/contornos/historial?')) return { trabajos: [JOB_1, JOB_2] };
      if (url.startsWith('/api/configuracion/preparacion/para-geometria?')) {
        const g = new URL('http://local' + url).searchParams.get('geometria');
        if (g === GEO_ORIG) return { versiones: [PREP_1], reutilizable: PREP_1, crear: false };
        if (g === GEO_DERIV) return { versiones: [PREP_DERIV], reutilizable: PREP_DERIV, crear: false };
        return { versiones: [PREP_2], reutilizable: PREP_2, crear: false };
      }
      if (url.startsWith('/api/configuracion/preparacion?')) {
        const ver = new URL('http://local' + url).searchParams.get('version');
        if (ver === PREP_DERIV) return makePreconfig(PREP_DERIV, PREP_SHA_DERIV, GEO_DERIV, GEO_HUELLA_DERIV, GEO_SHA_DERIV);
        if (ver === PREP_2) return makePreconfig(PREP_2, PREP_SHA_2, GEO_OTRA);
        return makePreconfig(PREP_1, PREP_SHA_1, GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG);
      }
      if (url === '/api/contornos/preparar') {
        return {
          id: JOB_1,
          caso: body.caso,
          expediente_sha256: body.expediente_sha256,
          estado: 'preparado',
          paso: 'Preparación local terminada; sin envío.',
          tiene_respuesta_conservada: false,
          simulado: false,
          resultado: null,
          origen_preparacion: body.configuracion_preparacion,
          origen_sha256_configuracion: body.sha256_configuracion,
          criterios_calculo: body.limites_digitizacion
        };
      }
      if (url === '/api/contornos/ejecutar') {
        return { id: JOB_1, estado: 'en_ejecucion', aprueba_ingenieria: false };
      }
      if (url.startsWith('/api/contornos/estado?')) {
        const t = new URL('http://local' + url).searchParams.get('trabajo');
        return {
          id: t,
          caso: 'edificio-prueba',
          expediente_sha256: SHA_EXP_1,
          estado: 'contornos_borrador',
          paso: 'Propuestas calibradas conservadas. Revisa las observaciones y la geometría; no se aprobó ingeniería ni ejecutó ETABS.',
          tiene_respuesta_conservada: true,
          simulado: false,
          resultado: t === JOB_2
            ? { ...sampleRes, geometria_version: '88'.repeat(16), configuracion_preparacion: '77'.repeat(16), sha256_configuracion: '6'.repeat(64) }
            : sampleRes,
          origen_preparacion: PREP_1,
          origen_sha256_configuracion: PREP_SHA_1,
          criterios_calculo: {
            residuo_ajuste_max_m: 0.02,
            error_control_max_m: 0.03,
            incertidumbre_max_m: 0.08,
            localizacion_uv: 0.005,
            referencia_m: 0.005,
            condicion_max: 50,
            escala_min_m_por_uv: 0.1,
            escala_max_m_por_uv: 500,
            coordenada_abs_max_m: 1000
          }
        };
      }
      if (url === '/api/contornos/recuperar') {
        assert.deepEqual(body, { caso: 'edificio-prueba', expediente_sha256: SHA_EXP_1, trabajo: JOB_1 });
        return {
          id: JOB_1,
          caso: 'edificio-prueba',
          expediente_sha256: SHA_EXP_1,
          estado: 'contornos_borrador',
          paso: 'Propuestas calibradas conservadas desde respuesta local.',
          tiene_respuesta_conservada: true,
          simulado: false,
          resultado: sampleRes,
          origen_preparacion: PREP_1,
          origen_sha256_configuracion: PREP_SHA_1,
          criterios_calculo: {}
        };
      }
      throw new Error('Ruta no esperada en bloque 4: ' + url);
    });

    h.setCase('edificio-prueba', SHA_EXP_1);
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();

    h.el('cntConfirmarCriterios').click();
    h.el('cntPreparar').click();
    await flushMicrotasks();
    h.el('cntConfirmarEnvio').click();
    h.el('cntEjecutar').click();
    await flushMicrotasks();

    const preEvents = h.emittedEvents.filter(e => e.type === 'd2m-preconfig-created');
    const geoEvents = h.emittedEvents.filter(e => e.type === 'd2m-geometry-created');
    assert.equal(preEvents.length, 1, 'Debe emitir d2m-preconfig-created exactamente 1 vez.');
    assert.equal(geoEvents.length, 1, 'Debe emitir d2m-geometry-created exactamente 1 vez.');
    assert.deepEqual(preEvents[0].detail, {
      caso: 'edificio-prueba',
      expediente_sha256: SHA_EXP_1,
      configuracion_preparacion: PREP_DERIV,
      sha256_configuracion: PREP_SHA_DERIV,
      preparacion_origen: PREP_1
    });
    assert.deepEqual(geoEvents[0].detail, {
      caso: 'edificio-prueba',
      expediente_sha256: SHA_EXP_1,
      geometria: GEO_DERIV,
      estado: 'borrador',
      aprobacion: null
    });

    // Consultar repetidamente y reevaluar el mismo hijo: idempotencia total (no repite eventos)
    h.el('cntHistorial').value = JOB_1;
    h.el('cntHistorial').dispatchEvent(new FakeEvent('change'));
    h.el('cntConsultar').click();
    await flushMicrotasks();
    assert.equal(h.emittedEvents.filter(e => e.type === 'd2m-preconfig-created').length, 1);
    assert.equal(h.emittedEvents.filter(e => e.type === 'd2m-geometry-created').length, 1);

    // Recuperar respuesta conservada sin llamar a ejecutar/API
    const prevEjecutarCount = h.apiCalls.filter(c => c.url === '/api/contornos/ejecutar').length;
    assert.equal(h.el('cntRecuperar').disabled, false);
    h.el('cntRecuperar').click();
    await flushMicrotasks();
    assert.equal(h.apiCalls.filter(c => c.url === '/api/contornos/recuperar').length, 1);
    assert.equal(h.apiCalls.filter(c => c.url === '/api/contornos/ejecutar').length, prevEjecutarCount, 'Recuperar NO usa API.');
    assert.equal(h.emittedEvents.filter(e => e.type === 'd2m-geometry-created').length, 1, 'Idempotencia tras recuperar mismo hijo.');

    // Consultar otro trabajo desde otra rama o con edición sin guardar: muestra resultado disponible sin cambiar selección
    h.openGeo(GEO_OTRA, makeGeoRecord(GEO_OTRA, 'a1'.repeat(32), 'b1'.repeat(32)));
    await flushMicrotasks();
    h.geoJson.value = '{"editado_sin_guardar":true}';
    h.geoJson.dispatchEvent(new FakeEvent('input'));

    h.el('cntHistorial').value = JOB_2;
    h.el('cntHistorial').dispatchEvent(new FakeEvent('change'));
    h.el('cntConsultar').click();
    await flushMicrotasks();
    assert.equal(h.emittedEvents.filter(e => e.type === 'd2m-geometry-created').length, 1, 'No debe cambiar de rama al consultar historial.');
    assert.equal(h.geoSelect.value, GEO_OTRA, 'Debe conservar la geometría seleccionada por el ingeniero.');
    assert.equal(h.geoJson.value, '{"editado_sin_guardar":true}', 'No debe borrar ediciones sin guardar.');
    assert.equal(h.el('cntAvisoDisponible').hidden, false, 'Debe avisar que existe un nuevo resultado derivado disponible.');
    assert.equal(h.el('cntAbrirDerivado').disabled, true, 'Con edición sin guardar no permite abrir derivado por accidente.');
    passed++;
  }

  // --- BLOQUE 5: Agrupación de observaciones (elemento / dibujo / causa, sin objetos crudos ni duplicados) ---
  {
    const sampleConIncidencias = makeSampleResultado({ conHijo: false });
    const h = createHarness(async url => {
      if (url === '/api/reconstruccion/cuota') return {};
      if (url.startsWith('/api/contornos/historial?')) return { trabajos: [JOB_1] };
      if (url.startsWith('/api/configuracion/preparacion/para-geometria?')) {
        return { versiones: [PREP_1], reutilizable: PREP_1, crear: false };
      }
      if (url.startsWith('/api/configuracion/preparacion?')) return makePreconfig(PREP_1, PREP_SHA_1);
      if (url.startsWith('/api/contornos/estado?')) {
        return {
          id: JOB_1,
          caso: 'edificio-prueba',
          expediente_sha256: SHA_EXP_1,
          estado: 'contornos_borrador',
          paso: 'Incorporación retenida por observaciones.',
          tiene_respuesta_conservada: true,
          simulado: false,
          resultado: sampleConIncidencias,
          origen_preparacion: PREP_1,
          origen_sha256_configuracion: PREP_SHA_1,
          criterios_calculo: {}
        };
      }
      throw new Error('Ruta no esperada en bloque 5: ' + url);
    });

    h.setCase('edificio-prueba', SHA_EXP_1);
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();
    h.el('cntHistorial').value = JOB_1;
    h.el('cntHistorial').dispatchEvent(new FakeEvent('change'));
    h.el('cntConsultar').click();
    await flushMicrotasks();

    const obsBox = h.el('cntObservaciones');
    const grupos = obsBox.querySelectorAll('.obs-grupo');
    assert.ok(grupos.length >= 3, 'Las observaciones deben organizarse en grupos temáticos.');

    const items = obsBox.querySelectorAll('li').map(li => li.textContent);
    assert.ok(items.every(t => t.includes('Elemento:') && t.includes('Dibujo:') && t.includes('Causa:')),
      'Cada observación debe mostrar claramente Elemento, Dibujo y Causa.');
    assert.ok(items.some(t => t.includes('Elemento: Muro M_ESTE') && t.includes('Dibujo: DIB_PLANTA_1')),
      'Debe vincular el elemento afectado con su dibujo de respaldo.');

    // Verificar ausencia de duplicados planos de causas repetidas en lectura/incorporación/faltantes
    const ocurrenciasParapeto = items.filter(t => t.includes('Cota de coronación del parapeto')).length;
    const ocurrenciasControles = items.filter(t => t.includes('sin exactitud contrastada en al menos tres controles')).length;
    const ocurrenciasNorte = items.filter(t => t.includes('DIB_NORTE')).length;
    assert.equal(ocurrenciasParapeto, 1, 'No debe duplicar faltantes repetidos entre lectura y geometría.');
    assert.equal(ocurrenciasControles, 1, 'No debe duplicar advertencias repetidas entre lectura e incorporación.');
    assert.equal(ocurrenciasNorte, 1, 'No debe duplicar error de calibración con digitización ausente derivada.');
    assertSinJergaInternaVisible(obsBox.textContent);
    passed++;
  }

  // --- BLOQUE 6: Puente hacia panel de digitización (quita evidencias solo en evento y protege geometría derivada) ---
  {
    const sampleRes = makeSampleResultado({ conHijo: true });
    const h = createHarness(async url => {
      if (url === '/api/reconstruccion/cuota') return {};
      if (url.startsWith('/api/contornos/historial?')) return { trabajos: [JOB_1] };
      if (url.startsWith('/api/configuracion/preparacion/para-geometria?')) {
        const g = new URL('http://local' + url).searchParams.get('geometria');
        return { versiones: [g === GEO_DERIV ? PREP_DERIV : PREP_1], reutilizable: g === GEO_DERIV ? PREP_DERIV : PREP_1, crear: false };
      }
      if (url.startsWith('/api/configuracion/preparacion?')) {
        const ver = new URL('http://local' + url).searchParams.get('version');
        return ver === PREP_DERIV
          ? makePreconfig(PREP_DERIV, PREP_SHA_DERIV, GEO_DERIV, GEO_HUELLA_DERIV, GEO_SHA_DERIV)
          : makePreconfig(PREP_1, PREP_SHA_1, GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG);
      }
      if (url.startsWith('/api/contornos/estado?')) {
        return {
          id: JOB_1,
          caso: 'edificio-prueba',
          expediente_sha256: SHA_EXP_1,
          estado: 'contornos_borrador',
          paso: 'Propuestas calibradas conservadas.',
          tiene_respuesta_conservada: true,
          simulado: false,
          resultado: sampleRes,
          origen_preparacion: PREP_1,
          origen_sha256_configuracion: PREP_SHA_1,
          criterios_calculo: {
            residuo_ajuste_max_m: 0.015,
            error_control_max_m: 0.03,
            incertidumbre_max_m: 0.08,
            localizacion_uv: 0.005,
            referencia_m: 0.005,
            condicion_max: 50,
            escala_min_m_por_uv: 0.1,
            escala_max_m_por_uv: 500,
            coordenada_abs_max_m: 1000
          }
        };
      }
      throw new Error('Ruta no esperada en bloque 6: ' + url);
    });

    h.setCase('edificio-prueba', SHA_EXP_1);
    // Usuario está situado en la geometría DERIVADA
    h.openGeo(GEO_DERIV, makeGeoRecord(GEO_DERIV, GEO_HUELLA_DERIV, GEO_SHA_DERIV));
    await flushMicrotasks();

    h.el('cntHistorial').value = JOB_1;
    h.el('cntHistorial').dispatchEvent(new FakeEvent('change'));
    h.el('cntConsultar').click();
    await flushMicrotasks();

    assert.ok(h.el('cntPuenteAviso').textContent.includes('no sustituye ni actualiza automáticamente'));
    assert.ok(h.el('cntPuenteEstado').textContent.includes('geometría derivada'));

    // Intentar enviar estando en geometría derivada: NO emite evento ni cambia geometría por sorpresa
    h.el('cntEnviarDibujo').click();
    assert.equal(h.emittedEvents.filter(e => e.type === 'd2m-digitizacion-propuesta').length, 0);
    assert.equal(h.geoSelect.value, GEO_DERIV, 'No debe cambiar la geometría abierta por sorpresa.');

    // El ingeniero abre la geometría ORIGINAL por el selector normal -> ahora sí emite propuesta limpia
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();

    h.el('cntEnviarDibujo').click();
    const digEvents = h.emittedEvents.filter(e => e.type === 'd2m-digitizacion-propuesta');
    assert.equal(digEvents.length, 1, 'Debe emitir d2m-digitizacion-propuesta al estar en la geometría original.');
    const ev = digEvents[0].detail;

    assert.equal(ev.geometria, GEO_ORIG);
    assert.equal(ev.huella_geometria, GEO_HUELLA_ORIG);
    assert.equal(ev.sha256_geometria, GEO_SHA_ORIG);
    assert.equal(ev.referencia_origen, JOB_1);
    assert.equal(ev.propuesta_id, 'DIB_PLANTA_1');
    assert.equal(ev.limites.residuo_ajuste_max_m, 0.015);

    for (const grp of ['anclas', 'controles', 'puntos']) {
      assert.ok(ev[grp].length >= 1);
      for (const row of ev[grp]) {
        assert.equal('evidencias' in row, false, `Debe quitar evidencias de ${grp} en el evento emitido.`);
      }
    }
    // Verificar que las evidencias siguen intactas en la lectura original y en el estado conservado
    assert.deepEqual(sampleRes.lectura.datos.dibujos[0].anclas[0].evidencias, ['EV1']);
    assert.deepEqual(sampleRes.lectura.datos.dibujos[0].puntos[0].evidencias, ['EV5']);
    passed++;
  }

  // --- BLOQUE 7: Concurrencia estricta (respuestas/sondeos tardíos de otro caso, otra geometría, otra versión y edición) ---
  {
    const sampleRes = makeSampleResultado({ conHijo: true });
    let pendingPreparar = null;
    let pendingEstado = null;

    const h = createHarness((url, body) => {
      if (url === '/api/reconstruccion/cuota') {
        return Promise.resolve({
          openai: { configurada: true, limite: 5, usadas: 0, restantes: 5, credencial_configurada: true },
          gemini: { configurada: true, limite: 5, usadas: 0, restantes: 5, credencial_configurada: true }
        });
      }
      if (url.startsWith('/api/contornos/historial?')) return Promise.resolve({ trabajos: [JOB_1] });
      if (url.startsWith('/api/configuracion/preparacion/para-geometria?')) {
        const g = new URL('http://local' + url).searchParams.get('geometria');
        const p = g === GEO_OTRA ? PREP_2 : PREP_1;
        return Promise.resolve({ versiones: [p], reutilizable: p, crear: false });
      }
      if (url.startsWith('/api/configuracion/preparacion?')) {
        const ver = new URL('http://local' + url).searchParams.get('version');
        const c = new URL('http://local' + url).searchParams.get('caso');
        const fp = new URL('http://local' + url).searchParams.get('expediente_sha256');
        return Promise.resolve(
          ver === PREP_2
            ? makePreconfig(PREP_2, PREP_SHA_2, GEO_OTRA, 'a2'.repeat(32), 'b2'.repeat(32), c, fp)
            : makePreconfig(PREP_1, PREP_SHA_1, GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG, c, fp)
        );
      }
      if (url === '/api/contornos/preparar') {
        if (pendingPreparar) return pendingPreparar.promise;
        return Promise.resolve({
          id: JOB_1,
          caso: body.caso,
          expediente_sha256: body.expediente_sha256,
          estado: 'preparado',
          paso: 'Preparado localmente.',
          tiene_respuesta_conservada: false,
          simulado: false,
          resultado: null,
          origen_preparacion: body.configuracion_preparacion,
          origen_sha256_configuracion: body.sha256_configuracion,
          criterios_calculo: body.limites_digitizacion
        });
      }
      if (url === '/api/contornos/ejecutar') {
        return Promise.resolve({ id: JOB_1, estado: 'en_ejecucion', aprueba_ingenieria: false });
      }
      if (url.startsWith('/api/contornos/estado?')) {
        return pendingEstado.promise;
      }
      throw new Error('Ruta no esperada en bloque 7: ' + url);
    });

    // 7a. Respuesta tardía de preparar tras editar formulario: se descarta
    h.setCase('edificio-prueba', SHA_EXP_1);
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();

    pendingPreparar = deferred();
    h.el('cntConfirmarCriterios').click();
    h.el('cntPreparar').click();
    await flushMicrotasks(2);

    // El ingeniero edita un criterio mientras preparar estaba en vuelo
    h.el('cntCritControl').value = '0.04';
    h.el('cntCritControl').dispatchEvent(new FakeEvent('input'));
    pendingPreparar.resolve({
      id: JOB_1,
      caso: 'edificio-prueba',
      expediente_sha256: SHA_EXP_1,
      estado: 'preparado',
      paso: 'Preparación vieja tardía.',
      tiene_respuesta_conservada: false,
      simulado: false,
      resultado: null,
      origen_preparacion: PREP_1,
      origen_sha256_configuracion: PREP_SHA_1,
      criterios_calculo: {}
    });
    await flushMicrotasks();
    assert.equal(h.el('cntConfirmarEnvio').disabled, true, 'Preparación tardía tras edición no debe habilitar envío.');
    pendingPreparar = null;

    // 7b. Sondeo tardío cuando el ingeniero cambió a OTRA GEOMETRÍA: no emite eventos ni cambia selección
    h.el('cntConfirmarCriterios').click();
    h.el('cntPreparar').click();
    await flushMicrotasks();
    pendingEstado = deferred();
    h.el('cntConfirmarEnvio').click();
    h.el('cntEjecutar').click();
    await flushMicrotasks();

    h.openGeo(GEO_OTRA, makeGeoRecord(GEO_OTRA, 'a2'.repeat(32), 'b2'.repeat(32)));
    await flushMicrotasks();

    pendingEstado.resolve({
      id: JOB_1,
      caso: 'edificio-prueba',
      expediente_sha256: SHA_EXP_1,
      estado: 'contornos_borrador',
      paso: 'Terminado en segundo plano.',
      tiene_respuesta_conservada: true,
      simulado: false,
      resultado: sampleRes,
      origen_preparacion: PREP_1,
      origen_sha256_configuracion: PREP_SHA_1,
      criterios_calculo: {}
    });
    await flushMicrotasks();
    assert.equal(h.emittedEvents.filter(e => e.type === 'd2m-geometry-created').length, 0,
      'Sondeo tardío de otra geometría no debe publicar cambio de geometría.');
    assert.equal(h.geoSelect.value, GEO_OTRA);
    assert.equal(h.el('cntAvisoDisponible').hidden, false);

    // 7c. Sondeo tardío tras abrir OTRA VERSIÓN DE PREPARACIÓN en la misma geometría: tampoco navega automáticamente
    h.openGeo(GEO_ORIG, makeGeoRecord(GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG));
    await flushMicrotasks();
    h.el('cntPreparar').click();
    await flushMicrotasks();
    pendingEstado = deferred();
    h.el('cntConfirmarEnvio').click();
    h.el('cntEjecutar').click();
    await flushMicrotasks();

    // Se abre otra versión de preparación distinta a PREP_1
    h.window.dispatchEvent(new FakeCustomEvent('d2m-preconfig-opened', {
      detail: makePreconfig('99'.repeat(16), '9'.repeat(64), GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG)
    }));
    pendingEstado.resolve({
      id: JOB_1,
      caso: 'edificio-prueba',
      expediente_sha256: SHA_EXP_1,
      estado: 'contornos_borrador',
      paso: 'Terminado de versión previa.',
      tiene_respuesta_conservada: true,
      simulado: false,
      resultado: sampleRes,
      origen_preparacion: PREP_1,
      origen_sha256_configuracion: PREP_SHA_1,
      criterios_calculo: {}
    });
    await flushMicrotasks();
    assert.equal(h.emittedEvents.filter(e => e.type === 'd2m-preconfig-created').length, 0,
      'Sondeo tardío de otra versión de preparación no debe sobreescribir la rama actual.');

    // 7d. Sondeo tardío de OTRO EXPEDIENTE: se descarta íntegramente sin siquiera mostrar aviso en el caso nuevo
    h.window.dispatchEvent(new FakeCustomEvent('d2m-preconfig-opened', {
      detail: makePreconfig(PREP_1, PREP_SHA_1, GEO_ORIG, GEO_HUELLA_ORIG, GEO_SHA_ORIG)
    }));
    h.el('cntPreparar').click();
    await flushMicrotasks();
    pendingEstado = deferred();
    h.el('cntConfirmarEnvio').click();
    h.el('cntEjecutar').click();
    await flushMicrotasks();

    // Cambiar de expediente antes de que resuelva el sondeo
    h.setCase('otro-expediente', SHA_EXP_2);
    await flushMicrotasks();
    const eventsBeforeLate = h.emittedEvents.length;

    pendingEstado.resolve({
      id: JOB_1,
      caso: 'edificio-prueba',
      expediente_sha256: SHA_EXP_1,
      estado: 'contornos_borrador',
      paso: 'Respuesta de otro caso.',
      tiene_respuesta_conservada: true,
      simulado: false,
      resultado: sampleRes,
      origen_preparacion: PREP_1,
      origen_sha256_configuracion: PREP_SHA_1,
      criterios_calculo: {}
    });
    await flushMicrotasks();

    assert.equal(h.emittedEvents.length, eventsBeforeLate, 'No debe emitir ningún evento para un caso anterior.');
    assert.equal(h.el('cntAvisoDisponible').hidden, true, 'No debe contaminar otro expediente con avisos del caso previo.');
    passed++;
  }

  console.log(`OK: ${passed}/7 bloques DOM/Node superados en contornos_359_frontend.cjs`);
}

runTests().catch(err => {
  console.error(err);
  process.exit(1);
});
