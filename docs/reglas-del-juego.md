# Reglas del juego

Este documento describe el comportamiento que debe implementar el motor; no es un conjunto de funciones ya implementadas. Las reglas son deterministas y simétricas para `A` y `B`.

## Objetivo

La reina empieza como recurso neutral. Una unidad del bando que tiene el turno puede recogerla al llegar legalmente a su casilla, siempre que no tenga un rey propio en jaque. Si una unidad portadora llega legalmente a la base de su bando, ese bando gana **sin acción adicional de entrega**.

## Unidades y desplazamientos

| Tipo interno | Movimiento permitido | Obstáculos intermedios | Costo |
| --- | --- | --- | --- |
| `knight` (caballo) | En L: dos casillas en un eje y una en el otro | Salta por encima; solo cuenta el destino | Terreno de destino |
| `rook` (torre) | Recta horizontal o vertical, una o varias casillas | No puede atravesar bloqueos | Suma de casillas cruzadas, sin origen |
| `bishop` (alfil) | Diagonal, una o varias casillas | No puede atravesar bloqueos | Suma de casillas cruzadas, sin origen |
| `estandar` | **Una** casilla arriba, abajo, izquierda o derecha | No salta; solo hay destino adyacente | Terreno de destino |

Los desplazamientos deben quedar dentro de la cuadrícula. No se puede terminar sobre un obstáculo, un rey ni una unidad propia. Puede terminarse en la casilla de un enemigo **si el patrón de movimiento permite capturarlo**.

Para torre y alfil, otros actores, obstáculos y reyes bloquean las casillas intermedias. La reina en el suelo también bloquea el paso *a través* de su casilla; puede ser un destino para recogerla. Los terrenos transitables pueden tener costos diferentes; los algoritmos deben obtenerlos del escenario.

Los tipos internos de código se expresan en inglés por convención. El validador también admite los alias `caballo`, `torre` y `alfil` en JSON y el motor aplica sus mismos patrones de movimiento.

## Turnos y acciones

En cada turno se elige **una unidad móvil del bando activo** y se intenta realizar un desplazamiento completo. Un desplazamiento largo de torre o alfil consume una jugada, no un turno por casilla.

Una transición de partida válida comprende, conceptualmente:

1. Comprobar el bando, la unidad, su actividad y la legalidad del movimiento.
2. Calcular costo real según el tipo de unidad y el terreno.
3. Aplicar movimiento y captura, si corresponde.
4. Actualizar reina, posibles reapariciones y estado de jaque derivado.
5. Comprobar victoria o ausencia de movimientos legales; si continúa, alternar el turno.

Una acción inválida no modifica ningún dato oficial, no consume turno y no genera costo. La secuencia exacta entre comprobación de victoria y reapariciones debe permanecer consistente; los casos terminales no deben cambiar de resultado por el orden interno de funciones.

## Capturas y spawn

Una captura ocurre cuando una unidad termina legalmente en la casilla de una unidad enemiga. La unidad capturada intenta reaparecer inmediatamente en su `spawn`, que por decisión del equipo es **su posición inicial cargada del JSON**.

- Si la casilla `spawn` está transitable y libre de unidades activas, reyes y reina en el suelo, la unidad capturada reaparece allí.
- Si no está disponible, queda inactiva fuera del tablero, conservando su `spawn`.
- Después de cada acción se vuelve a comprobar si una unidad inactiva puede reaparecer.
- La partida no puede tener dos unidades móviles activas ocupando la misma casilla.

Si se captura al portador, la reina vuelve a su `recurso_spawn` original. **El atacante no recoge la reina automáticamente** y la reina nunca se coloca en la casilla de captura por este evento. El `spawn` de la ficha capturada conserva su posición inicial y se usa únicamente para su propia reaparición. Si la reina ya está en el suelo bajo una ficha aliada por la configuración del escenario, esa ficha puede realizar una recogida explícita que consume un turno.

## Reyes y jaque

Los reyes no se mueven, no pueden capturarse y no consumen turnos. Son **opcionales**: una partida sin reyes es válida y en ella no hay jaques.

Cuando existen, un rey está en jaque si una unidad enemiga lo amenaza según el patrón de movimiento aplicable:

- Caballo: las ocho posiciones en L, independientemente de obstáculos intermedios.
- Torre: misma fila o columna, con línea de ataque sin bloqueos.
- Alfil: misma diagonal, con línea de ataque sin bloqueos.
- `estandar`: una casilla ortogonal adyacente (consecuencia del movimiento elegido para ese tipo).

El jaque **solo impide recoger la reina**. No impide mover, capturar, bloquear, atacar o seguir transportando una reina que ya se tenía. No existe jaque mate. El jaque se **calcula** a partir de las posiciones: no debe guardarse como dato mutable independiente.

## Recogida, transporte y victoria

- Hay una sola reina y, como máximo, una unidad portadora.
- Si no hay portador, la reina tiene una posición sobre el tablero.
- Si existe portador, la reina no mantiene una segunda posición independiente en el estado interno.
- Recogerla exige una llegada legal a su casilla, turno del bando y ausencia de jaque propio. Si la unidad ya ocupa la casilla, puede usar una acción explícita de recogida bajo las mismas condiciones; consume un turno y no desplaza la unidad.
- Transportarla no cambia el patrón ni costo de movimiento de su unidad.
- Si la unidad portadora llega a la base de su equipo: victoria inmediata.

## Ausencia de movimientos y empate

**Decisión del equipo:** si el bando al que corresponde actuar no tiene ninguna acción legal (movimiento ni recogida explícita) con sus unidades, la partida termina **en empate, sin ganador**. Deben considerarse las reapariciones correspondientes antes de declarar esa condición. No se deben inventar jugadas de «pasar turno».

## Reglas de ocupación

- Las unidades activas no se superponen entre sí.
- Ninguna unidad activa ocupa obstáculo ni casilla de rey.
- Los reyes no pueden bloquear bases y sus ubicaciones deben ser válidas.
- La reina y una unidad pueden compartir posición únicamente si el escenario la carga así o si su `recurso_spawn` coincide con una unidad; el estado debe distinguir la posesión de mera coincidencia espacial.
- Una partida terminada no acepta más acciones.

**Referencias:** `TacticalGrid_Reglas.md`, secciones 1–6; `Primer proyecto.pdf`, pp. 2–3. Las normas de `estandar`, reyes opcionales y empate corresponden a decisiones posteriores del equipo.
