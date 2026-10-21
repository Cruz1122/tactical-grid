# TacticalGrid — Documento técnico

**Sistemas Inteligentes I · Proyecto 1 · UCaldas**  
**Versión de referencia:** octubre de 2026.  
**Autoría:** equipo de TacticalGrid. El uso sustancial de IA en código y documentación se detalla en la [declaración de IA](uso-de-ia.md).

> **Alcance.** Se describe la implementación de `backend/` y `frontend/` y se presentan mediciones reproducibles bajo las condiciones indicadas. La política adversarial es aproximada y no garantiza victoria en todos los escenarios.

## 1. Pregunta, objetivos y metodología

La pregunta central del documento del profesor es cómo cambia la toma de decisiones al pasar de encontrar *una* ruta, minimizar su costo, utilizar información heurística y finalmente competir contra un rival que también actúa. TacticalGrid conserva un único entorno: cuadrícula, terrenos transitables y bloqueados, bases A y B, recurso neutral —la reina— y unidades de ambos equipos. Cada módulo resuelve un problema **distinto**:

| Tipo de prueba JSON | Decisión producida | ¿Quién actúa durante el cálculo? | ¿Modifica la partida? |
|---|---|---|---|
| `busqueda` | Ruta de una unidad hacia `(fila, columna)` | Solo la unidad elegida hipotéticamente; otras piezas son el entorno | No |
| `adversarial` | Mejor acción legal del turno según la profundidad y la utilidad | Los dos bandos alternan en el árbol; se consideran todas las piezas activas | No |
| `partida` | Acciones de una partida real | Se aplica una acción por turno; la autopartida consulta recomendaciones sucesivas | Sí, mediante `/api/move` o `/api/collect` |

**No son sinónimos.** El recorrido de una búsqueda no asegura una secuencia de turnos real frente a un rival; la respuesta de Minimax no es una partida completa; el modo partida sí actualiza el estado oficial.

### Arquitectura realmente implementada

`backend/scenarios.py` prepara y normaliza escenarios externos; `backend/game/validation.py` valida el contrato y las invariantes; `backend/game/movement.py` calcula movimientos legales y costos; `backend/game/engine.py` implementa sucesores y transiciones; `backend/algorithms/` contiene BFS, DFS, UCS, A*, Beam, Minimax, alfa-beta, heurísticas y verificación; `backend/main.py` expone FastAPI; `frontend/index.html`, `styles.css`, `api.js` y `scene.js` muestran controles, tablero, acciones y métricas.

El frontend y la API comparten origen HTTP. Los resultados oficiales proceden del backend, no de rutas simuladas en JavaScript. La interfaz usa Phaser y KaTeX cargados desde CDN: **la visualización gráfica requiere conectividad a esos recursos** bajo la configuración actual.

## 2. Formato JSON y representación de estados

Se mantiene el contrato externo del profesor: `version`, `mapa.filas`, `mapa.columnas`, `tipos_terreno`, `terreno`, `bases.A`, `bases.B`, `recurso`, `unidades`, `turno`, `juego.portador_recurso` y el campo opcional `prueba`. El esquema se acepta sin incorporar coordenadas de escenarios concretos al algoritmo.

Un estado preparado incluye adicionalmente información para implementar las reglas del juego: `spawn` por unidad, `activo`, `recurso_spawn`, reyes si se configuran, y `juego.estado`/`juego.resultado`. Los campos agregados no sustituyen ni renombran las claves JSON exigidas.

En particular, dos estados con la misma posición de una ficha **no son equivalentes** si cambian el turno, el portador, la actividad de una unidad, la ubicación de la reina, la configuración de reyes o el resultado. `state_key` compone una representación inmutable y determinista de esas partes; `static_state_key` permite compartir la descripción fija del escenario entre estados de una búsqueda. Ello evita visitar erróneamente como «iguales» posiciones dinámicamente distintas.

### Validación atómica

`prepare_scenario` y los validadores comprueban dimensiones, matriz, catálogo y costos positivos de terrenos transitables, ubicaciones, identificadores únicos, bandos, ocupaciones, portador y demás coherencias del motor. El endpoint de carga prepara primero un **estado candidato**; solo después de validarlo sustituye `initial_state` y `current_state` bajo bloqueo. Un JSON inválido recibe error sin destruir la partida previa.

