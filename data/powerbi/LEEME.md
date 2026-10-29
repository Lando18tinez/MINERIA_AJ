# Datos para Power BI · Conocimiento evidente

Mismo dataset de las etapas anteriores: **Vehículos eléctricos e híbridos matriculados en Colombia – RUNT 2.0**
(datos.gov.co · `ntxy-q9ix`), con el tratamiento de la Etapa 2. No es un dataset nuevo.

**Ventana de análisis: 2015–2024** (alcance del proyecto). Se excluyen 2025 y 2026 (3.976 grupos, 177.124 vehículos);
2026 además es un año incompleto (la fuente se actualizó el 19/08/2026 y no trae mes).

> **No usar `vehiculos_limpios.csv`.** Tiene la carga triplicada, `cantidad` alterada y las columnas `clase` y
> `carroceria` vacías. Los datos correctos son los de este paquete o el CSV `vehiculos_hibridos_electricos_2015_2024.csv`:
> **son el mismo dato** (6.772 grupos, 155.777 vehículos, idénticos año por año).

Se regenera con `python conocimiento_evidente.py` (desde la raíz del proyecto).

## Dos formas de cargar los datos (las cifras son idénticas)

**A. Una sola tabla** (la que ya usa el `.pbix`): `vehiculos_hibridos_electricos_2015_2024.csv`. No tiene relaciones,
así que no hay riesgo de duplicar valores. Para contar territorios hay que crear la columna calculada
`Territorio = [Municipio_Estandar] & " (" & [Departamento_Estandar] & ")"`.

**B. Modelo en estrella** (esta carpeta). Permite demostrar relaciones correctas entre tablas:

| Archivo | Filas | Contenido |
|---|---:|---|
| `hechos_vehiculos.csv` | 6.772 | Una fila por **grupo de vehículos**. `cantidad` = cuántos vehículos tiene el grupo. |
| `dim_territorio.csv` | 247 | `territorio` (llave única: «MUNICIPIO (DEPARTAMENTO)»), `municipio`, `departamento`. |
| `dim_combustible.csv` | 4 | `combustible` (código) y `combustible_etiqueta` legible. |
| `dim_anio.csv` | 10 | `anio_registro` (2015–2024). |

Columnas de `hechos_vehiculos`: `combustible`, `clase`, `carroceria`, `anio_registro`, `modelo`, `territorio`,
`cantidad`, `modelo_inusual` (Sí/No), `grupo_grande` (Sí/No). UTF-8 con BOM, separador coma.

Relaciones (todas muchos a uno, un solo sentido: dimensión → hechos):

```
hechos_vehiculos[territorio]     →  dim_territorio[territorio]
hechos_vehiculos[combustible]    →  dim_combustible[combustible]
hechos_vehiculos[anio_registro]  →  dim_anio[anio_registro]
```

Se comprobó que al unir los hechos con las tres dimensiones quedan 6.772 filas y 155.777 vehículos (nada se duplica ni se pierde).

## Reglas para que las cifras sean correctas

1. **Los vehículos se cuentan con `SUM(cantidad)`** (`Cantidad_Vehiculos` en el CSV de una tabla), no con `COUNTROWS`. Contar filas cuenta grupos.
2. **Municipios: usar `territorio`, no `municipio`.** Tres nombres de municipio existen en más de un departamento:
   `DISTINCTCOUNT(territorio)` = 247, pero `DISTINCTCOUNT(municipio)` = 244 (fusiona homónimos).
3. **El año del modelo no es el año de registro.** Para series de tiempo usar `anio_registro` (`Ano_Registro`). `modelo` puede
   llegar a 2025 o 2026 en vehículos registrados en 2024 (modelo del año siguiente) y eso es normal.
4. **Porcentajes: declarar el denominador.** Participación = vehículos de la categoría / total (155.777); en perfiles por
   combustible o departamento, el denominador son los vehículos de ese combustible o departamento.
5. **No son vehículos únicos ni parque activo:** son matrículas por año de registro (no hay placa).
6. **`grupo_grande` = Sí** (942 grupos con `cantidad` > 16, umbral IQR de la Etapa 2) concentra el 88,35 % de los vehículos.
   Son datos reales (p. ej. un grupo de 8.071 camionetas híbridas en Bogotá en 2024), no errores: no se eliminan, se analizan ponderando por `cantidad`.
7. **`modelo_inusual` = Sí** (34 grupos con modelo > año de registro + 1): se marcan, no se corrigen.
8. La fuente no distingue HEV de PHEV, y no hay población ni puntos de carga: no hay tasas per cápita ni causas.

## Valores esperados para validar las medidas DAX

Calculados con pandas y **recalculados de forma independiente sobre `vehiculos_hibridos_electricos_2015_2024.csv`**
(módulo `csv`, sin el script): coinciden las 15. Los que llevan filtro sirven para comprobar que los segmentadores
modifican bien los indicadores.

| Medida | Filtro | Valor esperado |
|---|---|---:|
| Total vehículos | sin filtros | 155.777 |
| Grupos de registro (`COUNTROWS`) | sin filtros | 6.772 |
| Vehículos 2023 | año de registro = 2023 | 34.039 |
| Vehículos 2024 | año de registro = 2024 | 53.934 |
| Vehículos eléctricos (BEV) | combustible = ELECTRICO | 36.969 |
| % eléctricos sobre el total | sin filtros | 23,73 % |
| Vehículos en Antioquia | departamento = ANTIOQUIA | 31.566 |
| Antioquia + híbrido gasolina + 2024 | tres filtros combinados | 7.307 |
| % eléctricos dentro de Bogotá D.C. | departamento = BOGOTA D.C. | 18,87 % |
| Vehículos clase CAMIONETA | clase = CAMIONETA | 90.709 |
| Vehículos en grupos grandes | cantidad > 16 | 137.628 |
| Grupos con modelo inusual | modelo > año de registro + 1 | 34 |
| Variación % 2024 vs 2023 | base: 2023 | 58,45 % |
| Territorios distintos | sin filtros | 247 |

La lista completa, con las fórmulas DAX sugeridas y las cifras de cada una de las 4 preguntas (distribuciones,
series anuales, perfiles, casos atípicos), está en `data/processed/resultados_conocimiento_evidente.json`.
