# Documentación de TacticalGrid — Índice de entrega

Este índice agrupa documentos escritos a partir de las reglas reales y del código verificado. **No sustituye la lectura ni la revisión individual exigida por el profesor.** La redacción de esta documentación contó con asistencia sustancial de IA y está declarada.

## Ruta de lectura recomendada

| Documento | Para qué sirve | Puntos concretos |
|---|---|---|
| [Manual ilustrado](manual-usuario.md) | Usar el programa | Instalar, cargar JSON, ejecutar búsqueda, decisión adversarial, partida y verificación. Figuras **esquemáticas**, no screenshots. |
| [Documento técnico](documento-tecnico.md) | Sustentación de ingeniería | Modelo compuesto, costos por pieza, fórmulas de A*, función de utilidad con pesos actuales, Minimax y alfa-beta, complejidad. |
| [Resultados verificados](informe-verificacion.md) | Reproducibilidad | Tabla real BFS/DFS/UCS/A*/Beam; nodos de Minimax y alfa-beta, partidas y límites. |
| [Experimentos 7–10](experimentos-adversariales.md) | Preguntas adversariales | Acción defensiva, igualdad entre algoritmos, efecto de orden y profundidad. |
| [Declaración de IA](uso-de-ia.md) | Transparencia requerida | Intervención real en código, pruebas, estrategia y redacción; validación humana pendiente. |
| [Decisiones del equipo](decisiones-pendientes.md) | Evitar reglas inventadas | Mapeo a `estandar`, reyes opcionales, retorno a `recurso_spawn`, repetición no oficial. |
| [Capturas por validar](capturas-por-validar.md) | Evidencia visual honesta | Capturas in-game pendientes; criterios de calidad antes de su inclusión. |

## Consolidación documental

Se sustituyeron los borradores parciales de arquitectura, reglas, carga, modelos y búsqueda por **un documento técnico único y detallado**, el manual, el informe y los anexos. Las decisiones normativas del equipo permanecen explícitas en `decisiones-pendientes.md`. Las versiones antiguas siguen recuperables mediante el historial Git; no se conservan duplicados potencialmente contradictorios en la entrega final.

## Evidencia en el repositorio

`outputs/busqueda_comparacion_real.json` registra casos 1–5 medidos; `outputs/adversarial_comparacion.json` registra casos 7–10; `outputs/demo_partida_6x6.json` y `outputs/demo_adversarial_20x20.json` contienen trazas de autopartida. `backend/tests/` y `scenarios/error/` son pruebas de regresión, **no archivos sobrantes**.

La imagen técnica del manual se creó desde los JSON del juego y está etiquetada como diagrama. **No se inventaron screenshots**: queda una tarea visual pendiente.