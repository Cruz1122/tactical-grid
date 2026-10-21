# Manual de usuario — TacticalGrid

## 1. Inicio

1. Crear el entorno virtual, instalar las dependencias y ejecutar Uvicorn según `README.md`.
2. Abrir `http://127.0.0.1:8000/`, con conexión a internet para los recursos externos del frontend (Phaser/KaTeX).
3. Cargar un escenario `.json` desde el selector de archivos de la interfaz. El servidor valida el contrato y rechaza documentos incorrectos **sin sustituir la partida activa**.
4. Comprobar dimensiones, bases, reina, turno, fichas y estado presentados en la interfaz.
5. Si el escenario admite configuración de reyes, completarla antes de la primera jugada o jugar sin ellos según las reglas documentadas.

## 2. Partida real — `prueba.modo = "partida"`

- Seleccionar una unidad activa del bando cuyo turno está indicado.
- Elegir un destino legal. Las capturas y reapariciones se resuelven por el motor; los movimientos consumen turno.
- Si una unidad ocupa la casilla de la reina libre y está autorizada, utilizar la recogida explícita. Si se captura al portador, la reina regresa a su `recurso_spawn` original y el atacante no la recoge automáticamente.
- Llevar la reina a la **base propia** para ganar. El jaque impide recogerla, pero no transportarla ni entregarla legalmente.
- La función **Autojugar hasta finalizar** pide una recomendación por turno al adversarial seleccionado y ejecuta cada jugada. Puede tardar más según profundidad y ramificación. Una partida estratégicamente bloqueada puede mantenerse sin vencedor; una repetición no constituye empate automático bajo las reglas actuales.
- Reiniciar restaura el escenario inicial cargado.

## 3. Búsqueda — `prueba.modo = "busqueda"`

Elegir una unidad y un objetivo compatible con el escenario; seleccionar BFS, DFS, UCS, A* (`manhattan` o `second`) o Beam Search (ancho `k`). Ejecutar la consulta, examinar ruta, movimientos, costo y métricas. Las rutas son hipotéticas de una sola pieza: **no** aplican turnos enemigos ni modifican el estado oficial.

BFS minimiza cantidad de movimientos; UCS minimiza costo de terreno; DFS no garantiza optimalidad; A* depende de la heurística; Beam puede descartar caminos y no encontrar una solución existente.

## 4. Decisión adversarial — `prueba.modo = "adversarial"`

Elegir Minimax o alfa-beta, profundidad y orden. El botón **Calcular mejor movimiento** consulta al backend y muestra una acción legal recomendada y sus métricas. Para ejecutarla se utiliza la acción de aplicar recomendación; la consulta sola nunca modifica el turno. El bando del turno es MAX para esa consulta, sin colocar al otro bando en desventaja de reglas.

## 5. API y diagnóstico

`GET /api/state` lee una copia del estado. `POST /api/scenarios` carga JSON. `POST /api/move` mueve una unidad. `POST /api/collect` recoge la reina. `POST /api/search` consulta rutas; `POST /api/adversarial` recomienda la mejor jugada; `POST /api/test` aplica la configuración del modo. `POST /api/verify` comprueba estado, ruta o decisión. La especificación interactiva está en `/docs`.

En caso de error, revisar que sea JSON válido, que las coordenadas estén dentro del tablero, que el turno corresponda y que el objetivo o acción sean legales. Los errores de una solicitud deben conservar el estado anterior. Los resultados de Minimax a profundidad alta pueden consumir segundos o más; probar primero profundidades 1–3.

## 6. Ejemplos preparados

- `scenarios/partida/mapa_partida_presentacion.json`: tablero pequeño con dos unidades estándar y pasillos.
- `scenarios/adversarial/externo_adversarial_3v3.json`: tablero 20×20 con tres unidades estándar por bando.
- `scenarios/busqueda/`: casos reproducibles de geometría, costos, obstáculos y heurísticas.
- `scenarios/adversarial/`: casos 6–10 de decisión y estado compuesto.

No alterar el JSON de profesor cambiando sus claves al pasar de un modo a otro.