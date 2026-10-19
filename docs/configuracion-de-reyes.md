# Reyes: configuración opcional antes de jugar

## Por qué son opcionales

El contrato JSON del profesor no incluye `reyes` como campo obligatorio, mientras que el documento original de reglas de TacticalGrid sí los contemplaba. La decisión actual permite cargar el JSON común **sin añadir reyes ficticios**. La mecánica de jaque funciona únicamente en partidas donde hay reyes configurados.

## Formas de establecerlos

1. **Desde el JSON:** si llega un campo adicional `reyes`, se validan y conservan las posiciones indicadas.
2. **Manualmente en runtime:** durante la configuración, el usuario selecciona las posiciones de los reyes desde la interfaz.
3. **Automáticamente en runtime:** durante la configuración, el usuario solicita una distribución generada por el programa.
4. **Sin reyes:** el usuario puede iniciar la partida sin colocarlos; en ese caso no existe jaque.

**«Runtime» no significa «en cualquier momento».** La colocación manual y automática está permitida **solo antes del primer movimiento**. Una vez iniciada la partida, no se pueden añadir, trasladar ni eliminar reyes. Una nueva carga o un reinicio permiten volver a configurar.

## Validación de colocación

Una posición de rey solo es aceptable si:

- Está dentro del mapa y pertenece a una celda transitable.
- No coincide con obstáculos, otros reyes ni unidades activas.
- No ocupa una base ni impide llegar a ella.
- No se solapa con la posición de la reina presente en el suelo.
- Está asignada inequívocamente al bando correspondiente.

La generación automática debe **proponer** posiciones válidas y ser determinista: dado el mismo escenario y los mismos parámetros de generación, debe producir el mismo resultado. No se ha elegido todavía su algoritmo específico (por ejemplo, cómo priorizar casillas candidatas).

En caso de fallo, la operación de configuración debe informar la causa **sin dejar reyes colocados parcialmente**.

## Relación con el estado

Distinguir conceptualmente dos momentos:

```text
Escenario cargado → Configuración previa al juego → Partida iniciada → Partida terminada
```

Las modificaciones de reyes ocurren exclusivamente en «Configuración previa al juego». No consumen turnos. Una vez iniciada la partida, las posiciones de los reyes son inmutables.

El jaque no se almacena como propiedad editable de rey. El motor lo calcula usando las amenazas de las unidades enemigas a partir del estado actual. Si no hay reyes, la comprobación de jaque es falsa para ambos bandos.

## Restricción de alcance

La generación y la interacción visual para colocar reyes son funcionalidades de configuración, **no forman parte de la carga básica del JSON**. El lector de escenarios acepta su ausencia. Tampoco se permite que una búsqueda hipotética coloque reyes para «mejorar» una ruta.

**Referencias:** `TacticalGrid_Reglas.md`, secciones 1, 2 y 5; contrato de `Primer proyecto.pdf`, pp. 5–6; decisiones posteriores del equipo.
