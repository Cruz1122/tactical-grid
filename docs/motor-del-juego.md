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

Las unidades capturadas pasan a inactivas fuera del tablero (`fila` y `columna` iguales a `-1`). Después de cada acción se prueban sus `spawn` en orden ascendente por ID; reaparecen solo si la casilla es transitable y no está ocupada por una unidad activa, rey o reina en el suelo. La configuración de reyes también reserva los `spawn` de todas las unidades, incluidas las inactivas, para no impedir su reaparición. `recurso_spawn` conserva la posición inicial de la reina. Si el portador es capturado, la reina vuelve a ese spawn y no se recoge automáticamente; el `spawn` de la víctima permanece intacto.

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

## Proyección HTTP y validación

`backend/game/presentation.py` mantiene los datos transitorios de interfaz fuera del
estado oficial. `build_presentation` calcula jaques y autorizaciones de recogida;
`transition_events` compara dos estados confirmados para identificar captura y
reaparición, incluida la reaparición inmediata de una víctima en su `spawn`.
`GET /api/legal-moves` reutiliza `legal_moves` y añade la clasificación
normal/captura. Cuando la unidad está sobre una reina disponible, también añade
un descriptor `kind: "collect"` en su casilla actual para que la interfaz pueda
ejecutar la recogida como una acción del tablero, sin mantener reglas paralelas.

La suite automatizada se ejecuta con `python -m pytest -q` dentro de un entorno
virtual que instala `requirements.txt` y pytest. Las pruebas cubren pureza, errores
sin mutación, API, reapariciones, reina, resultados, configuración de reyes,
proyección de jaques, clasificación de destinos y bloqueo por turno/estado terminal.
La validación manual de navegador cubre la carga de escenarios 4×4 y 20×20, los
alias ingleses/españoles, la selección con destinos resaltados, un movimiento real,
recogida explícita y configuración manual de reyes. La pérdida de respuesta se
trata en el cliente como una condición de reconciliación: se consulta `/api/state`
y no se reintenta automáticamente la mutación.

Las jugadas del frontend incluyen opcionalmente la `revision` de la presentación
que el usuario vio. Si otro cliente cambió el estado antes del `POST`, la API
responde `409` sin mutar y el frontend vuelve a consultar el estado oficial.
