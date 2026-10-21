# Documentación de TacticalGrid

**Juan Camilo Cruz Parra · Sistemas Inteligentes I**

Los documentos están organizados por tarea: aprender a utilizar la aplicación, consultar las reglas, comprender la implementación y reproducir los resultados experimentales.

| Documento | Contenido |
|---|---|
| [Manual de usuario](manual-usuario.md) | Instalación, interfaz, carga de escenarios, búsqueda, decisión adversarial y juego por turnos. Incluye diagramas de los tableros. |
| [Reglas del juego](reglas-del-juego.md) | Piezas, terrenos, reyes, reina, capturas, victoria y semántica de los tres modos. |
| [Documento técnico](documento-tecnico.md) | Arquitectura, estado, validaciones, algoritmos, heurísticas, función de utilidad y complejidad. |
| [Informe de verificación](informe-verificacion.md) | Escenarios ejecutados, rutas, costos, métricas, pruebas automatizadas y resultados de partidas. |
| [Experimentos adversariales](experimentos-adversariales.md) | Comparación de Minimax y alfa-beta, orden de acciones y profundidades. |
| [Uso de inteligencia artificial](uso-de-ia.md) | Alcance de la asistencia en el desarrollo, generación de código, pruebas y métodos de validación. |

## Reproducir resultados

Los escenarios se encuentran en `scenarios/busqueda/`, `scenarios/adversarial/` y `scenarios/partida/`. Los archivos de `scenarios/error/` permiten comprobar los rechazos del validador. Las mediciones y trazas asociadas están en `outputs/`.

Para ejecutar los algoritmos desde la interfaz, sigue el [manual de usuario](manual-usuario.md). Para interpretar la complejidad, la admisibilidad de las heurísticas y los valores de Minimax, consulta el [documento técnico](documento-tecnico.md).