# Declaración del uso de IA generativa

Este proyecto utilizó asistencia de IA en explicación de conceptos, diseño de tests, revisión del motor, heurísticas, evaluación adversarial, depuración de ciclos y preparación de documentación. La decisión de mantener `estandar`, los alias de unidades, los reyes opcionales, el regreso de la reina a su spawn original y el contrato JSON fue ratificada por el equipo del proyecto; **la IA no debe sustituir esas decisiones**.

## Trazabilidad de la intervención

| Área | Intervención de IA identificada | Evidencia de comprobación técnica |
| --- | --- | --- |
| BFS, DFS, UCS, A*, Beam | Orientación algorítmica, diseño de heurísticas, métricas y casos límite | `backend/tests/test_search.py`, `test_final_scenarios.py`, `test_properties.py` |
| Motor y validación | Revisión de invariantes, capturas, turnos, errores atómicos y seguridad del recurso | `test_engine.py`, `test_scenarios.py`, `test_nemesis_*.py` |
| Minimax / alfa-beta | Diseño de utilidad, desempates y pruebas comparativas | `test_adversarial.py`, `docs/experimentos-adversariales.md` |
| Ajustes de presentación | Sustitución de Manhattan por distancia topológica, apoyo de segundo y tercer perseguidor, diagnóstico de ciclos | `test_autoplay_regression.py`, `outputs/demo_*.json` |
| Documentación | Estructura y redacción de README, manual, informe técnico y campos de docstring | Comparar contra el PDF y el código antes de entregar |

`AI usage: Yes` en los métodos revisados señala intervención en diseño, auditoría o documentación, no necesariamente que la función fue generada íntegramente. Si el detalle de un método fue exclusivamente manual, los autores deben corregir **ese método** a `AI usage: No` y describirlo con veracidad.

**Validación personal pendiente:** las pruebas ejecutadas en un sandbox y una revisión asistida no demuestran que cada estudiante haya leído y entendido los métodos. Cada integrante debe revisar, modificar y defender personalmente los algoritmos y registrar qué verificaciones hizo. No inventar nombres, autorías, porcentajes de IA ni revisiones no realizadas.

Antes de la sustentación confirmar: nombres de integrantes, historial real de contribuciones Git, docstrings, captura de resultados auténticos y reproducción de casos 1–10 con la versión entregada.