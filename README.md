<h1 align="center">TacticalGrid</h1>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white" alt="Backend: FastAPI"></a>
  <a href="https://phaser.io/"><img src="https://img.shields.io/badge/Frontend-Phaser%204-8A2BE2?logo=phaser&logoColor=white" alt="Frontend: Phaser 4"></a>
</p>

TacticalGrid es un juego táctico por turnos y un entorno de experimentación para
algoritmos de búsqueda y decisión adversarial. Dos bandos compiten por una reina
neutral: deben recogerla y transportarla hasta su propia base mientras el terreno,
las capturas, los reyes opcionales y el turno modifican las acciones legales.

El repositorio incluye un backend FastAPI, una interfaz web servida por la misma
aplicación, escenarios JSON y pruebas deterministas para el motor, la API, BFS,
DFS, UCS, A*, Beam Search, Minimax y poda alfa-beta.

## Requisitos

- Python 3.10 o posterior.
- `pip`, que normalmente se instala junto con Python.
- Acceso a Internet al abrir la interfaz por primera vez, porque Phaser se carga
  desde un CDN. El backend y las pruebas Python no dependen de Phaser.

## Instalación y ejecución

Ejecuta los comandos desde la raíz del repositorio, donde está
`requirements.txt`.

### 1. Comprueba la versión de Python

```bash
python3 --version
```

Si `python3` no existe, prueba con `python --version`. Necesitas Python 3.10 o
posterior. Si la versión es anterior o no tienes Python instalado, instálalo
antes de continuar:

```bash
# Arch / CachyOS
sudo pacman -S --needed python

# Debian / Ubuntu
sudo apt update && sudo apt install python3 python3-venv python3-pip

# Fedora
sudo dnf install python3 python3-pip
```

