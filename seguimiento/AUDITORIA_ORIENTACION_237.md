# Auditoría independiente de orientación y niveles - 237

Fecha: 2026-10-21. Solo lectura de originales; sin API, ETABS ni Computer Use. No certifica ingeniería. Se aplicó la habilidad PDF para inspección visual y extracción local. No se modificó el borrador de Claude ni el producto.

## Dictamen para el piloto

**La evidencia favorece 3 estructural ↔ A arquitectónico; 2 ↔ C; 1 ↔ E. Confianza media-alta para ese sentido, pero no alcanza corroboración independiente por dos objetos asimétricos.** Se distingue entre una correspondencia favorecida por la escalera y una correspondencia probada por dos rasgos independientes. La cisterna no está identificada en arquitectura y el tanque no aporta un discriminante Y inequívoco. Por tanto D5 puede mantenerse como hipótesis explícita muy localizada; esta auditoría no la transforma en dato impreso o registro confirmado.

No se usó el residual de ejes para decidir el sentido: con 5+5 m en estructura y 3.15+1.85+1.85+3.15 en arquitectura, ambas reflexiones ajustan igual. Tampoco se tomó la declaración 3↔A del borrador como prueba.

## Fuentes y sistema de coordenadas

Todos son PDF de una página bajo `planos_muestra/proyecto_pueblo_libre/`. Coordenadas de este informe: puntos PDF en página visual apaisada, origen arriba a la izquierda; se aplicó la matriz de rotación de la página. No mezclar con las coordenadas de texto sin rotar usadas en calibración de Claude.

| Lámina | Archivo | Tamaño visual, pt | SHA-256 |
|---|---|---|---|
| E01/L0001 | Estructuras_Pueblo Libre1-Cimentación.pdf |3370 x 2384|ff669f23633b7c355bc7d89ea60809856df7e29a5b4019204307f7deef9ba8f5|
| E02/L0002 | Estructuras_Pueblo Libre1-Model.pdf |3370 x 2384|d655e6c5f2c8998a2049b300b83a65a62962c5de03a622bfd9978fd4a8f074fa|
| E03/L0003 | Estructuras_Pueblo Libre1.pdf |3370 x 2384|fb4284e82b7a55f4faeb4e9917269b37e94336c0788562873385e7e21c67a134|
| A01/L0004 | Arquitectura-Model1.pdf |2384 x 1684|1f2e8d9c2507cc85bbcd6d6cc9fc217baf4d272c6620417c1985eeb3d4b8be54|
| A02/L0005 | Arquitectura-Model2.pdf |2384 x 1684|f63d63ce7674c21b3437145cfde2f6ab66abe814c445c5c65873db99067b87bf|
| A03/L0006 | Arquitectura-Model3.pdf |2384 x 1684|ead656045a3c95739e2bd7cab3c5daddb6d1e42ebaa7aaf9afb6c34be07dce4a|

Las huellas coinciden con BORRADOR_CASO_08.json. También se leyeron INFORME_08.md y los PNG/textos de tmp/revision_arquitectura_229. Los recortes nuevos se generaron desde los PDF originales con PyMuPDF, no desde capturas del producto.

## Rasgos contrastados

### 1. Escalera: discriminante positivo

En la planta inferior de E02 (aligerado 2do/3er nivel), recorte visual `(1535,1460)-(1730,1830)`, el pequeño rectángulo con X está **encima** del hueco rectangular más largo. La C6 cruza la separación entre ambos, también por encima del eje central. El eje central 2 está a y≈1650 pt; la C6 está a y≈1630 pt. La escalera se encuentra a la derecha del eje H, consistente con la derecha del eje arquitectónico 2 al registrar H↔2.

En A02, recorte `(1545,520)-(1885,905)`, se repite el **pequeño hueco con X arriba del hueco largo**, y el elemento horizontal sobre el hueco largo está en el mismo lado superior de C. A03 repite esta disposición. La reflexión 3↔E llevaría el hueco pequeño debajo del largo y contradice esta asimetría. Esto favorece 3↔A de forma concreta y no por la simetría global.

La extensión del primer tramo de escalera hacia la derecha se aprecia en A01/A02, pero no se cuenta como segunda prueba independiente: E02 es planta de losa y su proyección no reproduce íntegramente el primer tramo arquitectónico. La geometría de un mismo núcleo no se presenta como dos objetos independientes.

### 2. Cisterna: compatible, sin contraprueba arquitectónica

