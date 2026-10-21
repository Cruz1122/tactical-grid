# TacticalGrid — Informe reproducible de verificación

**Corte técnico:** 21 de octubre de 2026.  
**Objeto:** copia ZIP de `develop` recibida del equipo y modificada en el sandbox; no afirmar que todos los entornos de despliegue reproducen exactamente los mismos tiempos.  
**Entorno observado:** Linux, Python 3.13.5, pruebas `unittest`, motor FastAPI/HTTP local. Datos de referencia: `outputs/busqueda_comparacion_real.json`, `outputs/adversarial_comparacion.json`, `outputs/demo_partida_6x6.json` y `outputs/demo_adversarial_20x20.json`.

## 1. Alcance, resultados y límites

**Ejecutado realmente:** `python -m unittest discover -s backend/tests -q` → **177 pruebas, OK**; `python -m uvicorn backend.main:app` y solicitud HTTP `GET /api/state` → **200**. Estos resultados prueban la ejecución de la suite y la disponibilidad de la API para esta versión. **No significan cobertura del 100 % de caminos, invulnerabilidad ni validación humana individual.**

Se midieron cinco experimentos de navegación con el código Python real. En el escenario 6×6 la simulación de alfa-beta terminó una partida con victoria oficial de B. En el escenario 20×20 se detectó un estado repetido después de 105 acciones en el script externo: **no fue un resultado terminal del motor**. No se aplicó una regla nueva de empate por repetición.

**Validación visual todavía pendiente:** la navegación del navegador automatizado a `127.0.0.1` fue bloqueada por política (`ERR_BLOCKED_BY_ADMINISTRATOR`). Los dos diagramas del manual están derivados de JSON, **no son screenshots**. La revisión de capturas genuinas debe hacerse en equipo con acceso a Phaser CDN según [capturas-por-validar.md](capturas-por-validar.md).

## 2. Batería de navegación — medidas reales

Los experimentos se ejecutaron sobre los escenarios del banco (20×20), con la unidad y el objetivo configurados en `prueba`. Cada operación volvió a empezar desde el mismo estado preparado. Los tiempos son de **una medición de referencia**, no promedios con intervalos de confianza; se incluye el JSON de salida para auditar.

| Caso y algoritmo | Éxito | Movimientos | Costo | Generados | Expandidos | Frontera | Tiempo aprox. |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 · BFS | Sí | 60 | 60 | 129 | 124 | 5 | 0,096 s |
| 1 · DFS | Sí | 60 | 60 | 184 | 183 | 5 | 0,183 s |
| 2 · BFS | Sí | 10 | 64 | 173 | 152 | 23 | 0,211 s |
| 2 · UCS | Sí | 12 | 12 | 201 | 174 | 29 | 0,198 s |
| 3 · A* Manhattan | Sí | 22 | 22 | 307 | 245 | 63 | 0,396 s |
| 3 · A* propia | Sí | 22 | 22 | 307 | 245 | 63 | 0,396 s |
| 4 · A* Manhattan | Sí | 27 | 32 | 303 | 257 | 60 | 0,558 s |
| 4 · A* propia | Sí | 27 | 32 | 254 | 197 | 68 | 0,299 s |
| 5 · Beam k=1 | No | — | — | 13 | 10 | 1 | 0,010 s |
| 5 · Beam k=2 | Sí | 19 | 19 | 59 | 37 | 2 | 0,030 s |
| 5 · Beam k=4 | Sí | 19 | 19 | 112 | 73 | 4 | 0,084 s |
| 5 · Beam k=8 | Sí | 19 | 19 | 180 | 139 | 8 | 0,138 s |

### Interpretación que debe defender el equipo

**Caso 1:** BFS y DFS hallaron rutas de 60 movimientos, pero DFS generó 184 estados frente a los 129 de BFS. La diferencia de exploración **sí** quedó demostrada; este mapa en particular no mostró una diferencia de longitud entre las rutas, por lo que no debe afirmarse que aquí DFS encontró una ruta más larga.

**Caso 2:** BFS encontró 10 movimientos de costo **64**, mientras UCS empleó 12 movimientos para costo **12**. Este caso sí demuestra inequívocamente que la ruta más corta en acciones no es necesariamente la más barata.

**Caso 3:** una barrera obliga a rodear; ambas heurísticas de A* coincidieron en camino/costo y métricas. No se inventó ventaja donde no se observó.

**Caso 4:** ambas heurísticas lograron ruta de costo **32**; la heurística propia redujo expandidos de 257 a 197 en **esta instancia**, a pesar de frontera máxima mayor (68 frente a 60). No garantiza mejoras en todos los escenarios.

**Caso 5:** `k=1` no encontró solución; desde `k=2` se encontró ruta de 19 movimientos/costo 19. Es un ejemplo directo del riesgo de descartes en Beam, no un bug de esa técnica.

Todos los resultados anteriores se registraron en `outputs/busqueda_comparacion_real.json`, con ruta concreta, costo y contadores originales de la función; pueden ejecutarse nuevamente desde el JSON sin cambiar el código.

