"""
Etapa 6 · Aprendizaje supervisado: réplica por código del flujo de Orange (orange/01_supervisado.ows).

Pregunta de predicción: dado un grupo de vehículos matriculados (clase, carrocería, departamento,
año de registro, año del modelo y antigüedad al registrar), ¿es eléctrico (BEV) o híbrido?
  - Variable objetivo: tipo_motorizacion (ELECTRICO | HIBRIDO)  -> CLASIFICACIÓN binaria.
  - Clase positiva para precisión/recall/F1: ELECTRICO.
  - `cantidad` NO es predictora: no existe al predecir y es el peso del grupo (meta).

Usa la librería Orange con los MISMOS parámetros por defecto de los widgets (Test and Score:
validación cruzada estratificada de 10 pliegues, semilla 42) para que el flujo gráfico y este
script den los mismos números. Resultados -> data/processed/etapa6/resultados_etapa6_supervisado.json

Además de las métricas por grupo (lo que muestra Test and Score de Orange) calcula las métricas
PONDERADAS por `cantidad` (por vehículo), porque el dataset es agregado y un grupo de 8.071
camionetas pesa mucho más que un grupo de 1 ciclomotor.

Uso (con el Python de Orange o un entorno con Orange3 instalado):
    pip install -r requirements-etapa6.txt
    python etapa6_preparar_datos.py
    python etapa6_modelos.py
"""

import json
import sys
from pathlib import Path

import numpy as np
from Orange.classification import LogisticRegressionLearner, RandomForestLearner, TreeLearner
from Orange.data import Table
from Orange.evaluation import AUC, CrossValidation
from Orange.preprocess import Normalize
from Orange.preprocess.score import GainRatio, Gini, InfoGain, ReliefF
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score

RAIZ = Path(__file__).resolve().parent
CARPETA = RAIZ / "data" / "processed" / "etapa6"
ENTRADA = CARPETA / "supervisado_tipo_motorizacion.tab"
SALIDA = CARPETA / "resultados_etapa6_supervisado.json"

SEMILLA = 42          # la misma que usa Test and Score en Orange
PLIEGUES = 10
POSITIVA = "ELECTRICO"


def metricas(y, pred, prob_pos, w=None):
    """Accuracy, precisión, recall, F1 (clase positiva = ELECTRICO) y AUC; w = peso por grupo."""
    exact = float(np.average(y == pred, weights=w))
    p, r, f, _ = precision_recall_fscore_support(y, pred, labels=[1], average=None, sample_weight=w, zero_division=0)
    return {
        "accuracy": round(exact, 4),
        "precision": round(float(p[0]), 4),
        "recall": round(float(r[0]), 4),
        "f1": round(float(f[0]), 4),
        "auc": round(float(roc_auc_score(y, prob_pos, sample_weight=w)), 4),
    }


