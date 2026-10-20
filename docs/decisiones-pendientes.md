# Decisiones pendientes y contradicciones visibles

Esta lista evita que se confundan **reglas ya acordadas** con detalles todavía abiertos. Las decisiones resueltas para el motor de la fase 3 aparecen documentadas abajo.

## Acordado

- `estandar` se mueve **exactamente una casilla** en cualquiera de las cuatro direcciones ortogonales; paga el terreno de destino.
- `spawn` inicial de cada unidad: la posición con la que llega del JSON.
- Los reyes son opcionales; cargarlos desde el JSON si existen, o configurarlos manual o automáticamente antes del primer movimiento.
- La importación **no** genera reyes cuando el JSON no los contiene. Se puede jugar sin reyes; en ese caso no hay jaque.
- Una vez comenzada la partida, las posiciones de los reyes quedan fijas.
- Si el bando activo no dispone de ningún movimiento legal (tras procesar las reapariciones correspondientes), la partida termina en **empate**.
- Se preservan las claves obligatorias del JSON del profesor. Los costos y las posiciones provienen del escenario.

## Sin cerrar: decidir antes de los casos que lo requieran

| Tema | Por qué importa | Decisión que aún falta |
| --- | --- | --- |

| Tipos no previstos | El PDF deja abiertos detalles de unidades, sin enumerar todos los tipos. | Qué error presentar ante tipos desconocidos, sin prometer compatibilidad que el motor no puede ejecutar. |
| Cantidad de unidades | El texto del PDF indica al menos 3 por bando, pero su ejemplo tiene 2. | Documentar formalmente la excepción para el importador; verificar interpretación con el docente si es posible. |
| Terminación anómala | Se acordó empate por falta de jugadas. | Si se requieren otras condiciones terminales (p. ej. límite de turnos o repeticiones), definirlas antes de usarlas. |
| Heurística adicional | Se exige A* con al menos dos heurísticas. | Fórmula y prueba/justificación de sus propiedades. |
| Evaluación Minimax | El docente no fija pesos ni fórmula. | Función de utilidad y criterio estable de desempate. |

## Decisiones implementadas en el motor de la fase 3

- Se aceptan los tipos internos `knight`, `rook`, `bishop`, `estandar` y sus alias `caballo`, `torre`, `alfil`.
- Reyes automáticos: celdas transitables en orden fila-columna, cantidades explícitas por bando y selección voraz determinista; puede fallar sin mutación aunque exista otra distribución.
- Ningún rey ocupa el `spawn` de una unidad, para no impedir una reaparición futura.
- Accesibilidad: las bases deben permanecer conectadas por celdas transitables ortogonales que no ocupen reyes.
- Reina tras captura del portador: vuelve a `recurso_spawn`, su posición inicial inmutable; el atacante no la recoge automáticamente y el `spawn` de la ficha capturada no se modifica.
- Jaque: bloquea la recogida explícita y se consulta tras retirar temporalmente la reina para una recogida normal; el portador conserva la reina aunque su rey quede en jaque.
- Estado externo con portador y `recurso` en la posición del portador: se valida, se conserva esa posición como `recurso_spawn` y se normaliza internamente a `recurso: null`.
- Orden por acción: movimiento/captura y reposición de la reina en `recurso_spawn`, reapariciones por ID, victoria inmediata; si no hay victoria, cambio de turno y comprobación de empate.

## Reglas del documento original modificadas por el equipo

`TacticalGrid_Reglas.md` presenta los reyes como parte permanente de cada bando. La decisión posterior **permite que no existan** en un escenario o partida. Por tanto, el documento original no se debe reutilizar sin señalar esta actualización.

En el PDF se muestra un contrato JSON común y se permite ampliar campos, **no sustituir ni renombrar** los oficiales. Nuestros campos `reyes` y `spawn` son complementos internos u opcionales, no requisitos nuevos para admitir un JSON del profesor.

## Cómo resolver futuras ambigüedades

1. Revisar primero el requisito explícito del PDF.
2. Revisar después las reglas propias documentadas.
3. Adoptar una regla determinista, simétrica y consistente con el estado.
4. Guardar el caso de prueba que demuestre la decisión.
5. No afirmar que el repositorio implementa una decisión hasta inspeccionarlo y probarlo.
