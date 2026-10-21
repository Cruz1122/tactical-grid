# Experimentos adversariales — casos 7–10

## Reproducción

Ejecuta desde la raíz del repositorio:

```bash
.venv/bin/python -m backend.tests.adversarial_experiments
```

El comando construye un estado válido de 6×6 mediante `prepare_scenario`, usa la misma posición para todas las comparaciones y emite JSON con acción, valor, profundidad, contadores y tiempo. El escenario está implementado en `backend/tests/test_adversarial.py::tactical_state`.

Posición: reina libre en `(3, 3)`; A1 estándar en `(3, 2)` y A2 torre en `(0, 1)`; B1 torre en `(3, 1)` y B2 estándar en `(0, 5)`; turno A; bases en las esquinas; sin reyes. B1 puede capturar a A1 después de que A1 recoja la reina. A2 puede capturar a B1 antes de que eso ocurra.

## Definición de métricas

- `nodes_generated`: sucesores legales materializados al expandir nodos; excluye la raíz. Se cuentan también hermanos materializados que luego no se visitan por un corte.
- `nodes_visited`: nodos cuya búsqueda recursiva comenzó; incluye la raíz.
- `nodes_evaluated`: hojas terminales o alcanzadas en el límite de profundidad que recibieron `evaluate`.
- `nodes_pruned`: ramas de sucesores inmediatos omitidas después de un corte alfa-beta. No estima ni suma descendientes que no llegaron a generarse.
- `depth_reached`: nivel máximo visitado, con la raíz en cero y cada acción completa sumando uno.
- `elapsed_seconds`: tiempo de pared medido con `perf_counter`; puede variar por equipo y carga.

Por esas definiciones, `nodes_generated` puede ser igual entre Minimax y alfa-beta aunque bajen las visitas y evaluaciones: los hermanos se materializan antes de recorrerlos.

## Caso 7 — decisión adversarial

A profundidad 1, Minimax recomienda que A1 avance a la reina (`(3, 3)`), con valor `930`. A profundidad 2, al considerar la respuesta de B1, recomienda que A2 capture la torre B1 en `(3, 1)`, con valor `90`. La captura intercepta la respuesta que capturaría al portador; el valor minimax de la alternativa de recoger la reina baja a `-10` ante la peor respuesta enemiga.

Esto demuestra en el estado concreto que aumentar la profundidad cambia una aproximación codiciosa por una captura defensiva. No se ha supuesto que cualquier captura sea buena: se calcula la transición y la respuesta con las reglas del motor.

## Caso 8 — Minimax frente a alfa-beta

Una ejecución local, misma posición y profundidad 3, orden normal:

| Algoritmo | Acción | Valor | Generados | Visitados | Evaluados | Podados | Tiempo (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Minimax | A2 captura B1 en `(3, 1)` | 1290 | 1198 | 1199 | 1094 | 0 | 0.382 |
| Alfa-beta | A2 captura B1 en `(3, 1)` | 1290 | 709 | 374 | 309 | 336 | 0.179 |

La decisión y el valor coinciden. Alfa-beta evaluó menos hojas y visitó menos nodos en esta ejecución; el tiempo es una medición puntual, no una garantía para todas las posiciones.

## Caso 9 — orden de acciones

Con alfa-beta, misma posición y profundidad 3:

| Orden | Acción | Valor | Generados | Visitados | Evaluados | Podados | Tiempo (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| normal | A2 captura B1 en `(3, 1)` | 1290 | 709 | 374 | 309 | 336 | 0.191 |
| reverse | A2 captura B1 en `(3, 1)` | 1290 | 485 | 281 | 236 | 207 | 0.127 |

El orden cambió visitas, hojas, podas y tiempo, pero no la acción ni el valor. Las pruebas también fuerzan valores empatados y comprueban que el desempate canónico no cambia al invertir la exploración.

## Caso 10 — profundidad

Una ejecución local de Minimax sobre la misma posición:

| Profundidad | Acción | Valor | Generados | Visitados | Evaluados | Tiempo (s) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | A1 avanza a la reina `(3, 3)` | 930 | 12 | 13 | 12 | 0.003 |
| 2 | A2 captura B1 en `(3, 1)` | 90 | 104 | 105 | 92 | 0.031 |
| 3 | A2 captura B1 en `(3, 1)` | 1290 | 1198 | 1199 | 1094 | 0.361 |
| 4 | A2 captura B1 en `(3, 1)` | 1290 | 12313 | 12314 | 11115 | 3.427 |

El salto de profundidad 1 a 2 cambia la acción; el valor no es monótono porque el horizonte y las respuestas disponibles cambian. En este escenario pequeño, profundidad 4 tardó unos 3.4 s y mantuvo la acción/valor de profundidad 3. En `scenarios/initial.json` (20×20), alfa-beta a profundidad 2 tuvo 49 acciones raíz, generó 2205 sucesores, visitó 1003 nodos, evaluó 953 hojas, podó 1203 ramas y tardó 1.327 s. No se extrapola ese tiempo a profundidad 4 ni se ejecutan profundidades mayores en el mapa inicial: la ramificación y el costo dependen del mapa y del estado.

## Alcance de la evidencia

En el árbol de trabajo no se encontraron `Primer proyecto.pdf` ni un archivo llamado `TacticalGrid_Reglas.md`; las referencias y criterios 7–10 se tomaron de `docs/busqueda-y-decision.md` y `docs/reglas-del-juego.md`. Por eso, los experimentos anteriores son casos válidos y reproducibles que cubren esos comportamientos, pero no se afirma que reproduzcan exactamente posiciones gráficas o datos ausentes de los documentos del profesor.
