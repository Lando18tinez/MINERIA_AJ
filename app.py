from flask import Flask, abort, render_template
from jinja2 import TemplateNotFound

app = Flask(__name__)

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
    return render_template(
        template_a_renderizar, seccion=seccion, active=f"etapa2:{slug}"
    )


if __name__ == "__main__":
    app.run(debug=True)