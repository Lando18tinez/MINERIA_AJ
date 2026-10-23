# Datos para Power BI · Conocimiento evidente

Mismo dataset de las etapas anteriores: **Vehículos eléctricos e híbridos matriculados en Colombia – RUNT 2.0**
(datos.gov.co · `ntxy-q9ix`), con el tratamiento de la Etapa 2. No es un dataset nuevo.

> **No usar `vehiculos_limpios.csv`.** Tiene la carga triplicada, `cantidad` alterada (suma 182.794 en vez de 332.901)
> y las columnas `clase` y `carroceria` vacías.

Se regenera con `python conocimiento_evidente.py` (desde la raíz del proyecto).

## Archivos (modelo en estrella)

| Archivo | Filas | Contenido |
|---|---:|---|
| `hechos_vehiculos.csv` | 10.748 | Una fila por **grupo de vehículos**. `cantidad` = cuántos vehículos tiene el grupo. |
| `dim_territorio.csv` | 265 | `territorio` (llave única: «MUNICIPIO (DEPARTAMENTO)»), `municipio`, `departamento`. |
| `dim_combustible.csv` | 4 | `combustible` (código) y `combustible_etiqueta` legible. |
| `dim_anio.csv` | 12 | `anio_registro` y `estado_anio` (`Completo` / `Parcial`). |

Columnas de `hechos_vehiculos`: `combustible`, `clase`, `carroceria`, `anio_registro`, `modelo`, `territorio`,
`cantidad`, `modelo_inusual` (Sí/No), `grupo_grande` (Sí/No).

Archivos UTF-8 con BOM, separador coma. En Power BI: *Obtener datos → Texto/CSV*, los cuatro archivos.

## Relaciones (todas muchos a uno, un solo sentido: dimensión → hechos)

```
hechos_vehiculos[territorio]     →  dim_territorio[territorio]
hechos_vehiculos[combustible]    →  dim_combustible[combustible]
hechos_vehiculos[anio_registro]  →  dim_anio[anio_registro]
```

Con estas relaciones no se duplican ni se pierden vehículos: se comprobó que al unir los hechos con las tres
dimensiones quedan 10.748 filas y 332.901 vehículos.

## Reglas para que las cifras sean correctas

1. **Los vehículos se cuentan con `SUM(cantidad)`**, no con `COUNTROWS`. Contar filas cuenta grupos.
2. **Municipios: usar `territorio`, no `municipio`.** Tres nombres de municipio existen en más de un departamento:
   `DISTINCTCOUNT(territorio)` = 265, pero `DISTINCTCOUNT(municipio)` = 262 (fusiona homónimos).
3. **2026 es un año parcial.** La fuente se actualizó el 19/08/2026 y no trae mes, así que no hay periodos equivalentes.
   No calcular variaciones contra 2026; mostrarlo marcado como parcial (`dim_anio[estado_anio]`).
4. **Porcentajes: declarar el denominador.** Participación = vehículos de la categoría / total de vehículos (332.901);
   en perfiles por combustible o departamento, el denominador son los vehículos de ese combustible o departamento.
5. **No son vehículos únicos ni parque activo:** son matrículas por año de registro (no hay placa).
6. **`grupo_grande` = Sí** (1.592 grupos con `cantidad` > 16) concentra el 91,35 % de los vehículos. Son datos reales
   (p. ej. un grupo de 17.230 camionetas híbridas en Bogotá), no errores: no se eliminan, se analizan ponderando por `cantidad`.
7. **`modelo_inusual` = Sí** (60 grupos con modelo > año de registro + 1): se marcan, no se corrigen.
8. La fuente no distingue HEV de PHEV, y no hay población ni puntos de carga: no hay tasas per cápita ni causas.

## Valores esperados para validar las medidas DAX

Calculados con pandas y **recalculados de forma independiente** (módulo `csv`, sin el script) con resultado idéntico.
Los que llevan filtro sirven para comprobar que los segmentadores modifican bien los indicadores.

| Medida | Filtro | Valor esperado |
|---|---|---:|
| Total vehículos | sin filtros | 332.901 |
| Grupos de registro (`COUNTROWS`) | sin filtros | 10.748 |
| Vehículos 2023 | `anio_registro = 2023` | 34.039 |
| Vehículos 2025 (último año completo) | `anio_registro = 2025` | 89.163 |
| Vehículos 2026 (parcial) | `anio_registro = 2026` | 87.961 |
| Vehículos eléctricos (BEV) | `combustible = ELECTRICO` | 89.900 |
| % eléctricos sobre el total | sin filtros | 27,01 % |
| Vehículos en Antioquia | `departamento = ANTIOQUIA` | 66.029 |
| Antioquia + híbrido gasolina + 2024 | tres filtros combinados | 7.307 |
| % eléctricos dentro de Bogotá D.C. | `departamento = BOGOTA D.C.` | 27,17 % |
| Vehículos clase CAMIONETA | `clase = CAMIONETA` | 229.794 |
| Vehículos en grupos grandes | `grupo_grande = Sí` | 304.116 |
| Grupos con modelo inusual | `modelo_inusual = Sí` | 60 |
| Variación % 2025 vs 2024 | base: 2024 | 65,32 % |
| Territorios distintos | sin filtros | 265 |

La lista completa, con las fórmulas DAX sugeridas y las cifras de cada una de las 4 preguntas (distribuciones,
series anuales, perfiles, casos atípicos), está en `data/processed/resultados_conocimiento_evidente.json`.