**Decisión propia importante:** identificadores de tipo desconocidos pero textuales se normalizan a `estandar` durante la preparación, tal como se implementó en `backend/scenarios.py`; alias conocidos `caballo`, `torre` y `alfil` mantienen sus movimientos equivalentes a `knight`, `rook` y `bishop`. No se corrige ni elimina este comportamiento por ser diferente del ajedrez clásico.

### Estados y transiciones

Para una acción del motor, el flujo es: validar la acción → copiar el estado → mover/capturar/recoger cuando corresponda → resolver actividad y reaparición → alternar turno → comprobar victoria/empate → validar estado resultante. Las acciones inválidas no dejan mutaciones parciales. La navegación emplea `hypothetical_move` y `unit_successors` sin turnos enemigos; Minimax y alfa-beta emplean `action_successors` y la transición adversarial del motor.

## 3. Reglas de movimiento y función de costo

Para un recorrido hipotético P con aristas e, el costo acumulado es **G(P) = Σ c(e)**. El costo de cada casilla proviene del catálogo `tipos_terreno` del JSON, sin penalizaciones secretas en BFS/UCS/A*.

| Unidad | Geometría de movimiento | Costo de un movimiento | Particularidad |
|---|---|---|---|
| `estandar` | Una casilla horizontal o vertical | Costo de la casilla destino | Tipo de respaldo cuando hay un nombre genérico no reconocido |
| `knight` | Salto en L: (±2, ±1) o (±1, ±2) | Costo de destino | Salta sobre casillas intermedias |
| `rook` | Línea horizontal o vertical | Suma de todas las casillas recorridas excepto el origen | No atraviesa bloqueos |
| `bishop` | Línea diagonal | Suma de todas las casillas recorridas excepto el origen | No atraviesa bloqueos |

Una captura ocurre al terminar en casilla ocupada por enemigo: el capturado reaparece en su `spawn` **si está libre**; de lo contrario permanece inactivo hasta poder reaparecer. Si portaba la reina, esta vuelve a su **`recurso_spawn` original**, no a la casilla de captura; el atacante no se hace portador automáticamente. Si el rey propio está en jaque no se puede recoger la reina, pero sí mover, conservarla y ganar entregándola legalmente. Los reyes son opcionales, inmóviles y no capturables. La recogida explícita (`collect`) es una acción que consume turno.

Las capturas hipotéticas de la búsqueda utilizan los efectos del motor, aunque ello no implica que una ruta sea una partida real garantizada.

## 4. Algoritmos de navegación: qué optimiza cada uno

Se explora un grafo implícito de estados. Cada arista representa una acción **completa** de la pieza seleccionada: una torre que se desliza cinco casillas recorre una arista, no cinco movimientos BFS. Definimos *V* como el número de estados alcanzables, *E* como el número de transiciones y *b* como la ramificación máxima del estado.

### BFS — búsqueda en anchura

Mantiene una cola FIFO (`collections.deque`). Descubre por niveles y marca visitados por clave de estado. Si encuentra solución, minimiza **el número de acciones**, no la suma de terreno. Registra generados, expandidos, frontera máxima, tiempo, longitud y costo real de la ruta. Complejidad de grafo explícito: O(V+E) tiempo y O(V) almacenamiento, más el costo de producir y copiar cada sucesor.

### DFS — búsqueda en profundidad

Mantiene una pila LIFO, con orden determinista de sucesores. Sirve para demostrar el efecto del orden y la estrategia de exploración; no garantiza menos movimientos ni costo menor. Con visitados evita ciclos infinitos en grafos finitos. Complejidad de grafo explícito: O(V+E) en el peor caso con visitados, hasta O(V) almacenamiento; su recorrido depende del orden.

### UCS — búsqueda de costo uniforme

Utiliza `heapq` para priorizar la menor distancia acumulada g(n). Si alcanza el mismo estado con menor g, relaja la ruta y actualiza su padre. Las entradas antiguas del heap se ignoran. Con costos de transición estrictamente positivos encuentra un costo mínimo al extraer la meta de la cola. En un grafo explícito con heap, una referencia aproximada es O((V+E) log V), sin ocultar el costo de materializar transiciones o gestionar entradas repetidas.

