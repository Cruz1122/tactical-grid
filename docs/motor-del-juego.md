# Motor de la partida

## Propósito

`backend/game/engine.py` implementa las transiciones de partida como funciones puras: reciben un estado, verifican una acción y devuelven un estado independiente. `legal_moves`, `move_cost` e `is_in_check` siguen siendo la fuente única de las reglas de movimiento, costo y jaque. `backend/game/state.py` conserva las importaciones históricas como reexportador.

El motor cubre movimientos, turnos, capturas, reapariciones, transporte y recogida de la reina, victoria y empate. No implementa BFS, DFS, UCS, A*, Beam Search, Minimax ni alfa-beta.

## Estado y acciones

Al preparar un escenario, `juego.estado` comienza como `configuracion` y `juego.resultado` como `null`, salvo que el portador ya esté en su propia base (victoria inmediata) o que el bando inicial no tenga movimientos ni recogida explícita legales (empate). Las unidades inactivas no generan acciones antes de que una transición provoque su reaparición; no se inventan turnos para reactivarlas. El primer movimiento o recogida válida inicia la partida. Los estados `en_curso` no aceptan cambios de reyes; `finalizado` no acepta acciones. Los JSON del profesor mantienen sus claves: `spawn`, actividad y campos de partida son datos internos añadidos durante la preparación.

Acciones de `transition`:

```json
{"type": "move", "unit_id": "A1", "destination": {"fila": 2, "columna": 3}}
```

```json
{"type": "collect", "unit_id": "A1"}
```

La segunda acción no mueve la unidad y consume el turno. Solo es legal si la reina está disponible bajo la unidad activa del bando en turno y el rey de ese bando no está en jaque.

Las unidades capturadas pasan a inactivas fuera del tablero (`fila` y `columna` iguales a `-1`). Después de cada acción se prueban sus `spawn` en orden ascendente por ID; reaparecen solo si la casilla es transitable y no está ocupada por una unidad activa, rey o reina en el suelo. La configuración de reyes también reserva los `spawn` de todas las unidades, incluidas las inactivas, para no impedir su reaparición. Si el portador es capturado, la reina cae donde ocurrió la captura y no se recoge automáticamente.

Una unidad que transporta la reina y llega a su propia base gana; esta victoria tiene prioridad sobre el empate. De lo contrario, después de cambiar el turno y procesar las reapariciones deterministas, la ausencia de movimientos y de recogida explícita legal termina la partida en empate. Configurar reyes también finaliza en empate si deja al bando inicial sin acciones. El jaque se calcula con `is_in_check`, nunca se almacena; solo restringe recoger la reina. Una reina ya transportada se conserva aunque aparezca jaque.

## Configuración de reyes

`configure_kings` recibe posiciones manuales por bando; `generate_kings` recibe cantidades no negativas para `A` y `B`. Ambas operaciones solo funcionan durante `configuracion`, validan primero una copia completa y no dejan cambios parciales. La generación recorre las celdas en orden fila-columna y usa las dimensiones reales del mapa. Los reyes no pueden ocupar terreno no transitable, posiciones actuales o `spawn` de unidades, otros reyes, bases o reina en el suelo. Se rechaza una configuración que desconecte las bases mediante celdas transitables ortogonales sin reyes.

La API expone esas operaciones en `POST /api/kings` con `mode: "manual"`, `"automatic"` o `"none"`. Para modo automático, `counts` debe contener cantidades para ambos bandos.

## Contratos de las funciones principales

- **Preconditions:** estado preparado y válido; acción conocida, unidad activa y perteneciente al bando en turno; destinos incluidos en `legal_moves`. La recogida explícita requiere disponibilidad de reina, coincidencia de casilla y ausencia de jaque propio.
- **Postconditions:** entrada sin modificaciones; el estado devuelto es independiente, refleja consecuencias, turno y resultado, y pasa `validate_state`. Una acción inválida lanza `ValueError` (regla) o `TypeError` (forma/tipo) sin afectar el estado oficial.
- **Complejidad:** una transición cuesta `O(U + K·U·max(F,C) + R·C)` en el peor caso, además del tamaño de la copia. `U` son unidades, `K` reyes y `R×C` las celdas del mapa. La validación de conectividad de bases se ejecuta al cargar el escenario y al configurar reyes, no en cada transición. `successors` cuesta `O(A·T)`, donde `A` es el número de acciones candidatas y `T` el costo de una transición; su salida ocupa `O(A·S)` para estados de tamaño `S`.

## Limitaciones deliberadas de esta fase

- `state_key` incluye el mapa y sus reglas para distinguir estados de escenarios distintos. Si la fase 4 necesita una clave más pequeña para navegación dentro de un mapa fijo, debe definirse por separado.
- `successors` conserva el contrato de esta fase: devuelve estados. Cada acción se aplica mediante `transition`; cualquier contradicción entre `legal_moves` y `transition` se propaga. No se cambia ahora a pares acción-estado ni se integra con Minimax.
- `generate_kings` usa una selección voraz determinista por orden fila-columna. Devuelve todas las cantidades pedidas si encuentra una configuración válida; en caso contrario lanza `ValueError` sin mutar la entrada. No garantiza encontrar una solución que exista si la selección previa bloqueó las opciones restantes.

## Declaración académica

### AI intervention

Se utilizó IA generativa durante el desarrollo para proponer y editar código, pruebas y documentación. La IA no forma parte del motor en tiempo de ejecución. Las fuentes `Primer proyecto.pdf` y `TacticalGrid_Reglas.md` no están incluidas en este repositorio, por lo que no fue posible contrastar el formato exacto de la declaración académica.

### Student validation

Pendiente de confirmación por el estudiante. En esta sesión se ejecutaron las pruebas automatizadas indicadas abajo, pero eso no demuestra que un integrante haya revisado personalmente el código ni validado el comportamiento en una ejecución manual. Antes de entregar, el estudiante debe ejecutar y revisar los casos y actualizar esta declaración con su validación real.

## Validación

Prueba automatizada: `.venv/bin/python -m unittest discover -s backend/tests -v`. Las pruebas cubren pureza, errores sin mutación, API, reapariciones, reina, resultados y configuración de reyes.
