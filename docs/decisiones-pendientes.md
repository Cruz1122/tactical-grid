# Decisiones efectivas y cuestiones todavía abiertas

## Confirmadas por el equipo e implementadas

- `estandar`: un paso ortogonal, pagando el destino. Tipos conocidos `knight`, `rook`, `bishop` y sus alias `caballo`, `torre`, `alfil`. **Otros nombres textuales no vacíos** se mapean a `estandar` según la normalización existente; no cambiar esta política por una validación más estricta.
- JSON del profesor conserva sus claves en español; `spawn`, `reyes` y `recurso_spawn` complementan el estado interno.
- Reyes opcionales configurables antes de la primera acción; su jaque solo impide recoger la reina, no transportarla ni ganar por entrega.
- Al capturar al portador, la reina **regresa a `recurso_spawn`**, no a la casilla de captura; el atacante no la recoge automáticamente.
- Las unidades capturadas reaparecen en spawn original si está libre y legal; de lo contrario esperan inactivas.
- No superponer unidades activas ni ocupar obstáculos/reyes; el estado oficial se modifica solo por transiciones válidas.
- Si el bando al que corresponde jugar no dispone de acciones legales, se declara empate según la implementación.
- Rutas de búsqueda: movimiento voluntario de una pieza sin alternar turnos. Minimax y alfa-beta: acciones de todas las piezas y alternancia real.

## Abiertas: requieren decisión expresa del equipo

- **Repetición/ciclos tácticos:** no existe una regla de empate por repetición ni por límite fijo de turnos. El banco experimental detecta repeticiones y puede detener mediciones, pero no declara un empate oficial. No implementar regla nueva sin aprobación del equipo.
- **Cantidad mínima de piezas:** el texto del profesor habla de al menos tres por bando para desarrollo, pero muestra ejemplos menores. Los escenarios pequeños son útiles para regresión; la sustentación debe incluir el caso 3v3 y los escenarios >=20×20.
- **Pesos adversariales:** son parámetros experimentales, no valores aprendidos ni certificados como óptimos en todos los mapas. Mantener trazas de pruebas al modificarlos.

El contrato de la entrega y las reglas confirmadas prevalecen sobre comentarios históricos desactualizados. No reescribir el motor para acomodar antiguos ejemplos contradictorios.