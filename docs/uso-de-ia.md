# Declaración de uso de inteligencia artificial generativa

**TacticalGrid · Declaración de asistencia en el desarrollo**  
**Alcance:** diseño, implementación, revisión, pruebas y documentación.

## 1. Declaración principal

> **La IA generativa intervino de forma sustancial en el desarrollo de TacticalGrid.** No se usó únicamente para corregir ortografía o sugerir documentación: participó en el diseño e implementación de funciones, generación de prompts para agentes programadores, escritura/revisión de algoritmos de búsqueda, definición de heurísticas, modelado de estados, diseño de pruebas, depuración del comportamiento adversarial, ajuste de la función de evaluación y redacción de documentación. El grado de intervención varía por archivo y no se dispone de una atribución porcentual fiable de código generado frente a código editado manualmente.

La asistencia se materializó mediante conversaciones con ChatGPT y trabajos solicitados a agentes de programación. **La iniciativa y varias decisiones de reglas procedieron del equipo**, pero parte de la codificación fue generada o transformada con IA. La responsabilidad académica por comprender, probar y defender la versión final corresponde a los integrantes, tal como exige *Primer proyecto.pdf* (sección Uso de inteligencia artificial generativa).

## 2. Matriz de intervención por componente

| Componente | Intervención de IA declarada | Qué sabemos y qué no podemos atribuir con precisión |
|---|---|---|
| Escenarios, estado, normalización JSON | Análisis de contrato, validaciones, casos límite, revisión de capturas/spawns, pruebas de aceptación | El equipo decidió conservar tipos desconocidos mapeados a `estandar`, reyes opcionales y reina en `recurso_spawn`. No hay registro exacto de líneas humanas vs. IA. |
| Motor de movimientos y transiciones | Estructura, revisión de consistencia, propuestas de corrección, pruebas Nemesis y depuración | El motor se contrastó con casos de regresión. La regla de retorno de reina fue **corregida explícitamente por el usuario frente a una sugerencia equivocada de IA**. |
| BFS y DFS | Explicación conceptual, diseño e implementación asistida mediante prompts, comentarios educativos, tests | La implementación contó con asistencia de IA. |
| UCS | Explicación de heap/relajación, propuesta de implementación y pruebas de caminos de distinto costo | La validación automatizada no demuestra por sí misma comprensión individual. |
| A*, Manhattan y `second_heuristic` | Construcción asistida de heurísticas, justificación, código y pruebas sobre costos/consistencia | El equipo participó en las decisiones; la fórmula por filas/columnas también se desarrolló con asistencia de IA. |
| Beam Search | Estructura por niveles y ancho k, selección heurística, pruebas de descarte | Se registra asistencia de IA en código y diseño. |
| Minimax, alfa-beta y utilidad | Diseño de pesos, evaluación de amenazas, comparaciones, solución a oscilaciones, nuevas distancias topológicas e intercepción | La corrección estratégica propuesta y codificada en esta revisión fue realizada con asistencia de IA. Su éxito en 6×6 no demuestra dominio perfecto del 20×20. |
| API y frontend | Revisión de endpoints, integración y asistencia sobre visualización, acciones y autopartida | No es posible determinar autoría línea a línea; los estados/acciones reales se verifican mediante API y pruebas. |
| Pruebas y bancos JSON | Generación de escenarios válidos, inválidos, adversariales, propiedades, regresiones y matrices de aceptación | Las pruebas automáticas aportan evidencia funcional, aunque no sustituyen la revisión humana. |
| Documentación y PDFs | Redacción sustancial con IA; estructuración respecto a la rúbrica, texto técnico, manual, tablas, diagramas y anexos | Se declara expresamente que esta memoria también fue redactada con IA. El documento es parte de la declaración académica del proyecto. |

## 3. Errores y límites de la IA que el proyecto permitió identificar

Esta sección es esencial para demostrar **criterio crítico**, no solo consumo de código generado.

- Durante el desarrollo, una respuesta de IA afirmó incorrectamente que la reina debía caer en la casilla de captura. **La regla verificada establece que la reina vuelve a su spawn original.** La versión final del motor respeta la decisión humana.
- Una primera función de utilidad utilizaba una cercanía geométrica que indujo oscilaciones ante muros; se cambió a una señal topológica tras reproducir el fallo. La corrección mejoró el caso pequeño, pero **no eliminó** la repetición adversarial del 20×20.
- La documentación incluye explicaciones de las heurísticas y distingue generación asistida, resultados experimentales y garantías matemáticas.
- Las 177 pruebas aprobadas constituyen verificación automatizada; no prueban por sí solas la comprensión individual de los métodos.

## 4. Evidencia de verificación y responsabilidad académica

**Evidencia técnica:** pruebas `unittest`, ejemplos de búsqueda bajo `scenarios/busqueda/`, escenarios de decisión `scenarios/adversarial/`, verificadores de rutas/acciones y trazas `outputs/`. En el entorno de referencia se ejecutaron 177 pruebas satisfactoriamente. Las trazas incluyen una partida terminada en 6×6 y un caso 20×20 detenido por repetición en el simulador de diagnóstico.

**Alcance de la validación humana:** las pruebas automatizadas certifican comportamientos observables, pero la autoría y la comprensión individual no pueden deducirse de sus resultados. Las revisiones personales de cada integrante requieren evidencias propias.


## 5. Cómo leer `AI usage`, `AI intervention` y `Student validation`

Para métodos relevantes se usan encabezados **exactos** del PDF, con contenido en español:

- **`AI usage: Yes`**: hubo asistencia de IA en la creación, modificación, diseño o verificación del método en el alcance que puede rastrearse; por decisión conservadora, los algoritmos centrales se declaran asistidos. **No significa que la IA haya generado necesariamente cada línea**.
- **`AI intervention`**: debe describir la parte sustancial de la intervención, como generación de lógica de búsqueda, planteamiento de heurística, modelado de evaluación o pruebas adversariales. No ocultarla detrás de «ayudó a documentar» cuando hubo generación de código.
- **`Student validation`**: distingue evidencia objetiva de ejecución (`unittest`, oráculos, trazas) de la revisión **personal de un estudiante**, que debe acreditarse independientemente mediante revisión del código y reproducción de experimentos.

La indicación `AI usage: Yes` se utiliza en los métodos centrales para reconocer la participación de IA en diseño, programación y validación, sin pretender atribuir un porcentaje exacto.

## 6. Responsabilidad y política de entrega

La rúbrica autoriza herramientas de IA, pero exige una declaración consistente con el código y una capacidad real de explicación. La participación de IA se declara para facilitar la trazabilidad académica. La comprobación de resultados se fundamenta en escenarios reproducibles, pruebas automatizadas y análisis del comportamiento de los algoritmos.