E01 tiene una caja situada a la derecha de H y por encima del eje central 2: recorte `(1535,430)-(1740,880)`. Su borde inferior queda próximo al eje 2. El detalle TECHO CISTERNA de E03 respalda que esa caja es la cisterna: C3/C6, dimensiones y forma de techo. En E03 el título está en `(2134.6,2235.3)-(2348.2,2256.5)`.

A01 no rotula ni delimita una cisterna equivalente; la región tiene la escalera y acceso. Que una cisterna esté bajo el núcleo es compatible con 3↔A, pero no prueba el sentido. No debe inventarse una correspondencia de sus bordes en arquitectura. Tampoco la ausencia de una cisterna en planta arquitectónica de piso es una contradicción concluyente.

### 3. Tanque: evidencia de existencia, no discriminante suficiente de Y

A03 muestra TANQUE DE AGUA en `(1320.9,690.3)-(1411.9,719.1)` dentro de una caja aproximadamente entre B y D. Su contorno casi centrado en C conserva prácticamente la misma ubicación al reflejar Y. El título y +14.60 no determinan el sentido.

E03 muestra el corte del tanque y marcas NACE C2 cerca de F/G, alrededor del eje central; recorte `(1200,570)-(1530,940)`. No hay una planta de tanque inequívocamente acotada y enlazada al contorno de A03. Los nacimientos no deben transformarse automáticamente en las cuatro esquinas de la caja arquitectónica. Su ubicación y el contorno de A03 requieren revisión antes de localizar apoyos/masas. No se cuenta este rasgo como corroboración independiente de 3↔A.

## Conflictos y límites de registro

- El eje central a la derecha de E01/E02/E03 aparece como 1 aunque el izquierdo es 2. Las coordenadas y la posición distinguen el eje; no usar el 1 derecho como un cuarto eje.
- El eje F difiere entre E01 y E03. Esta auditoría no valida una geometría unificada copiando F de una a otra; afecta al detalle de tanque y a la colocación de elementos.
- La escalera es la principal evidencia discriminante disponible. Si se exige orientación probada por dos objetos independientes, queda pendiente una vista o indicación adicional que ubique la cisterna en A01 o vincule el tanque/apoyos E03 con A03. La incertidumbre residual es **reflexión Y global**, no traslación o escala entre cadenas de ejes; y localmente, ubicación exacta de apoyos del tanque y cisterna.

## Niveles 5.20 y 7.80

**Son hipótesis razonables para un piloto uniforme, no cotas impresas ni alturas verificadas.** A01 imprime NPT ±0.00; A02 imprime +2.60 y su título agrupa segundo, tercer y cuarto piso; A03 imprime TECHO NTT +10.40. Las ubicaciones de texto verificadas incluyen A02 `(780.0,447.4)-(848.3,458.3)` para +2.60 y A03 el bloque `(799.9,692.2)-(1406.0,728.6)` para techo/tanque y sus NTT.

La progresión 0, 2.60, 5.20, 7.80, 10.40 cierra exactamente cuatro intervalos de 2.60. A02 no imprime los NPT de tercero/cuarto y su planta típica no constituye un corte vertical. Después de +2.60, el total restante 7.80 m admite muchas distribuciones de los tres entrepisos; la uniformidad es una elección sustentada por tipicidad y extremos, no una deducción única. Conservar estados `hipotesis_progresion_uniforme` de N2/N3; declarar igualmente uniforme el intervalo 7.80→10.40. Los nombres N0…N4 son convención del modelo, y losa/techo estructural deben asignarse explícitamente a cada elevación.

La discrepancia E03 NT +10.35 frente a A03 NTT +10.40 no se resuelve suponiendo acabados de 5 cm sin fuente. La diferencia entre altura de cuba/apoyos del corte y NTT +14.60 también queda abierta. Ninguna invalida por sí sola la hipótesis uniforme de pisos, pero impide usar el corte de tanque como verificación exacta del techo o de su cota superior.

## Evidencia auxiliar reproducible

Recortes en `tmp/auditoria_orientacion_237/`: E01_cisterna_original.png, E02_escalera_original.png, E03_apoyos_tanque_original.png, A01_escalera_original.png, A02_escalera_original.png, A03_tanque_original.png. Los sufijos `*-blocks.json` conservan extracción de bloques de cada PDF para inspección; sus coordenadas están sin rotar y deben transformarse con page.rotation_matrix antes de compararlas con este informe.

**Acción admisible para avanzar:** adoptar explícitamente la orientación favorecida y alturas uniformes como hipótesis de piloto, con estas limitaciones; no etiquetarlas como lectura aprobada. Si el protocolo exige dos rasgos independientes, la evidencia local actual no satisface ese umbral y D5 debe seguir pendiente.
