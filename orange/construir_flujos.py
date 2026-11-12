"""
Genera los flujos de trabajo de Orange Data Mining (.ows) de la Etapa 6.

Los .ows son XML; en lugar de dibujarlos a mano se generan con este script para que los
widgets, conexiones y parámetros queden documentados en código y se puedan reproducir.
Cada flujo se abre con Orange (File > Open, o doble clic al .ows). Las rutas de los datos son
RELATIVAS a la carpeta del flujo, así que funcionan en cualquier equipo que clone el repositorio.

Uso (con el Python de Orange):
    python orange/construir_flujos.py

Flujos:
    01_supervisado.ows        File -> Rank / Distributions -> Test and Score (3 modelos) -> Matriz de confusión / ROC
    02_clustering.ows         File -> k-Means (k óptimo por silueta) -> Scatter / Box Plot / Silhouette; Distances -> Hierarchical
    03_comentarios_youtube.ows  Corpus -> Preprocess Text -> Bag of Words -> Topic Modelling / Distances -> Hierarchical / Collocations
"""

import ast
import base64
import pickle
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from orangewidget.utils.filedialogs import RecentPath

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent


def nodo(clave, qualified_name, titulo, pos, settings=None, proyecto="Orange3"):
    nombre = qualified_name.rsplit(".", 1)[1]
    return {"clave": clave, "qn": qualified_name, "clase": nombre, "titulo": titulo, "pos": pos,
            "settings": settings, "proyecto": proyecto}


def enlace(origen, canal_origen, destino, canal_destino):
    return (origen, canal_origen, destino, canal_destino)


# (nombre del canal, id del canal) tomados de get_widget_description() de cada widget.
CANALES = {
    "File": {"out": {"data": "Data"}},
    "Table": {"in": {"data": "Data"}},
    "Distributions": {"in": {"data": "Data"}},
    "Rank": {"in": {"data": "Data"}},
    "Preprocess": {"out": {"preprocessor": "Preprocessor"}},
    "LR": {"in": {"data": "Data"}, "out": {"learner": "Learner"}},
    "Tree": {"in": {"data": "Data"}, "out": {"learner": "Learner", "model": "Model"}},
    "RF": {"in": {"data": "Data"}, "out": {"learner": "Learner"}},
    "TestAndScore": {"in": {"train_data": "Data", "learner": "Learner", "preprocessor": "Preprocessor"},
                     "out": {"evaluations_results": "Evaluation Results"}},
    "Confusion": {"in": {"evaluation_results": "Evaluation Results"}},
    "ROC": {"in": {"evaluation_results": "Evaluation Results"}},
    "TreeViewer": {"in": {"tree": "Tree"}},
    "KMeans": {"in": {"data": "Data"}, "out": {"annotated_data": "Data"}},
    "Scatter": {"in": {"data": "Data"}},
    "BoxPlot": {"in": {"data": "Data"}},
    "Silhouette": {"in": {"data": "Data"}},
    "Distances": {"in": {"data": "Data"}, "out": {"distances": "Distances"}},
    "Hier": {"in": {"distances": "Distances"}, "out": {"annotated_data": "Data"}},
    "Corpus": {"in": {"data": "Data"}, "out": {"corpus": "Corpus"}},
    "PreprocessText": {"in": {"corpus": "Corpus"}, "out": {"corpus": "Corpus"}},
    "BoW": {"in": {"corpus": "Corpus"}, "out": {"corpus": "Corpus"}},
    "Topic": {"in": {"corpus": "Corpus"}, "out": {"corpus": "Corpus"}},
    "Viewer": {"in": {"corpus": "Corpus"}},
    "Collocations": {"in": {"corpus": "Corpus"}, "out": {"corpus": "Table"}},
}


def serializar(props):
    """literal si es posible (como hace Orange); si no, pickle en base64."""
    texto = repr(props)
    try:
        if ast.literal_eval(texto) == props:
            return "literal", texto
    except (ValueError, SyntaxError):
        pass
    return "pickle", base64.encodebytes(pickle.dumps(props, protocol=4)).decode("ascii")


