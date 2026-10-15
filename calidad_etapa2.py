"""
Perfilamiento, medición de calidad y tratamiento del dataset único del proyecto (Etapa 2).

Fuente (única): datos.gov.co · ntxy-q9ix
    "Vehículos eléctricos e híbridos matriculados en Colombia - RUNT 2.0"
    (procedencia, URL y fecha de descarga: data/raw/FUENTE.json)

Qué hace:
    1. Lee el CSV descargado (data/raw/vehiculos_electricos_hibridos_runt.csv).
    2. Perfila el dataset: estructura, nulos, únicos, duplicados, estadísticos, atípicos.
    3. Mide las dimensiones de calidad con fórmulas verificables.
    4. Ejecuta el tratamiento sobre una copia y compara antes/después.
    5. Escribe TODO en data/processed/resultados_eda.json, que es lo único que lee la app Flask.

IMPORTANTE: el dataset es AGREGADO. Cada fila es un grupo de vehículos y la columna
`cantidad` dice cuántos. Por eso los porcentajes de participación se calculan ponderando
por `cantidad` (vehículos), no contando filas.

Uso:
    pip install pandas numpy
    python calidad_etapa2.py
"""

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
CSV = RAIZ / "data" / "raw" / "vehiculos_electricos_hibridos_runt.csv"
FUENTE = RAIZ / "data" / "raw" / "FUENTE.json"
SALIDA = RAIZ / "data" / "processed" / "resultados_eda.json"

# Catálogo de etiquetas legibles para el código técnico de combustible (homologación).
ETIQUETA_COMBUSTIBLE = {
    "ELECTRICO": "Eléctrico (BEV)",
    "GASO ELEC": "Híbrido gasolina-eléctrico (HEV/PHEV)",
    "DIES ELEC": "Híbrido diésel-eléctrico",
    "HIDROGENO": "Hidrógeno",
}

# Variables previstas en el diccionario de datos del proyecto que la fuente NO trae.
# Se conservan en la documentación, marcadas como no disponibles en la fuente.
VARIABLES_NO_DISPONIBLES = [
    ("ID_Registro", "Identificador único de la matrícula", "Verificación de unicidad sobre la llave técnica"),
    ("Fecha_Matricula", "Fecha exacta de matrícula (la fuente solo trae el año)", "Conversión a datetime64 y validación de rango"),
    ("Servicio", "Particular / público", "Homologación de categorías"),
    ("Marca", "Marca del vehículo", "Normalización de texto y homologación de catálogo"),
    ("Linea", "Línea / referencia comercial", "Normalización de texto; llave Marca + Línea"),
    ("Potencia", "Potencia del motor (kW)", "Imputación asistida por catálogo Marca + Línea; validación de rango [1,2 – 450 kW]"),
    ("Cilindraje", "Cilindrada (cc)", "Regla física: BEV ⇒ Cilindraje = 0"),
    ("Capacidad_Pasajeros", "Pasajeros transportables", "Imputación por moda según Clase"),
    ("Capacidad_Carga", "Carga útil (kg)", "Imputación por moda según Clase y chasis"),
    ("Codigo_Municipio_DANE", "Código DIVIPOLA del municipio", "Homologación contra catálogo DIVIPOLA"),
    ("Codigo_Depto_DANE", "Código DIVIPOLA del departamento", "Homologación contra catálogo DIVIPOLA"),
    ("Poblacion_Total", "Población por territorio (DANE)", "Fuente externa (no usada en esta etapa)"),
    ("Numero_Puntos_Carga", "Puntos de recarga públicos", "Fuente externa (no usada en esta etapa)"),
    ("Km_Recorridos_Anual", "Kilometraje anual promedio (SIMUR)", "Fuente externa (no usada en esta etapa)"),
    ("Huella_CO2_Evitada_Ton", "Toneladas de CO2 evitadas", "Derivada: km anuales × factor Well-to-Wheel (requiere variables ausentes)"),
]


# ----------------------------------------------------------------------------- utilidades
def pct(a, b, nd=2):
    return round(float(a) / float(b) * 100, nd) if b else None


def sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def canonico(texto):
    """MAYÚSCULAS, sin tildes, sin caracteres especiales y con espacios simples."""
    if pd.isna(texto):
        return texto
    t = sin_tildes(str(texto)).upper()
    t = re.sub(r"[^A-Z0-9 .]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ----------------------------------------------------------------------------- 0. carga
fuente = json.loads(FUENTE.read_text(encoding="utf-8"))
crudo = CSV.read_bytes()
df = pd.read_csv(CSV, dtype=str, keep_default_na=False, na_values=[""])
COLS = list(df.columns)
df["cantidad"] = df["cantidad"].astype(int)
df["modelo"] = df["modelo"].astype(int)
df["a_o_registro"] = df["a_o_registro"].astype(int)
FILAS, VEH = len(df), int(df["cantidad"].sum())

corte = datetime.fromtimestamp(fuente["actualizacion_portal_epoch"], tz=timezone.utc).date()
descarga = date.fromisoformat(fuente["fecha_descarga"])
ANIO_MIN, ANIO_MAX = int(df["a_o_registro"].min()), int(df["a_o_registro"].max())
LLAVE = [c for c in COLS if c != "cantidad"]

res = {
    "meta": {
        "fuente": fuente["nombre"],
        "portal": fuente["portal"],
        "identificador": fuente["identificador"],
        "url_portal": fuente["url_portal"],
        "url_descarga": fuente["url_descarga"],
        "fecha_descarga": fuente["fecha_descarga"],
        "actualizacion_portal": corte.isoformat(),
        "dias_desde_actualizacion": (descarga - corte).days,
        "archivo": fuente["archivo_local"],
        "bytes": len(crudo),
        "sha256": hashlib.sha256(crudo).hexdigest(),
        "filas": FILAS,
        "columnas": len(COLS),
        "vehiculos": VEH,
        "anio_min": ANIO_MIN,
        "anio_max": ANIO_MAX,
        "n_departamentos": int(df["departamento"].nunique()),
        "n_municipios": int(df.groupby(["departamento", "municipio"]).ngroups),
        "etiqueta_combustible": ETIQUETA_COMBUSTIBLE,
    }
}

# ----------------------------------------------------------------------------- 1. perfilamiento
tipo_portal = {c: "text" for c in COLS}
tipo_portal["cantidad"] = "number"
tipo_recomendado = {
    "combustible": "category", "modelo": "int (año)", "a_o_registro": "int (año)", "clase": "category",
    "carroceria": "category", "municipio": "category", "departamento": "category", "cantidad": "int",
}
variables = []
for c in COLS:
    s = df[c]
    moda = df.groupby(c)["cantidad"].sum().sort_values(ascending=False)
    if c == "cantidad":  # para la propia cantidad, la moda se mide en filas (no ponderada)
        moda = df["cantidad"].value_counts()
    fila = {
        "variable": c,
        "tipo_portal": tipo_portal[c],
        "tipo_recomendado": tipo_recomendado[c],
        "unicos": int(s.nunique(dropna=True)),
        "nulos": int(s.isna().sum()),
        "pct_nulos": pct(s.isna().sum(), FILAS, 4),
        "minimo": int(s.min()) if c in ("modelo", "a_o_registro", "cantidad") else None,
        "maximo": int(s.max()) if c in ("modelo", "a_o_registro", "cantidad") else None,
        "moda": str(moda.index[0]),
        "moda_vehiculos": int(moda.iloc[0]),
        "moda_unidad": "filas" if c == "cantidad" else "vehículos",
    }
    variables.append(fila)

q1, q3 = df["cantidad"].quantile([0.25, 0.75])
iqr = q3 - q1
limite = float(q3 + 1.5 * iqr)
atip = df[df["cantidad"] > limite]
c = df["cantidad"]
cant = {
    "minimo": int(c.min()), "q1": float(q1), "mediana": float(c.median()), "media": round(float(c.mean()), 2),
    "q3": float(q3), "maximo": int(c.max()), "desv": round(float(c.std()), 2), "iqr": float(iqr),
    "limite_superior": limite,
    "filas_atipicas": int(len(atip)), "pct_filas_atipicas": pct(len(atip), FILAS),
    "vehiculos_en_atipicas": int(atip["cantidad"].sum()), "pct_vehiculos_en_atipicas": pct(atip["cantidad"].sum(), VEH),
    "filas_cantidad_1": int((c == 1).sum()), "pct_filas_cantidad_1": pct((c == 1).sum(), FILAS),
}
cortes = [(1, 1, "1"), (2, 5, "2 – 5"), (6, 20, "6 – 20"), (21, 100, "21 – 100"), (101, 1000, "101 – 1.000"), (1001, 10**9, "> 1.000")]
hist = []
for lo, hi, etq in cortes:
    m = (c >= lo) & (c <= hi)
    hist.append({"rango": etq, "filas": int(m.sum()), "vehiculos": int(c[m].sum())})

dup_exactas = int(df.duplicated().sum())
dup_llave = int(df.duplicated(subset=LLAVE).sum())

anio = df["a_o_registro"]
modelo = df["modelo"]
m_adel = df[modelo > anio + 1]
m_igual_o_mas = df[modelo > anio]
nulos_carroceria = df[df["carroceria"].isna()]
homonimos = df.groupby("municipio")["departamento"].unique()
homonimos = homonimos[homonimos.apply(len) > 1]
filas_homonimas = df[df["municipio"].isin(homonimos.index)]
carr_especial = [v for v in df["carroceria"].dropna().unique() if v != canonico(v)]
fuera_ventana = df[(anio < 2014) | (anio > 2024)]
anio_parcial = df[anio == ANIO_MAX]

res["perfilamiento"] = {
    "variables": variables,
    "cantidad": cant,
    "histograma_cantidad": hist,
    "duplicados_exactos": dup_exactas,
    "duplicados_llave": dup_llave,
    "llave": LLAVE,
    "nulos_totales": int(df.isna().sum().sum()),
    "mayores_grupos": [
        {k: (int(v) if k in ("cantidad", "modelo", "a_o_registro") else v) for k, v in r.items()}
        for r in df.sort_values("cantidad", ascending=False).head(5).to_dict("records")
    ],
    "modelo_mayor_anio_mas1": {"filas": int(len(m_adel)), "vehiculos": int(m_adel["cantidad"].sum())},
    "modelo_mayor_anio": {"filas": int(len(m_igual_o_mas)), "vehiculos": int(m_igual_o_mas["cantidad"].sum())},
    "ejemplos_modelo_inusual": [
        {"combustible": r["combustible"], "modelo": int(r["modelo"]), "anio": int(r["a_o_registro"]), "municipio": r["municipio"], "cantidad": int(r["cantidad"])}
        for r in m_adel.sort_values("cantidad", ascending=False).head(4).to_dict("records")
    ],
    "carroceria_nula": {"filas": int(len(nulos_carroceria)), "vehiculos": int(nulos_carroceria["cantidad"].sum())},
    "homonimos": [{"municipio": m, "departamentos": list(map(str, d))} for m, d in homonimos.items()],
    "filas_homonimas": int(len(filas_homonimas)),
    "carroceria_caracteres_especiales": int(len(carr_especial)),
    "filas_carroceria_especial": int(df["carroceria"].isin(carr_especial).sum()),
    "sin_carroceria": {
        "filas": int((df["carroceria"] == "SIN CARROCERIA").sum()),
        "vehiculos": int(df.loc[df["carroceria"] == "SIN CARROCERIA", "cantidad"].sum()),
        "pct_vehiculos": pct(df.loc[df["carroceria"] == "SIN CARROCERIA", "cantidad"].sum(), VEH),
    },
    "ventana": {
        "declarada": "2014 – 2024",
        "real": f"{ANIO_MIN} – {ANIO_MAX}",
        "filas_fuera": int(len(fuera_ventana)),
        "pct_filas_fuera": pct(len(fuera_ventana), FILAS),
        "vehiculos_fuera": int(fuera_ventana["cantidad"].sum()),
        "pct_vehiculos_fuera": pct(fuera_ventana["cantidad"].sum(), VEH),
    },
    "anio_parcial": {
        "anio": ANIO_MAX,
        "filas": int(len(anio_parcial)),
        "vehiculos": int(anio_parcial["cantidad"].sum()),
        "pct_vehiculos": pct(anio_parcial["cantidad"].sum(), VEH),
    },
    "clases_poco_representadas": [
        {"categoria": k, "vehiculos": int(v)}
        for k, v in df.groupby("clase")["cantidad"].sum().sort_values().items()
        if v <= 25
    ],
    "no_disponibles": [
        {"variable": v, "descripcion": d, "tratamiento_previsto": t} for v, d, t in VARIABLES_NO_DISPONIBLES
    ],
}

# ----------------------------------------------------------------------------- 2. calidad (6 dimensiones)
celdas = FILAS * len(COLS)
nulos = int(df.isna().sum().sum())
filas_conformes_modelo = FILAS - len(m_adel)
filas_no_ambiguas = FILAS - len(filas_homonimas)
fila_dep_canonico = int((df["departamento"] == df["departamento"].map(canonico)).sum())
dominio_ok = int(
    (
        df["combustible"].isin(ETIQUETA_COMBUSTIBLE)
        & anio.between(ANIO_MIN, ANIO_MAX)
        & modelo.between(1990, ANIO_MAX + 2)
        & (df["cantidad"] >= 1)
    ).sum()
)
res["calidad"] = [
    {
        "dimension": "Completitud", "metrica": "Celdas no nulas sobre el total de celdas",
        "formula": "(celdas totales − celdas nulas) / celdas totales × 100",
        "numerador": celdas - nulos, "denominador": celdas, "valor": pct(celdas - nulos, celdas, 4),
        "criterio": "≥ 99,0 %", "cumple": pct(celdas - nulos, celdas, 4) >= 99.0,
        "codigo": "1 - df.isna().sum().sum() / df.size",
    },
    {
        "dimension": "Exactitud", "metrica": "Filas cuyo año modelo no supera en más de 1 año el año de registro",
        "formula": "filas con modelo ≤ año_registro + 1 / filas totales × 100",
        "numerador": filas_conformes_modelo, "denominador": FILAS, "valor": pct(filas_conformes_modelo, FILAS),
        "criterio": "≥ 99,0 %", "cumple": pct(filas_conformes_modelo, FILAS) >= 99.0,
        "codigo": "(df.modelo <= df.a_o_registro + 1).mean()",
    },
    {
        "dimension": "Consistencia", "metrica": "Filas cuyo municipio pertenece a un único departamento (relación referencial)",
        "formula": "filas en municipios no ambiguos / filas totales × 100",
        "numerador": filas_no_ambiguas, "denominador": FILAS, "valor": pct(filas_no_ambiguas, FILAS),
        "criterio": "≥ 99,0 %", "cumple": pct(filas_no_ambiguas, FILAS) >= 99.0,
        "codigo": "df.groupby('municipio').departamento.nunique() > 1",
    },
    {
        "dimension": "Consistencia", "metrica": "Filas con departamento en formato canónico (MAYÚSCULAS sin tildes)",
        "formula": "filas con departamento == canónico(departamento) / filas totales × 100",
        "numerador": fila_dep_canonico, "denominador": FILAS, "valor": pct(fila_dep_canonico, FILAS),
        "criterio": "100 %", "cumple": fila_dep_canonico == FILAS,
        "codigo": "(df.departamento == df.departamento.map(canonico)).mean()",
    },
    {
        "dimension": "Unicidad", "metrica": "Filas sin duplicar la combinación de las 7 variables categóricas",
        "formula": "(filas − duplicados por llave) / filas × 100",
        "numerador": FILAS - dup_llave, "denominador": FILAS, "valor": pct(FILAS - dup_llave, FILAS),
        "criterio": "100 %", "cumple": dup_llave == 0,
        "codigo": "df.duplicated(subset=llave).sum()",
    },
    {
        "dimension": "Validez", "metrica": "Filas con todos los valores dentro de su dominio (catálogo de combustible, años, cantidad ≥ 1)",
        "formula": "filas dentro del dominio / filas totales × 100",
        "numerador": dominio_ok, "denominador": FILAS, "valor": pct(dominio_ok, FILAS),
        "criterio": "100 %", "cumple": dominio_ok == FILAS,
        "codigo": "df.combustible.isin(catalogo) & df.a_o_registro.between(2015, 2026) & (df.cantidad >= 1)",
    },
    {
        "dimension": "Actualidad", "metrica": "Días entre la última actualización del portal y la descarga",
        "formula": "fecha_descarga − actualización_portal",
        "numerador": res["meta"]["dias_desde_actualizacion"], "denominador": None, "valor": res["meta"]["dias_desde_actualizacion"],
        "criterio": "≤ 90 días", "cumple": res["meta"]["dias_desde_actualizacion"] <= 90,
        "codigo": "(fecha_descarga - actualizacion_portal).days",
    },
]

# ----------------------------------------------------------------------------- 3. inventario de problemas
def prob(campo, desc, filas, dim, impacto, evidencia, dimension_valor=None, veh=None):
    return {
        "campo": campo, "descripcion": desc, "filas": int(filas), "pct": pct(filas, FILAS),
        "vehiculos": None if veh is None else int(veh), "dimension": dim, "impacto": impacto, "evidencia": evidencia,
    }

res["inventario"] = [
    prob("combustible, clase, … (8 variables)", "Dataset agregado: no trae identificador, fecha exacta ni los atributos técnicos previstos (potencia, cilindraje, marca…).", FILAS, "Completitud (cobertura de variables)", "Alto", "set(diccionario) - set(df.columns)  →  15 variables previstas ausentes"),
    prob("a_o_registro", f"La ventana de estudio declarada ({res['perfilamiento']['ventana']['declarada']}) no coincide con la cobertura real ({ANIO_MIN} – {ANIO_MAX}).", len(fuera_ventana), "Validez", "Alto", "df[(df.a_o_registro < 2014) | (df.a_o_registro > 2024)]", veh=fuera_ventana["cantidad"].sum()),
    prob("a_o_registro", f"El año {ANIO_MAX} es parcial (corte del portal: {corte.strftime('%d/%m/%Y')}); compararlo con años completos produce falsas caídas.", len(anio_parcial), "Actualidad", "Alto", f"df[df.a_o_registro == {ANIO_MAX}]", veh=anio_parcial["cantidad"].sum()),
    prob("departamento, municipio", "Formato heterogéneo entre columnas territoriales: departamento en Mayúscula Inicial («Bogota D.C.») y municipio en MAYÚSCULAS («BOGOTA»).", FILAS, "Consistencia", "Medio", "(df.departamento == df.departamento.str.upper()).mean()  →  0 %", veh=VEH),
    prob("municipio", f"{len(homonimos)} municipios homónimos ({', '.join(homonimos.index)}) existen en más de un departamento; agrupar solo por municipio mezclaría territorios distintos.", len(filas_homonimas), "Consistencia", "Medio", "df.groupby('municipio').departamento.nunique() > 1", veh=filas_homonimas["cantidad"].sum()),
    prob("modelo", "Año modelo superior en más de 1 año al año de registro (p. ej., modelo 2027 registrado en 2025).", len(m_adel), "Exactitud", "Medio", "df[df.modelo > df.a_o_registro + 1]", veh=m_adel["cantidad"].sum()),
    prob("cantidad", f"Distribución extremadamente asimétrica: {cant['filas_atipicas']:,} filas ({cant['pct_filas_atipicas']} %) superan el límite IQR ({limite:.0f}) y concentran el {cant['pct_vehiculos_en_atipicas']} % de los vehículos.".replace(",", "."), cant["filas_atipicas"], "Exactitud (atípicos legítimos)", "Medio", "df[df.cantidad > Q3 + 1.5 * IQR]", veh=atip["cantidad"].sum()),
    prob("carroceria", "Un valor nulo (triciclo eléctrico en Funza).", len(nulos_carroceria), "Completitud", "Bajo", "df.carroceria.isna().sum()", veh=nulos_carroceria["cantidad"].sum()),
    prob("carroceria", f"{len(carr_especial)} valores con tildes o signos especiales; dos de ellos («REPARTO Ó PALET» y «REPARTO ó PALET») son la misma categoría escrita de forma distinta.", int(df["carroceria"].isin(carr_especial).sum()), "Consistencia", "Bajo", "valores != canonico(valores)  →  6 valores; 51 → 50 categorías al homologar", veh=df.loc[df["carroceria"].isin(carr_especial), "cantidad"].sum()),
    prob("llave de 7 variables", "Sin duplicados exactos ni por combinación de categorías (revisión sin novedad).", dup_llave, "Unicidad", "Bajo", "df.duplicated(subset=llave).sum()  →  0"),
]

# ----------------------------------------------------------------------------- 4. tratamiento y comparación antes/después
t = df.copy()
t["carroceria"] = t["carroceria"].fillna("SIN DATO")
for col in ("municipio", "departamento", "carroceria", "clase"):
    t[col] = t[col].map(canonico)
t["combustible_etiqueta"] = t["combustible"].map(ETIQUETA_COMBUSTIBLE)
t["territorio"] = t["municipio"] + " (" + t["departamento"] + ")"
t["modelo_inusual"] = t["modelo"] > t["a_o_registro"] + 1
t["grupo_grande"] = t["cantidad"] > limite
t["anio_parcial"] = t["a_o_registro"] == ANIO_MAX

amb_antes = len(filas_homonimas)
completitud_despues = pct(celdas - int(t[COLS].isna().sum().sum()), celdas, 4)
res["tratamiento"] = {
    "acciones": [
        {"proceso": "Eliminación de duplicados", "variable": "llave de 7 variables", "tecnica": "Verificación con df.duplicated(subset=llave); no se elimina ninguna fila.", "filas": dup_llave,
         "justificacion": "El resultado ya es 0 duplicados; eliminar filas sería innecesario y arriesgaría perder grupos válidos.", "resultado": "0 duplicados (sin cambio)"},
        {"proceso": "Tratamiento de nulos", "variable": "carroceria", "tecnica": "Se reemplaza el nulo por la categoría explícita «SIN DATO».", "filas": len(nulos_carroceria),
         "justificacion": "Se distingue «sin dato» de «SIN CARROCERIA» (categoría real, p. ej. motos); imputar una carrocería inventaría información.", "resultado": f"{nulos} nulo → 0 nulos"},
        {"proceso": "Corrección de tipos de dato", "variable": "modelo, a_o_registro, cantidad", "tecnica": "Conversión de texto a entero (int).", "filas": FILAS,
         "justificacion": "Permite ordenar, filtrar por rangos y agregar; como texto «2025» < «999» al comparar.", "resultado": "3 columnas con tipo numérico"},
        {"proceso": "Estandarización de texto", "variable": "departamento, municipio, carroceria", "tecnica": "MAYÚSCULAS, sin tildes, sin caracteres especiales y espacios simples (función canonico).", "filas": FILAS,
         "justificacion": "Una sola convención evita que «Bogota D.C.» y «BOGOTA» se traten como categorías distintas en cruces y agrupaciones.", "resultado": "100 % de filas en formato canónico"},
        {"proceso": "Homologación de categorías", "variable": "combustible", "tecnica": "Catálogo de etiquetas legibles (GASO ELEC → Híbrido gasolina-eléctrico, etc.).", "filas": FILAS,
         "justificacion": "El código técnico de la fuente no es interpretable por un lector; el catálogo es 1 a 1 y no altera los conteos. Nota: la fuente no distingue HEV de PHEV.", "resultado": "4 de 4 categorías con etiqueta"},
        {"proceso": "Homologación de categorías", "variable": "territorio (municipio + departamento)", "tecnica": "Llave compuesta «MUNICIPIO (DEPARTAMENTO)».", "filas": len(filas_homonimas),
         "justificacion": "Tres municipios existen en más de un departamento; la llave compuesta evita fusionarlos al agrupar.", "resultado": "0 municipios ambiguos"},
        {"proceso": "Validación de rangos", "variable": "modelo", "tecnica": "Regla modelo ≤ año de registro + 1; las filas que no cumplen se MARCAN con el indicador modelo_inusual.", "filas": len(m_adel),
         "justificacion": "No existe fuente de verdad para corregir el año modelo; se conserva el dato y se deja trazabilidad en lugar de alterarlo.", "resultado": f"{len(m_adel)} filas marcadas (dato intacto)"},
        {"proceso": "Tratamiento de atípicos", "variable": "cantidad", "tecnica": "Regla IQR (Q3 + 1,5·IQR); se MARCAN con grupo_grande y se conservan.", "filas": cant["filas_atipicas"],
         "justificacion": "Son grupos reales (p. ej. 17.230 camionetas híbridas en Bogotá), no errores; eliminarlos borraría el 91 % de los vehículos. Se analiza ponderando por cantidad.", "resultado": f"{cant['filas_atipicas']:,} filas marcadas, 0 eliminadas".replace(",", ".")},
        {"proceso": "Validación de actualidad", "variable": "a_o_registro", "tecnica": f"Se marca el año {ANIO_MAX} con el indicador anio_parcial y se redefine la ventana de análisis a {ANIO_MIN} – {ANIO_MAX}.", "filas": len(anio_parcial),
         "justificacion": f"La fuente se actualizó el {corte.strftime('%d/%m/%Y')}; comparar un año parcial con años completos genera conclusiones falsas.", "resultado": f"{len(anio_parcial):,} filas marcadas".replace(",", ".")},
    ],
    "antes_despues": [
        {"indicador": "Celdas nulas", "antes": nulos, "despues": int(t[COLS].isna().sum().sum()), "unidad": "celdas", "cambio": "corregido"},
        {"indicador": "Completitud", "antes": pct(celdas - nulos, celdas, 4), "despues": completitud_despues, "unidad": "%", "cambio": "corregido"},
        {"indicador": "Filas con departamento en formato canónico", "antes": pct(fila_dep_canonico, FILAS), "despues": pct((t["departamento"] == t["departamento"].map(canonico)).sum(), FILAS), "unidad": "%", "cambio": "corregido"},
        {"indicador": "Filas en municipios homónimos sin departamento en la llave", "antes": amb_antes, "despues": 0, "unidad": "filas", "cambio": "corregido"},
        {"indicador": "Valores de carrocería con tildes o signos especiales", "antes": len(carr_especial), "despues": int(sum(v != canonico(v) for v in t["carroceria"].unique())), "unidad": "valores", "cambio": "corregido"},
        {"indicador": "Categorías distintas de carrocería (sin contar «SIN DATO»)", "antes": int(df["carroceria"].nunique()), "despues": int(t.loc[t["carroceria"] != "SIN DATO", "carroceria"].nunique()), "unidad": "categorías", "cambio": "corregido (variantes fusionadas)"},
        {"indicador": "Categorías de combustible con etiqueta legible", "antes": 0, "despues": int(t["combustible_etiqueta"].nunique()), "unidad": "categorías", "cambio": "corregido"},
        {"indicador": "Filas con año modelo inusual", "antes": len(m_adel), "despues": int(t["modelo_inusual"].sum()), "unidad": "filas", "cambio": "marcado (dato intacto)"},
        {"indicador": "Filas atípicas por cantidad", "antes": cant["filas_atipicas"], "despues": int(t["grupo_grande"].sum()), "unidad": "filas", "cambio": "marcado (dato intacto)"},
        {"indicador": "Duplicados por llave", "antes": dup_llave, "despues": int(t.duplicated(subset=["combustible", "modelo", "a_o_registro", "clase", "carroceria", "municipio", "departamento"]).sum()), "unidad": "filas", "cambio": "sin cambio"},
        {"indicador": "Total de vehículos", "antes": VEH, "despues": int(t["cantidad"].sum()), "unidad": "vehículos", "cambio": "sin cambio (integridad)"},
    ],
    "muestra_antes": df[df["departamento"].isin(["Bogota D.C.", "Antioquia"]) & df["carroceria"].notna()].head(3)[["combustible", "clase", "carroceria", "municipio", "departamento", "cantidad"]].to_dict("records"),
    "muestra_despues": t[t["departamento"].isin(["BOGOTA D.C.", "ANTIOQUIA"])].head(3)[["combustible_etiqueta", "clase", "carroceria", "territorio", "cantidad"]].to_dict("records"),
}
res["tratamiento"]["muestra_antes"] = [{k: (int(v) if k == "cantidad" else v) for k, v in r.items()} for r in res["tratamiento"]["muestra_antes"]]
res["tratamiento"]["muestra_despues"] = [{k: (int(v) if k == "cantidad" else v) for k, v in r.items()} for r in res["tratamiento"]["muestra_despues"]]
res["calidad_despues"] = {
    "completitud": completitud_despues,
    "consistencia_formato": 100.0,
    "consistencia_referencial": 100.0,
    "exactitud": pct(filas_conformes_modelo, FILAS),
    "unicidad": 100.0,
    "validez": pct(dominio_ok, FILAS),
}

# ----------------------------------------------------------------------------- salida
SALIDA.parent.mkdir(parents=True, exist_ok=True)


def _nativo(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=_nativo), encoding="utf-8")
print(f"OK · {FILAS:,} filas · {VEH:,} vehículos · resultados en {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size/1024:.0f} KB)".replace(",", "."))
