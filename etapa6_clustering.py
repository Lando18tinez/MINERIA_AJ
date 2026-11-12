"""
Etapa 6 · Aprendizaje no supervisado: réplica por código del flujo de Orange (orange/02_clustering.ows).

Pregunta: ¿qué perfiles de territorio (municipio + departamento) existen según la composición de
clases de vehículos, la antigüedad del parque registrado y su tamaño?

  - Unidad: territorio con >= 30 vehículos (ver etapa6_preparar_datos.py).
  - Variables: log10 de vehículos, % camioneta, % automóvil, % campero, % micromovilidad,
    % registrado en 2022-2024, año de registro medio y antigüedad media (modelo vs registro).
  - NO se usa combustible ni tipo_motorizacion (variable objetivo del ejercicio supervisado)
    para formar los grupos. Solo se usa DESPUÉS, como variable ilustrativa para describirlos.
  - Normalización: sí (estandarización μ=0, σ=1, igual que «Normalize columns» de k-Means en Orange),
    porque las variables están en escalas distintas (porcentajes 0-100, años ~2020, log ~2-5) y
    k-Means usa distancia euclídea: sin normalizar dominarían las de mayor escala.
  - Algoritmo: k-Means (k-means++, 10 inicializaciones, 300 iteraciones, semilla 0).
  - Elección de k: silueta media para k = 2..8; se elige el mejor k con k >= 3 si la silueta
    del k = 2 solo separa un grupo muy pequeño (criterio documentado en el resultado).

Resultados -> data/processed/etapa6/resultados_etapa6_clustering.json y
              data/processed/etapa6/clustering_territorios_grupos.tab (con el grupo asignado)

Uso (Python de Orange o entorno con Orange3):
    python etapa6_preparar_datos.py
    python etapa6_clustering.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from Orange.clustering import KMeans
from Orange.data import Table
from Orange.preprocess import Normalize
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, silhouette_samples, silhouette_score

RAIZ = Path(__file__).resolve().parent
CARPETA = RAIZ / "data" / "processed" / "etapa6"
ENTRADA = CARPETA / "clustering_territorios.tab"
HECHOS = RAIZ / "data" / "powerbi" / "hechos_vehiculos.csv"
TERRITORIO = RAIZ / "data" / "powerbi" / "dim_territorio.csv"
SALIDA = CARPETA / "resultados_etapa6_clustering.json"

SEMILLA = 0  # la misma que usa el widget k-Means de Orange
K_MIN, K_MAX = 2, 8
VARIABLES = ["log10_vehiculos", "pct_camioneta", "pct_automovil", "pct_campero", "pct_micromovilidad",
             "pct_registro_2022_2024", "anio_registro_medio", "antiguedad_media"]


def ajustar(datos, k):
    """k-Means de Orange sobre los datos normalizados; devuelve etiquetas, silueta y inercia."""
    modelo = KMeans(n_clusters=k, init="k-means++", n_init=10, max_iter=300, random_state=SEMILLA, preprocessors=[]).get_model(datos)
    etiquetas = np.asarray(modelo.labels)
    return etiquetas, float(silhouette_score(datos.X, etiquetas)), float(((datos.X - np.asarray(modelo.centroids)[etiquetas]) ** 2).sum())


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows (cp1252) no imprime μ, é, etc.
    crudo = Table(str(ENTRADA))
    datos = Normalize()(crudo)  # estandarización (μ=0, σ=1), como la casilla «Normalize columns» del widget
    nombres = [a.name for a in crudo.domain.attributes]
    assert nombres == VARIABLES, nombres
    meta_nombres = [m.name for m in crudo.domain.metas]
    metas = pd.DataFrame(crudo.metas, columns=meta_nombres)
    metas["vehiculos"] = metas["vehiculos"].astype(float).astype(int)
    metas["grupos"] = metas["grupos"].astype(float).astype(int)
    df = pd.DataFrame(crudo.X, columns=nombres)
    df["territorio"] = metas["territorio"].values
    df["departamento"] = metas["departamento"].values
    df["vehiculos"] = metas["vehiculos"].values

    # --- Comparación de alternativas: silueta y suma de cuadrados intra-grupo para cada k.
    comparacion = []
    ajustes = {}
    for k in range(K_MIN, K_MAX + 1):
        et, sil, inercia = ajustar(datos, k)
        ajustes[k] = et
        tamanos = np.bincount(et, minlength=k)
        comparacion.append({
            "k": k, "silueta": round(sil, 4), "inercia": round(inercia, 2),
            "tamanos": [int(x) for x in tamanos], "grupo_mas_pequeno": int(tamanos.min()),
        })

    # Criterio de elección: mayor silueta entre los k cuyo grupo más pequeño tiene >= 5 territorios
    # (un grupo de 1-4 territorios no es un perfil sino un caso atípico) y k >= 3.
    candidatos = [c for c in comparacion if c["k"] >= 3 and c["grupo_mas_pequeno"] >= 5]
    elegido = max(candidatos, key=lambda c: c["silueta"])
    k = elegido["k"]
    et = ajustes[k]

    # --- Ordena los grupos por tamaño de parque (grupo 1 = el de más vehículos totales) y perfila.
    df["grupo_bruto"] = et
    orden = df.groupby("grupo_bruto")["vehiculos"].sum().sort_values(ascending=False).index.tolist()
    mapa = {g: i + 1 for i, g in enumerate(orden)}
    df["grupo"] = df["grupo_bruto"].map(mapa)
    sil_i = silhouette_samples(datos.X, et)
    df["silueta"] = sil_i

    # Variable ilustrativa (NO usada para formar los grupos): % de vehículos eléctricos por grupo.
    h = pd.read_csv(HECHOS, encoding="utf-8-sig").merge(pd.read_csv(TERRITORIO, encoding="utf-8-sig"), on="territorio")
    h = h.merge(df[["territorio", "grupo"]], on="territorio")
    h["bev"] = h["cantidad"] * (h["combustible"] == "ELECTRICO")
    ilus = h.groupby("grupo").agg(veh=("cantidad", "sum"), bev=("bev", "sum"))
    ilus["pct_electricos"] = (100 * ilus["bev"] / ilus["veh"]).round(2)

    media_global = df[VARIABLES].mean()
    sd_global = df[VARIABLES].std(ddof=0)
    total_veh = int(df["vehiculos"].sum())
    perfiles = []
    for g in sorted(df["grupo"].unique()):
        sub = df[df["grupo"] == g]
        z = ((sub[VARIABLES].mean() - media_global) / sd_global).round(2)
        distintivas = z.abs().sort_values(ascending=False).index[:3].tolist()
        top_terr = sub.sort_values("vehiculos", ascending=False).head(5)
        deptos = sub.groupby("departamento")["vehiculos"].sum().sort_values(ascending=False).head(3)
        perfiles.append({
            "grupo": int(g),
            "territorios": int(len(sub)),
            "vehiculos": int(sub["vehiculos"].sum()),
            "pct_vehiculos": round(100 * sub["vehiculos"].sum() / total_veh, 2),
            "promedio_variables": {v: round(float(sub[v].mean()), 2) for v in VARIABLES},
            "z_vs_global": {v: float(z[v]) for v in VARIABLES},
            "variables_distintivas": distintivas,
            "silueta_media": round(float(sub["silueta"].mean()), 3),
            "territorios_principales": [f"{r.territorio} ({int(r.vehiculos):,} veh.)".replace(",", ".") for r in top_terr.itertuples()],
            "departamentos_principales": [f"{d} ({int(v):,})".replace(",", ".") for d, v in deptos.items()],
            "pct_electricos_ilustrativo": float(ilus.loc[g, "pct_electricos"]),
        })

    # --- Robustez: ¿otro algoritmo (Ward jerárquico) agrupa parecido?
    ward = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(datos.X)
    ari = float(adjusted_rand_score(et, ward))

    resultado = {
        "algoritmo": "k-Means (Orange): k-means++, 10 inicializaciones, 300 iteraciones máx., semilla 0",
        "normalizacion": "estandarización μ=0, σ=1 de las 8 variables (Normalize columns)",
        "variables": VARIABLES,
        "excluidas_a_proposito": ["combustible", "tipo_motorizacion"],
        "territorios": int(len(df)),
        "vehiculos": total_veh,
        "comparacion_k": comparacion,
        "criterio_k": "mayor silueta entre k >= 3 cuyo grupo más pequeño tenga >= 5 territorios",
        "k_elegido": k,
        "silueta_elegida": elegido["silueta"],
        "silueta_k2": next(c["silueta"] for c in comparacion if c["k"] == 2),
        "perfiles": perfiles,
        "robustez_ward_ari": round(ari, 3),
    }
    SALIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    # .tab con el grupo asignado (útil para cargar en Orange: Scatter Plot, Box Plot, Data Table).
    out = df[["territorio", "departamento", "vehiculos"] + VARIABLES + ["grupo", "silueta"]].copy()
    out["grupo"] = "G" + out["grupo"].astype(str)
    out["silueta"] = out["silueta"].round(4)
    cols = VARIABLES + ["grupo", "territorio", "departamento", "vehiculos", "silueta"]
    out = out[cols]
    tipos = {c: "c" for c in VARIABLES}
    tipos.update({"grupo": "d", "territorio": "s", "departamento": "s", "vehiculos": "c", "silueta": "c"})
    roles = {"grupo": "class", "territorio": "meta", "departamento": "meta", "vehiculos": "meta", "silueta": "meta"}
    with open(CARPETA / "clustering_territorios_grupos.tab", "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(cols) + "\n")
        f.write("\t".join(tipos[c] for c in cols) + "\n")
        f.write("\t".join(roles.get(c, "") for c in cols) + "\n")
        for fila in out.itertuples(index=False):
            f.write("\t".join(str(v) for v in fila) + "\n")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
