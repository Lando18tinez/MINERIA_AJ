"""
Etapa 6 · Preparación de los datos para Orange Data Mining (aprendizaje supervisado y clustering).

Fuente (la misma de las etapas anteriores): datos.gov.co · ntxy-q9ix, ya tratada en la Etapa 2 y
limitada a la ventana 2015-2024 (data/powerbi/hechos_vehiculos.csv + dim_territorio.csv).
No se descarga nada nuevo ni se inventa ninguna cifra.

IMPORTANTE: el dataset es AGREGADO. Cada fila es un grupo de vehículos y `cantidad` dice cuántos.
Los vehículos se cuentan con SUM(cantidad), no con COUNT(*).

Produce, en data/processed/etapa6/ (formato .tab de Orange: tipos y roles ya definidos):

  supervisado_tipo_motorizacion.tab
      Una fila por grupo de vehículos. Clase (variable objetivo): tipo_motorizacion = ELECTRICO | HIBRIDO.
      Predictoras: clase, carroceria, departamento, anio_registro, modelo, antiguedad_modelo.
      `cantidad` va como META (no es predictora: no se conoce al predecir y es el peso del grupo).

  clustering_territorios.tab
      Una fila por territorio (municipio + departamento) con >= MIN_VEHICULOS vehículos.
      Variables: perfil de clases de vehículo, antigüedad y tamaño. NO incluye combustible ni
      tipo_motorizacion (la variable objetivo del ejercicio supervisado).

  resultados_etapa6_preparacion.json
      Cifras de la preparación (filas, vehículos, balance de clases, exclusiones) que lee la app.

Uso:
    python etapa6_preparar_datos.py          (solo requiere pandas y numpy)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
HECHOS = RAIZ / "data" / "powerbi" / "hechos_vehiculos.csv"
TERRITORIO = RAIZ / "data" / "powerbi" / "dim_territorio.csv"
SALIDA = RAIZ / "data" / "processed" / "etapa6"

# Territorios con menos vehículos que este umbral se excluyen del clustering: sus porcentajes
# (p. ej. «% camionetas») se calculan sobre muy pocos vehículos y serían ruido, no perfil.
MIN_VEHICULOS = 30

# Agrupación de clases para el perfil territorial (cada clase de la fuente queda en un solo grupo).
LIVIANOS_MICRO = {"CICLOMOTOR", "CUADRICICLO", "MOTOCICLETA", "MOTOCARRO", "TRICIMOTO", "MOTOTRICICLO", "CUATRIMOTO"}


def pct(parte, total):
    return round(100 * parte / total, 2)


def escribir_tab(df, tipos, roles, ruta):
    """Escribe un .tab de Orange: fila 1 nombres, fila 2 tipos (c/d/s), fila 3 roles (class/meta)."""
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(df.columns) + "\n")
        f.write("\t".join(tipos[c] for c in df.columns) + "\n")
        f.write("\t".join(roles.get(c, "") for c in df.columns) + "\n")
        for fila in df.itertuples(index=False):
            f.write("\t".join(str(v) for v in fila) + "\n")


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows (cp1252) no imprime μ, é, etc.
    SALIDA.mkdir(parents=True, exist_ok=True)
    h = pd.read_csv(HECHOS, encoding="utf-8-sig").merge(
        pd.read_csv(TERRITORIO, encoding="utf-8-sig"), on="territorio", validate="m:1"
    )
    total_grupos, total_veh = len(h), int(h["cantidad"].sum())
    assert (total_grupos, total_veh) == (6772, 155777), "los datos tratados no coinciden con la Etapa 2/5"

    # ------------------------------------------------------------------ 1. Supervisado
    # Pregunta: dado un grupo de vehículos (clase, carrocería, departamento, año de registro y año
    # del modelo), ¿es eléctrico (BEV) o híbrido? Hidrógeno (4 grupos, 4 vehículos) no es ni una
    # cosa ni la otra y no tiene ejemplos suficientes: se excluye y se documenta.
    s = h[h["combustible"] != "HIDROGENO"].copy()
    excl_h = h[h["combustible"] == "HIDROGENO"]
    s["tipo_motorizacion"] = np.where(s["combustible"] == "ELECTRICO", "ELECTRICO", "HIBRIDO")
    # Antigüedad al registrar: 0 = vehículo del año; >0 usado; <0 modelo del año siguiente.
    s["antiguedad_modelo"] = s["anio_registro"] - s["modelo"]
    cols = ["clase", "carroceria", "departamento", "anio_registro", "modelo", "antiguedad_modelo",
            "tipo_motorizacion", "cantidad"]
    sup = s[cols].reset_index(drop=True)
    tipos = {"clase": "d", "carroceria": "d", "departamento": "d", "anio_registro": "c", "modelo": "c",
             "antiguedad_modelo": "c", "tipo_motorizacion": "d", "cantidad": "c"}
    roles = {"tipo_motorizacion": "class", "cantidad": "meta"}
    escribir_tab(sup, tipos, roles, SALIDA / "supervisado_tipo_motorizacion.tab")

    g = sup.groupby("tipo_motorizacion")["cantidad"].agg(grupos="size", vehiculos="sum")
    pred = ["clase", "carroceria", "departamento", "anio_registro", "modelo", "antiguedad_modelo"]
    vectores = sup.groupby(pred)["tipo_motorizacion"].nunique()

    # ------------------------------------------------------------------ 2. Clustering
    por_terr = h.groupby(["territorio", "municipio", "departamento"], as_index=False)["cantidad"].sum()
    por_terr = por_terr.rename(columns={"cantidad": "vehiculos"})
    grandes = por_terr[por_terr["vehiculos"] >= MIN_VEHICULOS]["territorio"]
    t = h[h["territorio"].isin(grandes)].copy()
    t["w_anio"] = t["cantidad"] * t["anio_registro"]
    t["w_antig"] = t["cantidad"] * (t["anio_registro"] - t["modelo"])
    t["w_cam"] = t["cantidad"] * (t["clase"] == "CAMIONETA")
    t["w_aut"] = t["cantidad"] * (t["clase"] == "AUTOMOVIL")
    t["w_cmp"] = t["cantidad"] * (t["clase"] == "CAMPERO")
    t["w_mic"] = t["cantidad"] * t["clase"].isin(LIVIANOS_MICRO)
    t["w_rec"] = t["cantidad"] * (t["anio_registro"] >= 2022)
    a = t.groupby("territorio").agg(
        municipio=("municipio", "first"), departamento=("departamento", "first"),
        vehiculos=("cantidad", "sum"), grupos=("cantidad", "size"),
        w_anio=("w_anio", "sum"), w_antig=("w_antig", "sum"), w_cam=("w_cam", "sum"), w_aut=("w_aut", "sum"),
        w_cmp=("w_cmp", "sum"), w_mic=("w_mic", "sum"), w_rec=("w_rec", "sum"),
    ).reset_index()
    v = a["vehiculos"]
    cl = pd.DataFrame({
        "territorio": a["territorio"],
        "log10_vehiculos": np.round(np.log10(v), 4),
        "pct_camioneta": np.round(100 * a["w_cam"] / v, 2),
        "pct_automovil": np.round(100 * a["w_aut"] / v, 2),
        "pct_campero": np.round(100 * a["w_cmp"] / v, 2),
        "pct_micromovilidad": np.round(100 * a["w_mic"] / v, 2),
        "pct_registro_2022_2024": np.round(100 * a["w_rec"] / v, 2),
        "anio_registro_medio": np.round(a["w_anio"] / v, 3),
        "antiguedad_media": np.round(a["w_antig"] / v, 3),
        "departamento": a["departamento"],
        "vehiculos": v,
        "grupos": a["grupos"],
    })
    tipos_c = {c: "c" for c in cl.columns}
    tipos_c.update({"territorio": "s", "departamento": "s"})
    roles_c = {"territorio": "meta", "departamento": "meta", "vehiculos": "meta", "grupos": "meta"}
    escribir_tab(cl, tipos_c, roles_c, SALIDA / "clustering_territorios.tab")

    resumen = {
        "fuente": "data/powerbi/hechos_vehiculos.csv + dim_territorio.csv (datos.gov.co ntxy-q9ix, 2015-2024, tratado en Etapa 2)",
        "base": {"grupos": total_grupos, "vehiculos": total_veh},
        "supervisado": {
            "archivo": "data/processed/etapa6/supervisado_tipo_motorizacion.tab",
            "variable_objetivo": "tipo_motorizacion (ELECTRICO | HIBRIDO)",
            "predictoras": pred,
            "excluida_hidrogeno": {"grupos": int(len(excl_h)), "vehiculos": int(excl_h["cantidad"].sum())},
            "grupos": int(len(sup)),
            "vehiculos": int(sup["cantidad"].sum()),
            "balance": {
                k: {
                    "grupos": int(g.loc[k, "grupos"]),
                    "pct_grupos": pct(g.loc[k, "grupos"], len(sup)),
                    "vehiculos": int(g.loc[k, "vehiculos"]),
                    "pct_vehiculos": pct(g.loc[k, "vehiculos"], sup["cantidad"].sum()),
                }
                for k in ("ELECTRICO", "HIBRIDO")
            },
            "vectores_predictores_unicos": int(len(vectores)),
            "vectores_con_ambas_clases": int((vectores > 1).sum()),
            "antiguedad_negativa_grupos": int((sup["antiguedad_modelo"] < 0).sum()),
        },
        "clustering": {
            "archivo": "data/processed/etapa6/clustering_territorios.tab",
            "min_vehiculos": MIN_VEHICULOS,
            "territorios_totales": int(len(por_terr)),
            "territorios_incluidos": int(len(cl)),
            "territorios_excluidos": int(len(por_terr) - len(cl)),
            "vehiculos_incluidos": int(cl["vehiculos"].sum()),
            "pct_vehiculos_incluidos": pct(cl["vehiculos"].sum(), total_veh),
            "variables": [c for c in cl.columns if c not in ("territorio", "departamento", "vehiculos", "grupos")],
            "agrupacion_micromovilidad": sorted(LIVIANOS_MICRO),
        },
    }
    (SALIDA / "resultados_etapa6_preparacion.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
