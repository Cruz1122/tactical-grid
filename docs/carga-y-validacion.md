# Carga y validación de escenarios

## Principio fundamental: carga atómica

Un archivo inválido **no puede modificar la partida actual**. Toda carga se prepara como candidata; solo si termina correctamente la lectura, la validación y la construcción del estado se reemplaza el estado oficial.

```text
JSON externo
   ↓
Lectura y análisis sintáctico
   ↓
Copiar y normalizar tipos de unidad no admitidos a `estandar`
   ↓
validate_scenario   ── error ──→ informar y conservar la partida anterior
   ↓
Construir estado candidato y obtener spawns iniciales
   ↓
validate_state      ── error ──→ informar y conservar la partida anterior
   ↓
Sustituir el estado oficial una sola vez
   ↓
Configuración opcional de reyes, antes del primer movimiento
```

La normalización y la validación no son lo mismo: `prepare_scenario` copia la entrada y convierte cualquier tipo de unidad presente que no esté admitido a `estandar`; `validate_scenario` **inspecciona** el escenario ya normalizado. No se modifica el JSON de entrada. Un campo `tipo` ausente sigue siendo inválido.

## Qué valida `validate_scenario`

**Estructura y tipos**

- JSON correctamente analizado y con los campos del contrato común.
- Objeto `mapa` con filas y columnas positivas; matriz rectangular del tamaño declarado.
- Catálogo `tipos_terreno` consistente; cada terreno usado por la matriz existe.
- Terrenos transitables con costo numérico positivo; obstáculos no requieren ese costo.
- Bases, recurso y unidades con coordenadas válidas dentro del tablero.
- `recurso_spawn`, si aparece, con coordenadas transitables; sin portador debe coincidir con la posición inicial de `recurso`. Si la partida empieza con portador y `recurso` es `null`, `recurso_spawn` es obligatorio y no puede coincidir con un rey.
- Campos `id`, `bando`, `tipo` y posición de cada unidad donde correspondan. Cualquier tipo de unidad presente que no esté admitido se normaliza a `estandar` durante la preparación del escenario.
- IDs únicos; bandos y turno `A` o `B`.
- `juego.portador_recurso` nulo o referencia a una unidad existente.
- `prueba`, si aparece, con estructura compatible con el modo de prueba solicitado.

**Restricciones del escenario**

- Una unidad no comienza en una celda no transitable.
- Dos unidades activas no empiezan superpuestas.
- Los reyes, si llegan en JSON, no se solapan con elementos prohibidos ni con el `spawn` de unidades inactivas; tampoco pueden ocupar `recurso_spawn` cuando la reina empieza transportada.
- Las bases son transitables y permanecen conectadas por celdas transitables ortogonales sin reyes.

El PDF no obliga a rechazar un mapa externo por medir menos de 20 × 20. Tampoco obliga a que cada unidad externa incluya `spawn` o a que el escenario contenga reyes. No introducir restricciones nuevas y silenciosas sobre campos que el contrato deja abiertos.

## Qué hace la construcción del estado

- Preserva el significado de los campos del contrato oficial.
- Normaliza tipos de unidad desconocidos a `estandar` y obtiene el `spawn` de cada unidad a partir de su posición de inicio.
- Inicializa el estado de actividad y los datos internos necesarios para el motor, sin inventar reyes ausentes.
- Mantiene coherencia entre reina en tablero y portador del recurso.
- Conserva `recurso_spawn` desde el `recurso` inicial; una captura posterior usa esa posición y nunca la casilla de captura.
- Deja la partida en una condición apta para configuración previa al primer movimiento.

No decide rutas ni ejecuta movimientos. No convierte la carga de un JSON en una jugada.

## Qué valida `validate_state`

Examina invariantes del estado candidato o de futuros sucesores del motor:

- Unidad activa con posición real y legal; unidad inactiva correctamente representada fuera del tablero.
- Ausencia de dos unidades activas en una casilla.
- Bases, reyes, obstáculos y unidades sin ocupaciones contradictorias.
- Reina única: posición en tablero **o** referencia a un portador, nunca dos portadores.
- Portador existente, activo y consistente con la representación del recurso.
- Turno, resultado y modo de ejecución coherentes.
- Spawns definidos y válidos; los reyes no ocupan ningún `spawn`.
- Conectividad entre bases cuando se valida carga/configuración.

Las transiciones vuelven a validar invariantes dinámicas, pero omiten la conectividad estática porque terreno, bases y reyes no cambian durante una partida. No se modifica el estado «para arreglarlo»: un estado incoherente se rechaza.

## `validate_action`: responsabilidad diferente

Una acción pertenece a una partida en configuración o ya iniciada: la primera acción válida inicia la partida. Su validación comprueba el turno, la identidad y actividad de la unidad, el tipo de acción, el destino legal del movimiento o las condiciones de recogida explícita.

La validación de acciones reutiliza `legal_moves`, `move_cost` e `is_in_check`; no mantiene una segunda implementación de las reglas de movimiento. Una operación inválida falla antes de modificar el estado oficial.

## Respuestas de la API

El endpoint propuesto `POST /api/scenarios` recibe un **objeto JSON** con el escenario. Cuando es válido, retorna una confirmación y un estado inicial verificable. Cuando es inválido, retorna un error claro (por ejemplo, HTTP `422`) y **no sustituye** la partida anterior.

Un mensaje útil señala el campo y el motivo: «`terreno[2][4]`: tipo desconocido `lava`» o «`tipos_terreno.pantano.costo`: debe ser mayor que cero». Evitar mensajes genéricos como «archivo inválido» sin más contexto.

## Pruebas de contrato

| Entrada | Resultado esperado |
| --- | --- |
| JSON válido con `estandar` y sin reyes | Se carga y queda listo para configurar/iniciar |
| JSON mal formado | Se rechaza sin cambios |
| Dimensiones inconsistentes con la matriz | Se rechaza |
| Terreno desconocido o costo no positivo | Se rechaza |
| Unidad sobre obstáculo o fuera de límites | Se rechaza |
| IDs duplicados o turno inválido | Se rechaza |
| Tipo de unidad no admitido | Se carga como `estandar` sin modificar el JSON original |
| Portador que no existe | Se rechaza |
| `recurso_spawn` contradictorio con `recurso` inicial sin portador | Se rechaza |
| Portador con `recurso: null` sin `recurso_spawn` | Se rechaza |
| Dos unidades activas superpuestas | Se rechaza |
| Reyes explícitos en posiciones ilegales | Se rechaza |
| Escenario de dimensiones válidas distintas a 20 × 20 | Se acepta si cumple las demás reglas |
| Escenario válido seguido de uno inválido | El estado válido anterior sigue intacto |

Las pruebas deben comprobar además que la normalización no muta el JSON original si se reutiliza en otra ejecución.

**Referencias:** `Primer proyecto.pdf`, pp. 5–7; `TacticalGrid_Reglas.md`, secciones 2 y 6; criterios de carga acordados por el equipo.
