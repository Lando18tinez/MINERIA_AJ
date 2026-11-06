# Resultados de validación del modelo estrella · Etapa 5

Generado por `validar_modelo.py` el 2026-11-05. La base se abre en **solo lectura**; este informe no la modifica.

**Base validada:** `data/modelo/modelo_estrella.db` · **Consultas:** `sql/02_validaciones.sql` · **Orígenes:** `data/powerbi/hechos_vehiculos.csv` y `data/processed/resultados_conocimiento_evidente.json`.

Los vehículos se cuentan con `SUM(cantidad)`. La diferencia es *modelo − origen*.

## Resumen

| Bloque | Comprobaciones | Correctas | Con diferencia o falla |
| --- | ---: | ---: | ---: |
| Validaciones del esquema (SQL, deben dar 0) | 24 | 24 | 0 |
| Comparaciones A–D con el origen (una por fila de cada tabla) | 51 | 51 | 0 |

## 1. Validaciones del esquema (`sql/02_validaciones.sql`)

Las comprobaciones «deben ser 0» cuentan los casos que incumplen la regla. Las informativas solo se reportan.

### Unicidad de claves primarias

| Id | Comprobación | Valor | Esperado | Estado |
| --- | --- | ---: | ---: | --- |
| PK01 | dim_tiempo.id_tiempo: valores repetidos | 0 | 0 | OK |
| PK02 | dim_territorio.id_territorio: valores repetidos | 0 | 0 | OK |
| PK03 | dim_combustible.id_combustible: valores repetidos | 0 | 0 | OK |
| PK04 | dim_vehiculo.id_vehiculo: valores repetidos | 0 | 0 | OK |
| PK05 | dim_modelo.id_modelo: valores repetidos | 0 | 0 | OK |
| PK06 | hechos_registros.id_hecho: valores repetidos | 0 | 0 | OK |

### Unicidad de llaves naturales

| Id | Comprobación | Valor | Esperado | Estado |
| --- | --- | ---: | ---: | --- |
| NK01 | dim_tiempo (anio): valores repetidos | 0 | 0 | OK |
| NK02 | dim_territorio (territorio): valores repetidos | 0 | 0 | OK |
| NK03 | dim_combustible (codigo): valores repetidos | 0 | 0 | OK |
| NK04 | dim_vehiculo (clase, carroceria): parejas repetidas | 0 | 0 | OK |
| NK05 | dim_modelo (anio_modelo): valores repetidos | 0 | 0 | OK |

### Correspondencia de claves foráneas

| Id | Comprobación | Valor | Esperado | Estado |
| --- | --- | ---: | ---: | --- |
| FK01 | hechos_registros.id_tiempo sin pareja en dim_tiempo | 0 | 0 | OK |
| FK02 | hechos_registros.id_territorio sin pareja en dim_territorio | 0 | 0 | OK |
| FK03 | hechos_registros.id_combustible sin pareja en dim_combustible | 0 | 0 | OK |
| FK04 | hechos_registros.id_vehiculo sin pareja en dim_vehiculo | 0 | 0 | OK |
| FK05 | hechos_registros.id_modelo sin pareja en dim_modelo | 0 | 0 | OK |
| FK06 | PRAGMA foreign_key_check: violaciones en toda la base | 0 | 0 | OK |

### Duplicados en las 5 claves foráneas

| Id | Comprobación | Valor | Esperado | Estado |
| --- | --- | ---: | ---: | --- |
| DU01 | combinaciones (id_tiempo, id_territorio, id_combustible, id_vehiculo, id_modelo) repetidas | 0 | 0 | OK |

### Ausencia de NULL

| Id | Comprobación | Valor | Esperado | Estado |
| --- | --- | ---: | ---: | --- |
| NU01 | hechos_registros.id_tiempo NULL | 0 | 0 | OK |
| NU02 | hechos_registros.id_territorio NULL | 0 | 0 | OK |
| NU03 | hechos_registros.id_combustible NULL | 0 | 0 | OK |
| NU04 | hechos_registros.id_vehiculo NULL | 0 | 0 | OK |
| NU05 | hechos_registros.id_modelo NULL | 0 | 0 | OK |
| NU06 | hechos_registros.cantidad NULL | 0 | 0 | OK |

### SIN DATO y SIN CARROCERIA

| Id | Comprobación | Valor | Esperado | Estado |
| --- | --- | ---: | ---: | --- |
| SD01 | SIN DATO: miembros en dim_vehiculo | 1 | — | Informativo |
| SD02 | SIN DATO: grupos en hechos_registros | 1 | — | Informativo |
| SD03 | SIN DATO: vehículos (SUM de cantidad) | 2 | — | Informativo |
| SC01 | SIN CARROCERIA: miembros en dim_vehiculo | 7 | — | Informativo |
| SC02 | SIN CARROCERIA: grupos en hechos_registros | 2.117 | — | Informativo |
| SC03 | SIN CARROCERIA: vehículos (SUM de cantidad) | 17.260 | — | Informativo |