**Experimento obligatorio:** un corredor corto sobre terreno caro frente a otro más largo y barato. BFS minimiza movimientos; UCS puede seleccionar más movimientos con menor costo.

## 5. A*: dos heurísticas realmente implementadas

A* ordena la frontera con **f(n) = g(n) + h(n)**. El término g es el costo acumulado real del terreno; h debe estimar el costo aún necesario desde **cada posición actual** hasta la meta. La estimación no es una constante durante el recorrido.

### 5.1. Primera heurística: Manhattan

**hM(n) = |fila_actual − fila_objetivo| + |columna_actual − columna_objetivo|**.

Información utilizada: coordenadas del estado y del objetivo, sin inspeccionar obstáculos ni precios. Costo computacional O(1) por evaluación. Se comporta intuitivamente con `estandar` cuando cada paso cuesta al menos 1, pero **no es universalmente admisible**: para caballo un salto `(0,0)→(2,1)` cuesta una sola casilla de destino y Manhattan vale 3; con terrenos baratos inferiores a 1 también puede sobreestimar. Para torre/alfil, la sobreestimación depende de la geometría y de los costos (por ejemplo, diagonal de alfil con costo unitario). A* con esta heurística se usa como **comparación experimental**; no prometemos optimalidad general.

### 5.2. Segunda heurística: geometría de cada unidad y mínimos de terreno

Se calcula `cmin`, el menor costo positivo de una celda transitable, además de los costos mínimos `min_fila[i]` y `min_columna[j]`. `heuristics.py` mantiene las fórmulas siguientes. Sea Δf la diferencia absoluta de filas y Δc la de columnas:

| Pieza | Heurística propia | Justificación de cota inferior |
|---|---|---|
| `estandar` | Σ mínimos de **cada fila** que necesariamente se entra + Σ mínimos de **cada columna** que necesariamente se entra | Cada acción cambia solo fila o columna; para alcanzar el destino se cruzan esas coordenadas como mínimo una vez |
| `rook` | `cmin · (Δf + Δc)` | Toda variación ortogonal exige atravesar al menos esa cantidad de casillas, aun con deslizamientos largos |
| `bishop` | `cmin · max(Δf, Δc)` | Un paso diagonal cambia como máximo una unidad por eje; casillas de color incompatible pueden ser inalcanzables |
| `knight` | `cmin · max(ceil((Δf+Δc)/3), ceil(max(Δf,Δc)/2))` | Un salto en L cambia Manhattan como máximo 3, y un eje como máximo 2 |

La formulación estima *costo*, no distancia visual. Los obstáculos y terrenos caros pueden hacer que el costo real sea mayor. **Admisibilidad:** los términos no superan las necesidades geométricas mínimas valoradas a costo inferior; para `estandar`, mínimos por fila/columna son cotas de los pasos obligatorios. **Consistencia:** en una arista legal, la disminución máxima de h queda acotada por el costo de las casillas que la acción cruza o alcanza. Estas garantías se aplican al modelo de costo de movimiento implementado, no implican que A* encuentre solución cuando no existe.

**Ejemplo explicable:** en el tablero 3×3 de costos `[[1,2,1],[3,4,3],[1,2,1]]`, desde `(0,0)` hasta `(2,2)` la Manhattan vale **4**, pero la segunda heurística para `estandar` vale **(3+1)+(2+1)=7**. No «sabe» el camino: suma los pisos de costo que inevitablemente se pagan al atravesar esas filas y columnas. Desde una posición distinta recalcula únicamente los índices aún pendientes.

**Complejidad:** `_terrain_minima` recorre una matriz F×C y requiere O(FC) tiempo y O(F+C) espacio auxiliar. Usando esos mínimos precalculados, la evaluación de `estandar` efectúa sumas de hasta O(Δf+Δc); las ramas de otras piezas son O(1). No es correcto afirmar que el cálculo de la heurística `estandar` sea O(1) solo porque se precalcularon los mínimos.

## 6. Beam Search: poda por ancho, no poda alfa-beta

Beam se organiza por niveles y conserva únicamente los **k estados distintos con mejor h(n)** de cada nivel, con costo real como desempate. Se implementó para `k = 1, 2, 4, 8` y valores adicionales dentro del límite API. Los estados descartados no equivalen a estados ya explorados. Las métricas cuentan candidatos únicos generados, expandidos, frontera retenida y candidatos descartados.

