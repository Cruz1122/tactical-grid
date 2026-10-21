# Documento técnico — TacticalGrid

## 1. Problema y arquitectura

TacticalGrid es un problema determinista de planificación sobre un juego táctico 2D por turnos. A y B controlan unidades móviles con patrones geométricos; compiten por recoger una reina neutral y trasladarla a la **base del portador**. El motor del juego valida acciones, calcula costos, produce nuevos estados e informa victoria/empate. FastAPI publica una API y sirve una interfaz HTML/CSS/JS/Phaser del mismo origen. La UI nunca calcula resultados ficticios.

La representación del estado conserva `version`, `mapa`, `filas`, `columnas`, `tipos_terreno`, `terreno`, `bases`, `recurso`, `unidades`, `turno`, `juego.portador_recurso` y `prueba`, además de información interna de actividad, `spawn`, `recurso_spawn`, reyes y resultado. `state_key` diferencia posiciones, actividad, turno, recurso, portador, estado terminal y configuración estática. La validación rechaza JSON incoherente antes de sustituir el estado oficial.

## 2. Reglas y costos

`estandar` se mueve una casilla ortogonal; `knight` salta en L; `rook` se desplaza por filas o columnas y `bishop` por diagonales, sin atravesar bloqueos. Estándar/caballo pagan costo del destino. Torre/alfil pagan **la suma de todas las casillas atravesadas sin contar origen**. Los valores y obstáculos provienen exclusivamente del JSON.

Capturar envía al enemigo a su spawn si está libre; en otro caso queda inactivo hasta que pueda reaparecer. Al capturar al portador, la reina retorna al `recurso_spawn` original; no se entrega automáticamente al capturador. Jaque impide recoger, pero no transportar ni entregar. Los reyes son opcionales según la configuración de cada escenario. Estas son reglas propias, no ajedrez ortodoxo.

## 3. Búsqueda de rutas

Para BFS, DFS, UCS, A* y Beam los demás jugadores son entorno estático respecto de sus acciones voluntarias: solo una ficha elegida se mueve hipotéticamente. Los sucesores comparten las reglas y los efectos de captura del motor. La ruta reconstruida no equivale a turnos reales garantizados.

| Algoritmo | Selección | Garantía bajo condiciones |
| --- | --- | --- |
| BFS | FIFO, profundidad creciente | Menor número de movimientos en grafo finito |
| DFS | LIFO | Puede encontrar solución, no menor longitud |
| UCS | Heap por costo acumulado `g` | Menor costo con aristas positivas |
| A* | Heap por `f=g+h` | Optimalidad condicionada por heurística y relajaciones correctas |
| Beam | `k` candidatos por nivel | Puede perder soluciones y optimalidad |

Las métricas incluyen generados, expandidos, frontera máxima, movimientos, costo y `perf_counter`. Cada salto largo de torre/alfil representa un movimiento aunque recorra múltiples terrenos.

### Heurísticas de A*

`manhattan = |dr|+|dc|` es un experimento de referencia; no necesariamente admisible para patrones de ajedrez o costos inferiores a 1. `second_heuristic` usa mínimos de terreno: para `estandar`, suma mínimos de filas y columnas que necesariamente debe atravesar; para torre usa `min_cost*(dr+dc)`; para alfil `min_cost*max(dr,dc)`; para caballo usa `min_cost*max(ceil((dr+dc)/3),ceil(max(dr,dc)/2))`. Estas son cotas optimistas para el costo real. Los obstáculos pueden obligar a un rodeo pero no invalidan la cota inferior. Los mínimos del mapa se precalculan cuando la implementación lo permite.

## 4. Planificación adversarial

Minimax y poda alfa-beta consideran acciones legales de **todas** las piezas del turno, alternan los bandos y evalúan estados con una perspectiva MAX fija. Profundidad `d` cuenta acciones individuales, por lo que `d=2` incluye respuesta enemiga. Alfa-beta mantiene `alpha` (cota inferior de MAX) y `beta` (superior de MIN) y omite hermanos cuando `alpha>=beta`; debe devolver la misma utilidad y acción canónica que Minimax. El orden `normal` y `reverse` afecta las podas y el tiempo.

### Utilidad actual

Se devuelve +100000 por victoria del bando evaluado, -100000 por derrota y 0 para empate oficial. Fuera de un final, `U(s,A)=P_A-P_B`, `U(s,B)=-U(s,A)`, donde cada puntuación incorpora:

- Unidad activa: +60; posesión de reina: +1000.
- Cercanía geométrica a reina libre: hasta +100; al llevarla, cercanía geométrica a base: hasta +200.
- Seguridad de portador: +150 sin captura enemiga inmediata; -150 si es capturable.
- Jaque contra rey enemigo cuando reina libre: +80.
- Progreso topológico hacia reina con distancias estáticas por tipo de pieza: ponderaciones 35 (primer aspirante), 12 (segundo), 5 (tercero), escaladas según diámetro del tablero.
- Intercepción del portador rival: 25, 8 y 3 para los tres perseguidores más próximos.
- Progreso del portador hacia su base: -45 puntos por movimiento estimado restante, **contabilizando aliados como bloqueos temporales**.

El mapa topológico usa movimientos de cada tipo y muros/reyes estáticos; **no** sustituye a BFS/UCS oficial ni predice turnos enemigos. Las fichas amigas pueden moverse después y por eso sus bloqueos solo se tratan explícitamente al estimar la salida de su propio portador. Los pesos son manuales y deben justificarse con pruebas; no están aprendidos ni garantizan victoria.

### Complejidad

Con factor de ramificación `b`, profundidad `d` y costo `T` de generar/aplicar cada sucesor, Minimax exige `O(b^d*T)` en el peor caso. Alfa-beta tiene el mismo peor caso, pero poda según el orden. Al materializar todos los hijos en cada nodo, la memoria depende de la profundidad, el número de estados hijos retenidos y el tamaño de cada copia; no asumir O(d) simple. La función de evaluación recurre a BFS topológico cacheado en mapas y geometría inmutables, además de consultas de amenazas y jaques; puede influir significativamente en la latencia para mapas grandes.

## 5. Metodología y resultados

Se utilizaron casos deterministas del banco `scenarios/busqueda` (BFS/DFS, costo vs movimientos, barrera, dos heurísticas, Beam k=1/2/4/8), estados compuestos y casos adversariales `scenarios/adversarial` (defensa, Minimax/alfa-beta, orden y profundidad). La suite incluye validación, pruebas de propiedades y regresiones. Las evidencias efectivamente ejecutadas se describen en `informe-verificacion.md`, `experimentos-adversariales.md` y `outputs/`.

El 6×6 suministrado terminó con ganador B en 24 acciones a profundidad 2 con alfa-beta. El 20×20 llegó a posición de repetición en 105 acciones a profundidad 2 sin ganador. **No confundir repetición diagnosticada por un script con empate oficial, ni presentar el 20×20 como victoria automática.**

## 6. Limitaciones y ética de IA

La autopartida puede quedar en bloqueos mutuos. No existe regla de empate por repetición; modificarla requiere decisión formal. A profundidad alta, tiempo y ramificación crecen rápidamente. Los recursos Phaser/KaTeX dependen de CDN y pueden no cargarse sin internet. La captura de interfaz no pudo verificarse en este sandbox por bloqueo de navegación local; no se incorporan imágenes inventadas.

Uso de IA, alcance y revisión pendiente: ver `uso-de-ia.md`. Todos los datos experimentales deben repetirse en la versión que se presente. Los integrantes deben revisar y defender personalmente el código, conforme al PDF.