## 3. Minimax y alfa-beta — medidas reales

Se usó el estado del test `backend.tests.test_adversarial.tactical_state`, no los dos escenarios anteriores. El bando A actúa al inicio; la reina está libre, el tablero es 6×6, A1 estándar está en `(3,2)`, A2 torre en `(0,1)`, B1 torre en `(3,1)` y B2 estándar en `(0,5)`.

| Prueba | Algoritmo/orden/d | Acción elegida | Valor | Hojas evaluadas | Podados | Tiempo aprox. |
|---|---|---|---:|---:|---:|---:|
| Decisión inmediata | Minimax d=1 | A1 → (3,3) | 362 | 12 | 0 | 0,0035 s |
| Respuesta enemiga | Minimax d=2 | A2 → (3,1), captura B1 | 315 | 92 | 0 | 0,026 s |
| Igualdad | Minimax d=3 | A2 → (3,1) | 845 | 1094 | 0 | 0,265 s |
| Igualdad y poda | Alfa-beta d=3 | A2 → (3,1) | 845 | 328 | 314 | 0,126 s |
| Orden inverso | Alfa-beta reverse d=3 | A2 → (3,1) | 845 | 204 | 146 | 0,067 s |
| Profundidad alta | Minimax d=4 | A2 → (3,1) | 820 | 11115 | 0 | 2,689 s |

La jugada recomendada por Minimax y alfa-beta a d=3 y su **valor 845 coinciden**, mientras alfa-beta evaluó menos hojas. Invertir el orden cambió evaluaciones y podas, **no** la acción/valor. La utilidad de d=4 bajó a 820 aun escogiendo la misma acción; más profundidad no implica valoración monotónica.

**Precisión de contadores:** `nodes_pruned` cuenta sucesores inmediatos excluidos por corte, no el número de todas las posiciones descendientes que hipotéticamente podrían haber existido. Por ello las cifras de podados pueden ser menores aun cuando alfa-beta con orden inverso evalúa menos hojas.

## 4. Autopartida y limitación estratégica constatada

| Escenario real | Estrategia | Acciones | Fin observado | Ganador del motor |
|---|---|---:|---|---|
| `scenarios/partida/mapa_partida_presentacion.json` (6×6) | Alfa-beta, d=2 | 24 | Estado terminal | B |
| `scenarios/adversarial/externo_adversarial_3v3.json` (20×20, usado en simulación de partida) | Alfa-beta, d=2 | 105 | Detector externo de repetición | Ninguno |

El segundo caso **no** se convierte automáticamente en empate: el juego solo declara sus propios finales. La repetición se reporta honestamente como limitación de la política de evaluación y horizonte bajo un conflicto entre bandos. La decisión de introducir una regla formal de repetición corresponde al equipo y requeriría cambios explícitos de contrato y pruebas.

Para reproducir desde la raíz:

```bash
python -m scripts.self_play scenarios/partida/mapa_partida_presentacion.json --depth 2 --max-turns 40
python -m scripts.self_play scenarios/adversarial/externo_adversarial_3v3.json --depth 2 --max-turns 120
```

Estos comandos ejecutan el script de diagnóstico y dejan que el motor valide acciones. Para las cifras del informe, consulta los JSON existentes bajo `outputs/`.

## 5. Estado, validez de las rutas y resistencia a errores

Las pruebas cubren validadores de escenario, costos, movimientos, transiciones, rutas, decisiones, atomicidad de carga, equivalencia Minimax/alfa-beta y casos de regresión. Los casos de rechazo intencional del banco (`scenarios/error/`) deben permanecer en el repositorio como evidencia de validación: **no se eliminan solo porque no sean escenarios jugables**.

Un estado válido no basta para afirmar «algoritmo correcto»: se comprueba que el camino reconstruido usa sucesores legales reales, que la suma de costos corresponde al JSON y que el objetivo está satisfecho. También se comprueba que las peticiones `/api/search` y `/api/adversarial` no ejecutan sus recomendaciones en `current_state`.

## 6. Qué queda por verificar antes del squash merge

- Capturar y **revisar manualmente** pantallas reales con Phaser, incluyendo resultados de búsqueda y adversarial.
- Completar nombres del equipo y validar **personalmente** los docstrings y la declaración de IA generativa.
- Reproducir los diez casos del profesor en el ordenador de sustentación, incluida una carga de JSON externo desconocido.
- Aceptar conscientemente el límite de 20×20 o mejorar la política **sin inventar reglas de victoria o empate**.
- Ejecutar la suite después de cualquier cambio final y registrar commit, entorno y fecha de la ejecución.

## 7. Fuentes de esta verificación

Código Python de `backend/`, HTML/JS de `frontend/`, resultados serializados `outputs/*.json` y la rúbrica `Primer proyecto.pdf` (métricas, verificación, casos 1–10 y entregables). Los números presentados se derivan de ejecuciones reales de estas fuentes; las fórmulas y sus garantías se discuten en el [documento técnico](documento-tecnico.md). Las validaciones humanas pendientes no se declaran completadas.