def matriz(y, pred, w=None):
    """[[VN, FP], [FN, VP]] con la clase positiva (ELECTRICO) en la segunda fila/columna."""
    m = confusion_matrix(y, pred, labels=[0, 1], sample_weight=w)
    return [[int(round(x)) for x in fila] for fila in m]


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows (cp1252) no imprime μ, é, etc.
    datos = Table(str(ENTRADA))
    dom = datos.domain
    valores = list(dom.class_var.values)
    pos = valores.index(POSITIVA)
    y = (datos.Y == pos).astype(int)
    cantidad = datos.metas[:, [m.name for m in dom.metas].index("cantidad")].astype(float)

    # --- Selección de variables (widget Rank): puntajes de relevancia respecto a la clase.
    ranking = {}
    for nombre, score in (("Ganancia de información", InfoGain()), ("Razón de ganancia", GainRatio()),
                          ("Gini", Gini()), ("ReliefF", ReliefF(n_iterations=100, k_nearest=10))):
        ranking[nombre] = {a.name: round(float(score(datos, a)), 4) for a in dom.attributes}

    # --- Tres modelos con los parámetros por defecto del widget (salvo árboles del bosque y semilla).
    aprendices = {
        "Regresión logística": LogisticRegressionLearner(penalty="l2", C=1.0),
        "Árbol de decisión": TreeLearner(binarize=False, min_samples_leaf=2, min_samples_split=5,
                                         max_depth=100, sufficient_majority=0.95),
        "Random Forest": RandomForestLearner(n_estimators=100, min_samples_split=5, random_state=0),
    }
    prep = Normalize(norm_type=Normalize.NormalizeBySD)  # widget Preprocess: estandarizar numéricas (μ=0, σ=1)
    res = CrossValidation(k=PLIEGUES, stratified=True, random_state=SEMILLA)(
        datos, list(aprendices.values()), preprocessor=prep)
    assert not np.isnan(res.predicted).any(), "algún modelo falló en algún pliegue"
    actual = (res.actual.astype(int) == pos).astype(int)  # 1 = ELECTRICO (clase positiva)
    orden = res.row_indices  # fila original de cada predicción

    # Subconjunto «difícil»: clases donde conviven eléctricos e híbridos (la clase del vehículo
    # casi determina el combustible en el resto).
    clase_col = datos.get_column("clase")
    nombres_clase = dom["clase"].values
    mixtas = {nombres_clase.index(c) for c in ("AUTOMOVIL", "CAMIONETA")}
    es_dificil = np.isin(clase_col[orden].astype(int), list(mixtas))

    salida = {"parametros": {}, "ranking_variables": ranking, "modelos": {}}
    salida["parametros"] = {
        "validacion": f"validación cruzada estratificada de {PLIEGUES} pliegues, semilla {SEMILLA}",
        "clase_positiva": POSITIVA,
        "regresion_logistica": "penalización L2 (Ridge), C = 1; variables numéricas estandarizadas con Preprocess y categóricas en one-hot (automático)",
        "arbol": "divisiones multivía (sin binarizar: carrocería y departamento tienen más de 16 valores), mín. 2 instancias por hoja, no dividir subconjuntos < 5, profundidad máx. 100, mayoría suficiente 95 %",
        "random_forest": "100 árboles, no dividir subconjuntos < 5, semilla fija",
    }
    for i, nombre in enumerate(aprendices):
        pred = (res.predicted[i].astype(int) == pos).astype(int)
        prob = res.probabilities[i][:, pos]
        w = cantidad[orden]
        salida["modelos"][nombre] = {
            "por_grupo": {**metricas(actual, pred, prob), "auc": round(float(AUC(res)[i]), 4)},  # AUC como Test and Score
            "por_vehiculo": metricas(actual, pred, prob, w),
            "matriz_por_grupo": matriz(actual, pred),
            "matriz_por_vehiculo": matriz(actual, pred, w),
            # ¿Dónde se equivoca? Grupos grandes (cantidad > 16, umbral de la Etapa 2) frente al resto.
            "por_tamano_de_grupo": {
                nombre_t: {
                    "grupos": int(m_t.sum()),
                    "vehiculos": int(w[m_t].sum()),
                    "accuracy_por_grupo": round(float(np.mean(actual[m_t] == pred[m_t])), 4),
                }
                for nombre_t, m_t in (("grandes_cantidad_mayor_16", w > 16), ("pequenos_cantidad_hasta_16", w <= 16))
            },
            "subconjunto_automovil_camioneta": {
                "grupos": int(es_dificil.sum()),
                "por_grupo": metricas(actual[es_dificil], pred[es_dificil], prob[es_dificil]),
                "por_vehiculo": metricas(actual[es_dificil], pred[es_dificil], prob[es_dificil], w[es_dificil]),
            },
        }

    # Línea base: predecir siempre la clase mayoritaria (por grupo y por vehículo).
    w = cantidad
    base_grupo = max(y.mean(), 1 - y.mean())
    base_veh = max(np.average(y, weights=w), 1 - np.average(y, weights=w))
    salida["linea_base"] = {
        "accuracy_por_grupo": round(float(base_grupo), 4),
        "accuracy_por_vehiculo": round(float(base_veh), 4),
        "descripcion": "predecir siempre la clase mayoritaria",
    }

    # --- Modelo interpretable: árbol entrenado con todos los datos (solo para leer reglas).
    arbol = aprendices["Árbol de decisión"](datos)
    salida["arbol_completo"] = {
        "nodos": int(arbol.node_count()),
        "hojas": int(arbol.leaf_count()),
        "profundidad": int(arbol.depth()),
    }

    # Composición por clase de vehículo (apoya la lectura del modelo: qué clases son «fáciles»).
    cuenta = {}
    for c_idx, c_nombre in enumerate(nombres_clase):
        m = clase_col.astype(int) == c_idx
        if m.sum() == 0:
            continue
        cuenta[c_nombre] = {
            "grupos": int(m.sum()),
            "vehiculos": int(cantidad[m].sum()),
            "pct_electricos_grupos": round(float(100 * y[m].mean()), 2),
            "pct_electricos_vehiculos": round(float(100 * np.average(y[m], weights=cantidad[m])), 2),
        }
    # ¿Qué parte de los vehículos eléctricos es micromovilidad (ciclomotores, cuadriciclos, motos…)?
    micro = {"CICLOMOTOR", "CUADRICICLO", "MOTOCICLETA", "MOTOCARRO", "TRICIMOTO", "MOTOTRICICLO", "CUATRIMOTO"}
    clase_txt = np.array(nombres_clase)[clase_col.astype(int)]
    es_micro = np.isin(clase_txt, list(micro))
    bev_total = float(cantidad[y == 1].sum())
    bev_micro = float(cantidad[(y == 1) & es_micro].sum())
    salida["electricos_micromovilidad"] = {
        "clases": sorted(micro),
        "vehiculos_electricos": int(bev_total),
        "vehiculos_electricos_micromovilidad": int(bev_micro),
        "pct_de_los_electricos": round(100 * bev_micro / bev_total, 2),
        "pct_de_todos_los_vehiculos": round(100 * float(cantidad[es_micro].sum()) / float(cantidad.sum()), 2),
    }
    salida["composicion_por_clase"] = dict(sorted(cuenta.items(), key=lambda kv: -kv[1]["grupos"]))

    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(salida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
