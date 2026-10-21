# TacticalGrid — Manual ilustrado de usuario

**Sistemas Inteligentes I · Guía para estudiantes y evaluadores · edición 2026**

Este manual explica *qué hace cada control, qué cambia en la partida y qué significan los resultados*. Se basa en la interfaz `frontend/index.html`, `frontend/api.js` y las rutas reales de `backend/main.py`; no es un tutorial imaginario. **Los diagramas incorporados se derivaron de escenarios JSON comprobados y no se presentan como capturas del navegador.** Para obtener capturas in-game genuinas y revisarlas se incluye [un procedimiento de captura](capturas-por-validar.md).

## 1. Preparar el proyecto

**Necesitas:** Python 3.11 o superior, navegador moderno, Git opcional y conexión a internet para cargar Phaser y KaTeX desde las URL CDN que aparecen en el HTML.

Desde la carpeta raíz del repositorio, en Linux o Arch:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

El primer comando crea un entorno virtual local; el segundo lo activa en la terminal actual; el tercero instala las dependencias del backend; y el último inicia la API y el frontend en **un único servidor**. Abre `http://127.0.0.1:8000/` en el navegador. Mantén la terminal con Uvicorn abierta. Swagger está en `http://127.0.0.1:8000/docs`.

En Arch Linux, si falta el intérprete, consulta [ArchWiki: Python](https://wiki.archlinux.org/title/Python). `venv`: [documentación oficial](https://docs.python.org/3/library/venv.html). FastAPI: [primeros pasos](https://fastapi.tiangolo.com/tutorial/first-steps/).

**Antes de presentar:** comprueba que aparece una cuadrícula dibujada por Phaser, no solamente el panel HTML. Si el panel carga y el tablero no, inspecciona la consola del navegador: puede fallar la carga de Phaser desde CDN. No ejecutes la sustentación hasta resolver esa dependencia.

## 2. Entender la pantalla antes de pulsar botones

La interfaz está dividida en un **tablero** y un **panel de controles**. El tablero muestra terreno, unidades A/B, reyes si existen, bases, reina, turno y marcas de búsqueda o decisión. El panel presenta el nombre del archivo cargado, el modo de prueba, opciones de selección y métricas. No todas las opciones aparecen en todos los modos.

![Diagrama de escenario de partida 6x6 construido desde JSON](figuras/diagrama-partida-6x6.svg)

*Figura 1 — Diagrama explicativo creado a partir de `scenarios/partida/mapa_partida_presentacion.json`. No es una captura de la aplicación. Azul = A, rojo = B, rombo = recurso, casilla oscura = obstáculo. Los anillos señalan las bases.*

**Distinción básica:** que una pieza esté visualmente cerca del recurso no significa que pueda alcanzarlo con el siguiente movimiento: las barreras, los costos y el tipo de unidad importan. Tampoco significa que una recomendación adversarial se ejecute sola.

### Leer los elementos

| Elemento | Significado en el juego | Qué observar |
|---|---|---|
| Base A / base B | Casillas de entrega del recurso para su equipo | No se gana por llegar sin reina |
| Reina neutral | Objetivo compartido; su posición inicial queda guardada en `recurso_spawn` | El portador se identifica en el estado; capturarlo devuelve reina al spawn |
| Pieza A / B | Unidad móvil de uno de los equipos | Solo actúa el equipo cuyo turno esté activo |
| Obstáculo | Terreno no transitable | Una torre/alfil no puede atravesarlo; caballo puede saltar según reglas |
| Costo de terreno | Costo de *entrar* o cruzar una casilla | Se usa para UCS/A* y cálculo real de rutas |
| Rey | Pieza estática no capturable | El jaque bloquea recoger la reina, **no** entregarla |

## 3. Cargar uno de los tres modos

En el panel de escenario usa el selector de archivo JSON y escoge, por ejemplo:

| Archivo de ejemplo | `prueba.modo` | Resultado esperado |
|---|---|---|
| `scenarios/busqueda/02_bfs_ucs_dos_corredores.json` | `busqueda` | Se habilita el panel de navegación de una unidad |
| `scenarios/adversarial/07_intercepcion_portador.json` | `adversarial` | Minimax o alfa-beta recomienda la jugada del turno |
| `scenarios/partida/mapa_partida_presentacion.json` | `partida` | Se puede jugar manualmente o activar la autopartida |

**Proceso:** 1) pulsa cargar/seleccionar escenario; 2) elige el JSON; 3) espera confirmación del servidor; 4) revisa nombre, tipo de prueba, dimensiones y turno; 5) antes de una nueva demostración utiliza **reiniciar escenario** si quieres partir de su estado inicial.

Si aparece un error 422, lee el detalle: el servidor rechaza el JSON completo sin sobrescribir la partida que tenías antes. No «arregles» un archivo ocultando unidades o costos; corrígelo según el formato de la rúbrica.

### Qué se guarda al cargar

