"""
Conocimiento evidente: datos para Power BI y cifras de referencia verificables.

Fuente (única, la misma de las etapas anteriores): datos.gov.co · ntxy-q9ix
    "Vehículos eléctricos e híbridos matriculados en Colombia - RUNT 2.0"
    (procedencia, URL y fecha de descarga: data/raw/FUENTE.json)

Qué hace:
    1. Lee el CSV original y aplica el MISMO tratamiento de calidad de la Etapa 2
       (calidad_etapa2.py): nulo de carrocería -> «SIN DATO», texto canónico,
       marcas modelo_inusual / grupo_grande. No elimina filas por calidad.
       Luego limita el análisis a la ventana del proyecto, 2015-2024 (ANIO_INICIO / ANIO_FIN);
       2025 y 2026 quedan fuera (2026 además es un año incompleto).
    2. Escribe el modelo en estrella que se importa en Power BI (data/powerbi/):
           hechos_vehiculos.csv   una fila por grupo de vehículos (tabla de hechos)
           dim_territorio.csv     territorio (municipio + departamento), llave única
           dim_combustible.csv    código de combustible y etiqueta legible
           dim_anio.csv           años de registro de la ventana
    3. Calcula las cifras de referencia de las 4 preguntas y las escribe en
       data/processed/resultados_conocimiento_evidente.json. Sirven para comprobar que
       las medidas DAX de Power BI dan el mismo resultado (ver bloque «verificaciones»).
    4. Comprueba que lo calculado coincide con resultados_eda.json (Etapa 2) y que el
       modelo en estrella no duplica ni pierde vehículos. Si algo falla, se detiene.

IMPORTANTE: el dataset es AGREGADO. Cada fila es un grupo de vehículos y la columna
`cantidad` dice cuántos. Todo indicador usa SUM(cantidad); contar filas cuenta grupos,
no vehículos. Tampoco son vehículos únicos (no hay placa): son matrículas por año de registro.

Uso:
    pip install pandas numpy
    python conocimiento_evidente.py
"""

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
RESULTADOS_ETAPA2 = RAIZ / "data" / "processed" / "resultados_eda.json"
CARPETA_POWERBI = RAIZ / "data" / "powerbi"
SALIDA = RAIZ / "data" / "processed" / "resultados_conocimiento_evidente.json"

# Ventana de análisis del proyecto (alcance definido desde la Etapa 1).
ANIO_INICIO, ANIO_FIN = 2015, 2024

# Mismo catálogo de etiquetas que calidad_etapa2.py (homologación de combustible).
ETIQUETA_COMBUSTIBLE = {
    "ELECTRICO": "Eléctrico (BEV)",
    "GASO ELEC": "Híbrido gasolina-eléctrico (HEV/PHEV)",
    "DIES ELEC": "Híbrido diésel-eléctrico",
    "HIDROGENO": "Hidrógeno",
}


# ----------------------------------------------------------------------------- utilidades
def pct(a, b, nd=2):
    return round(float(a) / float(b) * 100, nd) if b else None


def miles(n):
    """Entero con punto de miles (es-CO): 3976 -> 3.976."""
    return f"{int(n):,}".replace(",", ".")


def sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def canonico(texto):
    """MAYÚSCULAS, sin tildes, sin caracteres especiales y con espacios simples (igual que Etapa 2)."""
    if pd.isna(texto):
        return texto
    t = sin_tildes(str(texto)).upper()
    t = re.sub(r"[^A-Z0-9 .]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def verificar(condicion, mensaje):
    if not condicion:
        raise SystemExit(f"VERIFICACIÓN FALLIDA: {mensaje}")


def si_no(serie_bool):
    return serie_bool.map({True: "Sí", False: "No"})


def distribucion(df, col, tope=None, etiquetas=None):
    """Vehículos y % por categoría. Denominador: total de vehículos del df recibido."""
    g = (
        df.groupby(col)["cantidad"]
        .agg(vehiculos="sum", grupos="size")
        .sort_values("vehiculos", ascending=False)
    )
    total = int(g["vehiculos"].sum())
    filas = []
    for categoria, r in (g.head(tope) if tope else g).iterrows():
        fila = {
            "categoria": categoria,
            "vehiculos": int(r["vehiculos"]),
            "pct": pct(r["vehiculos"], total),
            "grupos": int(r["grupos"]),
        }
        if etiquetas:
            fila["etiqueta"] = etiquetas.get(categoria, categoria)
        filas.append(fila)
    return filas


def composicion(df, grupo, col, tope=3):
    """Dentro de cada `grupo`, las `tope` categorías de `col` con mayor %.
    Denominador: vehículos de ese grupo (no del total)."""
    salida = {}
    for valor, sub in df.groupby(grupo):
        salida[valor] = {
            "vehiculos": int(sub["cantidad"].sum()),
            "top": distribucion(sub, col, tope=tope),
        }
    return salida


# ----------------------------------------------------------------------------- 1. carga y tratamiento
fuente = json.loads(FUENTE.read_text(encoding="utf-8"))
df = pd.read_csv(CSV, dtype=str, keep_default_na=False, na_values=[""])
COLS = list(df.columns)
for c in ("cantidad", "modelo", "a_o_registro"):
    df[c] = df[c].astype(int)
FILAS_FUENTE, VEH_FUENTE = len(df), int(df["cantidad"].sum())
ANIO_FUENTE_MAX = int(df["a_o_registro"].max())
ANIO_MIN, ANIO_MAX = ANIO_INICIO, ANIO_FIN

# Misma regla de atípicos que Etapa 2 (Q3 + 1,5·IQR sobre `cantidad`, dataset completo).
q1, q3 = df["cantidad"].quantile([0.25, 0.75])
LIMITE_ATIPICO = float(q3 + 1.5 * (q3 - q1))

t = df.copy()
t["carroceria"] = t["carroceria"].fillna("SIN DATO")
for col in ("municipio", "departamento", "carroceria", "clase"):
    t[col] = t[col].map(canonico)
t["territorio"] = t["municipio"] + " (" + t["departamento"] + ")"
t["modelo_inusual"] = t["modelo"] > t["a_o_registro"] + 1
t["grupo_grande"] = t["cantidad"] > LIMITE_ATIPICO
t = t.rename(columns={"a_o_registro": "anio_registro"})

# Dataset completo (para comprobar contra la Etapa 2) y ventana de análisis 2015-2024.
t_fuente = t
t = t[t["anio_registro"].between(ANIO_INICIO, ANIO_FIN)].copy()
FILAS, VEH = len(t), int(t["cantidad"].sum())

corte = datetime.fromtimestamp(fuente["actualizacion_portal_epoch"], tz=timezone.utc).date()
descarga = date.fromisoformat(fuente["fecha_descarga"])

# ----------------------------------------------------------------------------- 2. modelo en estrella
hechos = t[["combustible", "clase", "carroceria", "anio_registro", "modelo", "territorio", "cantidad"]].copy()
hechos["modelo_inusual"] = si_no(t["modelo_inusual"])
hechos["grupo_grande"] = si_no(t["grupo_grande"])

dim_territorio = (
    t[["territorio", "municipio", "departamento"]].drop_duplicates().sort_values("territorio").reset_index(drop=True)
)
dim_combustible = pd.DataFrame(
    [{"combustible": k, "combustible_etiqueta": v} for k, v in ETIQUETA_COMBUSTIBLE.items()]
)
dim_anio = pd.DataFrame({"anio_registro": sorted(t["anio_registro"].unique())})

# El modelo no debe duplicar ni perder vehículos al unir hechos con cada dimensión.
verificar(dim_territorio["territorio"].is_unique, "dim_territorio.territorio no es una llave única")
verificar(dim_combustible["combustible"].is_unique, "dim_combustible.combustible no es una llave única")
verificar(dim_anio["anio_registro"].is_unique, "dim_anio.anio_registro no es una llave única")
for nombre, dim, llave in (
    ("territorio", dim_territorio, "territorio"),
    ("combustible", dim_combustible, "combustible"),
    ("año", dim_anio, "anio_registro"),
):
    unido = hechos.merge(dim, on=llave, how="left", validate="many_to_one", indicator=True)
    verificar(len(unido) == FILAS, f"la unión con la dimensión {nombre} cambió el número de filas")
    verificar((unido["_merge"] == "both").all(), f"hay hechos sin dimensión {nombre}")
    verificar(int(unido["cantidad"].sum()) == VEH, f"la unión con {nombre} cambió el total de vehículos")

CARPETA_POWERBI.mkdir(parents=True, exist_ok=True)
for nombre, tabla in (
    ("hechos_vehiculos", hechos),
    ("dim_territorio", dim_territorio),
    ("dim_combustible", dim_combustible),
    ("dim_anio", dim_anio),
):
    tabla.to_csv(CARPETA_POWERBI / f"{nombre}.csv", index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------- 3. cifras de referencia
res = {
    "meta": {
        "fuente": fuente["nombre"],
        "identificador": fuente["identificador"],
        "url_portal": fuente["url_portal"],
        "fecha_descarga": fuente["fecha_descarga"],
        "actualizacion_portal": corte.isoformat(),
        "periodo": {"desde": ANIO_MIN, "hasta": ANIO_MAX},
        "fuera_de_la_ventana": {
            "anios": f"{ANIO_MAX + 1}-{ANIO_FUENTE_MAX}",
            "grupos": FILAS_FUENTE - FILAS,
            "vehiculos": VEH_FUENTE - VEH,
            "motivo": (
                f"El alcance del proyecto es {ANIO_MIN}-{ANIO_MAX}. Además, {ANIO_FUENTE_MAX} es un año "
                f"incompleto (la fuente se actualizó el {corte.strftime('%d/%m/%Y')}) y no trae mes."
            ),
        },
        "unidad_analisis": (
            "Cada fila es un grupo de vehículos eléctricos o híbridos matriculados con las mismas "
            "características (combustible, modelo, año de registro, clase, carrocería y municipio); "
            "`cantidad` indica cuántos vehículos tiene el grupo. No es un vehículo individual ni "
            "parque activo: son matrículas por año de registro."
        ),
    }
}

# --- Preparación: qué se hizo, cuántos registros quedan y qué problemas siguen
res["preparacion"] = {
    "registros_fuente": FILAS_FUENTE,
    "vehiculos_fuente": VEH_FUENTE,
    "registros_analisis": len(hechos),
    "vehiculos": VEH,
    "excluidos_por_ventana": {"grupos": FILAS_FUENTE - FILAS, "vehiculos": VEH_FUENTE - VEH},
    "filas_eliminadas_por_calidad": 0,
    "tratamientos": [
        "Sin duplicados por la llave de 7 variables (ninguna fila eliminada).",
        "Un nulo de carrocería (triciclo eléctrico en Funza) reemplazado por «SIN DATO».",
        "modelo, año de registro y cantidad convertidos a entero.",
        "Texto canónico (mayúsculas, sin tildes ni caracteres especiales) en departamento, municipio, clase y carrocería.",
        "Llave territorial «MUNICIPIO (DEPARTAMENTO)»: 3 nombres de municipio existen en más de un departamento.",
        "Combustible homologado a etiquetas legibles (catálogo 1 a 1).",
        f"Se MARCAN, sin eliminar, {int(t['modelo_inusual'].sum())} grupos con modelo > año de registro + 1 (modelo_inusual).",
        f"Se MARCAN, sin eliminar, {int(t['grupo_grande'].sum())} grupos con cantidad > {LIMITE_ATIPICO:.0f} según IQR (grupo_grande; umbral de la Etapa 2).",
        f"Ventana de análisis {ANIO_MIN}-{ANIO_MAX} (alcance del proyecto): se excluyen {miles(FILAS_FUENTE - FILAS)} grupos y {miles(VEH_FUENTE - VEH)} vehículos registrados en {ANIO_MAX + 1}-{ANIO_FUENTE_MAX}.",
    ],
    "problemas_pendientes": [
        "El dataset no trae mes ni fecha: la unidad temporal mínima es el año de registro.",
        "La fuente no distingue HEV de PHEV: «Híbrido gasolina-eléctrico» agrupa ambos.",
        "Sin placa ni identificador: no se pueden contar vehículos únicos ni parque activo.",
        "Sin población, ingresos ni puntos de carga: no se pueden calcular tasas per cápita ni explicar causas.",
        "Distribución muy asimétrica: pocos grupos grandes concentran la mayoría de los vehículos.",
        "La fuente no trae códigos DIVIPOLA; el territorio se identifica por nombre.",
    ],
    "marcas": {
        "modelo_inusual": {"grupos": int(t["modelo_inusual"].sum()), "vehiculos": int(t.loc[t["modelo_inusual"], "cantidad"].sum())},
        "grupo_grande": {"grupos": int(t["grupo_grande"].sum()), "vehiculos": int(t.loc[t["grupo_grande"], "cantidad"].sum()), "limite_cantidad": LIMITE_ATIPICO},
    },
    "modelo_estrella": {
        "hechos_vehiculos": {"filas": len(hechos), "columnas": list(hechos.columns)},
        "dim_territorio": {"filas": len(dim_territorio), "llave": "territorio"},
        "dim_combustible": {"filas": len(dim_combustible), "llave": "combustible"},
        "dim_anio": {"filas": len(dim_anio), "llave": "anio_registro"},
        "relaciones": [
            "hechos_vehiculos[territorio] -> dim_territorio[territorio]  (muchos a uno, un solo sentido)",
            "hechos_vehiculos[combustible] -> dim_combustible[combustible]  (muchos a uno, un solo sentido)",
            "hechos_vehiculos[anio_registro] -> dim_anio[anio_registro]  (muchos a uno, un solo sentido)",
        ],
    },
}

# --- P1 · Composición y distribución
por_comb = distribucion(t, "combustible", etiquetas=ETIQUETA_COMBUSTIBLE)
por_clase = distribucion(t, "clase")
res["p1_composicion"] = {
    "pregunta": f"¿Cómo se compone la población de vehículos eléctricos e híbridos registrados en Colombia entre {ANIO_MIN} y {ANIO_MAX}, según su combustible, clase, carrocería y año del modelo?",
    "variables": ["combustible", "clase", "carroceria", "modelo", "cantidad"],
    "denominador": "Total de vehículos (suma de cantidad) = %d" % VEH,
    "indicadores": {
        "total_vehiculos": VEH,
        "grupos_de_registro": FILAS,
        "pct_electrico_bev": next(f["pct"] for f in por_comb if f["categoria"] == "ELECTRICO"),
        "clase_predominante": {"categoria": por_clase[0]["categoria"], "pct": por_clase[0]["pct"]},
        "pct_tres_clases_principales": pct(sum(f["vehiculos"] for f in por_clase[:3]), VEH),
    },
    "por_combustible": por_comb,
    "por_clase": por_clase,
    "clases_minoritarias_menor_1pct": [f["categoria"] for f in por_clase if f["pct"] < 1],
    "por_carroceria_top10": distribucion(t, "carroceria", tope=10),
    "por_anio_modelo": sorted(distribucion(t, "modelo"), key=lambda f: f["categoria"]),
    "composicion_de_cada_combustible_por_clase_top3": composicion(t, "combustible", "clase", 3),
    "concentracion_grupos_grandes": {
        "grupos": int(t["grupo_grande"].sum()),
        "pct_de_grupos": pct(t["grupo_grande"].sum(), FILAS),
        "pct_de_vehiculos": pct(t.loc[t["grupo_grande"], "cantidad"].sum(), VEH),
    },
}

# --- P2 · Comparación territorial
por_depto = distribucion(t, "departamento")
por_terr = distribucion(t, "territorio")
res["p2_territorial"] = {
    "pregunta": "¿Cómo se concentran los vehículos eléctricos e híbridos entre departamentos y municipios, y qué tecnología predomina en los principales?",
    "variables": ["departamento", "municipio (territorio)", "combustible", "cantidad"],
    "denominador": "Total de vehículos (%d); para la mezcla por combustible, vehículos de cada departamento" % VEH,
    "indicadores": {
        "departamentos_con_registros": int(t["departamento"].nunique()),
        "territorios_con_registros": int(t["territorio"].nunique()),
        "municipios_por_nombre": int(t["municipio"].nunique()),
        "departamento_lider": {"categoria": por_depto[0]["categoria"], "pct": por_depto[0]["pct"]},
        "pct_tres_primeros_departamentos": pct(sum(f["vehiculos"] for f in por_depto[:3]), VEH),
        "pct_diez_primeros_territorios": pct(sum(f["vehiculos"] for f in por_terr[:10]), VEH),
    },
    "por_departamento": por_depto,
    "territorios_top10": por_terr[:10],
    "territorios_con_menos_de_10_vehiculos": int(
        (t.groupby("territorio")["cantidad"].sum() < 10).sum()
    ),
    "mezcla_combustible_top5_departamentos": composicion(
        t[t["departamento"].isin([f["categoria"] for f in por_depto[:5]])], "departamento", "combustible", 4
    ),
    "nota_territorial": (
        "BOGOTA D.C. y CUNDINAMARCA son territorios distintos en la fuente. "
        "No hay población ni área: se comparan cantidades y participaciones, no tasas per cápita."
    ),
}

# --- P3 · Comportamiento temporal
anual = t.groupby("anio_registro")["cantidad"].sum()
bev_anual = t[t["combustible"] == "ELECTRICO"].groupby("anio_registro")["cantidad"].sum()
cobertura = t.groupby("anio_registro").agg(
    departamentos=("departamento", "nunique"), territorios=("territorio", "nunique"), clases=("clase", "nunique")
)
serie = []
for anio, vehiculos in anual.items():
    previo = anual.get(anio - 1)
    serie.append(
        {
            "anio": int(anio),
            "vehiculos": int(vehiculos),
            "pct_del_total": pct(vehiculos, VEH),
            "var_abs": int(vehiculos - previo) if previo is not None else None,
            "var_pct": pct(vehiculos - previo, previo) if previo is not None else None,
            "pct_electrico_bev": pct(bev_anual.get(anio, 0), vehiculos),
            "departamentos": int(cobertura.loc[anio, "departamentos"]),
            "territorios": int(cobertura.loc[anio, "territorios"]),
            "clases": int(cobertura.loc[anio, "clases"]),
        }
    )
por_anio_comb = (
    t.pivot_table(index="anio_registro", columns="combustible", values="cantidad", aggfunc="sum", fill_value=0)
    .astype(int)
    .reset_index()
    .to_dict("records")
)
res["p3_temporal"] = {
    "pregunta": f"¿Cómo evolucionó el registro anual de vehículos eléctricos e híbridos en Colombia entre {ANIO_MIN} y {ANIO_MAX}, y en qué años hubo los mayores cambios?",
    "variables": ["anio_registro", "combustible", "cantidad"],
    "denominador": "Variación porcentual: vehículos del año anterior. Participación: total de vehículos (%d)" % VEH,
    "indicadores": {
        "anio_maximo": {"anio": int(anual.idxmax()), "vehiculos": int(anual.max())},
        "anio_minimo": {"anio": int(anual.idxmin()), "vehiculos": int(anual.min())},
        f"veces_{ANIO_MAX}_vs_2019": round(float(anual[ANIO_MAX] / anual[2019]), 2),
        "var_pct_ultimo_anio": next(s["var_pct"] for s in serie if s["anio"] == ANIO_MAX),
        "anio_mayor_variacion_pct": max((s for s in serie if s["var_pct"] is not None), key=lambda s: s["var_pct"])["anio"],
    },
    "serie_anual": serie,
    "por_anio_y_combustible": por_anio_comb,
    "nota_periodos": (
        f"Los {ANIO_MAX - ANIO_MIN + 1} años de la ventana son comparables entre sí. La fuente no trae mes, "
        f"así que no hay periodos más finos que el año. {ANIO_MAX + 1} y {ANIO_FUENTE_MAX} quedan fuera "
        f"({ANIO_FUENTE_MAX} es parcial)."
    ),
}

# --- P4 · Multivariado (combustible × clase × departamento)
combos = (
    t.groupby(["combustible", "clase", "departamento"])["cantidad"]
    .agg(vehiculos="sum", grupos="size")
    .sort_values("vehiculos", ascending=False)
    .reset_index()
)
top_grupos = t.sort_values("cantidad", ascending=False).head(10)
hidrogeno = t[t["combustible"] == "HIDROGENO"]
pocos = por_clase[-4:]
dep_top5 = [f["categoria"] for f in por_depto[:5]]
perfil_dep = {}
for dep in dep_top5:
    sub = t[t["departamento"] == dep]
    perfil_dep[dep] = {
        "vehiculos": int(sub["cantidad"].sum()),
        "pct_electrico_bev": pct(sub.loc[sub["combustible"] == "ELECTRICO", "cantidad"].sum(), sub["cantidad"].sum()),
        "clase_principal": distribucion(sub, "clase", tope=1)[0],
    }
res["p4_multivariado"] = {
    "pregunta": "¿Qué perfiles surgen al cruzar combustible, clase de vehículo y departamento, y qué grupos son atípicos?",
    "variables": ["combustible", "clase", "departamento", "cantidad"],
    "denominador": "Total de vehículos (%d); en los perfiles, vehículos del combustible o departamento indicado" % VEH,
    "indicadores": {
        "combinaciones_distintas": int(len(combos)),
        "combinacion_principal": {
            "combustible": combos.loc[0, "combustible"],
            "clase": combos.loc[0, "clase"],
            "departamento": combos.loc[0, "departamento"],
            "vehiculos": int(combos.loc[0, "vehiculos"]),
            "pct": pct(combos.loc[0, "vehiculos"], VEH),
        },
        "pct_diez_combinaciones_principales": pct(combos["vehiculos"].head(10).sum(), VEH),
    },
    "combinaciones_top10": [
        {**{k: (v if isinstance(v, str) else int(v)) for k, v in r.items()}, "pct": pct(r["vehiculos"], VEH)}
        for r in combos.head(10).to_dict("records")
    ],
    "perfil_de_cada_combustible_clase_top3": composicion(t, "combustible", "clase", 3),
    "perfil_top5_departamentos": perfil_dep,
    "casos_inusuales": {
        "grupos_mas_grandes_top10": [
            {
                "combustible": r.combustible,
                "clase": r.clase,
                "departamento": r.departamento,
                "municipio": r.municipio,
                "anio_registro": int(r.anio_registro),
                "cantidad": int(r.cantidad),
            }
            for r in top_grupos.itertuples()
        ],
        "pct_vehiculos_en_top10_grupos": pct(top_grupos["cantidad"].sum(), VEH),
        "hidrogeno": {
            "vehiculos": int(hidrogeno["cantidad"].sum()),
            "grupos": len(hidrogeno),
            "territorios": sorted(hidrogeno["territorio"].unique().tolist()),
        },
        "clases_con_menos_vehiculos": pocos,
        "modelo_inusual": res["preparacion"]["marcas"]["modelo_inusual"],
    },
}

# --- Verificaciones para comparar con las medidas DAX (con y sin filtros de segmentadores)
bog = t[t["departamento"] == "BOGOTA D.C."]
v2023 = int(anual[2023])
verificaciones = [
    ("Total vehículos", "sin filtros", VEH, "SUM(hechos_vehiculos[cantidad])"),
    ("Grupos de registro", "sin filtros", FILAS, "COUNTROWS(hechos_vehiculos)"),
    ("Vehículos 2023", "anio_registro = 2023", v2023, "CALCULATE([Total vehículos], dim_anio[anio_registro] = 2023)"),
    ("Vehículos 2024 (último año de la ventana)", "anio_registro = 2024", int(anual[2024]), "idem con 2024"),
    ("Vehículos eléctricos (BEV)", "combustible = ELECTRICO", int(t.loc[t["combustible"] == "ELECTRICO", "cantidad"].sum()), "CALCULATE([Total vehículos], dim_combustible[combustible] = \"ELECTRICO\")"),
    ("% eléctricos sobre el total", "sin filtros", pct(t.loc[t["combustible"] == "ELECTRICO", "cantidad"].sum(), VEH), "DIVIDE([Vehículos BEV], [Total vehículos]) * 100"),
    ("Vehículos en Antioquia", "departamento = ANTIOQUIA", int(t.loc[t["departamento"] == "ANTIOQUIA", "cantidad"].sum()), "CALCULATE([Total vehículos], dim_territorio[departamento] = \"ANTIOQUIA\")"),
    (
        "Vehículos Antioquia + híbrido gasolina + 2024",
        "departamento = ANTIOQUIA, combustible = GASO ELEC, anio_registro = 2024",
        int(t[(t["departamento"] == "ANTIOQUIA") & (t["combustible"] == "GASO ELEC") & (t["anio_registro"] == 2024)]["cantidad"].sum()),
        "tres filtros combinados",
    ),
    ("% eléctricos dentro de Bogotá D.C.", "departamento = BOGOTA D.C. (denominador: vehículos de Bogotá)", pct(bog.loc[bog["combustible"] == "ELECTRICO", "cantidad"].sum(), bog["cantidad"].sum()), "DIVIDE([Vehículos BEV], [Total vehículos]) * 100 con el filtro territorial"),
    ("Vehículos clase CAMIONETA", "clase = CAMIONETA", int(t.loc[t["clase"] == "CAMIONETA", "cantidad"].sum()), "CALCULATE([Total vehículos], hechos_vehiculos[clase] = \"CAMIONETA\")"),
    ("Vehículos en grupos grandes", "grupo_grande = Sí", int(t.loc[t["grupo_grande"], "cantidad"].sum()), "CALCULATE([Total vehículos], hechos_vehiculos[grupo_grande] = \"Sí\")"),
    ("Grupos con modelo inusual", "modelo_inusual = Sí", int(t["modelo_inusual"].sum()), "CALCULATE(COUNTROWS(hechos_vehiculos), hechos_vehiculos[modelo_inusual] = \"Sí\")"),
    ("Variación % 2024 vs 2023", "anio_registro = 2024 (base: 2023)", pct(anual[2024] - anual[2023], anual[2023]), "DIVIDE([Vehículos 2024] - [Vehículos 2023], [Vehículos 2023]) * 100"),
    ("Territorios distintos", "sin filtros", int(t["territorio"].nunique()), "DISTINCTCOUNT(hechos_vehiculos[territorio]) — usar territorio, no municipio"),
    ("Municipios distintos por nombre (NO usar)", "sin filtros", int(t["municipio"].nunique()), "DISTINCTCOUNT de municipio fusiona homónimos de distintos departamentos"),
]
res["verificaciones"] = [
    {"medida": m, "filtro": f, "valor_esperado": v, "dax_sugerido": d} for m, f, v, d in verificaciones
]

# ----------------------------------------------------------------------------- 4. coherencia con la Etapa 2
eda = json.loads(RESULTADOS_ETAPA2.read_text(encoding="utf-8"))
acciones = {(a["proceso"], a["variable"]): a["filas"] for a in eda["tratamiento"]["acciones"]}
# Se compara el dataset COMPLETO de la fuente (la Etapa 2 no aplicó la ventana 2015-2024).
coherencia = {
    "filas": (FILAS_FUENTE, eda["meta"]["filas"]),
    "vehiculos": (VEH_FUENTE, eda["meta"]["vehiculos"]),
    "grupos_modelo_inusual": (int(t_fuente["modelo_inusual"].sum()), acciones[("Validación de rangos", "modelo")]),
    "grupos_grande": (int(t_fuente["grupo_grande"].sum()), acciones[("Tratamiento de atípicos", "cantidad")]),
    "grupos_anio_parcial": (int((t_fuente["anio_registro"] == ANIO_FUENTE_MAX).sum()), acciones[("Validación de actualidad", "a_o_registro")]),
}
for nombre, (calculado, etapa2) in coherencia.items():
    verificar(calculado == etapa2, f"{nombre}: aquí {calculado} y en resultados_eda.json {etapa2}")
verificar(sum(f["vehiculos"] for f in por_comb) == VEH, "la distribución por combustible no suma el total")
verificar(sum(f["vehiculos"] for f in por_depto) == VEH, "la distribución por departamento no suma el total")
verificar(int(anual.sum()) == VEH, "la serie anual no suma el total")
res["coherencia_con_etapa2"] = {k: {"esta_etapa": a, "etapa2": b, "coincide": a == b} for k, (a, b) in coherencia.items()}


def _nativo(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=_nativo), encoding="utf-8")
print(
    f"OK · {FILAS:,} grupos · {VEH:,} vehículos · modelo en estrella en {CARPETA_POWERBI.relative_to(RAIZ)} · "
    f"cifras en {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1024:.0f} KB)".replace(",", ".")
)