En macOS puedes usar `brew install python` o el instalador de
[python.org](https://www.python.org/downloads/). En Windows, instala desde
python.org y marca **Add Python to PATH**; después comprueba la versión con
`py -3 --version`.

### 2. Crea y activa un entorno virtual

Si aún no tienes un entorno virtual, créalo dentro del repositorio. Los
siguientes comandos generan la carpeta `.venv`:

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows CMD:

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
```

Con el entorno activo verás `(.venv)` al principio del prompt. Si el comando
`python3 -m venv` falla en Debian o Ubuntu por falta de `ensurepip`, instala
`python3-venv` con el comando de la sección anterior y vuelve a intentarlo.

También puedes usar el intérprete del entorno sin activarlo:

```bash
# Linux / macOS
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --reload

# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

### 3. Instala las dependencias

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Ejecuta la aplicación

```bash
python -m uvicorn backend.main:app --reload
```

La aplicación queda disponible en <http://127.0.0.1:8000>. La documentación
interactiva de la API está en <http://127.0.0.1:8000/docs>. Para detener el
servidor pulsa <kbd>Ctrl</kbd>+<kbd>C</kbd>; para salir del entorno virtual,
ejecuta `deactivate`.

Si no puedes usar un entorno virtual, puedes instalar las dependencias para tu
usuario e iniciar el servidor con el mismo intérprete:

```bash
python3 -m pip install --user -r requirements.txt
python3 -m uvicorn backend.main:app --reload
```

Este modo puede fallar si la distribución bloquea las instalaciones globales
(PEP 668, por ejemplo en Debian/Ubuntu). En ese caso, usa el entorno virtual:
es la opción recomendada.

La interfaz permite cargar un escenario JSON, configurar reyes antes de la
primera acción, jugar manualmente, buscar rutas y solicitar una recomendación
Minimax o alfa-beta. Las búsquedas y recomendaciones trabajan sobre copias del
estado oficial; solo los endpoints de movimiento, recogida, configuración, carga
y reinicio modifican la partida.

## Verificación automatizada

Ejecuta toda la suite desde la raíz del repositorio:

```bash
.venv/bin/python -m unittest discover -s backend/tests -t . -v
```

Si activaste el entorno virtual, puedes usar `python` en lugar de
`.venv/bin/python`. En Windows, sustituye `.venv/bin/python` por
`.venv\Scripts\python.exe`.

La suite cubre, entre otros contratos:

- carga y preparación de escenarios válidos, además del rechazo de entradas inválidas;
- carga de los 31 fixtures de búsqueda y adversarial en `scenarios/busqueda/` y `scenarios/adversarial/`;
- movimientos, costos, capturas, reaparición y retorno de la reina a su
  `recurso_spawn` original;
- rutas reproducidas paso a paso y estado inmutable durante búsquedas;
- optimalidad aplicable a BFS, UCS y A* con la segunda heurística;
- ancho y descarte real de Beam Search;
- paridad de acción y valor entre Minimax y alfa-beta;
- contratos HTTP y rechazo controlado de entradas inválidas.

Para una comprobación sintáctica adicional:

```bash
.venv/bin/python -m compileall -q backend
```

Los tiempos son observaciones de la máquina que ejecuta la prueba, no contratos.
La ramificación adversarial crece rápidamente: los escenarios 20×20 pueden
superar un límite breve a profundidad 3, especialmente con Minimax sin poda.

## Estructura

```text
backend/
  algorithms/   Búsquedas, heurísticas, evaluación y verificación
  game/         Estado, movimientos, validación y transiciones
  tests/        Pruebas unitarias, de integración y contratos HTTP
frontend/       Interfaz web y recursos visuales/sonoros
scenarios/
  partida/      Escenarios iniciales y de juego
  adversarial/  Fixtures de Minimax y alfa-beta
  busqueda/     Fixtures de algoritmos de búsqueda de rutas
  error/        Entradas inválidas de referencia
docs/           Reglas, arquitectura y documentación técnica
```

## Contratos importantes

- Los terrenos transitables tienen costo estrictamente positivo.
- Se aceptan `knight`, `rook`, `bishop`, `estandar` y los alias `caballo`,
  `torre`, `alfil`; otros nombres textuales no vacíos se mapean a `estandar`,
  mientras los tipos ausentes, vacíos o no textuales se rechazan.
- Capturar al portador devuelve la reina a su `recurso_spawn` original. El
  atacante no la recoge automáticamente.
- Los mapas rectangulares y tamaños externos válidos se aceptan; 20×20 es un
  tamaño de desarrollo, no una restricción del importador.
- Una importación admite como máximo 2 MiB, mapas de 100×100 (10 000
  celdas), 200 unidades y 200 reyes. Beam admite `k` entre 1 y 64. Las
  solicitudes adversariales explícitas por HTTP usan profundidades entre 0 y 5;
  la profundidad definida dentro del escenario acepta cualquier entero no
  negativo. El tope HTTP es una protección operativa, no una regla del juego.
- Las claves JSON duplicadas se rechazan porque su interpretación depende del
  analizador. Los campos adicionales se conservan y las cadenas deben poder
  serializarse como UTF-8.


## Documentación

La guía de lectura está en [docs/README.md](docs/README.md). Los documentos más
relevantes para implementar o sustentar el proyecto son:

- [Reglas del juego](docs/reglas-del-juego.md)
- [Estado y contrato JSON](docs/estado-y-json.md)
- [Carga y validación](docs/carga-y-validacion.md)
- [Motor del juego](docs/motor-del-juego.md)
- [Búsqueda y decisión](docs/busqueda-y-decision.md)
- [Arquitectura y API](docs/arquitectura.md)
- [Informe de verificación integral](docs/informe-verificacion.md)

El uso de IA y el estado de validación personal del estudiante se declaran en
[docs/motor-del-juego.md](docs/motor-del-juego.md). La validación automatizada no
sustituye la revisión personal, la evidencia visual de la interfaz ni la defensa
oral de los métodos.
