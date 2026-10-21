# Informe de verificación de entrega — revisión en sandbox

Fecha: 2026-10-20/21 (hora Colombia). Fuente: ZIP suministrado de la rama `develop`, no una copia sincronizada por `git clone`. Entorno: Python 3.13.5, Linux, FastAPI del entorno disponible. Los experimentos ejecutados sobre esta copia **no prueban automáticamente** el último commit de GitHub ni la interfaz instalada en otra máquina.

## Estado automatizado

- Antes del ajuste: `python -m unittest discover -s backend/tests -q` — **173 pruebas, todas aprobadas**.
- Tras corregir la evaluación, documentar funciones y añadir regresiones: **177 pruebas, todas aprobadas** en unos 13 segundos.
- Verificación: `python -m compileall -q backend` — correcta.
- Reglas preservadas: tipos desconocidos textuales se mapean a `estandar`; rey opcional; reina capturada retorna a spawn original; jaque no bloquea entrega.

## Partidas completas y diagnósticos

| Escenario | Política | Profundidad | Acciones realmente ejecutadas | Resultado oficial | Observación |
| --- | --- | ---: | ---: | --- | --- |
| `mapa_partida_presentacion.json` 6×6 | alfa-beta | 2 | 24 | B gana | Dejó de oscilar ante el muro, recorrió pasillos y entregó reina |
| `externo_adversarial_3v3.json` 20×20 | alfa-beta | 2 | 105 | Sin ganador | Repetición de posición detectada por banco; no es empate reglamentario |

La traza exacta de acciones legales y métricas está en `outputs/demo_partida_6x6.json` y `outputs/demo_adversarial_20x20.json`. Se generan con `python -m scripts.self_play RUTA --depth 2 --max-turns 120 --output outputs/archivo.json`.

**Interpretación:** el objetivo de reproducir una partida válida se cumple en el ejemplo pequeño. No hay evidencia para afirmar que la función actual siempre finalice partidas 3v3, incluso con profundidad 5. La simetría del juego y las respuestas defensivas pueden crear un estancamiento legítimo. No añadir por defecto victoria ni empate artificial por límite experimental.

## Rendimiento observado

La primera recomendación alfa-beta en el mapa 20×20 tardó unos 0.24 s con profundidad 3 y unos **6.0 s** con profundidad 5 (en esta copia). La elección inicial fue la misma. Minimax sigue siendo exponencial y no se promete respuesta instantánea para profundidad alta. Estas mediciones puntuales no representan un SLA.

## Comparación adversarial 7–10

Los casos 7–10 se ejecutaron nuevamente con la evaluación modificada. Minimax d=3 y alfa-beta d=3 eligieron A2 → (3,1), valor 845. Alfa-beta evaluó 328 hojas frente a 1094 de Minimax. Cambiar el orden produjo 328 frente a 204 hojas evaluadas por alfa-beta, sin alterar acción/valor. Consultar `experimentos-adversariales.md`.

## Calidad documental y frontend

- Se documentaron métodos principales con siete campos exigidos por el PDF, en contenido español y etiquetas de rúbrica.
- Se redactaron `README.md`, manual, informe técnico y declaración de IA. Los nombres reales del equipo y su validación personal no se pueden inferir del código; siguen pendientes.
- Se intentó abrir la interfaz en Chromium/Playwright contra Uvicorn local, pero el navegador devolvió `ERR_BLOCKED_BY_ADMINISTRATOR`. **No se generaron ni adjuntaron capturas in-game no verificadas**. Es obligatorio capturarlas en el entorno real y revisar que tablero/etiquetas/métricas sean legibles.

## Pendientes antes de declarar aprobación total

1. Revisar los 10 casos del PDF frente a las cifras de esta misma versión en el equipo de presentación.
2. Completar nombres de los integrantes y confirmar personalmente la declaración de IA en cada método.
3. Decidir si se desea introducir formalmente una regla de repetición/tiempo, actualmente inexistente.
4. Verificar Phaser/KaTeX y capturas auténticas en navegador accesible.
5. Abrir PR de `develop` hacia `main` después de confirmar que la versión publicada incorpora todos los archivos probados; efectuar squash merge solo tras las comprobaciones finales.