// herramienta_e030.js - Automatización Sísmica según Norma E.030-2026 (RM 183-2026-VIVIENDA)
// Sin emojis. Todo renderizado en LaTeX mediante KaTeX.
// Integra Análisis Sísmico Estático, Dinámico y Exportación Espectral para ETABS.

(function () {
  'use strict';

  const TABLA1_Z = { 4: 0.45, 3: 0.35, 2: 0.25, 1: 0.10 };
  const TABLA4_S = {
    4: { S0: 0.80, S1: 1.00, S2: [1.00, 1.10], S3: [1.10, 1.20] },
    3: { S0: 0.80, S1: 1.00, S2: [1.00, 1.15], S3: [1.15, 1.20], S4: 1.30 },
    2: { S0: 0.80, S1: 1.00, S2: [1.00, 1.30], S3: [1.30, 1.40], S4: 1.70 },
    1: { S0: 0.80, S1: 1.00, S2: [1.00, 1.30], S3: [1.30, 1.60], S4: 2.40 }
  };
  const TABLA5_TP = { S0: 0.3, S1: 0.4, S2: [0.4, 0.6], S3: [0.6, 0.9], S4: 1.2 };
  const TABLA5_TL = { S0: 3.0, S1: 2.5, S2: [2.5, 2.0], S3: [2.0, 1.6], S4: 1.6 };
  const SIN_VS30 = { S2: [0.6, 2.0], S3: [0.9, 1.6] };
  const VS30_INTERVALO = { S2: [350.0, 550.0], S3: [200.0, 350.0] };

  const TABLA7_U = { A1: 1.5, A2: 1.5, B: 1.3, C: 1.0, D: 1.0 };
  const TABLA10_R0 = {
    concreto_porticos: 8.0,
    concreto_dual: 7.0,
    concreto_muros_estructurales: 6.0,
    muros_ductilidad_limitada: 4.0,
    albanileria_armada_o_confinada: 3.0,
    acero_smf: 8.0,
    madera: 7.0
  };
  const TABLA11_CT = {
    concreto_porticos: 35,
    concreto_dual: 45,
    concreto_muros_estructurales: 60,
    muros_ductilidad_limitada: 60,
    albanileria_armada_o_confinada: 60,
    acero_smf: 35,
    madera: 45
  };
  const TABLA14_DERIVA = {
    concreto_porticos: 0.007,
    concreto_dual: 0.007,
    concreto_muros_estructurales: 0.007,
    muros_ductilidad_limitada: 0.005,
    albanileria_armada_o_confinada: 0.005,
    acero_smf: 0.010,
    madera: 0.010
  };

  const DEPARTAMENTOS_DEFAULT = [
    "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA", "CALLAO", "CUSCO",
    "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN", "LA LIBERTAD", "LAMBAYEQUE", "LIMA", "LORETO",
    "MADRE DE DIOS", "MOQUEGUA", "PASCO", "PIURA", "PUNO", "SAN MARTIN", "TACNA", "TUMBES", "UCAYALI"
  ];

  let estadoActual = {
    departamento: 'LIMA',
    provincia: 'LIMA',
    distrito: 'PUEBLO LIBRE',
    zona: 4,
    Z: 0.45,
    perfil: 'S1',
    vs30: null,
    S: 1.00,
    TP: 0.40,
    TL: 2.50,
    metodoSuelo: 'Valor tabulado',
    categoria: 'C',
    U: 1.00,
    alfa_cv: 0.25,
    sistema: 'concreto_muros_estructurales',
    R0: 6.0,
    Ia: 1.0,
    Ip: 1.0,
    R: 6.0,
    hn_m: 12.0,
    CT: 60,
    T: 0.200,
    T_manual: false,
    C: 2.50,
    k: 1.00,
    C_R: 0.4167,
    cumpleCRMinimo: true,
    peso_CM: 4681.8,
    peso_CV: 995.4,
    peso_total_P: 4930.65,
    peso_manual: false,
    coef_sismico: 0.1875,
    V_estatico: 924.50,
    V_estatico_manual: false,
    V_dinamico: 1387.53,
    tipoEspectro: 'C',
    ortogonal30: true
  };

  function obtenerTokenSesion() {
    if (typeof window !== 'undefined' && window.__SESION__) return window.__SESION__;
    if (typeof document !== 'undefined') {
      const meta = document.querySelector('meta[name="revision-session"]') || document.querySelector('meta[name="csrf-token"]');
      if (meta) return meta.getAttribute('content') || meta.content || '';
    }
    return '';
  }

  async function apiGet(ruta) {
    const sep = ruta.includes('?') ? '&' : '?';
    const token = obtenerTokenSesion();
    const headers = { 'Host': window.location.host };
    if (token) headers['X-Revision-Session'] = token;
    const res = await fetch(ruta + (token ? `${sep}token=${encodeURIComponent(token)}` : ''), { credentials: 'same-origin', headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  }

  function calcularParametrosSuelo(zona, perfil, vs30) {
    const s_data = TABLA4_S[zona] ? TABLA4_S[zona][perfil] : 1.0;
    if (s_data === undefined) {
      return { S: 1.0, TP: 0.4, TL: 2.5, metodo: 'Estudio de sitio específico requerido (S4 en Zona 4)' };
    }
    const tp_data = TABLA5_TP[perfil];
    const tl_data = TABLA5_TL[perfil];

    if (!Array.isArray(s_data)) {
      return { S: s_data, TP: tp_data, TL: tl_data, metodo: 'Valor tabulado según perfil' };
    }

    if (vs30 === null || isNaN(vs30) || vs30 <= 0) {
      const tp_tl = SIN_VS30[perfil];
      return {
        S: Math.max(...s_data),
        TP: tp_tl[0],
        TL: tp_tl[1],
        metodo: 'Regla conservadora sin Vs,30 (Tablas 4 y 5: valor superior del intervalo)'
      };
    }

    const intervalo = VS30_INTERVALO[perfil];
    if (intervalo && vs30 >= intervalo[0] && vs30 < intervalo[1]) {
      const t = (intervalo[1] - vs30) / (intervalo[1] - intervalo[0]);
      const s_calc = s_data[0] + t * (s_data[1] - s_data[0]);
      const tp_calc = tp_data[0] + t * (tp_data[1] - tp_data[0]);
      const tl_calc = tl_data[0] + t * (tl_data[1] - tl_data[0]);
      return {
        S: Math.round(s_calc * 1000) / 1000,
        TP: Math.round(tp_calc * 1000) / 1000,
        TL: Math.round(tl_calc * 1000) / 1000,
        metodo: `Interpolación lineal con Vs,30 = ${vs30.toFixed(1)} m/s (E.030 Tabla 3)`
      };
    }

    const tp_tl = SIN_VS30[perfil];
    return {
      S: Math.max(...s_data),
      TP: tp_tl[0],
      TL: tp_tl[1],
      metodo: 'Vs,30 fuera de intervalo; rige cota conservadora superior'
    };
  }

  function calcularC(T, TP, TL) {
    if (T <= 0.2 * TP) {
      return 1.0 + 7.5 * (T / TP);
    } else if (T <= TP) {
      return 2.50;
    } else if (T < TL) {
      return 2.50 * (TP / T);
    } else {
      return 2.50 * (TP * TL / (T * T));
    }
  }

  function calcularK(T) {
    return T <= 0.5 ? 1.0 : Math.min(0.75 + 0.5 * T, 2.0);
  }

  function actualizarCalculos() {
    // 1. Suelo
    const suelo = calcularParametrosSuelo(estadoActual.zona, estadoActual.perfil, estadoActual.vs30);
    estadoActual.S = suelo.S;
    estadoActual.TP = suelo.TP;
    estadoActual.TL = suelo.TL;
    estadoActual.metodoSuelo = suelo.metodo;

    // 2. Uso y porcentaje de carga viva (E.030 Art. 15 y 33)
    estadoActual.U = TABLA7_U[estadoActual.categoria] || 1.0;
    estadoActual.alfa_cv = (estadoActual.categoria === 'A1' || estadoActual.categoria === 'A2' || estadoActual.categoria === 'B') ? 0.50 : 0.25;

    // 3. Sistema y Coeficiente R
    estadoActual.R0 = TABLA10_R0[estadoActual.sistema] || 8.0;
    estadoActual.R = Math.round(estadoActual.R0 * estadoActual.Ia * estadoActual.Ip * 1000) / 1000;

    // 4. Coeficiente CT y Periodo Fundamental T (Art. 34.1)
    estadoActual.CT = TABLA11_CT[estadoActual.sistema] || 35;
    if (!estadoActual.T_manual) {
      estadoActual.T = Math.round((estadoActual.hn_m / estadoActual.CT) * 1000) / 1000;
    }

    // 5. Factor de amplificación sísmica C y exponente k (Art. 14 y 35)
    estadoActual.C = Math.round(calcularC(estadoActual.T, estadoActual.TP, estadoActual.TL) * 1000) / 1000;
    estadoActual.k = Math.round(calcularK(estadoActual.T) * 1000) / 1000;
    estadoActual.C_R = Math.round((estadoActual.C / estadoActual.R) * 10000) / 10000;
    estadoActual.cumpleCRMinimo = estadoActual.C_R >= 0.11;

    // 6. Peso sísmico efectivo P (Art. 33)
    if (!estadoActual.peso_manual) {
      estadoActual.peso_total_P = Math.round((estadoActual.peso_CM + estadoActual.alfa_cv * estadoActual.peso_CV) * 100) / 100;
    }

    // 7. Coeficiente basal y Cortante Estático en la base Vest (Art. 34)
    const C_calc = estadoActual.cumpleCRMinimo ? estadoActual.C : (0.11 * estadoActual.R);
    estadoActual.coef_sismico = Math.round(((estadoActual.Z * estadoActual.U * C_calc * estadoActual.S) / estadoActual.R) * 10000) / 10000;

    if (!estadoActual.V_estatico_manual) {
      estadoActual.V_estatico = Math.round(estadoActual.coef_sismico * estadoActual.peso_total_P * 100) / 100;
    }

    // 8. Sincronizar UI
    renderizarParametrosUI();
  }

  function renderizarParametrosUI() {
    if (typeof document === 'undefined') return;

    // Resumen de parámetros
    const elZ = document.getElementById('e030ResumenZ');
    if (elZ) elZ.textContent = `$Z = ${estadoActual.Z.toFixed(2)}$ (Zona ${estadoActual.zona}: ${estadoActual.distrito})`;

    const elS = document.getElementById('e030ResumenS');
    if (elS) elS.textContent = `$S = ${estadoActual.S.toFixed(2)}, T_P = ${estadoActual.TP.toFixed(2)}\\text{ s}, T_L = ${estadoActual.TL.toFixed(2)}\\text{ s}$`;

    const elMetodoSuelo = document.getElementById('e030MetodoSuelo');
    if (elMetodoSuelo) elMetodoSuelo.textContent = estadoActual.metodoSuelo;

    const elU = document.getElementById('e030ResumenU');
    if (elU) elU.textContent = `$U = ${estadoActual.U.toFixed(2)}$ (Cat. ${estadoActual.categoria}, $\\alpha_{CV} = ${(estadoActual.alfa_cv * 100).toFixed(0)}\\%$)`;

    const elR = document.getElementById('e030ResumenR');
    if (elR) elR.textContent = `$R_0 = ${estadoActual.R0.toFixed(1)}, I_a = ${estadoActual.Ia.toFixed(2)}, I_p = ${estadoActual.Ip.toFixed(2)} \\Rightarrow R = ${estadoActual.R.toFixed(2)}$`;

    const elC = document.getElementById('e030ResumenC');
    if (elC) elC.textContent = `$T = ${estadoActual.T.toFixed(3)}\\text{ s} \\Rightarrow C = ${estadoActual.C.toFixed(3)}, k = ${estadoActual.k.toFixed(3)}$`;

    const elCR = document.getElementById('e030ResumenCR');
    if (elCR) {
      const minSymbol = estadoActual.cumpleCRMinimo ? '\\ge' : '<';
      const obs = estadoActual.cumpleCRMinimo ? 'Cumple Art. 34.2' : 'Aplica corte mínimo C/R = 0.11';
      elCR.textContent = `$\\frac{C}{R} = ${estadoActual.C_R.toFixed(4)} ${minSymbol} 0.11$ (${obs})`;
    }

    // Campos del cálculo estático
    const tonfP = (estadoActual.peso_total_P / 9.80665).toFixed(2);
    const tonfVest = (estadoActual.V_estatico / 9.80665).toFixed(2);

    const elPesoP = document.getElementById('e030ResumenPesoP');
    if (elPesoP) elPesoP.textContent = `$P = ${estadoActual.peso_total_P.toFixed(2)}\\text{ kN} \\; (${tonfP}\\text{ tonf})$`;

    const elCoefBasal = document.getElementById('e030ResumenCoefBasal');
    if (elCoefBasal) elCoefBasal.textContent = `$\\frac{Z U C S}{R} = ${estadoActual.coef_sismico.toFixed(4)}$`;

    const elVest = document.getElementById('e030ResumenVest');
    if (elVest) elVest.textContent = `$V_{est} = ${estadoActual.V_estatico.toFixed(2)}\\text{ kN} \\; (${tonfVest}\\text{ tonf})$`;

    const inpVest = document.getElementById('e030VestInput');
    if (inpVest && !estadoActual.V_estatico_manual) {
      inpVest.value = estadoActual.V_estatico.toFixed(1);
    }

    const inpPesoP = document.getElementById('e030PesoTotalInput');
    if (inpPesoP && !estadoActual.peso_manual) {
      inpPesoP.value = estadoActual.peso_total_P.toFixed(1);
    }

    const inpPeriodoT = document.getElementById('e030PeriodoInput');
    if (inpPeriodoT && !estadoActual.T_manual) {
      inpPeriodoT.value = estadoActual.T.toFixed(3);
    }

    // Sincronizar tarjetas del panel normativo superior
    const valZ = document.getElementById('normValZ');
    if (valZ) valZ.textContent = `$Z = ${estadoActual.Z.toFixed(2)}$ (Zona ${estadoActual.zona}: ${estadoActual.distrito})`;

    const valU = document.getElementById('normValU');
    if (valU) valU.textContent = `$U = ${estadoActual.U.toFixed(2)}$ (Cat. ${estadoActual.categoria})`;

    const valS = document.getElementById('normValS');
    if (valS) valS.textContent = `$S = ${estadoActual.S.toFixed(2)}, T_P = ${estadoActual.TP.toFixed(2)}\\text{ s}, T_L = ${estadoActual.TL.toFixed(2)}\\text{ s}$`;

    const valR = document.getElementById('normValR');
    if (valR) valR.textContent = `$R = ${estadoActual.R.toFixed(2)}$ (${estadoActual.sistema.replace(/_/g, ' ')})`;

    // Re-render LaTeX
    if (window.scheduleLaTeXRender) {
      window.scheduleLaTeXRender(document.getElementById('e030AutomationSection'));
      window.scheduleLaTeXRender(document.getElementById('normParamPanel'));
    }
  }

  async function cargarDepartamentos() {
    const selDep = document.getElementById('e030DepSelect');
    if (!selDep) return;

    // Precargar lista por defecto para que el selector nunca aparezca vacío
    if (selDep.options.length === 0) {
      DEPARTAMENTOS_DEFAULT.forEach(dep => {
        const opt = document.createElement('option');
        opt.value = dep;
        opt.textContent = dep;
        if (dep === estadoActual.departamento) opt.selected = true;
        selDep.appendChild(opt);
      });
    }

    try {
      const data = await apiGet('/api/normativa/anexo-ii');
      if (data && Array.isArray(data.departamentos) && data.departamentos.length > 0) {
        selDep.innerHTML = '';
        data.departamentos.forEach(dep => {
          const opt = document.createElement('option');
          opt.value = dep;
          opt.textContent = dep;
          if (dep === estadoActual.departamento) opt.selected = true;
          selDep.appendChild(opt);
        });
      }
      await cargarProvincias(estadoActual.departamento);
    } catch (err) {
      console.warn('Draft2Model: Anexo II cargado con defaults locales:', err.message);
      await cargarProvincias(estadoActual.departamento);
    }
  }

  async function cargarProvincias(dep) {
    const selProv = document.getElementById('e030ProvSelect');
    if (!selProv) return;
    try {
      const data = await apiGet(`/api/normativa/anexo-ii?departamento=${encodeURIComponent(dep)}`);
      if (data && Array.isArray(data.provincias) && data.provincias.length > 0) {
        selProv.innerHTML = '';
        data.provincias.forEach(prov => {
          const opt = document.createElement('option');
          opt.value = prov;
          opt.textContent = prov;
          if (prov === estadoActual.provincia) opt.selected = true;
          selProv.appendChild(opt);
        });
        const provActiva = selProv.value || data.provincias[0];
        estadoActual.provincia = provActiva;
        await cargarDistritos(dep, provActiva);
      }
    } catch (err) {
      console.warn('Draft2Model: Provincias cargadas localmente:', err.message);
    }
  }

  async function cargarDistritos(dep, prov) {
    const selDist = document.getElementById('e030DistSelect');
    if (!selDist) return;
    try {
      const data = await apiGet(`/api/normativa/anexo-ii?departamento=${encodeURIComponent(dep)}&provincia=${encodeURIComponent(prov)}`);
      if (data && Array.isArray(data.distritos) && data.distritos.length > 0) {
        selDist.innerHTML = '';
        data.distritos.forEach(d => {
          const opt = document.createElement('option');
          opt.value = d.distrito;
          opt.textContent = `${d.distrito} (Zona ${d.zona}, Z = ${d.Z.toFixed(2)})`;
          opt.dataset.zona = d.zona;
          opt.dataset.z = d.Z;
          if (d.distrito === estadoActual.distrito) opt.selected = true;
          selDist.appendChild(opt);
        });
        if (selDist.selectedOptions.length > 0) {
          const optSel = selDist.selectedOptions[0];
          estadoActual.distrito = optSel.value;
          estadoActual.zona = parseInt(optSel.dataset.zona, 10);
          estadoActual.Z = parseFloat(optSel.dataset.z);
        }
        actualizarCalculos();
      }
    } catch (err) {
      console.warn('Draft2Model: Distritos cargados localmente:', err.message);
    }
  }

  async function descargarEspectroTxt() {
    const z = estadoActual.Z;
    const u = estadoActual.U;
    const s = estadoActual.S;
    const r = estadoActual.R;
    const tp = estadoActual.TP;
    const tl = estadoActual.TL;
    const tipo = estadoActual.tipoEspectro;
    const url = `/api/normativa/espectro-etabs?Z=${z}&U=${u}&S=${s}&R=${r}&TP=${tp}&TL=${tl}&tipo=${tipo}&descargar=1`;

    const token = obtenerTokenSesion();
    const headers = {};
    if (token) headers['X-Revision-Session'] = token;

    const res = await fetch(url, { headers });
    if (!res.ok) {
      alert('Error al descargar archivo de espectro.');
      return;
    }
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `Espectro_E030_2026_${estadoActual.tipoEspectro}_Z${estadoActual.Z}_U${estadoActual.U}_S${estadoActual.S}_R${estadoActual.R}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  function verificarCortanteBasal() {
    const elVest = document.getElementById('e030VestInput');
    const elVdin = document.getElementById('e030VdinInput');
    const elRes = document.getElementById('e030ResultadoCortante');
    if (!elVest || !elVdin || !elRes) return;

    const vest = parseFloat(elVest.value) || 0;
    const vdin = parseFloat(elVdin.value) || 0;
    if (vest <= 0 || vdin <= 0) {
      elRes.innerHTML = '<span class="norm-status-warn">Ingrese valores numéricos positivos para cortante estático y dinámico.</span>';
      return;
    }

    const regular = (estadoActual.Ia === 1.0 && estadoActual.Ip === 1.0);
    const fraccion = regular ? 0.80 : 0.90;
    const vmin = fraccion * vest;
    const cumple = vdin >= vmin - 1e-4;
    const factorEscala = cumple ? 1.0 : (vmin / vdin);

    let html = `<div class="e030-verif-box ${cumple ? 'verif-ok' : 'verif-scale'}">`;
    html += `<div><strong>Verificación de Cortante Basal Mínimo - Art. 44 (E.030-2026):</strong></div>`;
    html += `<div>Estructura: <em>${regular ? 'Regular (límite 80% Vest)' : 'Irregular (límite 90% Vest)'}</em></div>`;
    const tonfVmin = (vmin / 9.80665).toFixed(2);
    const tonfVestCalc = (vest / 9.80665).toFixed(2);
    const tonfVdin = (vdin / 9.80665).toFixed(2);
    html += `<div>$V_{din,min} = ${vmin.toFixed(2)}\\text{ kN} \\; (${tonfVmin}\\text{ tonf}) \\quad (${(fraccion * 100).toFixed(0)}\\% \\times ${vest.toFixed(2)}\\text{ kN} \\; [${tonfVestCalc}\\text{ tonf}])$</div>`;
    html += `<div>$V_{din} = ${vdin.toFixed(2)}\\text{ kN} \\; (${tonfVdin}\\text{ tonf})$</div>`;

    if (cumple) {
      html += `<div class="verif-badge-ok">Cumple con la fuerza cortante mínima en la base ($V_{din} \\ge V_{min}$). No requiere escala adicional en ETABS (Factor = $1.000$).</div>`;
    } else {
      html += `<div class="verif-badge-scale">Cortante dinámico insuficiente ($V_{din} < V_{min}$). <strong>Se debe escalar en ETABS por factor = $${factorEscala.toFixed(4)}$</strong> en los Load Cases espectrales (RSX, RSY).</div>`;
    }
    html += `</div>`;
    elRes.innerHTML = html;

    if (window.scheduleLaTeXRender) {
      window.scheduleLaTeXRender(elRes);
    }
  }

  function inicializarEventos() {
    const selDep = document.getElementById('e030DepSelect');
    if (selDep) {
      selDep.addEventListener('change', async (e) => {
        estadoActual.departamento = e.target.value;
        await cargarProvincias(estadoActual.departamento);
      });
    }

    const selProv = document.getElementById('e030ProvSelect');
    if (selProv) {
      selProv.addEventListener('change', async (e) => {
        estadoActual.provincia = e.target.value;
        await cargarDistritos(estadoActual.departamento, estadoActual.provincia);
      });
    }

    const selDist = document.getElementById('e030DistSelect');
    if (selDist) {
      selDist.addEventListener('change', (e) => {
        const opt = e.target.selectedOptions[0];
        if (opt) {
          estadoActual.distrito = opt.value;
          estadoActual.zona = parseInt(opt.dataset.zona, 10);
          estadoActual.Z = parseFloat(opt.dataset.z);
          actualizarCalculos();
        }
      });
    }

    const selSuelo = document.getElementById('e030SueloSelect');
    if (selSuelo) {
      selSuelo.addEventListener('change', (e) => {
        estadoActual.perfil = e.target.value;
        actualizarCalculos();
      });
    }

    const inpVs30 = document.getElementById('e030Vs30Input');
    if (inpVs30) {
      inpVs30.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        estadoActual.vs30 = isNaN(val) ? null : val;
        actualizarCalculos();
      });
    }

    const selCat = document.getElementById('e030CatSelect');
    if (selCat) {
      selCat.addEventListener('change', (e) => {
        estadoActual.categoria = e.target.value;
        actualizarCalculos();
      });
    }

    const selSistema = document.getElementById('e030SistemaSelect');
    if (selSistema) {
      selSistema.addEventListener('change', (e) => {
        estadoActual.sistema = e.target.value;
        actualizarCalculos();
      });
    }

    const selIa = document.getElementById('e030IaSelect');
    if (selIa) {
      selIa.addEventListener('change', (e) => {
        estadoActual.Ia = parseFloat(e.target.value);
        actualizarCalculos();
      });
    }

    const selIp = document.getElementById('e030IpSelect');
    if (selIp) {
      selIp.addEventListener('change', (e) => {
        estadoActual.Ip = parseFloat(e.target.value);
        actualizarCalculos();
      });
    }

    const inpHn = document.getElementById('e030HnInput');
    if (inpHn) {
      inpHn.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val > 0) {
          estadoActual.hn_m = val;
          actualizarCalculos();
        }
      });
    }

    const inpPeriodo = document.getElementById('e030PeriodoInput');
    if (inpPeriodo) {
      inpPeriodo.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val > 0) {
          estadoActual.T = val;
          estadoActual.T_manual = true;
          actualizarCalculos();
        } else {
          estadoActual.T_manual = false;
          actualizarCalculos();
        }
      });
    }

    const inpPesoCM = document.getElementById('e030PesoCMInput');
    if (inpPesoCM) {
      inpPesoCM.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val >= 0) {
          estadoActual.peso_CM = val;
          estadoActual.peso_manual = false;
          actualizarCalculos();
        }
      });
    }

    const inpPesoCV = document.getElementById('e030PesoCVInput');
    if (inpPesoCV) {
      inpPesoCV.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val >= 0) {
          estadoActual.peso_CV = val;
          estadoActual.peso_manual = false;
          actualizarCalculos();
        }
      });
    }

    const inpPesoTotal = document.getElementById('e030PesoTotalInput');
    if (inpPesoTotal) {
      inpPesoTotal.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val > 0) {
          estadoActual.peso_total_P = val;
          estadoActual.peso_manual = true;
          actualizarCalculos();
        } else {
          estadoActual.peso_manual = false;
          actualizarCalculos();
        }
      });
    }

    const inpVest = document.getElementById('e030VestInput');
    if (inpVest) {
      inpVest.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val > 0) {
          estadoActual.V_estatico = val;
          estadoActual.V_estatico_manual = true;
        } else {
          estadoActual.V_estatico_manual = false;
        }
      });
    }

    const selTipoEspectro = document.getElementById('e030TipoEspectro');
    if (selTipoEspectro) {
      selTipoEspectro.addEventListener('change', (e) => {
        estadoActual.tipoEspectro = e.target.value;
      });
    }

    const chkOrto = document.getElementById('e030OrtoCheckbox');
    if (chkOrto) {
      chkOrto.addEventListener('change', (e) => {
        estadoActual.ortogonal30 = e.target.checked;
      });
    }

    const btnDescargar = document.getElementById('btnDescargarEspectroEtabs');
    if (btnDescargar) {
      btnDescargar.addEventListener('click', descargarEspectroTxt);
    }

    const btnVerifCortante = document.getElementById('btnVerifCortante');
    if (btnVerifCortante) {
      btnVerifCortante.addEventListener('click', verificarCortanteBasal);
    }

    // Escuchar cambios de módulo desde navegacion_modulos.js
    window.addEventListener('moduloCambiado', (ev) => {
      const modId = ev.detail?.id;
      if (modId === 'porticado') {
        estadoActual.sistema = 'concreto_porticos';
        if (selSistema) selSistema.value = 'concreto_porticos';
      } else if (modId === 'albanileria') {
        estadoActual.sistema = 'albanileria_armada_o_confinada';
        if (selSistema) selSistema.value = 'albanileria_armada_o_confinada';
      }
      actualizarCalculos();
    });
  }

  function inicializar() {
    if (typeof document === 'undefined') return;
    const root = document.getElementById('e030AutomationSection');
    if (!root) return;
    const selSistema = document.getElementById('e030SistemaSelect'); if (selSistema) selSistema.value = estadoActual.sistema;
    const inpHn = document.getElementById('e030HnInput'); if (inpHn) inpHn.value = estadoActual.hn_m;
    const inpCM = document.getElementById('e030PesoCMInput'); if (inpCM) inpCM.value = estadoActual.peso_CM;
    const inpCV = document.getElementById('e030PesoCVInput'); if (inpCV) inpCV.value = estadoActual.peso_CV;
    const inpP = document.getElementById('e030PesoTotalInput'); if (inpP) inpP.value = estadoActual.peso_total_P;
    const inpVdin = document.getElementById('e030VdinInput'); if (inpVdin) inpVdin.value = estadoActual.V_dinamico;
    inicializarEventos();
    cargarDepartamentos();
    actualizarCalculos();
    verificarCortanteBasal();
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', inicializar);
    } else {
      setTimeout(inicializar, 40);
    }
  }

  if (typeof window !== 'undefined') {
    window.HerramientaSismicaE030 = {
      estado: estadoActual,
      actualizar: actualizarCalculos,
      descargarEspectro: descargarEspectroTxt,
      verificarCortante: verificarCortanteBasal
    };
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      calcularParametrosSuelo,
      calcularC,
      calcularK
    };
  }
})();
