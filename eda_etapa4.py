"""
Análisis exploratorio (EDA) de la población — Etapa 4.

Fuente (única): datos.gov.co · ntxy-q9ix
    "Vehículos eléctricos e híbridos matriculados en Colombia - RUNT 2.0"
    (procedencia, URL y fecha de descarga: data/raw/FUENTE.json)

Calcula las cuatro dimensiones del análisis exploratorio:
    poblacional · territorial · temporal · relacional y multivariada
y las escribe en data/processed/resultados_etapa4.json, que es lo que lee la app Flask.

IMPORTANTE:
  * El dataset es AGREGADO: cada fila es un grupo de vehículos y `cantidad` dice cuántos.
    Los porcentajes se calculan ponderando por `cantidad` (vehículos), no contando filas.
  * Requiere haber ejecutado antes calidad_etapa2.py (lee data/processed/resultados_eda.json
    para reutilizar los totales y hallazgos del perfilamiento).

Uso:
    pip install -r requirements-dev.txt
    python calidad_etapa2.py
    python eda_etapa4.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
CSV = RAIZ / "data" / "raw" / "vehiculos_electricos_hibridos_runt.csv"
FUENTE = RAIZ / "data" / "raw" / "FUENTE.json"
BASE = RAIZ / "data" / "processed" / "resultados_eda.json"
SALIDA = RAIZ / "data" / "processed" / "resultados_etapa4.json"

ETIQUETA_COMBUSTIBLE = {
    "ELECTRICO": "Eléctrico (BEV)",
    "GASO ELEC": "Híbrido gasolina-eléctrico (HEV/PHEV)",
    "DIES ELEC": "Híbrido diésel-eléctrico",
    "HIDROGENO": "Hidrógeno",
}


# ----------------------------------------------------------------------------- utilidades
def pct(a, b, nd=2):
    return round(float(a) / float(b) * 100, nd) if b else None


def resumen(df, col, total, top=None):
    g = (
        df.groupby(col)
        .agg(vehiculos=("cantidad", "sum"), filas=("cantidad", "size"))
        .sort_values("vehiculos", ascending=False)
    )
    g["pct"] = (g["vehiculos"] / total * 100).round(2)
    g["acum"] = g["pct"].cumsum().round(2)
    if top:
        g = g.head(top)
    return [
        {"categoria": str(i), "vehiculos": int(r.vehiculos), "filas": int(r.filas), "pct": float(r.pct), "acum": float(r.acum)}
        for i, r in g.iterrows()
    ]


def cramers_v(a, b, pesos):
    t = pd.crosstab(a, b, values=pesos, aggfunc="sum").fillna(0).to_numpy(dtype=float)
    n = t.sum()
    esperado = np.outer(t.sum(1), t.sum(0)) / n
    m = esperado > 0
    chi2 = (((t - esperado) ** 2)[m] / esperado[m]).sum()
    k = min(t.shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if k > 0 else 0.0


def fuerza(v):
    return "muy fuerte" if v >= 0.5 else "fuerte" if v >= 0.3 else "moderada" if v >= 0.15 else "débil"


# ----------------------------------------------------------------------------- 0. carga
fuente = json.loads(FUENTE.read_text(encoding="utf-8"))
base = json.loads(BASE.read_text(encoding="utf-8"))  # resultados de calidad_etapa2.py
df = pd.read_csv(CSV, dtype=str, keep_default_na=False, na_values=[""])
df["cantidad"] = df["cantidad"].astype(int)
df["modelo"] = df["modelo"].astype(int)
df["a_o_registro"] = df["a_o_registro"].astype(int)
FILAS, VEH = len(df), int(df["cantidad"].sum())
c = df["cantidad"]
anio = df["a_o_registro"]
modelo = df["modelo"]
ANIO_MIN, ANIO_MAX = int(anio.min()), int(anio.max())
corte = datetime.fromtimestamp(fuente["actualizacion_portal_epoch"], tz=timezone.utc).date()
res = {}

# ----------------------------------------------------------------------------- 5. ETAPA 4 · poblacional
comb = resumen(df, "combustible", VEH)
for r in comb:
    r["etiqueta"] = ETIQUETA_COMBUSTIBLE[r["categoria"]]
clases = resumen(df, "clase", VEH)
carrs = resumen(df, "carroceria", VEH)
top_carr = carrs[:10]
otras_carr = {"categoria": "Otras carrocerías", "vehiculos": VEH - sum(r["vehiculos"] for r in top_carr), "filas": 0, "pct": 0.0, "acum": 100.0}
otras_carr["pct"] = pct(otras_carr["vehiculos"], VEH)
por_modelo = df.assign(m=np.where(df["modelo"] <= 2014, "≤ 2014", df["modelo"].astype(str))).groupby("m")["cantidad"].sum()
orden_modelo = ["≤ 2014"] + [str(a) for a in range(2015, int(df["modelo"].max()) + 1)]
modelos = [{"categoria": m, "vehiculos": int(por_modelo.get(m, 0)), "pct": pct(por_modelo.get(m, 0), VEH)} for m in orden_modelo]
res["poblacional"] = {
    "filas": FILAS, "vehiculos": VEH, "promedio_por_fila": round(VEH / FILAS, 2), "mediana_por_fila": float(c.median()),
    "combustible": comb, "clase": clases, "carroceria_top": top_carr, "carroceria_otras": otras_carr, "n_carrocerias": int(df["carroceria"].nunique()),
    "modelo": modelos,
    "predominante_clase": clases[0], "top2_clase_pct": round(clases[0]["pct"] + clases[1]["pct"], 2),
    "minoritarias_clase": [r for r in clases if r["pct"] < 0.1],
    "minoritarias_combustible": [r for r in comb if r["pct"] < 1.0],
    "sin_carroceria_pct": base["perfilamiento"]["sin_carroceria"]["pct_vehiculos"],
}

# ----------------------------------------------------------------------------- 6. ETAPA 4 · territorial
deps = resumen(df, "departamento", VEH)
n_mun = df.groupby("departamento")["municipio"].nunique()
for r in deps:
    r["municipios"] = int(n_mun[r["categoria"]])
muni = (
    df.groupby(["departamento", "municipio"])["cantidad"].sum().sort_values(ascending=False).reset_index()
)
muni["pct"] = (muni["cantidad"] / VEH * 100).round(2)
muni["acum"] = muni["pct"].cumsum().round(2)
cuota = df.groupby("departamento")["cantidad"].sum() / VEH
hhi = round(float((cuota**2).sum() * 10000), 0)
pc = df.pivot_table(index="departamento", columns="combustible", values="cantidad", aggfunc="sum", fill_value=0)
pcl = df.pivot_table(index="departamento", columns="clase", values="cantidad", aggfunc="sum", fill_value=0)
comp = []
for d in [r["categoria"] for r in deps[:10]]:
    fila = pc.loc[d]
    tot = fila.sum()
    clase_dom = pcl.loc[d].idxmax()
    comp.append({
        "departamento": d, "vehiculos": int(tot),
        "pct_electrico": pct(fila.get("ELECTRICO", 0), tot), "pct_hibrido_gas": pct(fila.get("GASO ELEC", 0), tot),
        "pct_otros": pct(fila.get("DIES ELEC", 0) + fila.get("HIDROGENO", 0), tot),
        "clase_dominante": clase_dom, "pct_clase_dominante": pct(pcl.loc[d, clase_dom], tot),
    })
grandes = pc[pc.sum(1) >= 500].copy()
grandes["pct_electrico"] = (grandes["ELECTRICO"] / grandes.sum(1) * 100).round(2)
mas_bev = grandes.sort_values("pct_electrico", ascending=False).head(5)
menos_bev = grandes.sort_values("pct_electrico").head(3)
clase_dom_dep = pcl.idxmax(axis=1)
no_camioneta = [
    {"departamento": d, "clase": clase_dom_dep[d], "vehiculos": int(pcl.loc[d].sum()), "pct_clase": pct(pcl.loc[d, clase_dom_dep[d]], pcl.loc[d].sum())}
    for d in pcl.index if clase_dom_dep[d] != "CAMIONETA" and pcl.loc[d].sum() >= 100
]
res["territorial"] = {
    "n_departamentos": base["meta"]["n_departamentos"], "n_municipios": base["meta"]["n_municipios"],
    "departamentos": deps,
    "municipios_top": [{"departamento": r.departamento, "municipio": r.municipio, "vehiculos": int(r.cantidad), "pct": float(r.pct), "acum": float(r.acum)} for r in muni.head(15).itertuples()],
    "top1_pct": deps[0]["pct"], "top3_pct": deps[2]["acum"], "top5_pct": deps[4]["acum"], "hhi": hhi,
    "municipios_para_50": int((muni["acum"] < 50).sum() + 1), "municipios_para_80": int((muni["acum"] < 80).sum() + 1),
    "deps_menos_1pct": int(sum(r["pct"] < 1 for r in deps)), "deps_menos_01pct": int(sum(r["pct"] < 0.1 for r in deps)),
    "municipios_menos_10_veh": int((muni["cantidad"] < 10).sum()),
    "menores": deps[-8:][::-1],
    "composicion_top10": comp,
    "mayor_pct_electrico": [{"departamento": i, "vehiculos": int(r.drop("pct_electrico").sum()), "pct_electrico": float(r["pct_electrico"])} for i, r in mas_bev.iterrows()],
    "menor_pct_electrico": [{"departamento": i, "vehiculos": int(r.drop("pct_electrico").sum()), "pct_electrico": float(r["pct_electrico"])} for i, r in menos_bev.iterrows()],
    "clase_dominante_no_camioneta": no_camioneta,
    "bogota_vs_resto": {"bogota": deps[0]["vehiculos"], "resto": VEH - deps[0]["vehiculos"], "pct_bogota": deps[0]["pct"]},
}

# ----------------------------------------------------------------------------- 7. ETAPA 4 · temporal
por_anio = df.groupby("a_o_registro").agg(vehiculos=("cantidad", "sum"), filas=("cantidad", "size"))
anio_comb = df.pivot_table(index="a_o_registro", columns="combustible", values="cantidad", aggfunc="sum", fill_value=0)
serie = []
prev = None
for a, r in por_anio.iterrows():
    v = int(r.vehiculos)
    fila_c = anio_comb.loc[a]
    serie.append({
        "anio": int(a), "vehiculos": v, "filas": int(r.filas), "pct_total": pct(v, VEH),
        "var_pct": None if prev is None else round((v - prev) / prev * 100, 1),
        "var_abs": None if prev is None else v - prev,
        "pct_electrico": pct(fila_c.get("ELECTRICO", 0), v), "pct_hibrido_gas": pct(fila_c.get("GASO ELEC", 0), v),
        "electrico": int(fila_c.get("ELECTRICO", 0)), "hibrido_gas": int(fila_c.get("GASO ELEC", 0)),
        "hibrido_dies": int(fila_c.get("DIES ELEC", 0)), "hidrogeno": int(fila_c.get("HIDROGENO", 0)),
        "parcial": bool(a == ANIO_MAX),
    })
    prev = v
completos = [s for s in serie if not s["parcial"]]
mayor_alza = max([s for s in completos if s["var_pct"] is not None], key=lambda s: s["var_pct"])
mayor_alza_abs = max([s for s in completos if s["var_abs"] is not None], key=lambda s: s["var_abs"])
caidas = [s for s in completos if s["var_pct"] is not None and s["var_pct"] < 0]
def suma_periodo(a, b):
    return int(sum(s["vehiculos"] for s in serie if a <= s["anio"] <= b))
periodos = [
    {"periodo": "2015 – 2019", "vehiculos": suma_periodo(2015, 2019)},
    {"periodo": "2020 – 2023", "vehiculos": suma_periodo(2020, 2023)},
    {"periodo": f"2024 – {ANIO_MAX} (parcial)", "vehiculos": suma_periodo(2024, ANIO_MAX)},
]
for p in periodos:
    p["pct"] = pct(p["vehiculos"], VEH)
v18 = next(s["vehiculos"] for s in serie if s["anio"] == 2018)
v25 = next(s["vehiculos"] for s in serie if s["anio"] == ANIO_MAX - 1)
cagr = round(((v25 / v18) ** (1 / (ANIO_MAX - 1 - 2018)) - 1) * 100, 1)
meses = round(corte.timetuple().tm_yday / 365 * 12, 1)
v_parcial = next(s["vehiculos"] for s in serie if s["parcial"])
rezago = (anio - modelo)
bucket = pd.cut(rezago, [-10, -1, 0, 1, 4, 100], labels=["Modelo posterior al registro", "Mismo año", "1 año de antigüedad", "2 a 4 años", "5 años o más"])
lag = df.groupby(bucket, observed=False)["cantidad"].sum()
res["temporal"] = {
    "serie": serie, "anio_min": ANIO_MIN, "anio_max": ANIO_MAX,
    "mayor_alza_pct": mayor_alza, "mayor_alza_abs": mayor_alza_abs, "caidas": caidas,
    "anio_mas_vehiculos_completo": max(completos, key=lambda s: s["vehiculos"]), "anio_menos_vehiculos": min(serie, key=lambda s: s["vehiculos"]),
    "periodos": periodos, "cagr_2018_ultimo_completo": cagr, "anio_cagr_fin": ANIO_MAX - 1,
    "meses_transcurridos_parcial": meses,
    "ritmo_mensual_parcial": round(v_parcial / meses), "ritmo_mensual_ultimo_completo": round(v25 / 12),
    "ritmo_mensual_2018": round(v18 / 12),
    "rezago_modelo": [{"categoria": str(k), "vehiculos": int(v), "pct": pct(v, VEH)} for k, v in lag.items()],
    "granularidad": "anual",
    "estacionalidad_evaluable": False,
}

# ----------------------------------------------------------------------------- 8. ETAPA 4 · relacional / multivariado
top_clases = [r["categoria"] for r in clases[:6]]
cxc = df.pivot_table(index="clase", columns="combustible", values="cantidad", aggfunc="sum", fill_value=0)
cxc = cxc.loc[cxc.sum(1).sort_values(ascending=False).index]
cruce_cc = []
for k, r in cxc.iterrows():
    tot = int(r.sum())
    cruce_cc.append({"clase": k, "vehiculos": tot, "electrico": int(r.get("ELECTRICO", 0)), "hibrido_gas": int(r.get("GASO ELEC", 0)),
                     "hibrido_dies": int(r.get("DIES ELEC", 0)), "hidrogeno": int(r.get("HIDROGENO", 0)),
                     "pct_electrico": pct(r.get("ELECTRICO", 0), tot), "pct_hibrido_gas": pct(r.get("GASO ELEC", 0), tot)})
top_deps8 = [r["categoria"] for r in deps[:8]]
sub = df[df["departamento"].isin(top_deps8) & df["clase"].isin(top_clases[:5])]
cd = sub.pivot_table(index="departamento", columns="clase", values="cantidad", aggfunc="sum", fill_value=0).reindex(top_deps8)
cd_pct = (cd.div(df[df["departamento"].isin(top_deps8)].groupby("departamento")["cantidad"].sum().reindex(top_deps8), axis=0) * 100).round(1)
triple = (
    df.groupby(["combustible", "clase", "departamento"])["cantidad"].sum().sort_values(ascending=False).head(12).reset_index()
)
triple_lista = [{"combustible": r.combustible, "clase": r.clase, "departamento": r.departamento, "vehiculos": int(r.cantidad), "pct": pct(r.cantidad, VEH)} for r in triple.itertuples()]
triple_cca = (
    df.groupby(["combustible", "clase", "carroceria"])["cantidad"].sum().sort_values(ascending=False).head(10).reset_index()
)
combos_ccc = [{"combustible": r.combustible, "clase": r.clase, "carroceria": r.carroceria, "vehiculos": int(r.cantidad), "pct": pct(r.cantidad, VEH)} for r in triple_cca.itertuples()]
anios_mat = [a for a in range(2018, ANIO_MAX + 1)]
clases_mat = top_clases[:4]
mat = []
for k in clases_mat:
    fila = {"clase": k, "valores": []}
    for a in anios_mat:
        s = df[(df["clase"] == k) & (anio == a)]
        tot = int(s["cantidad"].sum())
        fila["valores"].append({"anio": a, "total": tot, "pct_electrico": pct(s.loc[s["combustible"] == "ELECTRICO", "cantidad"].sum(), tot, 1) if tot >= 20 else None})
    mat.append(fila)
vs = {
    "combustible – clase": cramers_v(df["combustible"], df["clase"], df["cantidad"]),
    "combustible – departamento": cramers_v(df["combustible"], df["departamento"], df["cantidad"]),
    "combustible – año de registro": cramers_v(df["combustible"], df["a_o_registro"], df["cantidad"]),
    "clase – departamento": cramers_v(df["clase"], df["departamento"], df["cantidad"]),
    "clase – año de registro": cramers_v(df["clase"], df["a_o_registro"], df["cantidad"]),
}
asoc = [{"par": k, "v": round(v, 3), "fuerza": fuerza(v)} for k, v in sorted(vs.items(), key=lambda x: -x[1])]
tabla = cxc.to_numpy(dtype=float)
esp = np.outer(tabla.sum(1), tabla.sum(0)) / tabla.sum()
resid = np.where(esp >= 5, (tabla - esp) / np.sqrt(np.where(esp > 0, esp, 1)), 0)
celdas_res = []
for i, cl in enumerate(cxc.index):
    for j, co in enumerate(cxc.columns):
        if esp[i, j] >= 5:
            celdas_res.append({"clase": cl, "combustible": co, "observado": int(tabla[i, j]), "esperado": round(float(esp[i, j]), 1), "residuo": round(float(resid[i, j]), 1)})
sobre = sorted(celdas_res, key=lambda x: -x["residuo"])[:6]
sub_rep = sorted(celdas_res, key=lambda x: x["residuo"])[:4]
casos = {
    "hidrogeno": [{"clase": r["clase"], "carroceria": r["carroceria"], "municipio": r["municipio"], "departamento": r["departamento"], "modelo": int(r["modelo"]), "anio": int(r["a_o_registro"])} for r in df[df["combustible"] == "HIDROGENO"].to_dict("records")],
    "mayores_grupos": base["perfilamiento"]["mayores_grupos"],
    "grupos_de_1": {"filas": int((c == 1).sum()), "pct_filas": pct((c == 1).sum(), FILAS), "pct_vehiculos": pct((c == 1).sum(), VEH, 2)},
    "modelo_inusual": base["perfilamiento"]["ejemplos_modelo_inusual"],
    "modelo_inusual_total": base["perfilamiento"]["modelo_mayor_anio_mas1"],
    "clases_poco_representadas": base["perfilamiento"]["clases_poco_representadas"],
    "electrico_pesados": [
        {"clase": r["clase"], "electrico": r["electrico"], "total": r["vehiculos"]} for r in cruce_cc if r["clase"] in ("BUS", "CAMION", "BUSETA", "MICROBUS")
    ],
}
res["multivariado"] = {
    "cruce_combustible_clase": cruce_cc,
    "cruce_clase_departamento": {
        "departamentos": top_deps8, "clases": list(cd.columns),
        "porcentaje": [[float(x) for x in cd_pct.loc[d].tolist()] for d in top_deps8],
        "vehiculos": [[int(x) for x in cd.loc[d].tolist()] for d in top_deps8],
    },
    "triple_comb_clase_dep": triple_lista,
    "combos_comb_clase_carroceria": combos_ccc,
    "matriz_clase_anio_electrico": {"anios": anios_mat, "filas": mat},
    "asociaciones": asoc,
    "sobre_representadas": sobre,
    "sub_representadas": sub_rep,
    "casos_inusuales": casos,
}

# ----------------------------------------------------------------------------- salida
SALIDA.parent.mkdir(parents=True, exist_ok=True)


def _nativo(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=_nativo), encoding="utf-8")
print(f"OK · {FILAS:,} filas · {VEH:,} vehículos · resultados en {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size/1024:.0f} KB)".replace(",", "."))
