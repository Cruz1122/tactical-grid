# Búsqueda, decisión y experimentación

## Dos problemas distintos

### Navegación de una sola unidad

Entrada conceptual: escenario válido, `unit_id`, objetivo y parámetros de búsqueda. Solo esa pieza se mueve **hipotéticamente**; las demás unidades, obstáculos y reyes forman el entorno. No se intercalan turnos del rival entre pasos de la ruta. La salida es una **ruta sugerida**, no una secuencia garantizada de turnos reales.

Los sucesores deben aplicar los patrones y costos reales de la pieza. En especial, un deslizamiento entero de torre o alfil es **un movimiento**, aunque cruce varias casillas y sume sus costos.

Las rutas hipotéticas conservan las capturas legales y simulan todos sus efectos mediante el motor: reaparición, cambio de portador y retorno de la reina a `recurso_spawn` cuando capturan al portador. No se omiten ni se aplican «capturas gratis» sin actualizar el estado explorado; la búsqueda no alterna turnos.

### Decisión adversarial

Entrada conceptual: estado completo y profundidad de análisis. La acción elegida pertenece a **cualquiera de las unidades del bando activo**. Tras esa acción juega el otro bando y ambos pueden cambiar posiciones, reyes amenazados y posesión de la reina.

No debe limitarse a seguir una ruta: interceptar un portador, dar jaque, romper un bloqueo o impedir una recogida pueden ser acciones estratégicamente superiores.

## Algoritmos y compromisos

| Método | Qué prioriza | Propiedad / limitación |
| --- | --- | --- |
| BFS | Menor número de movimientos | En un grafo no ponderado, obtiene el mínimo número de transiciones; no necesariamente menor costo de terreno |
| DFS | Profundizar por una rama | No garantiza la ruta más corta ni más económica |
| UCS | Menor suma de costos de acciones | Con costos positivos y manejo correcto de visitados/relajación, busca costo mínimo |
| A* | `f(n) = g(n) + h(n)` | La optimalidad depende de las propiedades de `h` y de la implementación |
| Beam Search | Conservar solo `k` candidatos por selección | Puede descartar rutas necesarias y no garantiza solución óptima ni completa |
| Minimax | Mejor acción ante la respuesta racional rival | Su resultado está condicionado por evaluación y profundidad limitada |
| Alfa-beta | El mismo valor minimax con poda | Reduce ramas visitadas; no cambia el objetivo matemático de Minimax |

Valores mínimos de Beam para comparar: `k = 1, 2, 4, 8`. En Minimax/alfa-beta, mantener la misma función de utilidad, profundidad y desempate permite comprobar igualdad de acción/valor. El orden de generación influye en cuánto poda alfa-beta.

## Heurísticas

A* usa costo acumulado `g(n)` y estimación restante `h(n)`. Deben existir al menos **dos** heurísticas: Manhattan puede ser una de ellas, pero **no se debe asumir que sea admisible** para caballo, torre o alfil. Estas piezas pueden alcanzar posiciones lejanas con pocos movimientos y costos que no respetan una estimación basada en pasos ortogonales.

La segunda heurística **ya está implementada**: mínimos de terreno por filas y columnas para `estandar`, y cotas geométricas escaladas por el costo mínimo para caballo, torre y alfil. Su definición y justificación están en [documento-tecnico.md](documento-tecnico.md).

## Evaluación adversarial

Minimax alterna MAX y MIN sobre el **mismo motor y el mismo conjunto de reglas**. MAX intenta maximizar utilidad desde una perspectiva elegida; MIN la minimiza porque compite por su propio objetivo, no porque tenga reglas peores.

`backend/algorithms/evaluation.py` implementa `evaluate(state, side)` con puntuación terminal, posesión, proximidad normalizada a base/reina, piezas activas, jaque con reina libre y seguridad inmediata del portador. Además utiliza distancias topológicas estáticas, coordinación de perseguidores e interceptación del portador. Los pesos son valores manuales experimentales: no se afirman optimizados globalmente.

## Métricas y verificación

Para búsquedas de ruta registrar, como mínimo: validez de entrada y motivo si es inválida, éxito, camino, cantidad de movimientos, costo, estados generados, estados expandidos, máximo tamaño de frontera y tiempo de ejecución. `states_generated` incluye el origen; `states_expanded` cuenta nodos extraídos que no eran meta; `max_frontier` incluye el tamaño inicial. El tiempo en segundos incluye preparación, exploración y reconstrucción de ruta.

Para decisión adversarial registrar: acción elegida, valor obtenido, nodos generados/evaluados/podados, profundidad alcanzada y tiempo. La comparación debe usar estados iniciales, parámetros y desempates reproducibles.

Verificar siempre:

- Todo desplazamiento del camino es legal para la pieza seleccionada.
- Los costos reportados se calculan desde el escenario, no de valores inventados.
- Ningún movimiento atraviesa bloqueos prohibidos.
- El último estado cumple el objetivo solicitado.
- No se generan estados inválidos.
- Las decisiones adversariales incluyen únicamente acciones legales.

## Casos experimentales exigidos

El PDF requiere demostrar diez situaciones reproducibles, no solo ejecutar algoritmos una vez:

1. BFS frente a DFS: exploraciones diferentes.
2. BFS frente a UCS: ruta de menos movimientos frente a menor costo.
3. Barrera que obliga a rodear una meta aparentemente cercana.
4. A* con dos heurísticas sobre el mismo problema.
5. Beam Search con variación del ancho `k`.
6. Estados con igual posición física pero distinta información adicional.
7. Jugada adversarial más conveniente que avanzar directamente a la reina.
8. Minimax y alfa-beta con igual valor y acción; poda observable.
9. Efecto del orden de generación de acciones sobre la poda.
10. Efecto de cambiar la profundidad en decisión, nodos y tiempo.

Los casos 7–10 tienen estados pequeños reproducibles y resultados medidos en [experimentos-adversariales.md](experimentos-adversariales.md); no se afirma que sus datos reproduzcan una posición exacta del PDF que no está disponible en el árbol local.

## Requisito documental de los métodos

Los métodos relevantes contienen los siete elementos del PDF dentro de sus docstrings: `Purpose`, `Preconditions`, `Postconditions`, `Complexity`, `AI usage`, `AI intervention` y `Student validation`. La redacción explicativa está en español y la validación personal del estudiante sigue pendiente hasta que cada integrante la realice. Véase [uso-de-ia.md](uso-de-ia.md).

**Referencias:** `Primer proyecto.pdf`, pp. 3–5 y 7–10; `TacticalGrid_Reglas.md`, sección 7.