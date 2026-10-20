# Arquitectura y responsabilidades

## Principio de diseño

Mantener **una sola fuente de verdad para las reglas**. El motor decide qué es legal y cómo cambia un estado. Los algoritmos le consultan; la interfaz solo visualiza y solicita acciones. Esta separación es importante para que una ruta, una recomendación y una jugada real no se contradigan.

## Componentes lógicos

| Componente | Responsabilidad | Lo que no debe hacer |
| --- | --- | --- |
| Escenarios | Leer JSON y preparar un estado candidato | Alterar una partida antes de validar |
| Validación | Revisar contrato, invariantes y acciones | Corregir silenciosamente entradas inválidas |
| Motor del juego (`backend/game/engine.py`) | Coordinar transiciones, capturas, reapariciones y sucesores usando movimiento y jaque existentes | Lógica de presentación y animaciones |
| Movimiento (`backend/game/movement.py`) | Generar movimientos, costos y amenazas de jaque | Cambiar el estado oficial |
| Búsqueda de rutas | Explorar movimientos hipotéticos de una sola unidad | Ejecutar turnos oficiales del rival |
| Decisión adversarial | Evaluar acciones completas de ambos bandos por turnos | Duplicar las reglas del motor |
| API | Exponer operaciones y errores claros | Contener las reglas de ajedrez simplificado |
| Interfaz | Mostrar tablero, estado, rutas, métricas y controles | Inventar estados, costos o resultados |

## Tecnología acordada

- **Backend:** Python, FastAPI, Pydantic y Uvicorn.
- **Frontend:** HTML, CSS, JavaScript y Phaser para el tablero.
- **Comunicación:** cliente y API bajo el mismo origen HTTP.
- **Escenarios:** archivos JSON externos; sin coordenadas fijas en algoritmos.

Estructura implementada relevante para el motor:

```text
backend/
  main.py
  scenarios.py
  game/
    movement.py       # Movimientos legales, costos y jaque
    costs.py          # Wrapper histórico de costos
    validation.py     # Contrato, invariantes y acciones
    engine.py         # Transiciones y sucesores de partida
    state.py          # Reexportaciones históricas del motor
frontend/
  index.html          # Página del juego
  styles.css          # Estilos
  ...                 # JavaScript y Phaser según la estructura real
scenarios/
  ...                 # Ejemplos y escenarios reproducibles

docs/
  ...                 # Diseño y reglas (esta documentación)
```

No crear módulos vacíos por anticipado, ni duplicar un módulo que el repositorio ya tenga. La división anterior expresa responsabilidades, no un requisito de contar con exactamente esos seis archivos Python.

## API como frontera

Rutas orientativas del proyecto (deben verificarse en el código real):

- `GET /api/state`: consultar el estado oficial.
- `POST /api/scenarios`: sustituir el escenario tras una carga válida.
- `POST /api/reset`: reiniciar conforme al escenario cargado.
- `POST /api/move`: solicitar una jugada válida.
- `POST /api/search`: resolver navegación de una unidad seleccionada.
- `POST /api/adversarial`: recomendar una acción mediante juego adversarial.
- `POST /api/verify`: revisar una ruta, decisión o estado.
- `POST /api/test`: ejecutar una prueba configurada, si la aplicación la admite.
- `/docs`: documentación interactiva de FastAPI cuando está activo el servicio.

No suponer que una ruta propuesta ya funciona: estas son **interfaces de diseño**.

## Flujo conceptual de una jugada

```text
Usuario/IA solicita movimiento
  → API recibe datos
  → validación de acción y consulta al motor
  → transición calcula un nuevo estado sin alterar el anterior
  → validación de invariantes
  → confirmación del estado oficial
  → API responde
  → frontend redibuja a partir de la respuesta real
```

Una jugada inválida se corta antes del reemplazo oficial. Una búsqueda hipotética usa copias o estados derivados y jamás modifica la partida viva.

## Simplicidad y legibilidad

Preferir funciones con entradas/salidas claras (`validate_scenario`, `validate_state`, `legal_moves`, `move_cost`, `transition`, `successors`, `state_key`) y estructuras de datos entendibles. No crear un motor paralelo para cada algoritmo: eso introduce divergencias de reglas y dificulta la sustentación.

**Referencias:** `Primer proyecto.pdf`, pp. 2, 6–9; decisiones del equipo sobre stack y separación de responsabilidades.
