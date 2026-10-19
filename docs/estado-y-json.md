# Estado del juego y contrato JSON

## Escenario externo frente a estado interno

El **escenario** es la entrada que describe mapa, terreno, bases, unidades, recurso y datos de prueba. El **estado de partida** representa una situación concreta y puede cambiar después de cada jugada. Es conveniente separar:

- **Datos relativamente estáticos:** matriz, catálogo de terrenos/costos, bases y spawns; posiciones de reyes una vez iniciada la partida.
- **Datos dinámicos:** turno, ubicación/actividad de unidades, posición o portador de reina, resultado y modo de configuración/partida.

Esto no obliga a crear clases complejas: sirve para que los algoritmos sepan qué información determina una situación y qué datos pueden cambiar.

## Campos del JSON común

| Campo | Significado | Consideración |
| --- | --- | --- |
| `version` | Versión del formato | Preservar y validar según el contrato aceptado |
| `mapa.filas`, `mapa.columnas` | Dimensiones | Enteros positivos; coincidir con matriz |
| `tipos_terreno` | Catálogo de terrenos | Cada transitable tiene costo positivo y atributo de transitabilidad |
| `terreno` | Matriz de identificadores | Cada identificador debe existir en el catálogo |
| `bases.A`, `bases.B` | Bases | Coordenadas `fila` y `columna` válidas |
| `recurso` | Ubicación de la reina si está en el suelo | Coherencia con el portador |
| `unidades` | Objetos con `id`, `bando`, `tipo`, `fila`, `columna` | IDs únicos, posiciones válidas, bandos `A` o `B` |
| `turno` | Próximo bando | `A` o `B` |
| `juego.portador_recurso` | ID del portador o `null` | Debe referirse a una unidad existente si no es nulo |
| `prueba` | Configuración de la prueba | **Opcional**, no debe confundirse con una regla de partida |

En el PDF, `prueba` aparece entre los campos descritos pero se identifica expresamente como **configuración opcional**. Sus modos contemplan `busqueda`, `partida` y `adversarial`.

Los nombres de las claves del JSON oficial están en español y **no deben renombrarse**. Las funciones y nombres internos del código pueden estar en inglés.

## Ejemplo mínimo de escenario externo

Este ejemplo ilustra el formato del PDF con `estandar`, sin `reyes` ni `spawn`. **No es un mapa de desarrollo ≥20 × 20**, pero demuestra la aceptación de otras dimensiones válidas.

```json
{
  "version": "1.0",
  "mapa": {"filas": 4, "columnas": 4},
  "tipos_terreno": {
    "camino": {"costo": 1, "transitable": true},
    "pasto": {"costo": 2, "transitable": true},
    "muro": {"transitable": false}
  },
  "terreno": [
    ["camino", "camino", "pasto", "camino"],
    ["camino", "muro", "camino", "camino"],
    ["camino", "camino", "camino", "pasto"],
    ["camino", "pasto", "camino", "camino"]
  ],
  "bases": {
    "A": {"fila": 0, "columna": 0},
    "B": {"fila": 3, "columna": 3}
  },
  "recurso": {"fila": 2, "columna": 2},
  "unidades": [
    {"id": "A1", "bando": "A", "tipo": "estandar", "fila": 0, "columna": 1},
    {"id": "B1", "bando": "B", "tipo": "estandar", "fila": 3, "columna": 2}
  ],
  "turno": "A",
  "juego": {"portador_recurso": null}
}
```

## Normalización, sin alterar el contrato

Al cargar una unidad con posición `(fila, columna)`, el programa puede incorporar internamente `spawn = (fila, columna)`; el JSON externo **no tiene que traer `spawn`**. Si no llegan reyes, el escenario permanece sin reyes. No se generan de oficio durante la importación.

Los tipos previstos internamente son `knight`, `rook`, `bishop` y `estandar`. El PDF no enumera todos los valores posibles de `tipo`; el tratamiento de otros valores y alias en español debe definirse explícitamente antes de afirmar compatibilidad universal.

## Invariantes de estado

Un estado de partida es coherente si al menos se cumple lo siguiente:

1. Turno `A` o `B` mientras la partida esté activa.
2. Mapa y terrenos válidos; posiciones dentro de sus límites.
3. Cada unidad tiene ID único, bando válido, `spawn` definido y actividad coherente con su posición.
4. No hay dos unidades activas en la misma casilla; ninguna ocupa un obstáculo o rey.
5. Hay como máximo un portador y la reina está **o** en el suelo **o** transportada.
6. Los reyes, si existen, son estáticos, pertenecen a un bando y no ocupan casillas prohibidas ni bloquean bases.
7. El estado distingue «configuración», «partida activa» y «terminada» para impedir jugadas en momentos inválidos.
8. Bases accesibles conforme al criterio de alcanzabilidad que se defina para el motor; no dar por probada su accesibilidad solo por ser transitables.

Un estado de búsqueda no se identifica necesariamente solo por `(fila, columna)`: durante juego adversarial importan el turno, todas las piezas, actividad y portador. Los detalles inmutables del escenario pueden compartirse como referencia sin copiarlos en cada sucesor.

**Referencias:** `Primer proyecto.pdf`, pp. 3, 5–7; `TacticalGrid_Reglas.md`, secciones 2 y 6; decisiones posteriores del equipo sobre normalización.