def escribir_flujo(ruta, titulo, descripcion, nodos, enlaces):
    ids = {n["clave"]: i for i, n in enumerate(nodos)}
    tipo = {n["clave"]: n["canal"] for n in nodos}
    xml = ["<?xml version='1.0' encoding='utf-8'?>",
           f"<scheme version=\"2.0\" title={quoteattr(titulo)} description={quoteattr(descripcion)}>", "\t<nodes>"]
    for n in nodos:
        xml.append(
            f"\t\t<node id=\"{ids[n['clave']]}\" name={quoteattr(n['nombre_widget'])} "
            f"qualified_name={quoteattr(n['qn'])} project_name={quoteattr(n['proyecto'])} version=\"\" "
            f"title={quoteattr(n['titulo'])} position=\"({n['pos'][0]}, {n['pos'][1]})\" />")
    xml.append("\t</nodes>")
    xml.append("\t<links>")
    for i, (o, co, d, cd) in enumerate(enlaces):
        nombre_o = CANALES[tipo[o]]["out"][co]
        nombre_d = CANALES[tipo[d]]["in"][cd]
        xml.append(
            f"\t\t<link id=\"{i}\" source_node_id=\"{ids[o]}\" sink_node_id=\"{ids[d]}\" "
            f"source_channel={quoteattr(nombre_o)} sink_channel={quoteattr(nombre_d)} enabled=\"true\" "
            f"source_channel_id={quoteattr(co)} sink_channel_id={quoteattr(cd)} />")
    xml.append("\t</links>")
    xml.append("\t<annotations />")
    xml.append("\t<thumbnail />")
    xml.append("\t<node_properties>")
    for n in nodos:
        if n["settings"] is not None:
            formato, texto = serializar(n["settings"])
            xml.append(f"\t\t<properties node_id=\"{ids[n['clave']]}\" format=\"{formato}\">{escape(texto)}</properties>")
    xml.append("\t</node_properties>")
    xml.append("\t<session_state>\n\t\t<window_groups />\n\t</session_state>")
    xml.append("</scheme>")
    Path(ruta).write_text("\n".join(xml) + "\n", encoding="utf-8")


def archivo(relativo):
    """Ajustes del widget File: ruta relativa a la carpeta del flujo (prefijo basedir)."""
    # La ruta absoluta es un marcador (no se publica la de este equipo): Orange resuelve por «basedir» + ruta relativa.
    absoluta = "C:/MINERIA_AJ/" + relativo
    rel = str(Path("..") / relativo).replace("\\", "/")
    return {"recent_paths": [RecentPath(absoluta, "basedir", rel)], "__version__": 1}


def armar(lista):
    """Completa cada nodo con su nombre de widget y la clave de canales."""
    nombres = {"File": "File", "Table": "Data Table", "Distributions": "Distributions", "Rank": "Rank",
               "Preprocess": "Preprocess", "LR": "Logistic Regression", "Tree": "Tree", "RF": "Random Forest",
               "TestAndScore": "Test and Score", "Confusion": "Confusion Matrix", "ROC": "ROC Analysis",
               "TreeViewer": "Tree Viewer", "KMeans": "k-Means", "Scatter": "Scatter Plot", "BoxPlot": "Box Plot",
               "Silhouette": "Silhouette Plot", "Distances": "Distances", "Hier": "Hierarchical Clustering",
               "Corpus": "Corpus", "PreprocessText": "Preprocess Text", "BoW": "Bag of Words",
               "Topic": "Topic Modelling", "Viewer": "Corpus Viewer", "Collocations": "Collocations"}
    for n in lista:
        n["canal"] = n["clave"].split("#")[0]
        n["nombre_widget"] = nombres[n["canal"]]
    return lista


