# Declaración de uso de inteligencia artificial generativa

**TacticalGrid · Registro explícito y no minimizado de asistencia**  
**Estado:** documento para revisión y ratificación del equipo antes de la entrega.  
**Origen de la declaración:** historial de trabajo compartido con ChatGPT, código del repositorio y confirmación directa del usuario de que una **gran parte del código fue hecha con IA**.

## 1. Declaración principal

> **La IA generativa intervino de forma sustancial en el desarrollo de TacticalGrid.** No se usó únicamente para corregir ortografía o sugerir documentación: participó en el diseño e implementación de funciones, generación de prompts para agentes programadores, escritura/revisión de algoritmos de búsqueda, definición de heurísticas, modelado de estados, diseño de pruebas, depuración del comportamiento adversarial, ajuste de la función de evaluación y redacción de documentación. El grado de intervención varía por archivo y no es posible derivar una autoría porcentual exacta solo a partir del código o del historial visible. Por tanto, **no afirmamos que el código sea íntegramente humano** ni asignamos porcentajes inventados.

La asistencia se materializó mediante conversaciones con ChatGPT y trabajos solicitados a agentes de programación. **La iniciativa y muchas decisiones de reglas procedieron del equipo/usuario**, pero parte de la codificación fue generada o transformada con IA. La responsabilidad académica por comprender, probar y defender la versión final corresponde a los integrantes, tal como exige *Primer proyecto.pdf* (sección Uso de inteligencia artificial generativa).

## 2. Matriz de intervención por componente

| Componente | Intervención de IA declarada | Qué sabemos y qué no podemos atribuir con precisión |
|---|---|---|
| Escenarios, estado, normalización JSON | Análisis de contrato, validaciones, casos límite, revisión de capturas/spawns, pruebas de aceptación | El equipo decidió conservar tipos desconocidos mapeados a `estandar`, reyes opcionales y reina en `recurso_spawn`. No hay registro exacto de líneas humanas vs. IA. |
| Motor de movimientos y transiciones | Estructura, revisión de consistencia, propuestas de corrección, pruebas Nemesis y depuración | El motor se contrastó con casos de regresión. La regla de retorno de reina fue **corregida explícitamente por el usuario frente a una sugerencia equivocada de IA**. |
| BFS y DFS | Explicación conceptual, diseño e implementación asistida mediante prompts, comentarios educativos, tests | No deben figurar como algoritmos escritos exclusivamente a mano. |
| UCS | Explicación de heap/relajación, propuesta de implementación y pruebas de caminos de distinto costo | La validación automatizada no demuestra por sí misma comprensión individual. |
| A*, Manhattan y `second_heuristic` | Construcción asistida de heurísticas, justificación, código y pruebas sobre costos/consistencia | El equipo participó en las decisiones; la fórmula por filas/columnas también se desarrolló con asistencia de IA. |
| Beam Search | Estructura por niveles y ancho k, selección heurística, pruebas de descarte | No atribuir 100 % de implementación al estudiante sin evidencias. |
| Minimax, alfa-beta y utilidad | Diseño de pesos, evaluación de amenazas, comparaciones, solución a oscilaciones, nuevas distancias topológicas e intercepción | La corrección estratégica propuesta y codificada en esta revisión fue realizada con asistencia de IA. Su éxito en 6×6 no demuestra dominio perfecto del 20×20. |
| API y frontend | Revisión de endpoints, integración y asistencia sobre visualización, acciones y autopartida | No es posible determinar autoría línea a línea; los estados/acciones reales se verifican mediante API y pruebas. |
| Pruebas y bancos JSON | Generación de escenarios válidos, inválidos, adversariales, propiedades, regresiones y matrices de aceptación | Una prueba escrita por IA puede descubrir un error, pero su presencia **no constituye validación humana**. |
| Documentación y PDFs | Redacción sustancial con IA; estructuración respecto a la rúbrica, texto técnico, manual, tablas, diagramas y anexos | Se declara expresamente que esta memoria también fue redactada con IA. Los autores deben revisarla y corregirla antes de firmar. |

