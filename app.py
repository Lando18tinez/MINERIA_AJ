import json
from pathlib import Path

from flask import Flask, abort, render_template, send_from_directory, url_for
from jinja2 import TemplateNotFound

app = Flask(__name__)

RAIZ = Path(__file__).resolve().parent

# --- Resultados verificables ---------------------------------------------------
# Todas las cifras de perfilamiento, calidad y tratamiento (Etapa 2) salen de este
# archivo, generado por calidad_etapa2.py a partir del CSV descargado de datos.gov.co
# (ntxy-q9ix). Para regenerarlo:  python calidad_etapa2.py
RESULTADOS = json.loads(
    (RAIZ / "data" / "processed" / "resultados_eda.json").read_text(encoding="utf-8")
)
# Resultados del análisis exploratorio de la Etapa 4 (python eda_etapa4.py)
RESULTADOS.update(
    json.loads(
        (RAIZ / "data" / "processed" / "resultados_etapa4.json").read_text(encoding="utf-8")
    )
)

# Archivos que la app permite descargar/consultar (evidencia de dónde salen los resultados).
DATOS_PUBLICOS = {
    "vehiculos_electricos_hibridos_runt.csv": RAIZ / "data" / "raw",
    "FUENTE.json": RAIZ / "data" / "raw",
    "resultados_eda.json": RAIZ / "data" / "processed",
    "resultados_etapa4.json": RAIZ / "data" / "processed",
}
CODIGO_PUBLICO = {"calidad_etapa2.py": RAIZ, "eda_etapa4.py": RAIZ}


def _numero(valor, decimales=0):
    """Formato es-CO: punto para miles y coma para decimales (1.234,5)."""
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("miles")
def filtro_miles(valor):
    return _numero(valor, 0)


@app.template_filter("dec")
def filtro_dec(valor, decimales=2):
    return _numero(valor, decimales)


@app.template_filter("pct")
def filtro_pct(valor, decimales=2):
    return "—" if valor is None else f"{_numero(valor, decimales)} %"


# --- Datos del proyecto -----------------------------------------------------

PROYECTO = "Transición energética y energías renovables"

# Secciones de la Etapa 1 (Comprensión del negocio y de los datos)
ETAPA1_SECCIONES = [
    {"slug": "problema-contexto", "num": 1, "titulo": "Problema y contexto"},
    {
        "slug": "preguntas",
        "num": 2,
        "titulo": "Pregunta principal y preguntas secundarias",
    },
    {
        "slug": "necesidades-informacion",
        "num": 3,
        "titulo": "Necesidades de información",
    },
    {"slug": "fuentes-datos", "num": 4, "titulo": "Fuentes de datos"},
    {"slug": "dataset", "num": 5, "titulo": "Dataset"},
    {
        "slug": "diccionario-datos",
        "num": 6,
        "titulo": "Diccionario de datos",
    },
    {
        "slug": "calidad-inicial",
        "num": 7,
        "titulo": "Calidad inicial de los datos",
    },
    {
        "slug": "limitaciones",
        "num": 8,
        "titulo": "Limitaciones y consideraciones",
    },
]

# Secciones de la Etapa 2 (Calidad de datos y remediación técnica)
ETAPA2_SECCIONES = [
    {
        "slug": "proposito-requisitos",
        "num": 1,
        "titulo": "Propósito y requisitos de calidad",
    },
    {
        "slug": "perfilamiento",
        "num": 2,
        "titulo": "Perfilamiento del dataset",
    },
    {
        "slug": "dimensiones-metricas",
        "num": 3,
        "titulo": "Dimensiones y métricas de calidad",
    },
    {
        "slug": "inventario-problemas",
        "num": 4,
        "titulo": "Inventario de problemas y causas",
    },
    {
        "slug": "plan-tratamiento",
        "num": 5,
        "titulo": "Plan de tratamiento y homologación",
    },
    {
        "slug": "comparacion-antes-despues",
        "num": 6,
        "titulo": "Comparación antes y después",
    },
]

# Secciones de la Etapa 3 (Preparación de los datos: ETL)
ETAPA3_SECCIONES = [
    {
        "slug": "etl",
        "num": 1,
        "titulo": "ETL: Extracción, Transformación y Carga",
    },
]

# Secciones de la Etapa 4 (Análisis exploratorio de la población)
ETAPA4_SECCIONES = [
    {"slug": "poblacional", "num": 1, "titulo": "Dimensión poblacional"},
    {"slug": "territorial", "num": 2, "titulo": "Dimensión territorial"},
]

# Evidencias de la Etapa 3: documento de soporte (PDF) y video explicativo.
# Ajusta estos dos valores cuando tengas el archivo y el enlace definitivos.
ETAPA3_PDF = "docs/etl_proceso.pdf"  # ruta dentro de static/
ETAPA3_VIDEO_URL = "https://youtu.be/_kH2HUqA0tc"

PARTICIPANTES = [
    {"nombre": "Angelica Rosa Olier Quiroga", "foto": "angelica.jpg"},
    {"nombre": "Johan Orlando Martinez Suarez", "foto": "johan.jpg"},
]