A diferencia de A*, **Beam no es completo ni óptimo**: un haz estrecho puede perder un corredor que inicialmente parece malo pero conduce al destino. La comparación de valores de k evidencia la renuncia a alternativas; más k consume más tiempo/memoria, y no garantiza que todas las instancias mejoren. Complejidad ilustrativa por nivel O(k·b·log(k·b)) para ordenar candidatos, además de generar y validar transiciones; la memoria histórica puede crecer por claves visitadas.

## 7. Minimax y alfa-beta: árbol de juego real

Aquí **MAX y MIN son roles**, no clases de fichas ni capacidades distintas. Al iniciar `minimax(state, depth)` el bando de `state.turno` es MAX y esa perspectiva permanece fija durante toda la recursión. `action_successors` ofrece pares `(acción, siguiente_estado)` para **cualquier pieza activa del bando que juega**, incluyendo la acción de recogida. Las acciones se aplican con el motor real y alternan turnos.

La profundidad d representa d acciones completas alternadas; d=2 considera nuestra jugada y la respuesta del enemigo. En estados terminales se evalúa inmediatamente. Al alcanzar el horizonte se llama a `evaluate`. Para el mismo estado, profundidad, evaluación y criterio de desempate, Minimax y alfa-beta deben coincidir en valor y acción. El algoritmo alfa-beta elimina sucesores cuando `α ≥ β`; **no** es una heurística que elija otro ganador. `normal` y `reverse` cambian la exploración, y por tanto las podas, sin modificar el objetivo estratégico.

Complejidad Minimax: O(b^d) nodos en el peor caso, con O(d) profundidad recursiva y almacenamiento adicional para los sucesores materializados por nivel. Alfa-beta tiene el mismo peor caso; el ahorro efectivo depende del orden. Para una ordenación ideal y estructura adecuada puede aproximarse a O(b^(d/2)) evaluaciones, pero **no garantizamos** ese comportamiento para todos los estados ni esa reducción medida en TacticalGrid.

### 7.1. Utilidad estratégica actual (pesos verificables en `evaluation.py`)

La utilidad se calcula como **U(s, A) = ScoreA(s) − ScoreB(s)** y **U(s, B) = −U(s, A)**; victoria propia devuelve `+100000`, derrota `−100000`, empate `0`. Para estados no terminales se suman factores por bando:

| Factor | Valor en código | Efecto real |
|---|---:|---|
| Unidad activa | `+60` por unidad | Disponibilidad temporal; una captura con reaparición inmediata puede no cambiarlo |
| Posesión de reina | `+1000` | Poseer el objetivo resulta mucho más valioso que una mejora local |
| Progreso geométrico a base, si hay portador | hasta `+200` | Desempate posicional normalizado |
| Distancia topológica de portador a base | `−45` por movimiento estimado | Evita que Manhattan favorezca meterse en callejones; considera aliados como obstáculos en esta estimación |
| Portador seguro / amenazado | `+150` / `−150` | Interpreta si existe captura legal enemiga inmediata |
| Carrera hacia reina libre | pesos `35`, `12`, `5` sobre hasta tres perseguidores | Premia progreso del mejor candidato y acompañamiento de compañeros |
| Cercanía geométrica a reina | hasta `+100` | Desempata con Manhattan normalizada |
| Interceptar portador contrario | pesos `25`, `8`, `3` | Orienta perseguidores hacia la posición actual del portador rival |
| Jaque con reina libre | `+80` | Premia impedir la recogida por el rival; **no** impide entregar la reina |

La señal topológica se obtiene de `_distance_map`: un BFS sobre terreno transitable y bloqueos estáticos, usando patrones geométricos de la pieza para contar movimientos optimistas. **No es el BFS de navegación oficial ni calcula una respuesta adversarial exacta.** Puede ignorar bloqueos móviles del rival y, según el factor, incorporar ocupación aliada. Para destinos que no alcanza, se utiliza una penalización derivada del tamaño del mapa. El cálculo está memoizado por tipo de unidad, mapa transitabilidad y destino; es un *trade-off* entre sensibilidad espacial y tiempo.

