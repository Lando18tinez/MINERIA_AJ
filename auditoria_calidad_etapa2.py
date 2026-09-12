import numpy as np
import pandas as pd

# 1. Carga de datos crudos
df = pd.read_csv("data/raw/dataset_movilidad.csv")  # Ajusta tu ruta local
total_filas = len(df)

# ==========================================
# 2. MEDICIÓN DE LAS DIMENSIONES DE CALIDAD
# ==========================================

# A. Completitud: % de registros no nulos
completitud_potencia = (
    (total_filas - df["Potencia"].isnull().sum()) / total_filas
) * 100
completitud_cilindraje = (
    (total_filas - df["Cilindraje"].isnull().sum()) / total_filas
) * 100

# B. Exactitud / Consistencia Lógica (Nivel 1 - Oliveira)
# Regla: Un vehículo 100% eléctrico (BEV) debe tener Cilindraje == 0
bev_inconsistentes = df[
    (df["Combustible"] == "ELECTRICO") & (df["Cilindraje"] > 0)
]
tasa_inconsistencia_bev = (len(bev_inconsistentes) / total_filas) * 100

# C. Unicidad (Nivel 2 - Oliveira)
duplicados_totales = df.duplicated().sum()
tasa_unicidad = ((total_filas - duplicados_totales) / total_filas) * 100

# D. Validez Geográfica (Nivel 3 - Oliveira)
# Suponiendo validación contra catálogo DIVIPOLA oficial (ej. longitud de 5 dígitos)
validez_divipola = (
    df["Codigo_Municipio_DANE"].astype(str).str.len() == 5
).sum() / total_filas * 100

# ==========================================
# 3. CONSTRUCCIÓN DE LA TABLA DE AUDITORÍA
# ==========================================
inventario_problemas = [
    {
        "Nivel_Granularidad": "1. Atributo / Tupla",
        "Campo_Afectado": "Cilindraje",
        "Dimension": "Exactitud / Consistencia",
        "Descripcion": "Vehículos 100% eléctricos (BEV) con cilindraje > 0 cc",
        "Registros_Afectados": len(bev_inconsistentes),
        "Impacto": "Alto",
        "Tratamiento": "Forzar Cilindraje_R = 0 determinísticamente",
    },
    {
        "Nivel_Granularidad": "1. Atributo / Tupla",
        "Campo_Afectado": "Potencia",
        "Dimension": "Completitud",
        "Descripcion": "Valores nulos (NaN) o en cero no válidos",
        "Registros_Afectados": int(df["Potencia"].isnull().sum()),
        "Impacto": "Alto",
        "Tratamiento": "Imputación por mediana técnica según Marca + Linea (_R)",
    },
    {
        "Nivel_Granularidad": "2. Una Relación",
        "Campo_Afectado": "ID_Registro / Tupla",
        "Dimension": "Unicidad",
        "Descripcion": "Filas idénticas por descargas acumuladas de datos abiertos",
        "Registros_Afectados": int(duplicados_totales),
        "Impacto": "Medio",
        "Tratamiento": "Deduplicación por huella digital vehicular",
    },
    {
        "Nivel_Granularidad": "3. Varias Relaciones",
        "Campo_Afectado": "Codigo_Municipio_DANE",
        "Dimension": "Consistencia Referencial",
        "Descripcion": "Discrepancias entre inspecciones RUNT y códigos DANE",
        "Registros_Afectados": int(
            (df["Codigo_Municipio_DANE"].isnull()).sum()
        ),
        "Impacto": "Alto",
        "Tratamiento": "Tabla puente de homologación territorial (Lookup Table)",
    },
]

df_inventario = pd.DataFrame(inventario_problemas)
print(df_inventario.to_string(index=False))