@app.context_processor
def inject_nav():
    """Deja disponibles todas las colecciones y metadatos en las plantillas Jinja2."""
    return {
        "proyecto": PROYECTO,
        "etapa1_secciones": ETAPA1_SECCIONES,
        "etapa2_secciones": ETAPA2_SECCIONES,
        "etapa3_secciones": ETAPA3_SECCIONES,
        "etapa4_secciones": ETAPA4_SECCIONES,
        "res": RESULTADOS,
    }


# --- Rutas Generales y Etapa 1 ----------------------------------------------


@app.route("/")
def home():
    return render_template("index.html", active="inicio")


@app.route("/participantes")
def participantes():
    return render_template(
        "participantes.html",
        participantes=PARTICIPANTES,
        active="participantes",
    )


@app.route("/etapa1/<slug>")
def etapa1_seccion(slug):
    seccion = next((s for s in ETAPA1_SECCIONES if s["slug"] == slug), None)
    if seccion is None:
        abort(404)

    plantillas = {
        "problema-contexto": "etapa1/problema_contexto.html",
        "preguntas": "etapa1/preguntas.html",
        "necesidades-informacion": "etapa1/necesidades_informacion.html",
        "fuentes-datos": "etapa1/fuentes_datos.html",
        "dataset": "etapa1/dataset.html",
        "diccionario-datos": "etapa1/diccionario_datos.html",
        "calidad-inicial": "etapa1/calidad_inicial.html",
        "limitaciones": "etapa1/limitaciones.html",
    }

    template_a_renderizar = plantillas.get(slug, "etapa1/seccion.html")
    return render_template(
        template_a_renderizar, seccion=seccion, active=f"etapa1:{slug}"
    )


# --- Rutas Etapa 2 ----------------------------------------------------------


@app.route("/etapa2/<slug>")
def etapa2_seccion(slug):
    seccion = next((s for s in ETAPA2_SECCIONES if s["slug"] == slug), None)
    if seccion is None:
        abort(404)

    plantillas = {
        "proposito-requisitos": "etapa2/proposito_requisitos.html",
        "perfilamiento": "etapa2/perfilamiento.html",
        "dimensiones-metricas": "etapa2/dimensiones_metricas.html",
        "inventario-problemas": "etapa2/inventario_problemas.html",
        "plan-tratamiento": "etapa2/plan_tratamiento.html",
        "comparacion-antes-despues": "etapa2/comparacion_antes_despues.html",
    }

    template_a_renderizar = plantillas.get(slug, "etapa2/seccion.html")
    ctx = {"seccion": seccion, "active": f"etapa2:{slug}"}
    # Si la plantilla específica aún no existe, se muestra la genérica
    # ("contenido en construcción") en lugar de lanzar un error 500.
    try:
        return render_template(template_a_renderizar, **ctx)
    except TemplateNotFound:
        return render_template("etapa2/seccion.html", **ctx)


# --- Rutas Etapa 3 ----------------------------------------------------------


@app.route("/etapa3/<slug>")
def etapa3_seccion(slug):
    seccion = next((s for s in ETAPA3_SECCIONES if s["slug"] == slug), None)
    if seccion is None:
        abort(404)

    plantillas = {
        "etl": "etapa3/etl.html",
    }

    template_a_renderizar = plantillas.get(slug, "etapa3/seccion.html")
    ctx = {
        "seccion": seccion,
        "active": f"etapa3:{slug}",
        "pdf_url": url_for("static", filename=ETAPA3_PDF),
        "video_url": ETAPA3_VIDEO_URL,
    }
    try:
        return render_template(template_a_renderizar, **ctx)
    except TemplateNotFound:
        return render_template("etapa3/seccion.html", **ctx)


# --- Rutas Etapa 4 ----------------------------------------------------------


@app.route("/etapa4/<slug>")
def etapa4_seccion(slug):
    seccion = next((s for s in ETAPA4_SECCIONES if s["slug"] == slug), None)
    if seccion is None:
        abort(404)

    plantillas = {
        "poblacional": "etapa4/poblacional.html",
        "territorial": "etapa4/territorial.html",
    }

    ctx = {"seccion": seccion, "active": f"etapa4:{slug}"}
    try:
        return render_template(plantillas.get(slug, "etapa4/seccion.html"), **ctx)
    except TemplateNotFound:
        return render_template("etapa4/seccion.html", **ctx)


# --- Evidencia: datos y código ----------------------------------------------


@app.route("/datos/<archivo>")
def descargar_datos(archivo):
    """Sirve el CSV fuente, su ficha de procedencia y los resultados calculados."""
    carpeta = DATOS_PUBLICOS.get(archivo)
    if carpeta is None:
        abort(404)
    return send_from_directory(carpeta, archivo)


@app.route("/codigo/<archivo>")
def ver_codigo(archivo):
    """Muestra el script que genera los resultados (texto plano, para auditarlo)."""
    carpeta = CODIGO_PUBLICO.get(archivo)
    if carpeta is None:
        abort(404)
    return send_from_directory(carpeta, archivo, mimetype="text/plain")


if __name__ == "__main__":
    app.run(debug=True)