Ejemplo: un portador a Manhattan 2 de su base puede necesitar 8 acciones por una barrera. Si solo premiamos Manhattan, la IA puede oscilar frente al muro; con distancia topológica se penaliza el rodeo realista y se vuelve preferible una salida practicable. **Esto no prueba que todas las partidas terminen ni que la función sea óptima:** en 20×20 aparecen bloqueos y repeticiones tácticas.

### 7.2. Qué no significa la evaluación

Los pesos **no fueron obtenidos por aprendizaje automático ni ajuste estadístico exhaustivo**. Se propusieron y modificaron con asistencia de IA para conseguir decisiones observables; carecemos de un estudio amplio de sensibilidad o de un torneo contra distintos agentes. La función interpreta la amenaza inmediata, pero no garantiza evitar trampas después del horizonte. Aumentar d de 2 a 5 no transforma una función estática en una estrategia perfecta y puede incrementar mucho el coste.

## 8. Métricas, verificación y experimento reproducible

**Búsqueda:** éxito, camino, movimientos, costo, estados generados, expandidos, máximo de frontera y tiempo. **Adversarial:** acción, valor, profundidad solicitada/alcanzada, nodos generados, visitados, evaluados, podados y tiempo. `nodes_pruned` de alfa-beta cuenta **ramas hermanas inmediatas omitidas**, no descendientes hipotéticos no materializados.

La API contiene `/api/verify` y funciones de verificación para estado, ruta y recomendación. En cada prueba se deben contrastar las coordenadas de la ruta con el movimiento legal en su **estado hipotético correspondiente**, su costo real y el objetivo final, no únicamente con una meta visual. Para decisiones, la recomendación debe coincidir con una acción legal del turno y no mutar el estado oficial.

### Experimentos y criterios

Se usan los diez casos de las páginas 8–9 del PDF: BFS/DFS; BFS/UCS; U y obstáculo; dos heurísticas; Beam con k; estado compuesto; intercepción Minimax; Minimax contra alfa-beta; orden normal/inverso; y profundidad. Los escenarios nombrados de cada caso se encuentran bajo `scenarios/busqueda/` y `scenarios/adversarial/`, junto con un banco de errores deliberados bajo `scenarios/error/`. Los resultados observados y la metodología de repetición están en [Informe de verificación](informe-verificacion.md) y [Experimentos adversariales](experimentos-adversariales.md).

**Precaución importante:** no todas las diferencias de nodos constituyen mejoras universalmente válidas; el tiempo varía por máquina, entorno, caché y número de estados. No se asignan mejoras porcentuales ficticias ni se presume que un resultado de un escenario garantiza rendimiento en otros.

## 9. Limitaciones y complejidad del sistema

1. **Explosión combinatoria:** el 20×20 con varias unidades y d=5 puede tardar segundos por recomendación; el orden de acciones y la profundidad deben justificarse.
2. **Repetición táctica:** la simulación 20×20 detectó estados repetidos sin victoria oficial. El detector está en el *script de diagnóstico*, no forma parte de la regla de empate del juego. No se debe presentar como partida ganada.
3. **Heurísticas frente a dinámica:** h geométricas ignoran algunas interacciones entre piezas; la función estratégica topológica es aproximada. Son estimaciones con fines distintos.
4. **Dependencias del frontend:** Phaser/KaTeX se cargan desde CDN. Un entorno sin acceso bloquea la visualización en navegador, aunque API y motor sigan operativos.
5. **Variación de rendimiento:** los tiempos dependen del número de acciones, la profundidad, los costos de validación, las copias de estados y el equipo utilizado.
6. **Intervención de IA:** la IA generativa participó sustancialmente en implementación, depuración, pruebas y redacción. Se describe el alcance en [uso-de-ia.md](uso-de-ia.md).

## 10. Declaración de uso de IA

Los métodos principales incluyen `Purpose`, `Preconditions`, `Postconditions`, `Complexity`, `AI usage`, `AI intervention` y `Student validation`, con descripciones en español de su finalidad, garantías, complejidad e intervención de IA. El proceso de desarrollo utilizó IA generativa de forma sustancial, incluida la generación y revisión de código, el diseño de heurísticas y los experimentos de regresión. Los mecanismos de verificación y el alcance de esa asistencia se detallan en [uso-de-ia.md](uso-de-ia.md).