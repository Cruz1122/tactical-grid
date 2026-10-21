# TacticalGrid — Casos 7–10: decisión adversarial, poda y profundidad

**Resultados de los casos 7–10.** Las mediciones se almacenaron en `outputs/adversarial_comparacion.json`, generadas sobre el estado de `backend.tests.test_adversarial.tactical_state` después de modificar la función de utilidad para incluir distancias topológicas. El objetivo de los cuatro casos es comparar **decisiones bajo un adversario**, no rutas independientes de una sola ficha.

## Escenario táctico compartido

Tablero 6×6, turno A (MAX): reina libre en `(3,3)`; `A1` tipo `estandar` en `(3,2)`; `A2` tipo `rook` en `(0,1)`; `B1` tipo `rook` en `(3,1)`; `B2` tipo `estandar` en `(0,5)`. No se supone que la dama se recoge mágicamente al capturar otra pieza; las acciones son legales según `action_successors`.

### Caso 7 — No siempre conviene avanzar a la reina

Con profundidad 1, Minimax recomendó mover `A1` a `(3,3)` (valor **362**); el algoritmo ve solo la primera acción, que parece favorable por cercanía. Con profundidad 2, al considerar una respuesta rival, recomendó `A2` a `(3,1)` y capturar a `B1` (valor **315**). **Interpretación:** una amenaza táctica del rival puede volver preferible interceptar o capturar. Los valores corresponden a horizontes distintos, por lo que no constituyen una comparación directa de calidad.

### Caso 8 — Equivalencia Minimax/alfa-beta

A profundidad 3, ambos escogieron `A2` → `(3,1)` con utilidad **845**. Minimax evaluó **1094** hojas (1198 sucesores generados), y alfa-beta evaluó **328** hojas (706 sucesores generados y 314 ramas inmediatas podadas). Por tanto la implementación ensayada conserva la decisión en el caso medido y reduce trabajo. Esto no sustituye las pruebas de igualdad sobre múltiples estados.

### Caso 9 — Influencia del orden de acciones

Mismo estado, misma utilidad, misma profundidad 3, dos órdenes de exploración:

| Orden alfa-beta | Acción | Valor | Generados | Evaluados | Podados | Tiempo |
|---|---|---:|---:|---:|---:|---:|
| Normal | A2 → (3,1) | 845 | 706 | 328 | 314 | 0,127 s |
| Inverso | A2 → (3,1) | 845 | 385 | 204 | 146 | 0,067 s |

**Lectura correcta:** el orden inverso evaluó menos hojas en esta posición, aunque el contador local de ramas podadas sea menor; esos contadores no miden la totalidad de descendientes evitados. Los resultados de tiempo no constituyen una aceleración universal; dependen del árbol y del sistema.

### Caso 10 — Horizonte de profundidad

| Profundidad Minimax | Acción recomendada | Utilidad | Hojas evaluadas | Tiempo aprox. |
|---:|---|---:|---:|---:|
| 1 | A1 → (3,3) | 362 | 12 | 0,003 s |
| 2 | A2 → (3,1) | 315 | 92 | 0,022 s |
| 3 | A2 → (3,1) | 845 | 1094 | 0,272 s |
| 4 | A2 → (3,1) | 820 | 11115 | 2,689 s |

La acción cambia al considerar la respuesta del rival. Pasar de profundidad 3 a 4 multiplicó las hojas evaluadas en la muestra, sin cambiar la acción. El valor de la utilidad no crece monótonamente: el horizonte cambia qué amenazas y ventajas se observan.

## Reproducción de los experimentos

Partir del mismo estado táctico y configurar el algoritmo (`minimax`/`alpha_beta`), la profundidad y el orden en el panel de decisión. Registrar acción, valor, nodos generados, evaluados, podados, profundidad alcanzada y tiempo. Para verificar automáticamente usar el script de experimentos existente cuando esté disponible y consultar el JSON serializado. La comparación requiere mantener los parámetros no analizados constantes.

La función de utilidad, la semántica de MAX/MIN y la condición de poda `α ≥ β` se describen en el [documento técnico](documento-tecnico.md).

## Límite: buenas decisiones locales no garantizan terminar una partida

La simulación adicional con el escenario 20×20 y seis fichas `estandar` detectó repetición tras 105 acciones a profundidad 2, pese a que las acciones individuales fueron legales. Ni el éxito de las pruebas unitarias ni la reducción de nodos por alfa-beta autoriza a afirmar que la estrategia completa sea perfecta. Una regla de empate por repetición **no existe** en el motor; el script de diagnóstico la usa solo para evitar bucles durante pruebas.