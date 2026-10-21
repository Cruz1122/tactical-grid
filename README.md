# TacticalGrid

**Sistemas Inteligentes I · Proyecto 1 · Ingeniería de Sistemas y Computación · Universidad de Caldas**

TacticalGrid es un laboratorio interactivo de inteligencia artificial: un juego táctico 2D por turnos donde dos equipos compiten por recoger una reina neutral y llevarla a su base. Se estudian búsquedas sin información, búsqueda de costo, heurísticas, memoria limitada y toma de decisiones adversarial.

> **Integrantes:** **pendiente de completar por el equipo antes de la entrega**. No atribuir nombres ni tareas no confirmadas. Una parte sustancial del código y la documentación fue creada o modificada con asistencia de IA. La trazabilidad está en [`docs/uso-de-ia.md`](docs/uso-de-ia.md).

## Qué hace cada modo

| JSON `prueba.modo` | Algoritmos o acción | Qué ocurre |
|---|---|---|
| `busqueda` | BFS, DFS, UCS, A*, Beam | Ruta hipotética de **una** pieza; el estado oficial no cambia |
| `adversarial` | Minimax, alfa-beta | Recomienda una **única** acción legal con turnos rivales simulados; no la ejecuta |
| `partida` | Turnos reales y autopartida | Permite mover, recoger y aplicar decisiones sucesivas al estado oficial |

## Instalar y ejecutar (Linux / Arch)

Requisitos: Python 3.11 o superior, pip, navegador actualizado y acceso a los CDNs indicados en `frontend/index.html` para cargar Phaser/KaTeX.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Los comandos crean un entorno virtual aislado, lo activan, instalan las dependencias y levantan el servidor de desarrollo. Abre **http://127.0.0.1:8000/**. La documentación de la API está en **http://127.0.0.1:8000/docs**. Frontend y backend se sirven desde el mismo origen HTTP.

Documentación oficial: [Python `venv`](https://docs.python.org/3/library/venv.html), [FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/), [ArchWiki: Python](https://wiki.archlinux.org/title/Python). En Arch, usa `sudo pacman -S python python-pip` solo si no están instalados (actualiza bases y revisa la documentación de pacman según tu entorno).

## Escenarios para demostrar

| Caso profesor | Ejemplo incluido |
|---|---|
| 1. BFS/DFS | `scenarios/busqueda/01_bfs_dfs_laberinto_perfecto.json` |
| 2. BFS/UCS | `scenarios/busqueda/02_bfs_ucs_dos_corredores.json` |
| 3. Obstáculo | `scenarios/busqueda/03_trampa_U_manhattan.json` |
| 4. Heurísticas | `scenarios/busqueda/04_heuristicas_franjas_costosas.json` |
| 5. Beam k | `scenarios/busqueda/05_beam_callejon_engañoso.json` |
| 6. Estado compuesto | `scenarios/adversarial/06_estado_compuesto_turno_A.json` y versión B |
| 7. Defensa | `scenarios/adversarial/07_intercepcion_portador.json` |
| 8. Minimax/alfa-beta | `scenarios/adversarial/08_minimax_alphabeta_intercambio.json` |
| 9. Orden | `scenarios/adversarial/09_orden_alpha_beta.json` |
| 10. Profundidad | `scenarios/adversarial/10_horizonte_profundidad.json` |

Estos archivos son para reproducir fenómenos, no suposiciones de resultados. Las métricas medidas de búsquedas y decisiones están en [`docs/informe-verificacion.md`](docs/informe-verificacion.md) y en `outputs/*.json`.

## Ejecutar las verificaciones

```bash
python -m unittest discover -s backend/tests -q
python -m compileall -q backend
python -m scripts.self_play scenarios/partida/mapa_partida_presentacion.json --depth 2 --max-turns 40
python -m scripts.self_play scenarios/adversarial/externo_adversarial_3v3.json --depth 2 --max-turns 120
```

Los dos primeros validan lógica y sintaxis. Los scripts de autopartida producen **diagnósticos experimentales**, no añaden una regla de empate por repetición. En la versión documentada se aprobaron **177 pruebas automatizadas**; la partida 6×6 terminó con victoria B en 24 acciones y el 20×20 mostró repetición después de 105 acciones sin ganador oficial. Estos límites están declarados, no ocultos.

## Leer antes de presentar

1. [Manual ilustrado de usuario](docs/manual-usuario.md) — controles, tres modos y procedimientos.
2. [Documento técnico](docs/documento-tecnico.md) — estados, complejidad, A* con dos heurísticas, evaluación adversarial y fórmulas reales.
3. [Informe reproducible de verificación](docs/informe-verificacion.md) — números medidos y sus limitaciones.
4. [Experimentos Minimax y alfa-beta](docs/experimentos-adversariales.md) — casos 7–10 con acciones, valores, nodos y tiempos.
5. [Uso de IA generativa](docs/uso-de-ia.md) — declaración **sustancial**, errores corregidos y validación individual pendiente.
6. [Reglas y decisiones confirmadas](docs/decisiones-pendientes.md) — incluye tipo genérico→`estandar` y reina→`recurso_spawn`.
7. [Capturas reales por validar](docs/capturas-por-validar.md) — no se presentan diagramas como pantallazos de Phaser.

## Compatibilidad y estructura

`backend/` contiene reglas, validadores, algoritmos y API; `frontend/`, HTML/CSS/JS + Phaser; `scenarios/`, los JSON de búsqueda, partida, adversarial y entradas erróneas deliberadas; `docs/`, explicación técnica y manual; `scripts/`, reproducción; `outputs/`, trazas y documentos de entrega. Las claves obligatorias del profesor se mantienen en español; los nombres de funciones y rutas del proyecto permanecen en inglés.

**No elimines el banco de regresiones antes de entregar.** Los JSON de error y los tests sirven como evidencia de calidad. El equipo debe añadir los nombres reales de los integrantes y revisar personalmente la documentación y la declaración de IA. El repositorio y sus PDFs deben corresponder al mismo commit ensayado en sustentación.