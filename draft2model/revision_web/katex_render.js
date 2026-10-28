/**
 * Draft2Model - Controlador de Renderizado LaTeX con KaTeX.
 * 
 * Renderiza dinámicamente fórmulas matemáticas, nomenclatura estructural,
 * derivas, cortantes basales, factores de reducción sísmica y memorias de cálculo
 * en toda la interfaz (fórmulas, etiquetas, tablas de resultados, fichas y reportes),
 * preservando de forma segura los campos de entrada de formulario nativos.
 */

'use strict';

(() => {
  const DEFAULT_OPTIONS = {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '\\[', right: '\\]', display: true },
      { left: '$', right: '$', display: false },
      { left: '\\(', right: '\\)', display: false }
    ],
    ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option', 'input'],
    ignoredClasses: ['no-latex', 'katex-ignore', 'drawing'],
    throwOnError: false,
    errorCallback: () => {}
  };

  function render(root = document.body, customOptions = {}) {
    if (typeof window.renderMathInElement !== 'function') return;
    try {
      const target = typeof root === 'string' ? document.querySelector(root) : root;
      if (!target) return;
      const opts = Object.assign({}, DEFAULT_OPTIONS, customOptions);
      window.renderMathInElement(target, opts);
    } catch (err) {
      console.warn('Draft2Model LaTeX render notice:', err);
    }
  }

  let timer = null;
  function scheduleRender(target, delay = 60) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      render(target || document.body);
    }, delay);
  }

  window.renderLaTeX = render;
  window.scheduleLaTeXRender = scheduleRender;

  function init() {
    // Renderizado inicial en todo el documento
    scheduleRender(document.body, 30);

    // Renderizar cuando cambie de etapa
    window.addEventListener('d2m-stage', e => {
      const stage = e.detail;
      const pane = document.querySelector(`.stage-pane[data-stage="${stage}"]`);
      if (pane) scheduleRender(pane, 40);
      else scheduleRender(document.body, 60);
    });

    // Renderizar al abrir modal de normativas
    const btnNormas = document.getElementById('btnVerNormativas');
    const btnNormasHeader = document.getElementById('btnVerNormativasHeader');
    [btnNormas, btnNormasHeader].forEach(btn => {
      if (btn) {
        btn.addEventListener('click', () => {
          setTimeout(() => {
            const modalBody = document.getElementById('normativaModalBody');
            if (modalBody) render(modalBody);
          }, 80);
        });
      }
    });

    // Eventos estructurales del ciclo de vida
    ['d2m-case', 'd2m-config', 'd2m-model', 'd2m-result', 'd2m-result-created', 'd2m-readings-opened', 'd2m-geometry-opened'].forEach(evt => {
      window.addEventListener(evt, () => scheduleRender(document.body, 100));
    });

    // Observar inserciones en contenedores dinámicos clave
    const containersToWatch = ['normParamPanel', 'modalFichaNormativa', 'analisisAdvancedGroup'];
    containersToWatch.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        const obs = new MutationObserver(() => scheduleRender(el, 50));
        obs.observe(el, { childList: true, subtree: true });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    setTimeout(init, 30);
  }
})();
