# Banco de escenarios de TacticalGrid

Este conjunto está construido a partir de `Primer proyecto.pdf`, `TacticalGrid_Reglas.md` y las decisiones del equipo sobre reyes opcionales, spawn inicial y `estandar`.

**Ámbito principal:** carga y validación de JSON (fase 1). No pretende demostrar BFS, DFS, UCS, A*, Beam Search ni Minimax; esos requieren ejecución real del motor.

## Cómo usarlo

1. Usar los archivos bajo `valid/` y esperar una carga correcta.
2. Enviar **cada** archivo de `invalid/` a `POST /api/scenarios` como objeto JSON y esperar rechazo; el estado anterior debe conservarse.
3. Los de `invalid/syntax/` no son JSON válidos: enviar el **texto crudo** del archivo con `Content-Type: application/json`. No parsearlos antes en un cliente, porque el error se produciría en el cliente.
4. `review/` contiene contradicciones o reglas aún por acordar: **NO** usarlos como pruebas de aprobación/rechazo obligatorias.
5. Consultar `manifest.csv` (para hoja de cálculo) o `manifest.json` (para automatización) para obtener categoría, campo, motivo y ejemplo de mensaje.

**Criterio de HTTP:** se propone `422` para JSON malformado y escenarios inválidos, conforme al flujo diseñado. En `manifest` hay **ejemplos de mensajes recomendados**, no salidas verificadas del servidor: el formato exacto depende de la implementación de FastAPI/Pydantic y de los validadores propios.

## Distribución

| Resultado | Cantidad | Interpretación |
|---|---:|---|
| ACEPTAR | 16 | Contrato correcto; construir estado y actualizar partida |
| RECHAZAR_422 | 66 | Error de sintaxis, estructura o invariantes |
| POR_DEFINIR | 7 | Requiere decisión de diseño antes de automatizar |

### Clasificaciones

| Carpeta | Casos | Qué comprueba |
|---|---:|---|
| `invalid/game/` | 4 | Turno y referencias de portador |
| `invalid/kings/` | 7 | Ubicación y estructura de reyes explícitos |
| `invalid/map/` | 8 | Forma y dimensiones de la matriz |
| `invalid/positions/` | 8 | Coordenadas, límites y casillas transitables |
| `invalid/structure/` | 15 | Campos obligatorios y tipos estructurales |
| `invalid/syntax/` | 3 | Texto JSON roto o imposible de interpretar |
| `invalid/terrain/` | 8 | Catálogo, transitabilidad y costos |
| `invalid/test_config/` | 4 | Forma y referencias de configuración de prueba |
| `invalid/units/` | 9 | IDs, bandos, tipos y ocupación |
| `review/` | 7 | Aspectos no resueltos por el contrato y reglas acordadas |
| `valid/` | 16 | Escenarios aceptables, con dimensiones, tipos, costos y reyes opcionales |

## Ejemplos de errores esperados

Estos son **ejemplos de contenido semántico** del error, no cadenas de texto exigidas al carácter:

- `terreno[2][1]: tipo de terreno lava desconocido`
- `tipos_terreno.pantano.costo: debe ser mayor que cero`
- `unidades[1].id: ID duplicado A1`
- `juego.portador_recurso: unidad Z999 no encontrada`
- `reyes.A[0]: no puede ocupar bases`
- `prueba.objetivo: coordenada fuera del mapa`

## Convenciones y límites

- Se respetan las claves externas del profesor: `version`, `mapa`, `tipos_terreno`, `terreno`, `bases`, `recurso`, `unidades`, `turno`, `juego` y la `prueba` opcional.
- Se admiten mapas externos menores de 20×20; los escenarios de desarrollo se preparan también en tamaño 20×20.
- `spawn` se deriva de la posición inicial de cada unidad; no se exige ese campo en los JSON.
- Si faltan los reyes, **NO** se generan automáticamente al cargar. Podrán agregarse en configuración previa al primer movimiento.
- `estandar` se mueve un cuadro en cuatro direcciones; los tests de esta carpeta solo validan que se acepte el tipo, no prueban sus movimientos.
- El PDF menciona al menos tres piezas por bando, pero muestra un ejemplo con dos. Este banco sigue la decisión de compatibilidad del equipo de **no exigir tres** para importar.
- `prueba` es opcional según la descripción del documento, aunque figure en la tabla de campos.
- Un costo decimal positivo se considera permitido por el requisito de positividad; no imponer entero como restricción nueva.
- La aceptación de `rook`, `bishop` y `knight` procede de las decisiones de diseño del equipo; no son valores impuestos por el JSON ilustrativo del profesor.
- No se comprueban efectos de jaque, capturas o movimientos en carga: son comportamiento del motor, no del validador del archivo.
- La validez de reyes explícitos usa un formato de extensión propuesto: `{ "reyes": { "A": [{"id": "A_KING", "fila": 0, "columna": 3}], "B": [] } }`. El PDF no impone esta estructura adicional.

## Atomicidad: prueba manual imprescindible

1. Cargar `valid/01_profesor_4x4.json` y guardar una copia de `GET /api/state`.
2. Intentar cargar `invalid/terrain/03_costo_negativo.json`: debería devolver rechazo (propuesta: HTTP 422).
3. Repetir `GET /api/state`: el estado oficial debe seguir siendo **idéntico** al guardado en el paso 1 (salvo metadatos no deterministas, si existieran; idealmente ninguno).
4. Repetir con `invalid/units/03_unidades_superpuestas.json` e `invalid/syntax/01_json_incompleto.json`.
5. Cargar `valid/10_turno_B.json`: debe reemplazar la partida y ahora indicar `turno = B`.

**No hay resultados reales de la API**: son resultados esperados para implementar y contrastar, no pruebas ejecutadas sobre el repositorio.

## Referencias

- `Primer proyecto.pdf`: contrato JSON, validación y compatibilidad externa, pp. 5–7.
- `TacticalGrid_Reglas.md`: reglas de movimiento, reyes, reina e invariantes.
- Decisiones del equipo: reyes opcionales antes de mover, spawn inicial, `estandar` en 4 direcciones, empate sin jugadas legales.
