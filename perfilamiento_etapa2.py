"""
Perfilamiento del conjunto de datos (Etapa 2, Sección 2).

Genera las tablas que se muestran en /etapa2/perfilamiento:
- Resumen general (registros, variables, duplicados, ventana temporal).
- Estructura de variables: tipo, valores únicos, nulos en origen y post-tratamiento (_R).
- Estadísticos descriptivos de las variables numéricas rectificadas.
- Detección de valores atípicos.

"""

import numpy as np
import pandas as pd

# --- 1. Carga de datos crudos -------------------------------------------------
RUTA_DATASET = "data/raw/dataset_movilidad.csv"  # Ajusta tu ruta local
df = pd.read_csv(RUTA_DATASET)
total_filas = len(df)
total_columnas = df.shape[1]

# ==============================================================================
# 2. RESUMEN GENERAL
# ==============================================================================
duplicados_exactos = df.duplicated().sum()
duplicados_id = (
    df["ID_Registro"].duplicated().sum() if "ID_Registro" in df.columns else np.nan
)

print("=" * 70)
print("RESUMEN GENERAL DEL PERFILAMIENTO")
print("=" * 70)
print(f"Registros analizados       : {total_filas:,}")
print(f"Variables evaluadas        : {total_columnas}")
print(f"Duplicados exactos (filas) : {duplicados_exactos}")
print(f"Duplicados en ID_Registro  : {duplicados_id}")
if "Anio_Registro" in df.columns:
    print(
        f"Ventana temporal           : {df['Anio_Registro'].min()} - "
        f"{df['Anio_Registro'].max()}"
    )
print()

# ==============================================================================
# 3. ESTRUCTURA DE VARIABLES, TIPOS Y COMPLETITUD
# ==============================================================================
# Sufijo de las columnas ya rectificadas por el plan de tratamiento (Sección 5).
# Ajusta esta lista según las columnas "_R" que existan realmente en tu dataset.
COLUMNAS_RECTIFICADAS = {
    "Potencia": "Potencia_R",
    "Cilindraje": "Cilindraje_R",
    "Capacidad_Pasajeros": "Capacidad_Pasajeros_R",
    "Capacidad_Carga": "Capacidad_Carga_R",
}

filas_perfilamiento = []
for columna in df.columns:
    nulos_origen = int(df[columna].isnull().sum())
    columna_r = COLUMNAS_RECTIFICADAS.get(columna)
    nulos_post = (
        int(df[columna_r].isnull().sum())
        if columna_r and columna_r in df.columns
        else (0 if columna_r is None else np.nan)
    )
    filas_perfilamiento.append(
        {
            "Variable": columna,
            "Tipo_Dato": str(df[columna].dtype),
            "Valores_Unicos": int(df[columna].nunique(dropna=True)),
            "Nulos_Origen_N": nulos_origen,
            "Nulos_Origen_Pct": round(nulos_origen / total_filas * 100, 2),
            "Nulos_Post_Tratamiento": nulos_post,
        }
    )

df_perfilamiento = pd.DataFrame(filas_perfilamiento)
print("=" * 70)
print("ESTRUCTURA DE VARIABLES, TIPOS Y ESTADO DE COMPLETITUD")
print("=" * 70)
print(df_perfilamiento.to_string(index=False))
print()

# ==============================================================================
# 4. ESTADÍSTICOS DESCRIPTIVOS (VARIABLES NUMÉRICAS RECTIFICADAS)
# ==============================================================================
columnas_numericas_r = [c for c in COLUMNAS_RECTIFICADAS.values() if c in df.columns]
if "Huella_CO2_Evitada_Ton" in df.columns:
    columnas_numericas_r.append("Huella_CO2_Evitada_Ton")

if columnas_numericas_r:
    descriptivos = df[columnas_numericas_r].describe().loc[
        ["min", "mean", "50%", "max", "std"]
    ]
    descriptivos.index = ["Mínimo", "Media", "Mediana", "Máximo", "Desv. Estándar"]
    print("=" * 70)
    print("ESTADÍSTICOS DESCRIPTIVOS DE VARIABLES NUMÉRICAS (_R)")
    print("=" * 70)
    print(descriptivos.round(2).to_string())
    print()

# ==============================================================================
# 5. DETECCIÓN DE VALORES ATÍPICOS (REGLA DE RANGO INTERCUARTÍLICO)
# ==============================================================================
print("=" * 70)
print("DETECCIÓN DE VALORES ATÍPICOS (IQR = Q3 - Q1, límites 1.5×IQR)")
print("=" * 70)
for columna in columnas_numericas_r:
    q1, q3 = df[columna].quantile([0.25, 0.75])
    iqr = q3 - q1
    limite_inf, limite_sup = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    atipicos = df[(df[columna] < limite_inf) | (df[columna] > limite_sup)]
    print(
        f"{columna:28s} -> {len(atipicos)} casos fuera de "
        f"[{limite_inf:.2f}, {limite_sup:.2f}]"
    )

# Exporta las tablas a CSV para adjuntarlas como evidencia en el informe técnico.
df_perfilamiento.to_csv("perfilamiento_variables.csv", index=False)
if columnas_numericas_r:
    descriptivos.to_csv("perfilamiento_estadisticos.csv")
