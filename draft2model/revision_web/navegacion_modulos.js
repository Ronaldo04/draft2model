/**
 * Draft2Model - Gestión de Módulos y Normativas RNE.
 * 
 * Gestiona:
 * 1. Módulo 1: Sistema Aporticado (Concreto Armado)
 *    - Normas completas: RNE E.030-2026, E.060, E.020, E.050 (todas a excepción de la E.070).
 *    - Criterios: R0 = 8.0, CT = 35, Deriva inelástica <= 0.007, Inercias 0.70 Ig / 0.35 Ig, Nudos 50%, Tabiquería 100% aislada.
 *    - Unidades estándar peruanas: kg/cm² para esfuerzos (f'c, fy), kg/m² para sobrecargas, tonf o kN para cortante basal.
 * 2. Módulo 2: Sistema de Albañilería Confinada (Muros Portantes)
 *    - Normas completas: RNE E.030-2026, E.070, E.060, E.020, E.050 (todas las anteriores más la E.070).
 *    - Criterios: R0 = 3.0, CT = 60, Deriva <= 0.005, f'm = 35 kg/cm², Em = 17500 kg/cm², Densidad de muros E.070 Art. 19.
 *    - Caso de demostración verificado: pueblo-libre-v04 (vivienda de 2 pisos aprobada).
 * 3. Modal de Ficha Técnica Normativa RNE accesible bajo demanda sin alterar ni obstruir el espacio de trabajo.
 */

'use strict';

