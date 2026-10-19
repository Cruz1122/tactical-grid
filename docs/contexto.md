# Contexto y objetivo

## Qué es TacticalGrid

Es un juego táctico en una cuadrícula bidimensional. Dos bandos, `A` y `B`, compiten por una reina neutral. Para ganar deben recogerla y llevarla a su propia base. El terreno afecta al costo de desplazamiento, los obstáculos condicionan el movimiento y el oponente puede modificar qué jugada conviene.

El propósito principal **no** es construir un videojuego comercial: el tablero hace observables los estados, rutas, costos, decisiones y resultados de algoritmos de inteligencia artificial.

## Preguntas que permite estudiar

1. ¿Qué ruta encuentra un algoritmo sin información heurística?
2. ¿Cambia la ruta cuando se minimiza costo en vez de cantidad de movimientos?
3. ¿Cuánto ayuda una heurística y cuándo puede ser engañosa?
4. ¿Qué se pierde al limitar las alternativas de búsqueda?
5. ¿Qué acción es conveniente cuando el adversario también puede actuar?

Estas preguntas usan el mismo mundo, pero no el mismo problema matemático: **buscar una ruta para una unidad** es distinto de **decidir una acción para un bando completo**.

## Elementos del mundo

- **Cuadrícula:** dimensiones variables, identificadores de terreno y costos externos.
- **Bases:** una para `A` y otra para `B`, definidas en el escenario.
- **Reina neutral:** recurso único, sobre el tablero o transportado por una unidad.
- **Unidades:** unidades móviles de ambos bandos, diferenciadas por tipo.
- **Reyes estratégicos opcionales:** posiciones fijas que pueden quedar amenazadas; no son piezas móviles.
- **Turno:** únicamente el bando activo puede ejecutar una jugada.

## Alcance impuesto por el proyecto

- Escenarios de desarrollo de al menos **20 × 20**, pero hay que aceptar otras dimensiones válidas suministradas desde JSON. El ejemplo del PDF es 4 × 4.
- Costos positivos para terrenos transitables; obstáculos no transitables.
- Importación de escenarios externos que conserven los campos del contrato del profesor.
- Estado completo, generación de acciones legales, costos, búsquedas, decisión adversarial y verificación de resultados.
- Comparaciones experimentales reproducibles y métricas medibles.
- Interfaz que permita observar juego, rutas y decisiones sin necesidad de animaciones complejas.

El texto del profesor dice «al menos tres unidades por bando», pero su JSON de ejemplo tiene dos por bando. Para preservar la compatibilidad con el ejemplo y escenarios externos se acordó **no imponer exactamente tres** en el importador. Esa diferencia sigue siendo un punto que debe explicarse en una sustentación.

## Qué debe poder defender el equipo

No basta con mostrar un camino o una jugada: hay que explicar cómo se representa un estado, por qué una acción es legal, cómo se calcula su costo, qué garantiza cada búsqueda, qué significa una evaluación Minimax y cómo cambia el resultado ante un JSON nunca visto.

**Referencias:** `Primer proyecto.pdf`, pp. 1–4 y 9–10; `TacticalGrid_Reglas.md`, secciones 1 y 7.
