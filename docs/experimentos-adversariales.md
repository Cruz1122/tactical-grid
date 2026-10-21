# Experimentos 7–10 — resultados regenerados

Ejecutados sobre `backend.tests.test_adversarial.tactical_state`, 6×6 con reina libre en (3,3), A1 estándar en (3,2), A2 torre en (0,1), B1 torre en (3,1) y B2 estándar en (0,5), turno A. La función de evaluación incluye distancia topológica y defensa de aliados. Medidas de un proceso Python 3.13.5 sobre Linux en sandbox; tiempos no transferibles a otras máquinas.

| Caso | Algoritmo / parámetro | Acción elegida | Valor | Hojas evaluadas | Podas | Tiempo aproximado |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 7 | Minimax d=1 | A1 mueve a (3,3) | 362 | 12 | 0 | 0.004 s |
| 7 | Minimax d=2 | A2 captura B1 en (3,1) | 315 | 92 | 0 | 0.026 s |
| 8 | Minimax d=3 | A2 → (3,1) | 845 | 1094 | 0 | 0.265 s |
| 8 | Alfa-beta d=3 | A2 → (3,1) | 845 | 328 | 314 | 0.126 s |
| 9 | Alfa-beta normal d=3 | A2 → (3,1) | 845 | 328 | 314 | 0.127 s |
| 9 | Alfa-beta reverse d=3 | A2 → (3,1) | 845 | 204 | 146 | 0.067 s |
| 10 | Minimax d=4 | A2 → (3,1) | 820 | 11115 | 0 | 2.689 s |

El valor de utilidad no es monótono con la profundidad por el efecto horizonte. Mismo valor/acción entre Minimax y alfa-beta para la misma profundidad y desempate; el número de hojas y podas sí cambia. La versión estructurada completa de resultados, acciones y métricas está en `outputs/adversarial_comparacion.json`, generada con `python -m backend.tests.adversarial_experiments`.

La exploración adversarial `normal/reverse` no es una clasificación de calidad de jugadas, sino un experimento de orden y poda. La exactitud de los valores depende de los pesos documentados y del estado usado.