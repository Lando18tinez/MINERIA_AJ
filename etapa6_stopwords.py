"""
Etapa 6 · Lista de stopwords en español para el análisis de comentarios.

Problema: el widget «Preprocess Text» de Orange aplica los pasos en este orden fijo: transformar (minúsculas,
quitar tildes) -> tokenizar -> normalizar (stemmer) -> filtrar (stopwords). Las stopwords de NLTK vienen con
tildes y sin stemmer («más», «para»), así que después de quitar tildes y aplicar el stemmer ya no coinciden
(«mas», «par») y palabras vacías como «para» o «más» se cuelan entre los términos principales.

Solución: transformar la lista de stopwords igual que el texto (minúsculas, sin tildes, stemmer Snowball
español) y guardarla en un archivo que se carga en el widget («Stopwords: From file») y en el script
etapa6_youtube_analisis.py.

Entradas : stopwords de NLTK (español) + etapa6_stopwords_extra.txt (palabras propias, editable: una por línea)
Salidas  : etapa6_stopwords_es.txt           (raíces; la usa el filtro tras el stemmer)
           etapa6_stopwords_es_palabras.txt  (palabras sin tildes; sirven para filtrar bigramas sin stemmer)

Uso:
    python etapa6_stopwords.py
"""

import sys
import unicodedata
from pathlib import Path

from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer

RAIZ = Path(__file__).resolve().parent
EXTRA = RAIZ / "etapa6_stopwords_extra.txt"


def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def palabras_base():
    from orangecontrib.text.misc import nltk_data_dir  # asegura la ruta de datos de NLTK que usa Orange
    import nltk
    nltk.data.path.insert(0, nltk_data_dir())
    try:
        base = set(stopwords.words("spanish"))
    except LookupError:
        nltk.download("stopwords", download_dir=nltk_data_dir(), quiet=True)
        base = set(stopwords.words("spanish"))
    extra = {l.strip() for l in EXTRA.read_text(encoding="utf-8").splitlines() if l.strip()} if EXTRA.exists() else set()
    return base, extra


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    base, extra = palabras_base()
    palabras = sorted({sin_tildes(w.lower()) for w in base | extra})
    st = SnowballStemmer("spanish")
    raices = sorted({st.stem(w) for w in palabras} | set(palabras))
    (RAIZ / "etapa6_stopwords_es_palabras.txt").write_text("\n".join(palabras) + "\n", encoding="utf-8")
    (RAIZ / "etapa6_stopwords_es.txt").write_text("\n".join(raices) + "\n", encoding="utf-8")
    print(f"NLTK: {len(base)} · propias: {len(extra)} · palabras: {len(palabras)} · raíces + palabras: {len(raices)}")


if __name__ == "__main__":
    main()
