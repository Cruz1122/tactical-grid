# Reglas de TacticalGrid

TacticalGrid es un juego táctico de dos bandos, **A** y **B**. El objetivo consiste en recoger una reina neutral y transportarla legalmente hasta la base del propio equipo. El tablero, los terrenos, los costos, las posiciones iniciales y las bases se definen mediante un archivo JSON.

## Unidades y movimientos

- **`knight` / `caballo`:** salta en L (dos casillas en un eje y una en el otro); paga el costo de la casilla de destino.
- **`rook` / `torre`:** se desplaza horizontal o verticalmente, sin atravesar obstáculos ni unidades; paga la suma de los costos de todas las casillas atravesadas, excluido el origen.
- **`bishop` / `alfil`:** se desplaza en diagonal, sin atravesar obstáculos ni unidades; paga la suma de los costos de las casillas atravesadas, excluido el origen.
- **`estandar`:** avanza una casilla horizontal o verticalmente; paga el costo del destino. También se aplica a nombres de tipo desconocidos que sean cadenas no vacías, conforme a la normalización del escenario.

Las casillas no transitables, los reyes estáticos y las unidades aliadas impiden terminar un movimiento. No pueden coexistir dos unidades activas en la misma casilla.

## Reina, captura y reaparición

La reina comienza en `recurso_spawn`. Una unidad puede recogerla al llegar legalmente a su posición, según las reglas del motor, o mediante la acción explícita `collect` cuando ya está sobre su casilla y está autorizada. Solo existe un portador a la vez.

Una unidad puede capturar a un rival terminando un movimiento legal en su casilla. El capturado reaparece en su **spawn original** si está disponible; en caso contrario permanece inactivo hasta que pueda reaparecer. Si el capturado llevaba la reina, esta regresa a **`recurso_spawn`**. El atacante no la recoge automáticamente.

## Reyes y jaque

Los reyes son opcionales, permanecen inmóviles y no pueden capturarse. Si el rey propio está en jaque, el bando **no puede recoger la reina** hasta que deje de estarlo. El jaque **no impide mover ni entregar** una reina que ya se transportaba.

## Turnos y victoria

En una partida real, A y B alternan acciones completas. Gana el bando que entrega la reina en su base mediante un movimiento legal. Cuando el bando que debe actuar no dispone de acciones legales, el motor declara empate. No existe un empate automático por tres repeticiones ni por una cantidad fija de turnos.

## Tipos de escenario

| `prueba.modo` | Comportamiento |
|---|---|
| `busqueda` | BFS, DFS, UCS, A* o Beam calculan la ruta hipotética de **una** pieza, sin turnos enemigos y sin alterar el estado oficial. |
| `adversarial` | Minimax y alfa-beta consideran las acciones legales de todas las unidades del bando activo y respuestas del rival; devuelven una recomendación sin ejecutarla. |
| `partida` | Se ejecutan movimientos, capturas, recogida y entrega, con alternancia de turnos y actualización del estado oficial; incluye autopartida. |

Los escenarios válidos pueden utilizar dimensiones rectangulares. El tablero de 20×20 se emplea como referencia experimental; no es el único tamaño admitido.