(() => {
  let activeModule = 'porticado'; // 'porticado' | 'albanileria'

  function getElements() {
    return {
      moduloSelect: document.getElementById('moduloSistema'),
      ingresoModulo: document.getElementById('ingresoModulo'),
      headerBadge: document.getElementById('headerModuleBadge'),
      headerModTitle: document.getElementById('headerModTitle'),
      headerModNorms: document.getElementById('headerModNorms'),
      btnNormasHeader: document.getElementById('btnVerNormativasHeader'),
      btnNormasIntro: document.getElementById('btnVerNormativas'),
      modalNormativa: document.getElementById('modalFichaNormativa'),
      btnCloseModal: document.getElementById('btnCloseNormativaModal'),
      btnAcceptModal: document.getElementById('btnAcceptNormativaModal'),
      modalTitle: document.getElementById('normativaModalModuleTitle'),
      modalBody: document.getElementById('normativaModalBody'),
      casoSelect: document.getElementById('caso')
    };
  }

  function setModule(modId) {
    activeModule = modId === 'albanileria' ? 'albanileria' : 'porticado';
    const el = getElements();

    if (el.moduloSelect && el.moduloSelect.value !== activeModule) {
      el.moduloSelect.value = activeModule;
    }
    if (el.ingresoModulo && el.ingresoModulo.value !== activeModule) {
      el.ingresoModulo.value = activeModule;
    }

    if (el.headerModTitle && el.headerModNorms) {
      if (activeModule === 'porticado') {
        el.headerModTitle.textContent = 'Módulo 1: Sistema Aporticado';
        el.headerModNorms.textContent = 'RNE: E.020 · E.030-2026 · E.050 · E.060 (Sin E.070)';
        if (el.headerBadge) {
          el.headerBadge.textContent = 'MÓDULO 1: APORTICADO (ACTIVO)';
          el.headerBadge.className = 'module-badge badge-porticado';
        }
      } else {
        el.headerModTitle.textContent = 'Módulo 2: Sistema de Albañilería Confinada';
        el.headerModNorms.textContent = 'RNE: E.020 · E.030-2026 · E.050 · E.060 · E.070 (Completo)';
        if (el.headerBadge) {
          el.headerBadge.textContent = 'MÓDULO 2: ALBAÑILERÍA (DEMOSTRACIÓN)';
          el.headerBadge.className = 'module-badge badge-albanileria';
        }
      }
    }

    try {
      sessionStorage.setItem('d2m_selected_module', activeModule);
    } catch (_) {}

    window.dispatchEvent(new CustomEvent('moduloCambiado', { detail: { id: activeModule } }));
  }

  function openNormativaModal() {
    const el = getElements();
    if (!el.modalNormativa || !el.modalBody) return;

    if (el.modalTitle) {
      el.modalTitle.textContent = activeModule === 'porticado'
        ? 'Ficha Técnica: Módulo 1 - Sistema Aporticado'
        : 'Ficha Técnica: Módulo 2 - Sistema de Albañilería Confinada';
    }

    if (activeModule === 'porticado') {
      el.modalBody.innerHTML = `
        <div class="norm-modal-content">
          <div class="norm-notice-box">
            <strong>Módulo 1: Sistema Aporticado (Concreto Armado)</strong>
            <p>Estructuración sismorresistente lateral y gravitacional mediante pórticos espaciales de vigas y columnas resistentes a momentos. Tabiquería no portante totalmente aislada con juntas sísmicas ($e \\ge 2.5\\text{ cm}$).</p>
          </div>

          <div class="norm-grid-details">
            <div class="norm-detail-card">
              <h4>Normas RNE Aplicables (Completas)</h4>
              <ul>
                <li><strong>Norma Técnica E.030-2026 (Diseño Sismorresistente):</strong>
                  <ul>
                    <li>Factor básico de reducción: $R_0 = 8.0$ (Pórticos de concreto armado, Tabla N° 10).</li>
                    <li>Período fundamental estimado: $T = \\frac{h_n}{C_T}$ con $C_T = 35.0$ (Art. 34.1).</li>
                    <li>Cortante basal estático de diseño:
                      $$V = \\left(\\frac{Z \\cdot U \\cdot C \\cdot S}{R}\\right) P$$
                    </li>
                    <li>Límite de distorsión inelástica de entrepiso: $\\frac{\\Delta_i}{h_e} \\le 0.007$ (Tabla N° 11).</li>
                    <li>Control de cortante dinámico mínimo (Art. 44): $V_{din} \\ge 0.80 V_{est}$ (regular) o $V_{din} \\ge 0.90 V_{est}$ (irregular).</li>
                    <li>Estimación de masa sísmica efectiva: $P = 1.00 CM + 0.25 CV$ (Edificaciones Cat. C).</li>
                  </ul>
                </li>
                <li><strong>Norma Técnica E.060 (Concreto Armado):</strong>
                  <ul>
                    <li>Modificadores de inercia por agrietamiento (Art. 10.11): $I_{col} = 0.70 I_g$ en columnas y $I_{viga} = 0.35 I_g$ en vigas.</li>
                    <li>Modelado de zonas rígidas en nudos viga-columna: $\\text{Rigid Zone Factor} = 50\\%$.</li>
                    <li>Criterio de diseño sismorresistente columna fuerte - viga débil:
                      $$\\sum M_{nc} \\ge 1.20 \\sum M_{nb}$$
                    </li>
                    <li>Secciones mínimas: columnas $b \\ge 25\\text{ cm}$, $A_g \\ge 1000\\text{ cm}^2$; vigas $b \\ge 25\\text{ cm}$.</li>
                    <li>Cuantías longitudinales: $\\rho_{min} = 0.01$ y $\\rho_{max} = 0.06$.</li>
                    <li>Materiales según práctica peruana: resistencia $f'_c \\ge 210\\text{ kg/cm}^2$ y fluencia del acero $f_y = 4200\\text{ kg/cm}^2$.</li>
                  </ul>
                </li>
                <li><strong>Norma Técnica E.020 (Cargas):</strong>
                  <ul>
                    <li>Peso volumétrico del concreto armado: $\\gamma = 2.4\\text{ tonf/m}^3\\ (2400\\text{ kg/m}^3)$.</li>
                    <li>Sobrecargas reglamentarias de uso: $200\\text{ kg/m}^2$ en entrepisos y $100\\text{ kg/m}^2$ en azoteas.</li>
                    <li>Combinaciones últimas de diseño por resistencia:
                      $$U = 1.4 D + 1.7 L \\quad ; \\quad U = 1.25(D + L) \\pm S \\quad ; \\quad U = 0.9 D \\pm S$$
                    </li>
                  </ul>
                </li>
                <li><strong>Norma Técnica E.050 (Suelos y Cimentaciones):</strong>
                  <ul>
                    <li>Parámetros de sitio: factor de suelo $S$, períodos $T_P$ y $T_L$, y capacidad portante admisible $q_a$ en $\\text{kg/cm}^2$ (o $\\text{tonf/m}^2$).</li>
                  </ul>
                </li>
                <li><strong>Excepción Normativa:</strong> La Norma E.070 (Albañilería) <strong>NO aplica</strong> para este módulo, debido a que la estructura no contiene muros portantes y los tabiques divisorios están completamente desligados mediante juntas sísmicas.</li>
              </ul>
            </div>

            <div class="norm-detail-card">
              <h4>Requisitos de Entrada para el Proyecto del Curso de Modelado</h4>
              <p>Datos técnicos requeridos para la ingesta y corrida en ETABS:</p>
              <ul class="checklist-items-clean">
                <li><strong>1. Planos de Arquitectura:</strong> Plantas por nivel, elevaciones y cortes con alturas libres $h_e$ y dimensiones de vanos.</li>
                <li><strong>2. Plano y Cuadro de Columnas:</strong> Secciones $b \\times h$, orientación en planta y detalles de confinamiento.</li>
                <li><strong>3. Encofrado de Vigas y Losas:</strong> Peraltes $h$, anchos $b$ de vigas principales y secundarias, y espesor de losa $e$.</li>
                <li><strong>4. Estudio de Mecánica de Suelos (EMS):</strong> Perfil de suelo $S$ ($S_0$ a $S_4$) y capacidad portante admisible $q_a$.</li>
                <li><strong>5. Ubicación Geográfica:</strong> Departamento, provincia y distrito para definir el factor de aceleración en roca $Z$ (Zona 1 a 4).</li>
                <li><strong>6. Especificaciones de Materiales:</strong> Resistencia del concreto $f'_c \\ge 210\\text{ kg/cm}^2$ y acero $f_y = 4200\\text{ kg/cm}^2$.</li>
              </ul>
            </div>
          </div>
        </div>
      `;
    } else {
      el.modalBody.innerHTML = `
        <div class="norm-modal-content">
          <div class="norm-notice-box notice-albanileria">
            <strong>Módulo 2: Sistema de Albañilería Confinada (Muros Portantes)</strong>
            <p>Estructuración sismorresistente y gravitacional mediante muros de ladrillo confinados por columnas y vigas soleras de amarre. Módulo en desarrollo continuo; conserva el caso verificado de demostración técnica.</p>
          </div>

          <div class="norm-grid-details">
            <div class="norm-detail-card">
              <h4>Normas RNE Aplicables (Completas)</h4>
              <ul>
                <li><strong>Norma Técnica E.070 (Albañilería):</strong>
                  <ul>
                    <li>Resistencia característica a compresión axial de la albañilería: $f'_m = 35.0\\text{ kg/cm}^2$ (artesanal) o $45.0\\text{ kg/cm}^2$ (industrial).</li>
                    <li>Módulo de elasticidad: $E_m = 500 f'_m = 17500\\text{ kg/cm}^2\\ (1.75 \\times 10^5\\text{ tonf/m}^2)$.</li>
                    <li>Módulo de corte: $G_m = 0.4 E_m = 7000\\text{ kg/cm}^2$.</li>
                    <li>Densidad mínima de muros portantes por eje (Art. 19):
                      $$\\frac{\\sum L \\cdot t}{A_p} \\ge \\frac{Z \\cdot U \\cdot S \\cdot N}{56}$$
                    </li>
                    <li>Espesor efectivo mínimo de muros (Art. 18): $t \\ge \\frac{h}{20}$.</li>
                    <li>Resistencia al corte admisible de muros confinados (Art. 26):
                      $$V_m = 0.5 \\cdot v'_m \\cdot \\alpha \\cdot t \\cdot L + 0.23 \\cdot P_g$$
                    </li>
                  </ul>
                </li>
                <li><strong>Norma Técnica E.030-2026 (Diseño Sismorresistente):</strong>
                  <ul>
                    <li>Factor básico de reducción: $R_0 = 3.0$ (Muros de albañilería confinada, Tabla N° 10).</li>
                    <li>Período fundamental de vibración: $T = \\frac{h_n}{C_T}$ con $C_T = 60.0$ (Art. 34.1).</li>
                    <li>Límite máximo de distorsión elástica de entrepiso: $\\frac{\\Delta_i}{h_e} \\le 0.005$ (Tabla N° 11).</li>
                  </ul>
                </li>
                <li><strong>Norma Técnica E.060 (Concreto Armado):</strong> Elementos de confinamiento de concreto (columnas y soleras con $f'_c \\ge 175\\text{ kg/cm}^2$); anclaje de refuerzo y estribos cerrados de confinamiento en nudos y extremos.</li>
                <li><strong>Norma Técnica E.020 (Cargas):</strong> Cargas permanentes de muros portantes de ladrillo, losas aligeradas y sobrecargas de uso reglamentarias ($200\\text{ kg/m}^2$).</li>
                <li><strong>Norma Técnica E.050 (Suelos y Cimentaciones):</strong> Cimientos corridos de concreto ciclópeo y sobrecimientos armados según perfil de suelo y capacidad portante admisible $q_a$.</li>
              </ul>
            </div>

            <div class="norm-detail-card">
              <h4>Caso de Demostración Verificado: pueblo-libre-v04</h4>
              <p>Expediente de referencia totalmente validado en las 7 etapas contra modelo manual de ETABS:</p>
              <ul>
                <li><strong>Ubicación:</strong> Distrito de Pueblo Libre, Lima (Zona 4: $Z = 0.45$, Suelo S1: $S = 1.00$, $T_P = 0.4\\text{ s}$, $T_L = 2.5\\text{ s}$, Uso C: $U = 1.0$).</li>
                <li><strong>Geometría:</strong> Vivienda unifamiliar de 2 pisos, altura total $H = 5.30\\text{ m}$, 9 paños de muros confinados.</li>
                <li><strong>Resultados Comprobados:</strong> Períodos fundamentales $T_1 = 0.088\\text{ s}$ (X) y $T_2 = 0.088\\text{ s}$ (Y); Cortante basal estático $V = 30.63\\text{ tonf}$; Deriva máxima elástica $\\Delta_{max} = 0.00036 \\le 0.005$.</li>
                <li><strong>Conformidad Técnica:</strong> Aprobado al 100% en las 7 fases por Ing. Ronaldo Cuchilla.</li>
              </ul>
            </div>
          </div>
        </div>
      `;
    }

    if (window.renderLaTeX) {
      window.renderLaTeX(el.modalBody);
    }

    if (typeof el.modalNormativa.showModal === 'function') {
      el.modalNormativa.showModal();
    } else {
      el.modalNormativa.setAttribute('open', '');
    }
  }

  function closeNormativaModal() {
    const el = getElements();
    if (!el.modalNormativa) return;
    if (typeof el.modalNormativa.close === 'function') {
      el.modalNormativa.close();
    } else {
      el.modalNormativa.removeAttribute('open');
    }
  }

  function init() {
    const el = getElements();

    if (el.moduloSelect) {
      el.moduloSelect.addEventListener('change', () => {
        setModule(el.moduloSelect.value);
        if (el.moduloSelect.value === 'albanileria' && el.casoSelect && !el.casoSelect.value) {
          const opt = Array.from(el.casoSelect.options).find(o => o.value.includes('pueblo-libre'));
          if (opt) {
            el.casoSelect.value = opt.value;
            el.casoSelect.dispatchEvent(new Event('change'));
          }
        }
      });
    }

    if (el.ingresoModulo) {
      el.ingresoModulo.addEventListener('change', () => {
        setModule(el.ingresoModulo.value);
      });
    }

    if (el.btnNormasHeader) el.btnNormasHeader.addEventListener('click', openNormativaModal);
    if (el.btnNormasIntro) el.btnNormasIntro.addEventListener('click', openNormativaModal);
    if (el.btnCloseModal) el.btnCloseModal.addEventListener('click', closeNormativaModal);
    if (el.btnAcceptModal) el.btnAcceptModal.addEventListener('click', closeNormativaModal);

    if (el.casoSelect) {
      el.casoSelect.addEventListener('change', () => {
        const val = (el.casoSelect.value || '').toLowerCase();
        if (val.includes('pueblo-libre')) {
          setModule('albanileria');
        } else if (val) {
          setModule('porticado');
        }
      });
    }

    // Estado inicial
    let saved = null;
    try {
      saved = sessionStorage.getItem('d2m_selected_module');
    } catch (_) {}

    if (saved) {
      setModule(saved);
    } else if (el.casoSelect && el.casoSelect.value.includes('pueblo-libre')) {
      setModule('albanileria');
    } else {
      setModule('porticado');
    }

    // Gestión reactiva del banner de contingencia para normalizaciones interrumpidas
    const recSel = document.getElementById('recuperacionOperacion');
    if (recSel) {
      const updateAlerta = () => {
        const alerta = document.getElementById('alertaNormalizacionInterrumpida');
        if (!alerta) return;
        const hasPending = recSel.options.length > 1 &&
          (recSel.options[0]?.text.includes('Selecciona operación pendiente') ||
           Array.from(recSel.options).some(o => o.value && !o.text.includes('Sin operaciones')));
        alerta.hidden = !hasPending;
      };
      const observer = new MutationObserver(updateAlerta);
      observer.observe(recSel, { childList: true });
      recSel.addEventListener('change', updateAlerta);
      setTimeout(updateAlerta, 100);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    setTimeout(init, 30);
  }
})();