## 2. Comparaciones con el origen

### A. Filas y SUM(cantidad)

Origen: `data/powerbi/hechos_vehiculos.csv` (filas y suma de `cantidad`)

| Concepto | Valor del modelo | Valor de origen | Diferencia | Estado |
| --- | ---: | ---: | ---: | --- |
| Filas (grupos de registro) | 6.772 | 6.772 | 0 | OK |
| SUM(cantidad) (vehículos) | 155.777 | 155.777 | 0 | OK |

### B. Vehículos por año

Origen: `p3_temporal.serie_anual` del JSON

| Año de registro | Valor del modelo | Valor de origen | Diferencia | Estado |
| --- | ---: | ---: | ---: | --- |
| 2015 | 586 | 586 | 0 | OK |
| 2016 | 504 | 504 | 0 | OK |
| 2017 | 450 | 450 | 0 | OK |
| 2018 | 2.104 | 2.104 | 0 | OK |
| 2019 | 5.435 | 5.435 | 0 | OK |
| 2020 | 7.908 | 7.908 | 0 | OK |
| 2021 | 20.304 | 20.304 | 0 | OK |
| 2022 | 30.513 | 30.513 | 0 | OK |
| 2023 | 34.039 | 34.039 | 0 | OK |
| 2024 | 53.934 | 53.934 | 0 | OK |
| Total | 155.777 | 155.777 | 0 | OK |

### C. Vehículos por combustible

Origen: `p1_composicion.por_combustible` del JSON

| Combustible | Valor del modelo | Valor de origen | Diferencia | Estado |
| --- | ---: | ---: | ---: | --- |
| GASO ELEC | 117.315 | 117.315 | 0 | OK |
| ELECTRICO | 36.969 | 36.969 | 0 | OK |
| DIES ELEC | 1.489 | 1.489 | 0 | OK |
| HIDROGENO | 4 | 4 | 0 | OK |
| Total | 155.777 | 155.777 | 0 | OK |

### D. Vehículos por departamento

Origen: `p2_territorial.por_departamento` del JSON

| Departamento | Valor del modelo | Valor de origen | Diferencia | Estado |
| --- | ---: | ---: | ---: | --- |
| BOGOTA D.C. | 63.610 | 63.610 | 0 | OK |
| ANTIOQUIA | 31.566 | 31.566 | 0 | OK |
| CUNDINAMARCA | 19.598 | 19.598 | 0 | OK |
| VALLE DEL CAUCA | 11.312 | 11.312 | 0 | OK |
| NORTE DE SANTANDER | 6.505 | 6.505 | 0 | OK |
| RISARALDA | 3.936 | 3.936 | 0 | OK |
| BOLIVAR | 3.367 | 3.367 | 0 | OK |
| ATLANTICO | 2.534 | 2.534 | 0 | OK |
| SANTANDER | 2.211 | 2.211 | 0 | OK |
| META | 1.711 | 1.711 | 0 | OK |
| CALDAS | 1.494 | 1.494 | 0 | OK |
| BOYACA | 1.325 | 1.325 | 0 | OK |
| TOLIMA | 1.225 | 1.225 | 0 | OK |
| NARINO | 729 | 729 | 0 | OK |
| HUILA | 683 | 683 | 0 | OK |
| CORDOBA | 617 | 617 | 0 | OK |
| CAUCA | 604 | 604 | 0 | OK |
| CESAR | 566 | 566 | 0 | OK |
| QUINDIO | 543 | 543 | 0 | OK |
| SUCRE | 409 | 409 | 0 | OK |
| CASANARE | 368 | 368 | 0 | OK |
| MAGDALENA | 309 | 309 | 0 | OK |
| CAQUETA | 286 | 286 | 0 | OK |
| PUTUMAYO | 105 | 105 | 0 | OK |
| ARAUCA | 43 | 43 | 0 | OK |
| LA GUAJIRA | 35 | 35 | 0 | OK |
| ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA | 32 | 32 | 0 | OK |
| GUAINIA | 24 | 24 | 0 | OK |
| GUAVIARE | 13 | 13 | 0 | OK |
| AMAZONAS | 9 | 9 | 0 | OK |
| CHOCO | 6 | 6 | 0 | OK |
| VICHADA | 2 | 2 | 0 | OK |
| Total | 155.777 | 155.777 | 0 | OK |

## 3. Diferencias encontradas

Ninguna. Todas las comparaciones A–D coinciden con su origen y las validaciones del esquema dan 0.
