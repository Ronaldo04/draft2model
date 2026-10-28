"""Comprueba páginas y contenido PDF reales; no compara reglas CSS."""
import copy
import json
from pathlib import Path
import re
import unicodedata
import unittest

import pymupdf

from draft2model.informe import CSS, _pdf, crear_informe, renderizar_html

EJEMPLOS = Path(__file__).resolve().parents[1] / 'examples'


def normalizar(texto):
    return ' '.join(unicodedata.normalize('NFKC', texto).split())


class PaginacionInformeTests(unittest.TestCase):
    def paginas(self, html):
        raw = _pdf(html)
        with pymupdf.open(stream=raw, filetype='pdf') as doc:
            paginas = [normalizar(p.get_text()) for p in doc]
            for i, page in enumerate(doc):
                self.assertIn(f'{i+1} / {len(doc)}', page.get_text())
                for bloque in page.get_text('blocks'):
                    self.assertGreaterEqual(bloque[0], 0)
                    self.assertGreaterEqual(bloque[1], 0)
                    self.assertLessEqual(bloque[2], page.rect.width+1)
                    self.assertLessEqual(bloque[3], page.rect.height+1)
                    self.assertLessEqual(bloque[3], page.rect.height-20)
        return paginas

    def misma_pagina(self, paginas, titulo, primero):
        titulos = [i for i, texto in enumerate(paginas) if normalizar(titulo) in texto]
        contenidos = [i for i, texto in enumerate(paginas) if normalizar(primero) in texto]
        self.assertEqual(len(titulos), 1, titulo)
        self.assertEqual(len(contenidos), 1, primero)
        self.assertEqual(titulos, contenidos, (titulo, primero, paginas))

    def informe(self, hipotesis=1):
        resultados = json.loads((EJEMPLOS/'resultados_estructurales_sinteticos.json').read_text(encoding='utf-8'))
        resultados['resultados'] = [r for r in resultados['resultados'] if r['variable'] != 'periodo']
        resultados['resultados'].append({'id':'DY', 'variable':'deriva', 'caso':'SX', 'direccion':'Y',
            'ubicacion':'N1', 'valor':None, 'unidad':'1', 'motivo_omision':'FILA-OMITIDA-DE-PRUEBA sin dato revisado.'})
        resultados['omisiones'].append('DY: FILA-OMITIDA-DE-PRUEBA sin dato revisado.')
        contexto = {'titulo':'Informe SINTÉTICO de paginación, sin evaluación de obra',
            'hipotesis':[f'HIP-{i:03d}: Solo datos fabricados para probar presentación y trazabilidad.' for i in range(hipotesis)],
            'faltantes':['Revisión de ingeniería y comparación manual pendientes.'], 'sitio':None}
        explicacion = {'trabajo':'a'*32, 'estado_trabajo':'contingencia', 'huella_salida':'b'*64,
            'modo':'contingencia_deterministica', 'causa':'sin_proveedor', 'generacion_llm_real':False,
            'modo_transporte':'ninguno', 'modelo_declarado':'No invocado', 'declaraciones':None,
            'abstenciones':[{'tema':'SOLO-SOFTWARE', 'motivo':'No se deduce una conclusión estructural de estos datos.'}],
            'limites_verificables':['LIMITE-FINAL: Identidad y competencia del revisor no autenticadas.'],
            'estado_revision':'propuesta_pendiente_revision_humana'}
        informe = crear_informe(resultados, None, contexto,
            contexto_verificado={'evaluacion':None, 'recuperacion':None, 'sitio':None}, explicacion=explicacion)
        return informe

    def test_titulos_primera_fila_y_abstencion_juntos_con_contenido_integro(self):
        # Variar el relleno obliga al mismo contenido a cruzar límites diferentes.
        for numero in (1, 5, 9, 13):
            informe = self.informe(numero)
            antes = copy.deepcopy(informe)
            paginas = self.paginas(renderizar_html(informe))
            with self.subTest(hipotesis=numero):
                self.misma_pagina(paginas, '4. Derivas por nivel y dirección', 'D1 / SX')
                self.misma_pagina(paginas, '5. Cortante basal por dirección', 'V1 / SX')
                self.misma_pagina(paginas, 'Abstenciones', 'SOLO-SOFTWARE: No se deduce')
                self.misma_pagina(paginas, '3. Periodos seleccionados',
                    'No disponible: no se proporcionaron resultados para esta categoría.')
                texto = ' '.join(paginas)
                for fila in ('D1 / SX', 'DY / SX', 'V1 / SX'):
                    self.assertEqual(texto.count(fila), 1)
                for etiqueta in ('0.002', '100.0', 'kN', 'FILA-OMITIDA-DE-PRUEBA',
                                 'LIMITE-FINAL', 'Trazabilidad y revisión', 'No se declara cumplimiento'):
                    self.assertIn(etiqueta, texto)
                for i in range(numero):self.assertIn(f'HIP-{i:03d}', texto)
                self.assertLessEqual(len(paginas), 4)
                self.assertEqual(informe, antes)

    def test_tabla_extensa_pagina_sin_perder_ni_duplicar_filas(self):
        filas = ''.join(f'<tr><td>FILA-{i:03d}</td><td>ETIQUETA-{i:03d}</td><td>{i}.25</td><td>kN</td></tr>'
                        for i in range(120))
        relleno = ''.join(f'<p>CONTEXTO-{i:02d}: texto sintético de relleno de presentación.</p>' for i in range(17))
        html = '<html><head><style>'+CSS+'</style></head><body>'+relleno
        html += '<h2>5. Cortante basal por dirección</h2><table><tr><th>ID</th><th>Etiqueta</th><th>Valor</th><th>Unidad</th></tr>'
        html += filas+'</table><h3>Abstenciones</h3><ul><li>ABSTENCION-FINAL de prueba.</li></ul></body></html>'
        paginas = self.paginas(html)
        self.misma_pagina(paginas, '5. Cortante basal por dirección', 'FILA-000')
        self.misma_pagina(paginas, 'Abstenciones', 'ABSTENCION-FINAL')
        texto = ' '.join(paginas)
        for i in range(120):
            self.assertEqual(texto.count(f'FILA-{i:03d}'), 1)
            self.assertEqual(texto.count(f'ETIQUETA-{i:03d}'), 1)
            self.assertIn(f'{i}.25', texto)
        self.assertGreaterEqual(len(paginas), 4)
        self.assertLessEqual(len(paginas), 7)

    def test_cadena_de_encabezados_y_lista_larga_no_se_convierte_en_bloque_indivisible(self):
        relleno = ''.join(f'<p>RELLENO-{i:02d}</p>' for i in range(25))
        lista = ''.join(f'<li>ITEM-{i:03d}: solo comprobación de software.</li>' for i in range(140))
        html = '<html><head><style>'+CSS+'</style></head><body>'+relleno
        html += '<h2>Hipótesis y límites</h2><h3>Abstenciones de la sección</h3><ul>'+lista+'</ul></body></html>'
        paginas = self.paginas(html)
        self.misma_pagina(paginas, 'Hipótesis y límites', 'ITEM-000')
        self.misma_pagina(paginas, 'Abstenciones de la sección', 'ITEM-000')
        texto = ' '.join(paginas)
        self.assertEqual(len(re.findall(r'ITEM-\d{3}:', texto)), 140)
        self.assertIn('ITEM-139', texto)
        self.assertLessEqual(len(paginas), 5)

    def test_estilo_previo_del_titulo_no_desaparece_al_reubicarlo(self):
        html = '<html><head><style>'+CSS+'</style></head><body>'
        html += ''.join(f'<p>ANTES-{i:02d}</p>' for i in range(26))
        html += '<h3 style="color: #123f54;">Abstención con estilo</h3><p>PRIMER-TEXTO-ESTILIZADO</p></body></html>'
        paginas = self.paginas(html)
        self.misma_pagina(paginas, 'Abstención con estilo', 'PRIMER-TEXTO-ESTILIZADO')
        self.assertEqual(' '.join(paginas).count('ANTES-'), 26)