Una carga válida sustituye el estado inicial y el estado actual del servidor. La búsqueda y la decisión adversarial utilizan **copias** del estado; un movimiento de partida sí cambia el oficial. Esta diferencia se comprueba leyendo `/api/state` antes y después de la operación.

## 4. Modo búsqueda: ejecutar BFS, DFS, UCS, A* o Beam

1. Carga un escenario con `prueba.modo = "busqueda"`, como el de los dos corredores.
2. Selecciona el algoritmo en el panel: BFS, DFS, UCS, A* o Beam Search.
3. Selecciona **unidad de inicio**. Es la única que avanzará hipotéticamente; las demás son el entorno.
4. En **Objetivo · fila, columna**, escribe la meta o pulsa **Elegir** y selecciónala en el tablero.
5. Si elegiste A*, escoge Manhattan o la segunda heurística; si elegiste Beam, indica `k`.
6. Pulsa **Ejecutar búsqueda**. Observa la ruta marcada y lee los indicadores de movimientos, costo, generados, expandidos, frontera máxima y tiempo.
7. Reinicia el escenario o limpia el resultado si vas a repetir con otro algoritmo.

**Cómo interpretar un resultado:** si BFS devuelve 5 movimientos con costo 20 y UCS 7 movimientos con costo 11, ambos pueden estar correctos. BFS optimiza **movimientos**; UCS optimiza **costo acumulado**. Un deslizamiento largo de torre o alfil es un solo movimiento, pero paga las casillas cruzadas.

**A*** selecciona con `f=g+h`. Manhattan cuenta diferencia absoluta de filas más columnas; la segunda heurística estima el costo faltante con mínimos de terreno y geometría de la pieza. La segunda es la elección apropiada para discutir admisibilidad; Manhattan no es siempre admisible en el sistema. **Beam** solo conserva los `k` mejores candidatos por nivel; un `k` pequeño puede perder soluciones.

### Experiencia sugerida para la sustentación

Abre `02_bfs_ucs_dos_corredores.json`. Ejecuta BFS y anota movimientos y costo. Sin modificar el JSON, ejecuta UCS con el mismo origen y destino y explica por qué puede tomar un rodeo de menor costo. Repite A* con ambas heurísticas y observa estados expandidos sin afirmar de antemano cuál será más rápida.

## 5. Modo adversarial: evaluar una acción sin ejecutarla

![Diagrama derivado del escenario 20x20 con tres unidades por bando](figuras/diagrama-adversarial-20x20.svg)

*Figura 2 — Esquema calculado desde `scenarios/adversarial/externo_adversarial_3v3.json`. No es una captura in-game. El fondo muestra terrenos baratos y caros; hay obstáculos cerca del recurso central.*

1. Carga un JSON con `prueba.modo = "adversarial"`.
2. En el apartado **Mejor movimiento del turno**, selecciona **Minimax** o **Alfa-beta**.
3. Escoge **Profundidad** (por ejemplo 2 para demostrar respuesta del rival; el límite de solicitud de la interfaz es 5).
4. Escoge **Orden de acciones**: normal o inverso.
5. Pulsa **Calcular mejor movimiento**.
6. Lee la acción recomendada y las métricas: valor, profundidad, nodos generados, visitados, evaluados, podados y tiempo.
7. Usa **Anterior/Siguiente** para inspeccionar opciones legales si el panel las muestra. La marca visual de una opción indica **origen y destino**, no representa toda la rama interna de Minimax.
8. Si quieres convertir esa recomendación en un turno real, usa **Ejecutar jugada recomendada**. La recomendación inicial por sí misma **no** modifica la partida.

El bando del turno es MAX en la raíz. MIN representa al rival y selecciona respuestas que perjudican la valoración de MAX; no tiene menos capacidad ni reglas diferentes. Con la misma profundidad y utilidad, Minimax y alfa-beta deben devolver la misma decisión; alfa-beta puede evaluar menos hojas porque poda ramas irrelevantes.

**Si tarda demasiado:** reduce profundidad antes de repetir. El crecimiento aproximado es exponencial respecto al número de acciones por turno. Profundidad 5 puede ser costosa en un 20×20; no demuestra mejor juego por sí sola.

## 6. Modo partida: jugar una partida completa

Este modo **sí** altera el estado del servidor. No es lo mismo que recibir una recomendación adversarial.

### Partida manual

1. Carga `scenarios/partida/mapa_partida_presentacion.json`.
2. Comprueba cuál bando tiene el turno y selecciona una unidad activa de ese bando en el tablero.
3. Elige un destino legal. Si la casilla contiene enemigo, el motor aplica la captura.
4. Comprueba el cambio de turno, posible reaparición, estado de la reina y avisos del juego.
5. Si una unidad ya está sobre la casilla de la reina y está autorizada, usa la acción explícita de **recoger reina**; también puede recogerse al llegar legalmente según las reglas del motor.
6. Lleva la reina hasta la base propia. El juego declara victoria solamente después de una entrega legal.

