"""
Etapa 6 · Análisis de texto de los comentarios de YouTube: réplica por código del flujo
orange/03_comentarios_youtube.ows (Orange3-Text).

Entrada : data/processed/etapa6/comentarios_limpios.tab   (etapa6_youtube_limpieza.py)
Salida  : data/processed/etapa6/resultados_youtube_analisis.json

Procesamiento (mismos pasos y orden que el widget «Preprocess Text»):
    transformar  -> minúsculas, quitar tildes, quitar URL
    tokenizar    -> expresión regular \\w+
    normalizar   -> stemmer Snowball en español
    filtrar      -> stopwords en español (NLTK + lista propia, transformadas como el texto: etapa6_stopwords.py),
                    números, términos que aparecen en menos de MIN_DOCS comentarios

Análisis
    1. Términos relevantes: frecuencia documental y TF-IDF (palabra visible = la forma más usada de cada raíz).
    2. Colocaciones: bigramas frecuentes (qué palabras van juntas).
    3. Temas con LDA (gensim, el mismo modelo del widget Topic Modelling): k de 3 a 8 comparado con
       coherencia c_v; se reporta cada tema con sus palabras, su peso y comentarios representativos.
    4. Categorías de interés definidas ANTES de mirar los datos (precio, carga, autonomía/batería,
       incentivos, mantenimiento, ambiente, desconfianza, marcas, micromovilidad…): proporción de comentarios
       que las mencionan y ejemplos. Es codificación por diccionario: aproximada y auditable, no «verdad».

Privacidad: no hay datos de autores en la entrada; los ejemplos se recortan a 160 caracteres.

Uso (Python de Orange):
    python etapa6_youtube_analisis.py
    python etapa6_youtube_analisis.py --entrada otra.tab --salida otra_carpeta
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
from gensim.corpora import Dictionary
from gensim.models import CoherenceModel, LdaModel
from nltk.stem import SnowballStemmer as NltkSnowball
from orangecontrib.text import Corpus
from orangecontrib.text.preprocess import (
    FrequencyFilter, LowercaseTransformer, NumbersFilter, RegexpTokenizer, SnowballStemmer,
    StopwordsFilter, StripAccentsTransformer, UrlRemover,
)

RAIZ = Path(__file__).resolve().parent
ENTRADA = RAIZ / "data" / "processed" / "etapa6" / "comentarios_limpios.tab"
SALIDA = RAIZ / "data" / "processed" / "etapa6"
STOPWORDS_RAICES = RAIZ / "etapa6_stopwords_es.txt"            # generada por etapa6_stopwords.py (para el filtro tras el stemmer)
STOPWORDS_PALABRAS = RAIZ / "etapa6_stopwords_es_palabras.txt"  # palabras sin tildes (para los bigramas, sin stemmer)

MIN_DOCS = 3                 # un término debe aparecer en al menos 3 comentarios
K_MIN, K_MAX = 3, 8
SEMILLA = 0
RECORTE = 160                # caracteres máximos de un ejemplo citado

# Categorías definidas a priori (texto en minúsculas y sin tildes). Cada una es una hipótesis de lectura.
CATEGORIAS = {
    "precio_costo": r"\bprecio|\bcost[oa]|\bcaro\b|\bcara\b|\bbarat|\bcuest|millon|\bplata\b|financ|credito|\bpesos\b|valor",
    "carga_infraestructura": r"carga\b|cargar|cargad|cargador|electrolinera|estacion(es)? de carga|enchuf|wallbox|punto(s)? de carga|infraestructura",
    "autonomia_bateria": r"autonomi|bateri|kilometr|\bkm\b|\brango\b|vida util|degrad|\bkwh\b",
    "incentivos_impuestos": r"incentiv|impuest|arancel|\biva\b|exenci|pico y placa|\bsoat\b|descuento|beneficio|subsidi|exoner",
    "mantenimiento_repuestos": r"mantenimiento|repuesto|taller|garantia|servicio tecnico|reparar|reparacion",
    "ambiente": r"ambient|contamin|\bco2\b|emision|ecolog|sostenib|limpi[oa]|planeta|litio|reciclaj|verde",
    "desconfianza_problemas": r"\bfalla|problema|peligro|incendi|riesgo|estafa|mentira|no sirve|no funciona|desventaja|inconveniente",
    "hibrido_mencion": r"hibrid|\bphev\b|\bhev\b|enchufable|rango extendido|mild",
    "electrico_mencion": r"electric|\bbev\b|\bev\b",
    "marcas_modelos": r"\bbyd\b|tesla|renault|\bkia\b|toyota|chevrolet|\bbmw\b|mercedes|nissan|hyundai|mazda|volvo|\bjac\b|zeekr|"
                       r"\bmg\b|ford|volkswagen|audi|\bgeely\b|\bchery\b|\bleapmotor\b|\bnio\b|\bxpeng\b|\bdongfeng\b|\bhonda\b",
    "micromovilidad": r"\bmoto\b|\bmotos\b|scooter|bicicleta|patineta|ciclomotor|motocicleta|\bbici\b",
    "territorio_ciudad": r"bogota|medellin|\bcali\b|barranquilla|bucaramanga|cartagena|\bciudad|pueblo|vereda|rural|carretera|viaje|"
                          r"altura|clima|calor|\bregion",
    "gasolina_comparacion": r"gasolina|combusti|diesel|petroleo|\bgalon|tanquear|tanqueo",
}


def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def recortar(t):
    t = " ".join(t.split())
    return t if len(t) <= RECORTE else t[: RECORTE - 1].rstrip() + "…"


def preprocesar(corpus):
    """Mismos pasos que el widget Preprocess Text; devuelve el corpus con .tokens."""
    corpus.attributes["language"] = "es"
    for pp in (LowercaseTransformer(), StripAccentsTransformer(), UrlRemover(), RegexpTokenizer(r"\w+"),
               SnowballStemmer("es"),
               StopwordsFilter(None, str(STOPWORDS_RAICES)),
               NumbersFilter(), FrequencyFilter(min_df=MIN_DOCS)):
        corpus = pp(corpus)
    return corpus


def formas_visibles(textos):
    """Para cada raíz (stem) devuelve la palabra completa más usada, para mostrar términos legibles."""
    stem = NltkSnowball("spanish")
    cuentas = {}
    for t in textos:
        for w in re.findall(r"\w+", sin_tildes(t.lower())):
            cuentas.setdefault(stem.stem(w), Counter())[w] += 1
    return {s: c.most_common(1)[0][0] for s, c in cuentas.items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Análisis de texto de comentarios")
    ap.add_argument("--entrada", default=str(ENTRADA))
    ap.add_argument("--salida", default=str(SALIDA))
    args = ap.parse_args()
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)

    corpus = Corpus.from_file(args.entrada)
    textos = [str(d) for d in corpus.documents]
    me_gusta = corpus.get_column("me_gusta").astype(float) if "me_gusta" in [v.name for v in corpus.domain.attributes] else np.zeros(len(textos))
    n = len(textos)
    visible = formas_visibles(textos)
    tok = preprocesar(corpus.copy()).tokens
    vocab = Dictionary(tok)
    bolsa = [vocab.doc2bow(t) for t in tok]
    docs_validos = [i for i, t in enumerate(tok) if len(t) >= 3]

    # 1. Términos relevantes: frecuencia documental y TF-IDF acumulado.
    df = {vocab[i]: c for i, c in vocab.dfs.items()}
    tfidf = Counter()
    for b in bolsa:
        total = sum(c for _, c in b) or 1
        for i, c in b:
            tfidf[vocab[i]] += (c / total) * np.log(len(bolsa) / vocab.dfs[i])
    def etiqueta(s):
        return visible.get(s, s)
    top_df = [{"termino": etiqueta(s), "comentarios": int(c), "pct": round(100 * c / n, 2)}
              for s, c in sorted(df.items(), key=lambda x: -x[1])[:30]]
    top_tfidf = [{"termino": etiqueta(s), "tfidf": round(float(v), 3)} for s, v in tfidf.most_common(30)]

    # 2. Colocaciones: bigramas contiguos sobre los tokens filtrados (sin stemming para que se lean).
    pares = Counter()
    vacias = {l.strip() for l in STOPWORDS_PALABRAS.read_text(encoding="utf-8").splitlines() if l.strip()}
    sin_stem = Corpus.from_file(args.entrada)
    sin_stem.attributes["language"] = "es"
    for pp in (LowercaseTransformer(), StripAccentsTransformer(), UrlRemover(), RegexpTokenizer(r"\w+")):
        sin_stem = pp(sin_stem)
    for t in sin_stem.tokens:
        t = [w for w in t if w not in vacias and not w.isdigit()]
        for a, b in zip(t, t[1:]):
            if len(a) > 2 and len(b) > 2:
                pares[(a, b)] += 1
    bigramas = [{"bigrama": f"{a} {b}", "veces": int(c)} for (a, b), c in pares.most_common(25) if c >= 3]

    # 3. LDA: comparación de k con coherencia c_v.
    comparacion, modelos = [], {}
    base = [tok[i] for i in docs_validos]
    bolsa_v = [bolsa[i] for i in docs_validos]
    if len(base) >= 30:
        for k in range(K_MIN, K_MAX + 1):
            lda = LdaModel(bolsa_v, id2word=vocab, num_topics=k, random_state=SEMILLA, passes=10, iterations=100, alpha="auto")
            coh = CoherenceModel(model=lda, texts=base, dictionary=vocab, coherence="c_v").get_coherence()
            modelos[k] = lda
            comparacion.append({"k": k, "coherencia_cv": round(float(coh), 4)})
        k_elegido = max(comparacion, key=lambda c: c["coherencia_cv"])["k"]
    else:
        k_elegido = None
    temas = []
    if k_elegido:
        lda = modelos[k_elegido]
        asignacion = [max(lda.get_document_topics(b, minimum_probability=0), key=lambda x: x[1]) for b in bolsa_v]
        for t in range(k_elegido):
            idx = [j for j, (tt, _) in enumerate(asignacion) if tt == t]
            palabras = [etiqueta(w) for w, _ in lda.show_topic(t, topn=10)]
            rep = sorted(idx, key=lambda j: -asignacion[j][1])[:3]
            temas.append({
                "tema": t + 1, "palabras": palabras, "comentarios": len(idx),
                "pct_comentarios": round(100 * len(idx) / len(base), 2),
                "ejemplos": [recortar(textos[docs_validos[j]]) for j in rep],
            })
        temas.sort(key=lambda x: -x["comentarios"])

    # 4. Categorías definidas a priori (codificación por diccionario).
    norm = [sin_tildes(t.lower()) for t in textos]
    categorias = {}
    for nombre, patron in CATEGORIAS.items():
        rx = re.compile(patron)
        hit = np.array([bool(rx.search(t)) for t in norm])
        top = np.argsort(-(me_gusta * hit))[:2]
        categorias[nombre] = {
            "comentarios": int(hit.sum()), "pct": round(100 * hit.mean(), 2) if n else None,
            "pct_ponderado_me_gusta": round(100 * (me_gusta * hit).sum() / me_gusta.sum(), 2) if me_gusta.sum() else None,
            "ejemplos": [recortar(textos[i]) for i in top if hit[i]],
        }
    hib = np.array([bool(re.search(CATEGORIAS["hibrido_mencion"], t)) for t in norm])
    ele = np.array([bool(re.search(CATEGORIAS["electrico_mencion"], t)) for t in norm])
    co_ocurrencia = {}
    for nombre in ("precio_costo", "carga_infraestructura", "autonomia_bateria", "incentivos_impuestos", "desconfianza_problemas"):
        rx = re.compile(CATEGORIAS[nombre])
        hit = np.array([bool(rx.search(t)) for t in norm])
        co_ocurrencia[nombre] = {
            "pct_en_comentarios_que_mencionan_hibrido": round(100 * hit[hib & ~ele].mean(), 2) if (hib & ~ele).sum() >= 20 else None,
            "pct_en_comentarios_que_mencionan_electrico": round(100 * hit[ele & ~hib].mean(), 2) if (ele & ~hib).sum() >= 20 else None,
        }

    resultado = {
        "entrada": "data/processed/etapa6/comentarios_limpios.tab",
        "comentarios": n,
        "comentarios_con_3_o_mas_terminos": len(docs_validos),
        "vocabulario": len(vocab),
        "procesamiento": "minúsculas, sin tildes, sin URL, tokens \\w+, stemmer Snowball (es), stopwords es (NLTK + propias, transformadas igual que el texto), "
                         f"sin números, términos en >= {MIN_DOCS} comentarios",
        "terminos_por_frecuencia_documental": top_df,
        "terminos_por_tfidf": top_tfidf,
        "bigramas": bigramas,
        "lda": {"comparacion_k": comparacion, "k_elegido": k_elegido,
                "criterio": "mayor coherencia c_v entre k = 3..8 (semilla 0, 10 pasadas)", "temas": temas},
        "categorias": categorias,
        "mencion_hibrido_vs_electrico": {
            "solo_hibrido": int((hib & ~ele).sum()), "solo_electrico": int((ele & ~hib).sum()),
            "ambos": int((hib & ele).sum()), "ninguno": int((~hib & ~ele).sum()),
            "co_ocurrencia": co_ocurrencia,
        },
        "advertencia": "Los comentarios son de quienes comentaron en los videos seleccionados; no representan a toda la población.",
    }
    (salida / "resultados_youtube_analisis.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Comentarios: {n} · vocabulario: {len(vocab)} · k LDA: {k_elegido}")


if __name__ == "__main__":
    main()
