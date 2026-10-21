# Capturas reales del juego — procedimiento de validación

**Estado actual: PENDIENTE.** La captura automática no pudo abrir la página local: Chromium/Playwright respondió `net::ERR_BLOCKED_BY_ADMINISTRATOR` para `http://127.0.0.1:8765/`. El servidor FastAPI sí devolvió HTTP 200 por `curl`. **No se fabricarán capturas ni se presentarán diagramas como pantallazos in-game.**

El manual incluye dos **diagramas fieles a escenarios JSON**, visualmente identificados como representaciones técnicas, no capturas. Para cumplir la expectativa del equipo de incluir pantallazos auténticos, capturar en un equipo con navegador funcional:

1. **Inicio / partida:** cargar `scenarios/partida/mapa_partida_presentacion.json`; mostrar tablero completo, unidades, bases, recurso y turno.
2. **Búsqueda:** cargar `scenarios/busqueda/02_bfs_ucs_dos_corredores.json`; seleccionar unidad/objetivo, ejecutar UCS, capturar ruta y métricas visibles.
3. **A* con heurísticas:** en `scenarios/busqueda/04_heuristicas_franjas_costosas.json`, ejecutar A* con `manhattan` y luego con `second`; capturar ambas ejecuciones con escenario y objetivo idénticos.
4. **Adversarial:** cargar `scenarios/adversarial/07_intercepcion_portador.json`, profundidad 2, ejecutar alfa-beta; mostrar acción recomendada y métricas.
5. **Autopartida:** cargar `scenarios/partida/mapa_partida_presentacion.json` y ejecutar los turnos; documentar el momento en que se transporta la reina y el resultado terminal real.

**Calidad mínima antes de insertar:** imagen PNG 1440×900 o superior; tablero **entero** y panel de resultados suficientemente legibles; sin barras del navegador que tapen el estado; escenario y parámetros identificables; sin datos personales; sin recortes que cambien la interpretación; sin indicadores de carga superpuestos; valores que coincidan con logs de API o ejecución. Validar visualmente cada captura antes de incluirla y conservar el JSON que la produjo.

Las capturas aprobadas deben guardarse bajo `docs/figuras/capturas/` con nombres `01-partida.png`, `02-ucs.png`, `03-astar-manhattan.png`, `04-astar-propia.png`, `05-alfa-beta.png`, `06-autopartida.png`. Solo entonces agregar sus imágenes al manual y al PDF regenerado. **Este paso requiere navegador real con Phaser/KaTeX cargados.**