# TacticalGrid — documentación de diseño

TacticalGrid es un juego táctico 2D por turnos y un banco de pruebas para algoritmos de búsqueda y toma de decisiones. **El juego proporciona los estados y las reglas; lo que se estudia es cómo decide el sistema inteligente.**

Estos documentos describen el **comportamiento esperado**, no funcionalidades comprobadas en el código. No organizan el proyecto por fases: cada archivo responde a una cuestión de diseño.

## Guía de lectura

| Documento | Qué explica |
| --- | --- |
| [contexto.md](contexto.md) | Problema académico, alcance, restricciones y propósito de los experimentos. |
| [reglas-del-juego.md](reglas-del-juego.md) | Unidades, movimientos, costos, turnos, capturas, jaque, reina, victoria y empate. |
| [estado-y-json.md](estado-y-json.md) | Estado completo, invariantes, contrato JSON y ejemplo compatible. |
| [configuracion-de-reyes.md](configuracion-de-reyes.md) | Reyes opcionales, colocación manual o automática y bloqueo de la configuración. |
| [carga-y-validacion.md](carga-y-validacion.md) | Validaciones, normalización y carga atómica de escenarios. |
| [arquitectura.md](arquitectura.md) | Separación de responsabilidades y comunicación entre backend, API e interfaz. |
| [motor-del-juego.md](motor-del-juego.md) | Contratos de transición, acciones, resultados y configuración de reyes implementados. |
| [busqueda-y-decision.md](busqueda-y-decision.md) | Diferencia entre planificar una ruta y escoger una jugada; métricas y verificaciones. |
| [decisiones-pendientes.md](decisiones-pendientes.md) | Ambigüedades y contradicciones aún no resueltas; no fingir que hay reglas acordadas. |

## Criterios transversales

- El mapa, los costos, las posiciones y los objetivos proceden del JSON: no se incrustan en los algoritmos.
- Ambos bandos usan exactamente las mismas reglas.
- Las operaciones inválidas no alteran una partida ni consumen turno.
- Las búsquedas consultan el motor; no mantienen versiones paralelas de sus reglas.
- La interfaz representa el estado y los resultados reales; no genera resultados simulados.
- Se prioriza código pequeño, explícito y legible; no se crean abstracciones sin una responsabilidad concreta.

## Fuentes y precedencia

1. `Primer proyecto.pdf`: requisitos del profesor y contrato de interoperabilidad.
2. `TacticalGrid_Reglas.md`: definición original de mecánicas propias.
3. Decisiones acordadas para este proyecto: `estandar` ortogonal de un paso; `spawn` inicial; reyes opcionales, configurables antes del primer movimiento; empate si no hay movimiento ni recogida explícita legal.

Cuando una decisión propia parece entrar en tensión con el PDF, se deja visible en [decisiones-pendientes.md](decisiones-pendientes.md), en vez de afirmar que está resuelta. El estado de implementación y las pruebas automatizadas se documentan en [motor-del-juego.md](motor-del-juego.md); la validación personal del estudiante se declara por separado.
