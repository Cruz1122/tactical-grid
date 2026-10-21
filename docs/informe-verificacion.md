# Informe de verificación integral

Fecha de ejecución: 2026-10-20 (America/Bogota). Commit base:
`42a77384b86e86aceaa732c277a851b965fd8d7a`, con cambios de verificación sin
confirmar en el árbol de trabajo. Entorno: Python 3.14.8 sobre
Linux 7.2.9-2-cachyos x86_64.

## Resultado automatizado

- Suite del repositorio: 178 pruebas aprobadas en 24,798 s.
- Oráculos independientes del paquete adjunto: 14 pruebas aprobadas en 0,093 s.
- Fixtures finales: 31 de 31 importados por el cargador real.
- Banco vigente: 17 válidos aceptados y 65 inválidos rechazados de forma
  atómica. Los siete casos `review/` siguen separados como decisiones pendientes.
- Propiedades generativas: semillas 0–99, mapas rectangulares, costos positivos y
  fraccionarios, alcanzabilidad variable, simetría, escalado y monotonía.
- Fuzzing: estructura, costos, coordenadas, Unicode, JSON mal formado, claves
  duplicadas, parámetros HTTP y límite de 2 MiB; ningún caso produjo HTTP 500
  ni sustituyó el estado oficial.

La política vigente para unidades es deliberada: cualquier nombre textual no
vacío que no sea un tipo conocido se normaliza a `estandar`. Se rechazan los
tipos ausentes, vacíos o no textuales. Esto reclasifica el antiguo caso
`06_tipo_no_implementado.json`: el banco local vigente contiene 17 aceptaciones y
65 rechazos, aunque el manifiesto histórico adjunto indicara 16/66.

## Diez experimentos y tiempos

Los diez casos se ejecutaron también desde la interfaz. Entre las observaciones
visibles estuvieron BFS con 10 movimientos y costo 64 frente a UCS con 12
movimientos y costo 12 en el caso 2; Beam sin ruta para `k=1` y con ruta para
`k=2,4,8` en el caso 5; estados A/B diferenciados en el caso 6; y paridad de
acción y valor entre Minimax y alfa-beta en las profundidades completadas de los
casos 7–10. También se cargó el escenario con tipo `mago`, se mostró como ficha
estándar y se ejecutó una jugada real con cambio de turno.

El ejecutor reproducible midió 40 configuraciones, cada una con cinco intentos,
y registra mediana y rango máximo-mínimo. Veintinueve configuraciones terminaron
y aprobaron sus propiedades. Once quedaron **inconclusas por timeout** de 2,5 s,
principalmente profundidad 3 y dos casos de profundidad 2. No se contabilizan
como aprobaciones ni como divergencias. En las ejecuciones completadas no hubo
diferencia de acción o valor entre Minimax y alfa-beta.

Los resultados completos están en
`outputs/tacticalgrid-verification/plantilla_evidencia.csv` y
`outputs/tacticalgrid-verification/verification_evidence.xlsx`. El límite se
puede cambiar con `--timeout`; aumentarlo requiere repetir toda la medición bajo
la misma máquina y configuración.

```bash
.venv/bin/python tools/run_verification_evidence.py /tmp/tacticalgrid-evidence.json --timeout 2.5
```

## Gate de entrega

El motor, la API, los escenarios, las propiedades, el fuzzing y la comprobación
representativa de interfaz quedaron verificados. No corresponde declarar el gate
total de rendimiento en verde mientras las once configuraciones adversariales
no terminen dentro del límite experimental elegido. La declaración de validación
personal del estudiante también sigue pendiente: una ejecución automatizada o
asistida no sustituye esa revisión académica.
