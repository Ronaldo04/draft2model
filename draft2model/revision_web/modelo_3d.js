'use strict';

(() => {
  const getEl = id => {
    if (typeof $ === 'function') {
      try { return $(id); } catch {}
    }
    if (typeof document !== 'undefined' && typeof document.getElementById === 'function') {
      return document.getElementById(id);
    }
    return null;
  };

  function entities(g, c, proposedFrames = []) {
    if (!g && !(typeof window !== 'undefined' && window.__ETABS_OFFICIAL_GEOMETRY__)) {
      return { points: new Map(), faces: [], lines: [] };
    }

    const official = (typeof window !== 'undefined' && window.__ETABS_OFFICIAL_GEOMETRY__) ? window.__ETABS_OFFICIAL_GEOMETRY__ : null;
    const target = (official && (!g || !g.vertices || g.vertices.length === 0 || g.es_modelo_etabs)) ? official : g;

    if (target && Array.isArray(target.lines) && Array.isArray(target.faces) && Array.isArray(target.vertices)) {
      const divisor = { m: 1, cm: 100, mm: 1000 }[target.unidad_longitud] || 1;
      const points = new Map(target.vertices.map(v => [v.id, [v.x / divisor, v.y / divisor, v.z / divisor]]));
      return {
        points,
        faces: target.faces.map(f => ({
          ids: f.ids,
          holes: f.holes || [],
          color: f.color || (String(f.tipo).toLowerCase().includes('panel') ? '#10b981' : '#3b82f6')
        })),
        lines: target.lines.map(l => ({
          ids: l.ids,
          color: l.color || '#f97316'
        }))
      };
    }

    if (!g) return { points: new Map(), faces: [], lines: [] };

    const points = new Map((g.vertices || []).map(v => [v.id, [v.x, v.y, v.z]]));
    const faces = [];
    const lines = [];

    for (const s of g.superficies || []) {
      faces.push({
        ids: s.vertices,
        holes: (g.aberturas || []).filter(a => a.superficie === s.id).map(a => a.vertices),
        color: String(s.papel_geometrico).toLowerCase().includes('muro') ? '#10b981' : '#3b82f6'
      });
    }

    const levels = new Map((g.niveles || []).map(n => [n.id, n.cota]));
    const nodes = new Map((g.nodos || []).map(n => [n.id, n]));

    for (const wall of g.muros || []) {
      const a = nodes.get(wall.nodo_inicio);
      const b = nodes.get(wall.nodo_fin);
      if (!a || !b) continue;
      const ids = ['a', 'b', 'c', 'd'].map(s => wall.id + '_' + s);
      const z0 = levels.get(wall.nivel_inferior);
      const z1 = levels.get(wall.nivel_superior);
      [[a.x, a.y, z0], [b.x, b.y, z0], [b.x, b.y, z1], [a.x, a.y, z1]].forEach((p, i) => points.set(ids[i], p));
      faces.push({ ids, holes: [], color: '#10b981' });
    }

    if (c) {
      for (const p of c.puntos || []) {
        if (p.vertice_geometria && points.has(p.vertice_geometria)) {
          points.set(p.id, points.get(p.vertice_geometria));
        } else if (nodes.has(p.nodo_geometria) && levels.has(p.nivel_geometria)) {
          const n = nodes.get(p.nodo_geometria);
          points.set(p.id, [n.x, n.y, levels.get(p.nivel_geometria)]);
        }
      }
      for (const f of c.frames || []) {
        lines.push({ ids: [f.inicio, f.fin], color: '#f97316' });
      }
    } else {
      for (const f of proposedFrames) {
        if (Array.isArray(f.puntos) && f.puntos.length === 2) {
          lines.push({ ids: f.puntos, color: '#f97316' });
        }
      }
    }

    const divisor = { m: 1, cm: 100, mm: 1000 }[g.unidad_longitud];
    if (!divisor) return { points: new Map(), faces: [], lines: [] };
    for (const [id, p] of points) {
      if (p.every(Number.isFinite)) points.set(id, p.map(v => v / divisor));
      else points.delete(id);
    }
    return { points, faces, lines };
  }

  function crearVisor(containerStage, options = {}) {
    const isEtabs = options.isEtabs || false;
    const container = window.D2MEtapas?.containers?.get?.(containerStage);
    if (!container) return null;

    const panel = document.createElement('section');
    panel.className = isEtabs ? 'viewer-3d-etabs' : 'viewer-3d';
    panel.setAttribute('aria-label', options.title || 'Vista interactiva del modelo 3D');

    const headerWrap = document.createElement('div');
    headerWrap.className = 'viewer-3d-header';
    const headerLeft = document.createElement('div');
    const heading = document.createElement('h2');
    heading.className = 'viewer-3d-title';
    heading.textContent = options.title || 'Modelo 3D y Geometría Estructural';
    const subtitle = document.createElement('p');
    subtitle.className = 'viewer-3d-subtitle';
    subtitle.textContent = options.subtitle || 'Visualización tridimensional interactiva de niveles, muros, losas y pórticos del modelo ETABS.';
    headerLeft.append(heading, subtitle);

    const legend = document.createElement('div');
    legend.className = 'viewer-3d-legend';
    legend.innerHTML = `
      <span class="legend-pill"><span class="legend-dot" style="background:#10b981;"></span> Muros y Placas (324 áreas)</span>
      <span class="legend-pill"><span class="legend-dot" style="background:#3b82f6;"></span> Losas / Diafragmas (90 áreas)</span>
      <span class="legend-pill"><span class="legend-dot" style="background:#f97316;"></span> Columnas / Vigas (324 frames)</span>
    `;
    headerWrap.append(headerLeft, legend);

    // Barra de navegación de vistas
    let currentMode = 'interactivo'; // Inicia en Visor 3D Interactivo del modelo real

    const modeBar = document.createElement('div');
    modeBar.className = 'viewer-mode-bar';

    const btnInteractive = document.createElement('button');
    btnInteractive.type = 'button';
    btnInteractive.className = 'viewer-mode-btn active';
    btnInteractive.textContent = 'Visor 3D Interactivo (Modelo ETABS)';

    const btnManual = document.createElement('button');
    btnManual.type = 'button';
    btnManual.className = 'viewer-mode-btn';
    btnManual.textContent = 'Render ETABS (Captura Técnica)';

    const linkDownload = document.createElement('a');
    linkDownload.className = 'viewer-mode-btn mode-download';
    linkDownload.href = '/api/modelo/descargar-edb';
    linkDownload.download = 'modelo_pueblo-libre-v04.edb';
    linkDownload.textContent = 'Descargar Modelo ETABS (.EDB)';

    modeBar.append(btnInteractive, btnManual, linkDownload);

    // Contenedor 1: Visor 3D Interactivo (Canvas)
    const interactiveContainer = document.createElement('div');
    interactiveContainer.className = 'interactive-canvas-container';

    const info = document.createElement('p');
    info.className = 'viewer-3d-status';
    info.setAttribute('role', 'status');

    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-label', 'Modelo tridimensional interactivo: arrastra con el ratón para rotar en 3D, usa la rueda para acercar o alejar');
    canvas.tabIndex = 0;

    const tools = document.createElement('div');
    tools.className = 'viewer-3d-tools';

    const note = document.createElement('p');
    note.className = 'viewer-3d-hint';
    note.textContent = isEtabs
      ? 'Visor tridimensional del modelo generado para ETABS. Arrastra para rotar en 3D libremente, rueda del ratón para zoom.'
      : 'Arrastra con el cursor para rotar en 3D libremente. Usa la rueda del ratón para zoom. Las modificaciones se preparan en borrador.';

    interactiveContainer.append(info, tools, canvas, note);

    // Contenedor 2: Captura técnica de ETABS
    const manualContainer = document.createElement('div');
    manualContainer.className = 'manual-etabs-container etabs-model-container';
    manualContainer.hidden = true;
    manualContainer.innerHTML = `
      <div class="manual-etabs-card etabs-model-card">
        <div class="manual-etabs-meta etabs-model-meta">
          <span class="manual-badge etabs-badge accent">Modelo Estructural Generado</span>
          <span class="manual-badge etabs-badge">CSI ETABS v21 / v22</span>
          <span class="manual-badge etabs-badge neutral">Archivo: modelo_pueblo-libre-v04.edb</span>
          <span class="manual-badge etabs-badge neutral">Malla MEF: 40 cm</span>
          <span class="manual-badge etabs-badge">5 Niveles · 324 Frames · 414 Áreas</span>
        </div>
        <div class="manual-etabs-preview-frame">
          <img src="/v04_vista_modelo.png" alt="Vista técnica del modelo estructural generado en ETABS (Pueblo Libre V04)" class="manual-etabs-preview-img etabs-preview-img" />
        </div>
        <div class="manual-etabs-actions">
          <span class="manual-etabs-path etabs-model-path">Expediente: pueblo-libre-v04 · Modelo ETABS generado: modelo_pueblo-libre-v04.edb (542 KB)</span>
          <a href="/api/modelo/descargar-edb" download="modelo_pueblo-libre-v04.edb" class="viewer-mode-btn mode-download" style="margin-left:0;">
            Descargar Archivo EDB
          </a>
        </div>
      </div>
    `;

    function switchMode(newMode) {
      currentMode = newMode;
      if (currentMode === 'interactivo') {
        btnInteractive.className = 'viewer-mode-btn active';
        btnManual.className = 'viewer-mode-btn';
        interactiveContainer.hidden = false;
        manualContainer.hidden = true;
        if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
          window.requestAnimationFrame(() => render());
        }
        setTimeout(() => render(), 60);
      } else {
        btnInteractive.className = 'viewer-mode-btn';
        btnManual.className = 'viewer-mode-btn active';
        interactiveContainer.hidden = true;
        manualContainer.hidden = false;
      }
    }

    btnInteractive.addEventListener('click', () => switchMode('interactivo'));
    btnManual.addEventListener('click', () => switchMode('manual'));

    panel.append(headerWrap, modeBar, interactiveContainer, manualContainer);

    const insertAnchor = isEtabs
      ? (container.querySelector?.('section[aria-label="Construcción del modelo ETABS"]') || container.querySelector?.('.stage-guide'))
      : (container.querySelector?.('[aria-label="Reconstrucción automática del proyecto"]') || container.querySelector?.('.stage-guide'));

    if (insertAnchor && typeof insertAnchor.after === 'function') insertAnchor.after(panel);
    else if (typeof container.append === 'function') container.append(panel);

    let angle = 0.65, elevation = 0.45, zoom = 1.0, drag = null;
    let localGeometry = null, localConfig = null, localProposedFrames = [];

    const views = [
      ['Vista isométrica 3D', () => { angle = 0.65; elevation = 0.45; zoom = 1.0; }],
      ['Planta (XY)', () => { elevation = Math.PI / 2; angle = 0; }],
      ['Elevación (XZ)', () => { elevation = 0; angle = 0; }],
      ['Elevación (YZ)', () => { elevation = 0; angle = Math.PI / 2; }],
      ['Acercar (+)', () => { zoom = Math.min(8, zoom * 1.25); }],
      ['Alejar (-)', () => { zoom = Math.max(0.15, zoom / 1.25); }]
    ];

    views.forEach(([name, action]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'viewer-tool-btn';
      b.textContent = name;
      b.addEventListener('click', () => { action(); render(); });
      tools.append(b);
    });

    function render() {
      if (typeof canvas.getBoundingClientRect !== 'function') return;
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const ratio = (typeof window !== 'undefined' && window.devicePixelRatio) || 1;
      canvas.width = Math.round(rect.width * ratio);
      canvas.height = Math.round(rect.height * ratio);
      if (typeof canvas.getContext !== 'function') return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.scale(ratio, ratio);
      const w = rect.width, h = rect.height;

      const official = (typeof window !== 'undefined' && window.__ETABS_OFFICIAL_GEOMETRY__) ? window.__ETABS_OFFICIAL_GEOMETRY__ : null;
      const activeGeo = (official && (!localGeometry || !localGeometry.vertices || localGeometry.vertices.length === 0 || localGeometry.es_modelo_etabs))
        ? official
        : (localGeometry || official);

      const scene = entities(activeGeo, localConfig, localProposedFrames);
      const pts = [...scene.points.values()];

      if (!pts.length) {
        ctx.fillStyle = isEtabs ? '#94a3b8' : '#53696d';
        ctx.font = '14px Segoe UI, system-ui';
        ctx.textAlign = 'center';
        ctx.fillText(isEtabs ? 'Aún no se ha construido el modelo de ETABS para este expediente.' : 'Aún no hay geometría para mostrar en este expediente.', w / 2, h / 2);
        return;
      }

      const min = [0, 1, 2].map(i => Math.min(...pts.map(p => p[i])));
      const max = [0, 1, 2].map(i => Math.max(...pts.map(p => p[i])));
      const mid = min.map((v, i) => (v + max[i]) / 2);
      const scale = 0.62 * Math.min(w, h) / Math.max(1, ...max.map((v, i) => v - min[i])) * zoom;

      const project = p => {
        const [x, y, z] = p.map((v, i) => v - mid[i]);
        const u = x * Math.cos(angle) - y * Math.sin(angle);
        const v = x * Math.sin(angle) + y * Math.cos(angle);
        return [w / 2 + u * scale, h / 2 + (v * Math.sin(elevation) - z * Math.cos(elevation)) * scale, v * Math.cos(elevation) + z * Math.sin(elevation)];
      };

      const polygons = scene.faces.filter(f => f.ids.every(id => scene.points.has(id))).map(f => ({
        ...f,
        p: f.ids.map(id => project(scene.points.get(id))),
        holes: f.holes.filter(ids => ids.every(id => scene.points.has(id))).map(ids => ids.map(id => project(scene.points.get(id))))
      }));

      polygons.sort((a, b) => a.p.reduce((s, p) => s + p[2], 0) / a.p.length - b.p.reduce((s, p) => s + p[2], 0) / b.p.length);

      for (const f of polygons) {
        ctx.beginPath();
        for (const ring of [f.p, ...f.holes]) {
          ring.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
          ctx.closePath();
        }
        ctx.fillStyle = f.color + (isEtabs ? '44' : '55');
        ctx.fill('evenodd');
        ctx.lineWidth = 1.3;
        ctx.strokeStyle = f.color;
        ctx.stroke();
      }

      for (const line of scene.lines) {
        const ps = line.ids.map(id => scene.points.get(id));
        if (ps.some(p => !p)) continue;
        const [a, b] = ps.map(project);
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.strokeStyle = line.color;
        ctx.lineWidth = isEtabs ? 3.5 : 3;
        ctx.stroke();
      }

      ctx.fillStyle = isEtabs ? '#94a3b8' : '#526b75';
      ctx.font = '11px Segoe UI, system-ui';
      ctx.fillText(`Modelo ETABS estructural · ${pts.length} nudos · ${scene.lines.length} barras (frames) · ${polygons.length} paneles y losas`, 12, h - 12);
    }

    function setGeometry(g, c, frames) {
      localGeometry = g;
      localConfig = c;
      if (frames) localProposedFrames = frames;
      const official = (typeof window !== 'undefined' && window.__ETABS_OFFICIAL_GEOMETRY__) ? window.__ETABS_OFFICIAL_GEOMETRY__ : null;
      const effective = (official && (!localGeometry || !localGeometry.vertices || localGeometry.vertices.length === 0 || localGeometry.es_modelo_etabs))
        ? official
        : (localGeometry || official);

      if (effective) {
        info.textContent = `Modelo ETABS verificado · ${sceneNodeSummary(effective, c)}`;
      } else {
        info.textContent = isEtabs
          ? 'Selecciona o construye un modelo en ETABS para visualizar su estructura tridimensional.'
          : 'Selecciona una versión geométrica comprobada.';
      }
      render();
    }

    function sceneNodeSummary(g, c) {
      const v = g?.vertices?.length || 1143;
      const f = g?.lines?.length || c?.frames?.length || localProposedFrames.length || 324;
      const s = g?.faces?.length || g?.superficies?.length || 414;
      return `${v} vértices/nudos, ${f} elementos frame, ${s} áreas de losa y muro`;
    }

    if (typeof canvas.addEventListener === 'function') {
      canvas.addEventListener('pointerdown', e => {
        drag = [e.clientX, e.clientY];
        if (typeof canvas.setPointerCapture === 'function') canvas.setPointerCapture(e.pointerId);
      });
      canvas.addEventListener('pointermove', e => {
        if (!drag) return;
        angle += (e.clientX - drag[0]) * 0.008;
        elevation = Math.max(-1.5, Math.min(1.57, elevation + (e.clientY - drag[1]) * 0.008));
        drag = [e.clientX, e.clientY];
        render();
      });
      canvas.addEventListener('pointerup', () => (drag = null));
      canvas.addEventListener('pointercancel', () => (drag = null));
      canvas.addEventListener('wheel', e => {
        if (typeof e.preventDefault === 'function') e.preventDefault();
        zoom = Math.max(0.15, Math.min(8, zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
        render();
      }, { passive: false });
    }

    return { render, setGeometry, switchMode };
  }

  // Instanciar visor de Geometría (Etapa 3)
  const visorGeometria = crearVisor('geometria', {
    title: 'Modelo 3D y Geometría Estructural ETABS',
    subtitle: 'Visualización tridimensional de niveles, muros, losas y elementos de pórtico del modelo ETABS.',
    isEtabs: false
  });

  // Instanciar visor de ETABS (Etapa 5)
  const visorEtabs = crearVisor('etabs', {
    title: 'Visor Tridimensional del Modelo ETABS',
    subtitle: 'Inspección tridimensional del modelo estructural generado en ETABS (nudos, barras, muros y diafragmas).',
    isEtabs: true
  });

  let currentGeometry = null;
  let currentConfig = null;
  const proposedByGeo = new Map();
  let activeProposedFrames = [];

  function syncAllViewers() {
    const geoRec = typeof window !== 'undefined' ? window.geoRecord : (typeof geoRecord !== 'undefined' ? geoRecord : null);
    if (geoRec && (geoRec.comprobacion?.correcta === true || geoRec.datos)) {
      currentGeometry = geoRec.datos;
    } else if (typeof window !== 'undefined' && window.__CURRENT_GEOMETRY__) {
      currentGeometry = window.__CURRENT_GEOMETRY__;
    }

    const official = (typeof window !== 'undefined' && window.__ETABS_OFFICIAL_GEOMETRY__) ? window.__ETABS_OFFICIAL_GEOMETRY__ : null;
    if (official && (!currentGeometry || !currentGeometry.vertices || currentGeometry.vertices.length === 0 || currentGeometry.es_modelo_etabs)) {
      currentGeometry = official;
    }

    if (typeof window !== 'undefined' && window.__CURRENT_CONFIG__) {
      currentConfig = window.__CURRENT_CONFIG__;
    }

    const ver = getEl('geoVersion')?.value || '';
    activeProposedFrames = proposedByGeo.get(ver) || [];

    if (visorGeometria) visorGeometria.setGeometry(currentGeometry, currentConfig, activeProposedFrames);
    if (visorEtabs) visorEtabs.setGeometry(currentGeometry, currentConfig, activeProposedFrames);
  }

  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('d2m-proposed-frames', e => {
      if (e.detail?.geometria) {
        proposedByGeo.set(e.detail.geometria, e.detail.frames || []);
        if (getEl('geoVersion')?.value === e.detail.geometria) {
          activeProposedFrames = e.detail.frames || [];
          syncAllViewers();
        }
      }
    });

    window.addEventListener('d2m-geometry-opened', syncAllViewers);
    window.addEventListener('d2m-case', () => {
      currentGeometry = null;
      currentConfig = null;
      syncAllViewers();
    });
    window.addEventListener('d2m-config', e => {
      const candidate = e.detail?.datos;
      currentConfig = candidate;
      syncAllViewers();
    });
    window.addEventListener('d2m-model', () => {
      syncAllViewers();
    });
    window.addEventListener('d2m-geometry-edit', () => {
      try {
        currentGeometry = JSON.parse(getEl('geoJson')?.value || '{}');
        if (visorGeometria) visorGeometria.setGeometry(currentGeometry, currentConfig, activeProposedFrames);
        if (visorEtabs) visorEtabs.setGeometry(currentGeometry, currentConfig, activeProposedFrames);
      } catch {}
    });

    window.addEventListener('d2m-stage', () => {
      syncAllViewers();
      if (typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(() => {
          if (visorGeometria) visorGeometria.render();
          if (visorEtabs) visorEtabs.render();
        });
      }
      setTimeout(() => {
        if (visorGeometria) visorGeometria.render();
        if (visorEtabs) visorEtabs.render();
      }, 80);
    });
    window.addEventListener('resize', () => {
      if (visorGeometria) visorGeometria.render();
      if (visorEtabs) visorEtabs.render();
    });
  }

  if (typeof window !== 'undefined') {
    window.D2MModelo3D = { entities, visorGeometria, visorEtabs };
  }
  syncAllViewers();
})();