# ----------------------------------------------------------------------------- 01 supervisado
def flujo_supervisado():
    nodos = armar([
        nodo("File", "Orange.widgets.data.owfile.OWFile", "Datos supervisados", (60, 200),
             archivo("data/processed/etapa6/supervisado_tipo_motorizacion.tab")),
        nodo("Table", "Orange.widgets.data.owtable.OWTable", "Tabla de datos", (240, 60)),
        nodo("Distributions", "Orange.widgets.visualize.owdistributions.OWDistributions", "Distribución de la clase", (240, 130)),
        nodo("Rank", "Orange.widgets.data.owrank.OWRank", "Relevancia de variables", (240, 200)),
        nodo("Preprocess", "Orange.widgets.data.owpreprocess.OWPreprocess", "Estandarizar numéricas", (400, 320),
             {"storedsettings": {"name": "", "preprocessors": [("orange.preprocess.scale", {"method": 2})]},
              "__version__": 2}),
        nodo("LR", "Orange.widgets.model.owlogisticregression.OWLogisticRegression", "Regresión logística", (400, 400),
             {"learner_name": "Regresión logística", "penalty_type": 1, "C_index": 61, "class_weight": False,
              "__version__": 2}),
        nodo("Tree", "Orange.widgets.model.owtree.OWTreeLearner", "Árbol de decisión", (400, 480),
             {"learner_name": "Árbol de decisión", "binary_trees": False, "limit_min_leaf": True, "min_leaf": 2,
              "limit_min_internal": True, "min_internal": 5, "limit_depth": True, "max_depth": 100,
              "limit_majority": True, "sufficient_majority": 95, "__version__": 1}),
        nodo("RF", "Orange.widgets.model.owrandomforest.OWRandomForest", "Random Forest", (400, 560),
             {"learner_name": "Random Forest", "n_estimators": 100, "use_random_state": True,
              "use_min_samples_split": True, "min_samples_split": 5, "use_max_features": False,
              "use_max_depth": False, "class_weight": False, "__version__": 1}),
        nodo("TestAndScore", "Orange.widgets.evaluate.owtestandscore.OWTestAndScore", "Validación cruzada 10 pliegues", (620, 400),
             {"resampling": 0, "n_folds": 3, "cv_stratified": True, "n_repeats": 3, "sample_size": 9,
              "shuffle_stratified": True, "use_rope": False, "rope": 0.1, "__version__": 4}),
        nodo("Confusion", "Orange.widgets.evaluate.owconfusionmatrix.OWConfusionMatrix", "Matriz de confusión", (820, 340)),
        nodo("ROC", "Orange.widgets.evaluate.owrocanalysis.OWROCAnalysis", "Curvas ROC", (820, 460)),
        nodo("TreeViewer", "Orange.widgets.visualize.owtreeviewer.OWTreeGraph", "Visor del árbol", (620, 540)),
    ])
    enlaces = [
        enlace("File", "data", "Table", "data"),
        enlace("File", "data", "Distributions", "data"),
        enlace("File", "data", "Rank", "data"),
        enlace("File", "data", "TestAndScore", "train_data"),
        enlace("File", "data", "Tree", "data"),
        enlace("Preprocess", "preprocessor", "TestAndScore", "preprocessor"),
        enlace("LR", "learner", "TestAndScore", "learner"),
        enlace("Tree", "learner", "TestAndScore", "learner"),
        enlace("RF", "learner", "TestAndScore", "learner"),
        enlace("TestAndScore", "evaluations_results", "Confusion", "evaluation_results"),
        enlace("TestAndScore", "evaluations_results", "ROC", "evaluation_results"),
        enlace("Tree", "model", "TreeViewer", "tree"),
    ]
    escribir_flujo(CARPETA / "01_supervisado.ows", "Etapa 6 · Supervisado: ¿eléctrico o híbrido?",
                   "Tres modelos (regresión logística, árbol, random forest) con la misma validación cruzada estratificada de 10 pliegues. "
                   "En Test and Score elegir «Target class: ELECTRICO». Réplica por código: etapa6_modelos.py.",
                   nodos, enlaces)


# ----------------------------------------------------------------------------- 02 clustering
def flujo_clustering():
    nodos = armar([
        nodo("File", "Orange.widgets.data.owfile.OWFile", "Territorios (variables sin combustible)", (60, 220),
             archivo("data/processed/etapa6/clustering_territorios.tab")),
        nodo("Table", "Orange.widgets.data.owtable.OWTable", "Tabla de datos", (240, 60)),
        nodo("KMeans#opt", "Orange.widgets.unsupervised.owkmeans.OWKMeans", "Comparar k = 2 a 8 (silueta)", (260, 120),
             {"k": 3, "k_from": 2, "k_to": 8, "optimize_k": True, "max_iterations": 300, "n_init": 10,
              "smart_init": 0, "normalize": True, "auto_commit": True, "__version__": 2}),
        nodo("KMeans#3", "Orange.widgets.unsupervised.owkmeans.OWKMeans", "k-Means con k = 3 (elegido)", (260, 260),
             {"k": 3, "k_from": 2, "k_to": 8, "optimize_k": False, "max_iterations": 300, "n_init": 10,
              "smart_init": 0, "normalize": True, "auto_commit": True, "__version__": 2}),
        nodo("Scatter", "Orange.widgets.visualize.owscatterplot.OWScatterPlot", "Dispersión por grupo", (480, 120)),
        nodo("BoxPlot", "Orange.widgets.visualize.owboxplot.OWBoxPlot", "Variables por grupo", (480, 220)),
        nodo("Silhouette", "Orange.widgets.visualize.owsilhouetteplot.OWSilhouettePlot", "Silueta por territorio", (480, 320)),
        nodo("Distances", "Orange.widgets.unsupervised.owdistances.OWDistances", "Distancias (euclídea normalizada)", (260, 420)),
        nodo("Hier", "Orange.widgets.unsupervised.owhierarchicalclustering.OWHierarchicalClustering",
             "Jerárquico (Ward): comprobación", (480, 420), {"linkage": "ward_placeholder"}),
    ])
    # El índice de «Ward» sale de la propia lista de Orange para no depender de un número fijo.
    from Orange.widgets.unsupervised.owhierarchicalclustering import LINKAGE
    indice_ward = [i for i, nombre in enumerate(LINKAGE) if str(nombre).lower().startswith("ward")][0]
    nodos[-1]["settings"] = {"linkage": indice_ward, "__version__": 1}
    enlaces = [
        enlace("File", "data", "Table", "data"),
        enlace("File", "data", "KMeans#opt", "data"),
        enlace("File", "data", "KMeans#3", "data"),
        enlace("KMeans#3", "annotated_data", "Scatter", "data"),
        enlace("KMeans#3", "annotated_data", "BoxPlot", "data"),
        enlace("KMeans#3", "annotated_data", "Silhouette", "data"),
        enlace("File", "data", "Distances", "data"),
        enlace("Distances", "distances", "Hier", "distances"),
    ]
    escribir_flujo(CARPETA / "02_clustering.ows", "Etapa 6 · Clustering de territorios",
                   "k-Means con normalización sobre 8 variables de perfil de clases y antigüedad. Un widget compara k = 2 a 8 por silueta "
                   "y otro fija k = 3 (elegido; ver criterio en la documentación). No usa combustible. Réplica: etapa6_clustering.py.",
                   nodos, enlaces)


