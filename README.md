# TacticalGrid — Sistemas Inteligentes I

Juego táctico 2D por turnos con búsqueda de rutas y planificación adversarial sobre escenarios JSON externos. Implementación: Python/FastAPI para motor y algoritmos; HTML/CSS/JavaScript y Phaser para el cliente. El frontend consulta resultados reales de la API.

**Integrantes:** completar antes de la entrega: `[nombre completo 1]`, `[nombre completo 2]`, `[nombre completo 3]` (ajustar al equipo real). No presentar el repositorio sin identificar a sus autores.

## Requisitos y ejecución

Python 3.11 o posterior y conexión a internet para cargar Phaser y KaTeX desde CDN (ver `frontend/index.html`). Desde la raíz del repositorio:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

El primer comando crea un entorno aislado; el segundo lo activa; el tercero instala las dependencias; el cuarto ejecuta el servidor de desarrollo. En Arch Linux instala Python mediante `sudo pacman -S python python-pip` si no están disponibles. Documentación: [ArchWiki — Python](https://wiki.archlinux.org/title/Python), [Python — venv](https://docs.python.org/3/library/venv.html), [FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/).

Abrir `http://127.0.0.1:8000/`. La documentación OpenAPI está en `/docs`. Se utiliza **el mismo origen HTTP** para interfaz y API.

## Modos de escenario

| `prueba.modo` | Comportamiento |
| --- | --- |
| `busqueda` | Navegación hipotética de **una** unidad mediante BFS, DFS, UCS, A* o Beam. No juega turnos enemigos ni cambia la partida oficial. |
| `adversarial` | Minimax o alfa-beta recomiendan **una** acción legal usando todas las unidades del turno y respuestas futuras del rival. La API no ejecuta la recomendación. |
| `partida` | La interfaz ejecuta turnos reales mediante el motor. La autopartida solicita recomendaciones sucesivas y aplica las acciones con `/api/move` o `/api/collect`. |

Los modos **no son intercambiables**. Una recomendación adversarial no es una partida completa, y una ruta de búsqueda no es una secuencia garantizada de turnos.

## Pruebas y reproducciones

```bash
python -m unittest discover -s backend/tests -v
python -m compileall -q backend
python -m scripts.self_play scenarios/partida/mapa_partida_presentacion.json --depth 2 --max-turns 40
python -m scripts.self_play scenarios/adversarial/externo_adversarial_3v3.json --depth 2 --max-turns 120
```

Los límites de turnos y detección de repetición del script son **diagnósticos**, no condiciones nuevas de victoria ni empate en el motor. Los resultados históricos de la muestra verificada están en `outputs/`.

## Documentación para la entrega

- [Manual de usuario](docs/manual-usuario.md)
- [Documento técnico](docs/documento-tecnico.md)
- [Resultados y limitaciones verificadas](docs/informe-verificacion.md)
- [Experimentos adversariales 7–10](docs/experimentos-adversariales.md)
- [Declaración y revisión del uso de IA](docs/uso-de-ia.md)
- [Reglas y decisiones acordadas](docs/decisiones-pendientes.md)
- [Índice de documentos existentes](docs/README.md)

Conservar los escenarios de desarrollo y las regresiones automatizadas: forman parte de la evidencia reproducible solicitada por el profesor. Antes de presentar, completar integrantes, verificar personalmente la trazabilidad de IA y repetir las pruebas en el equipo de sustentación.