### Autopartida

En modo partida aparece **Autojugar hasta finalizar**. Esta función solicita una recomendación adversarial, la transforma en una acción real, espera la confirmación del servidor y continúa con el siguiente bando. La autopartida no reemplaza la validación de movimientos; sigue utilizando `/api/move` y `/api/collect`. Si se detiene por ausencia de recomendación, error HTTP o repetición observada externamente, no lo presentes como victoria.

**Resultado reproducido:** el escenario de partida 6×6 con alfa-beta a profundidad 2 terminó con victoria oficial de B después de 24 acciones en el registro JSON. El escenario adversarial 20×20, jugado como simulación repetida, alcanzó 105 acciones y se detuvo por un detector de repetición **externo al motor**; no hubo ganador. Véase el informe para los parámetros exactos.

### Qué ocurre en una captura del portador

Cuando capturas a quien lleva la reina, **no te conviertes en portador automáticamente**. La reina vuelve a su posición inicial `recurso_spawn`. La víctima reaparece en su `spawn` si está disponible; en caso contrario permanece inactiva. Por eso una captura puede cambiar la valoración estratégica sin acercar físicamente la reina a tu base.

### Jaque y reyes

Si configuras reyes y tu rey está en jaque, no puedes **recoger** la reina mientras persista el jaque. Sin embargo, puedes **seguir moviendo** y, si ya llevabas la reina, **entregarla**. Los reyes son estáticos. No apliques jaque mate ni otras reglas del ajedrez convencional que el proyecto no define.

## 7. Cómo comparar algoritmos correctamente

Antes de comparar, asegura que escenario, unidad, objetivo, orden y profundidad sean los mismos. Para las búsquedas registra como mínimo los campos del panel; para Minimax y alfa-beta, compara **acción y valor**, luego nodos y tiempo. No mezcles tiempos entre computadores ni compares dos decisiones con profundidades distintas como si se hubiera variado solo la poda.

**Demostraciones esenciales:** BFS/DFS; BFS/UCS; obstáculo que obliga a rodear; A* con dos heurísticas; Beam con k=1,2,4,8; estado compuesto; decisión defensiva; Minimax/alfa-beta; orden normal/inverso; profundidad 1,2,3. Los archivos de escenarios de los diez casos ya están organizados por modo.

## 8. Verificar la respuesta desde la interfaz o la API

La aplicación implementa `/api/verify` para estado, ruta y decisión. En una ruta se revisan desplazamientos legales, costo real y meta alcanzada; en una recomendación se comprueba que la acción sea legal para el turno, no que la estrategia sea infalible. También puedes consultar `/docs` para ver el contrato de cada endpoint sin inventar campos.

Errores frecuentes que puedes explicar durante la sustentación:

| Síntoma | Causa probable | Acción correcta |
|---|---|---|
| Pantalla sin tablero, pero panel HTML visible | Phaser no cargó desde CDN | Revisar conectividad y consola JS antes de la demo |
| JSON rechazado | Dimensiones, identificadores, posiciones o costos no válidos | Leer error 422; conservar y corregir el archivo externo |
| Búsqueda sin ruta | Meta no alcanzable para esa pieza | Contrastar obstáculos, ocupación, tipo y, con alfil, paridad |
| Beam falla y BFS funciona | Se descartó el candidato útil | Aumentar k y mostrar la diferencia |
| Jugada adversarial no parece buena | Horizonte corto o pesos aproximados | Revisar evaluación y profundidad; no afirmar perfección |
| Autopartida repite posiciones | Bloqueo táctico o límite de evaluación | Detener diagnóstico, revisar traza; no inventar empate oficial |

## 9. Capturas visuales y control de calidad

**Estado actual de evidencia gráfica:** el servidor se probó mediante HTTP en el sandbox, pero el navegador automatizado devolvió `ERR_BLOCKED_BY_ADMINISTRATOR` al abrir `127.0.0.1`. Por rigor, este manual no incluye capturas ficticias del frontend. Las figuras 1 y 2 están etiquetadas expresamente como *diagramas*. El archivo [capturas-por-validar.md](capturas-por-validar.md) explica cómo obtener las cuatro imágenes requeridas (inicio, búsqueda, adversarial, partida) y los criterios visuales para aprobarlas; una vez verificadas, se pueden incorporar sin modificar datos ni escenarios.

## 10. Preparar la presentación oral

Ensaya las tres tareas por separado: **buscar una ruta**, **recomendar una acción** y **ejecutar turnos**. Explica al docente que la heurística propia de A* es una cota inferior, mientras que la utilidad adversarial no tiene obligación de ser admisible. Comprueba que todos los integrantes sepan cambiar `costo` en el JSON y defender una modificación pequeña en el método que les toque. Declara el uso real de IA: fue sustancial y requiere validación humana individual.