## 3. Errores y límites de la IA que el proyecto permitió identificar

Esta sección es esencial para demostrar **criterio crítico**, no solo consumo de código generado.

- Durante el desarrollo, una respuesta de IA afirmó incorrectamente que la reina debía caer en la casilla de captura. **El usuario rechazó esa regla; la reina vuelve a su spawn original.** La versión final del motor respeta la decisión humana.
- Una primera función de utilidad utilizaba una cercanía geométrica que indujo oscilaciones ante muros; se cambió a una señal topológica tras reproducir el fallo. La corrección mejoró el caso pequeño, pero **no eliminó** la repetición adversarial del 20×20.
- La redacción previa de documentación omitió justificaciones concretas de heurísticas y presentó la intervención de IA demasiado suavizada; esta versión la reemplaza sin minimizar su alcance.
- Una ejecución con 177 pruebas aprobadas no justifica afirmar que los estudiantes revisaron personalmente cada método; es una verificación automatizada, distinta de la sustentación individual.

## 4. Cómo se verifica la asistencia antes de la entrega

**Evidencia técnica ya disponible:** pruebas `unittest`, ejemplos de búsqueda bajo `scenarios/busqueda/`, escenarios de decisión `scenarios/adversarial/`, verificadores de rutas/acciones y trazas `outputs/`. En la copia trabajada localmente se reportaron 177 pruebas aprobadas. Las trazas incluyen una partida terminada en 6×6 y un caso 20×20 detenido por repetición en el simulador de diagnóstico.

**Validación humana todavía por documentar:** cada integrante debe completar su propia revisión de los métodos que defenderá. Ejemplos de tareas individualmente verificables: reconstruir una ruta UCS a mano; demostrar la cota inferior de la heurística propia; explicar una poda α–β con un árbol pequeño; predecir el efecto de un costo cambiado; localizar la condición que devuelve la reina a `recurso_spawn`; adaptar una pequeña regla solicitada por el profesor y ejecutar tests.

### Registro de revisión humana — completar antes de presentar

| Integrante | Métodos revisados | Prueba/experimento reproducido | Cambio o explicación realizado sin IA | Fecha |
|---|---|---|---|---|
| Por completar | Por completar | Por completar | Por completar | Por completar |
| Por completar | Por completar | Por completar | Por completar | Por completar |
| Por completar | Por completar | Por completar | Por completar | Por completar |

No llenar esta tabla con hechos supuestos. Si no hay revisión individual registrada, se declara pendiente.

## 5. Cómo leer `AI usage`, `AI intervention` y `Student validation`

Para métodos relevantes se usan encabezados **exactos** del PDF, con contenido en español:

- **`AI usage: Yes`**: hubo asistencia de IA en la creación, modificación, diseño o verificación del método en el alcance que puede rastrearse; por decisión conservadora, los algoritmos centrales se declaran asistidos. **No significa que la IA haya generado necesariamente cada línea**.
- **`AI intervention`**: debe describir la parte sustancial de la intervención, como generación de lógica de búsqueda, planteamiento de heurística, modelado de evaluación o pruebas adversariales. No ocultarla detrás de «ayudó a documentar» cuando hubo generación de código.
- **`Student validation`**: distingue evidencia objetiva de ejecución (`unittest`, oráculos, trazas) de la revisión **personal de un estudiante**, que sigue pendiente si no se ha confirmado. Nunca se atribuye una defensa personal no observada.

Si el equipo dispone de historial de herramientas que permite atribuir un método específico como totalmente humano, puede precisar esa sección a `AI usage: No` **solo después de comprobarlo**. Declarar conservadoramente el uso de IA es preferible a minimizarlo.

## 6. Responsabilidad y política de entrega

La rúbrica autoriza herramientas de IA, pero exige una declaración consistente con el código y una capacidad real de explicación. Este informe no intenta presentar un producto «sin IA». La nota del proyecto depende también de la sustentación individual: copiar código o docstrings sin comprenderlos contradice explícitamente el objetivo académico. La versión del repositorio debe coincidir con la versión ensayada; todo cambio después de medir debe generar una nueva evidencia de pruebas.