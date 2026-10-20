# Búsqueda, decisión y experimentación

## Dos problemas distintos

### Navegación de una sola unidad

Entrada conceptual: escenario válido, `unit_id`, objetivo y parámetros de búsqueda. Solo esa pieza se mueve **hipotéticamente**; las demás unidades, obstáculos y reyes forman el entorno. No se intercalan turnos del rival entre pasos de la ruta. La salida es una **ruta sugerida**, no una secuencia garantizada de turnos reales.

Los sucesores deben aplicar los patrones y costos reales de la pieza. En especial, un deslizamiento entero de torre o alfil es **un movimiento**, aunque cruce varias casillas y sume sus costos.

Si una ruta hipotética pudiera capturar, hay dos posibilidades aceptables para la prueba: **excluir expresamente esas transiciones** o **simular todos sus efectos**, incluyendo reaparición, reina y ocupación. No se permite «capturar gratis» sin actualizar el estado del escenario explorado.

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

La segunda heurística la propone el equipo; todavía **no hay una fórmula acordada**. Para cada una se debe justificar qué estima, qué datos usa, su complejidad, si es admisible y en qué mapas puede orientar mal.

## Evaluación adversarial

Minimax alterna MAX y MIN sobre el **mismo motor y el mismo conjunto de reglas**. MAX intenta maximizar utilidad desde una perspectiva elegida; MIN la minimiza porque compite por su propio objetivo, no porque tenga reglas peores.

La función `evaluate` todavía debe definirse. Factores posibles: posesión de reina, proximidad a base/reina, jaques, capturas, unidades activas, peligro del portador y control territorial. Los pesos no pueden darse por medidos o validados antes de experimentar.

## Métricas y verificación

Para búsquedas de ruta registrar, como mínimo: éxito, camino, cantidad de movimientos, costo, estados generados, estados expandidos, máximo tamaño de frontera y tiempo de ejecución.

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

Estos casos son criterios de diseño y aceptación, **no resultados obtenidos todavía**.

## Requisito documental de los métodos

Los métodos deben documentar su propósito, precondiciones, postcondiciones y complejidad cuando corresponda. La intervención de IA y la validación del estudiante se declaran una sola vez por alcance en la documentación técnica (ver [motor-del-juego.md](motor-del-juego.md)); no se repiten como frases de relleno en cada docstring. La validación del estudiante no debe afirmarse hasta que un integrante la haya realizado personalmente. La sustentación exige que cada integrante pueda explicar y modificar los métodos.

**Referencias:** `Primer proyecto.pdf`, pp. 3–5 y 7–10; `TacticalGrid_Reglas.md`, sección 7.