# ----------------------------------------------------------------------------- 03 comentarios
def flujo_comentarios():
    # Lista de stopwords transformada como el texto (ver etapa6_stopwords.py): el widget filtra DESPUÉS del stemmer.
    sw = RecentPath("C:/MINERIA_AJ/etapa6_stopwords_es.txt", "basedir", "../etapa6_stopwords_es.txt")
    nodos = armar([
        nodo("Corpus", "orangecontrib.text.widgets.owcorpus.OWCorpus", "Comentarios limpios (cargar comentarios_limpios.tab)",
             (60, 220), None, proyecto="Orange3-Text"),
        nodo("PreprocessText", "orangecontrib.text.widgets.owpreprocess.OWPreprocess", "Preprocesar texto (español)", (260, 220),
             {"storedsettings": {"preprocessors": [
                 ("preprocess.transform", {"methods": [0, 1, 3]}),
                 ("preprocess.tokenize", {"method": 3, "pattern": r"\w+"}),
                 ("preprocess.normalize", {"method": 1, "snowball_language": "es"}),
                 ("preprocess.filter", {"methods": [0, 2, 4], "language": None, "sw_path": sw, "sw_list": [sw],
                                        "freq_type": 1, "abs_start": 3, "abs_end": 1000000}),
             ]}, "__version__": 4}, proyecto="Orange3-Text"),
        nodo("BoW", "orangecontrib.text.widgets.owbagofwords.OWTBagOfWords", "Bolsa de palabras (TF-IDF)", (460, 220),
             {"wlocal": "Count", "wglobal": "IDF", "normalization": "L2 (Euclidean)", "__version__": 1},
             proyecto="Orange3-Text"),
        nodo("Topic", "orangecontrib.text.widgets.owtopicmodeling.OWTopicModeling", "Temas (LDA)", (660, 120),
             {"method_index": 1, "__version__": 1}, proyecto="Orange3-Text"),
        nodo("Viewer", "orangecontrib.text.widgets.owcorpusviewer.OWCorpusViewer", "Visor de comentarios", (860, 120),
             None, proyecto="Orange3-Text"),
        nodo("Distances", "Orange.widgets.unsupervised.owdistances.OWDistances", "Distancias coseno", (660, 260)),
        nodo("Hier", "Orange.widgets.unsupervised.owhierarchicalclustering.OWHierarchicalClustering",
             "Agrupación jerárquica de comentarios", (860, 260)),
        nodo("Collocations", "orangecontrib.text.widgets.owcollocations.OWCollocations", "Colocaciones (bigramas)", (460, 380),
             None, proyecto="Orange3-Text"),
    ])
    enlaces = [
        enlace("Corpus", "corpus", "PreprocessText", "corpus"),
        enlace("PreprocessText", "corpus", "BoW", "corpus"),
        enlace("PreprocessText", "corpus", "Collocations", "corpus"),
        enlace("BoW", "corpus", "Topic", "corpus"),
        enlace("Topic", "corpus", "Viewer", "corpus"),
        enlace("BoW", "corpus", "Distances", "data"),
        enlace("Distances", "distances", "Hier", "distances"),
    ]
    escribir_flujo(CARPETA / "03_comentarios_youtube.ows", "Etapa 6 · Comentarios de YouTube",
                   "Corpus en español: minúsculas, sin tildes ni URL, tokens \\w+, stemmer Snowball español, stopwords en español (archivo etapa6_stopwords_es.txt), "
                   "documentos con >= 3 apariciones; TF-IDF; LDA, agrupación jerárquica y colocaciones. Réplica: etapa6_youtube_analisis.py.",
                   nodos, enlaces)


if __name__ == "__main__":
    flujo_supervisado()
    flujo_clustering()
    flujo_comentarios()
    print("Flujos escritos en", CARPETA)
