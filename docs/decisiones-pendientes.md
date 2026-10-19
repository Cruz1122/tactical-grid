# Decisiones pendientes y contradicciones visibles

Esta lista evita que se confundan **reglas ya acordadas** con detalles todavía abiertos. No son tareas organizadas por fase.

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
| Alias de `tipo` | El PDF usa `estandar`; el archivo original de reglas ejemplifica `"torre"`; el diseño interno usa `rook`, `bishop`, `knight`. | Si se admiten también `torre`, `alfil`, `caballo` como alias externos y cómo se normalizan. |
| Tipos no previstos | El PDF deja abiertos detalles de unidades, sin enumerar todos los tipos. | Qué error presentar ante tipos desconocidos, sin prometer compatibilidad que el motor no puede ejecutar. |
| Cantidad de unidades | El texto del PDF indica al menos 3 por bando, pero su ejemplo tiene 2. | Documentar formalmente la excepción para el importador; verificar interpretación con el docente si es posible. |
| Reyes automáticos | La generación es opcional y debe ser válida. | Criterio concreto de elección de celdas, cantidad por equipo y desempate determinista. |
| Base «alcanzable» | Ser transitable no garantiza que un bando pueda llegar con sus piezas; con jaques/ocupación es más complejo. | Definir qué criterio de alcanzabilidad es exigible al cargar un escenario. |
| Reina y captura | Cuando cae la reina bajo el atacante, el atacante no la recoge automáticamente. | Cómo se permite recogerla más tarde sin ambigüedad, especialmente si la misma unidad ocupa su casilla. |
| Reina y jaque | Está prohibido recogerla en jaque, no mover. | Qué pasa si una unidad llega a la casilla de la reina estando su rey en jaque: posición compartida sin recogida o movimiento rechazado. |
| Representación externa del portador | El PDF especifica `juego.portador_recurso`, pero no un ejemplo completo de recurso ya transportado. | Cómo interpretar escenarios externos con portador y `recurso` informado, respetando el contrato. |
| Terminación anómala | Se acordó empate por falta de jugadas. | Si se requieren otras condiciones terminales (p. ej. límite de turnos o repeticiones), definirlas antes de usarlas. |
| Orden interno de eventos | Captura, caída de reina, respawn, victoria y empate pueden coincidir. | Fijar un orden de transición que sea determinista en todos los casos borde. |
| Heurística adicional | Se exige A* con al menos dos heurísticas. | Fórmula y prueba/justificación de sus propiedades. |
| Evaluación Minimax | El docente no fija pesos ni fórmula. | Función de utilidad y criterio estable de desempate. |

## Reglas del documento original modificadas por el equipo

`TacticalGrid_Reglas.md` presenta los reyes como parte permanente de cada bando. La decisión posterior **permite que no existan** en un escenario o partida. Por tanto, el documento original no se debe reutilizar sin señalar esta actualización.

En el PDF se muestra un contrato JSON común y se permite ampliar campos, **no sustituir ni renombrar** los oficiales. Nuestros campos `reyes` y `spawn` son complementos internos u opcionales, no requisitos nuevos para admitir un JSON del profesor.

## Cómo resolver futuras ambigüedades

1. Revisar primero el requisito explícito del PDF.
2. Revisar después las reglas propias documentadas.
3. Adoptar una regla determinista, simétrica y consistente con el estado.
4. Guardar el caso de prueba que demuestre la decisión.
5. No afirmar que el repositorio implementa una decisión hasta inspeccionarlo y probarlo.
