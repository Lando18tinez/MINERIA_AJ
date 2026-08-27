from flask import Flask, render_template, abort
from jinja2 import TemplateNotFound

app = Flask(__name__)

# --- Datos del proyecto -----------------------------------------------------

PROYECTO = "Transición energética y energías renovables"

# Secciones de la Etapa 1 (fase de comprensión del negocio y de los datos).
# El orden de la lista define el orden del submenú del navbar.
ETAPA1_SECCIONES = [
    {"slug": "problema-contexto", "num": 1, "titulo": "Problema y contexto"},
    {"slug": "preguntas", "num": 2, "titulo": "Pregunta principal y preguntas secundarias"},
    {"slug": "necesidades-informacion", "num": 3, "titulo": "Necesidades de información"},
    {"slug": "fuentes-datos", "num": 4, "titulo": "Fuentes de datos"},
    {"slug": "dataset", "num": 5, "titulo": "Dataset"},
    {"slug": "diccionario-datos", "num": 6, "titulo": "Diccionario de datos"},
    {"slug": "calidad-inicial", "num": 7, "titulo": "Calidad inicial de los datos"},
    {"slug": "limitaciones", "num": 8, "titulo": "Limitaciones y consideraciones"},
]

# "foto" es el nombre del archivo dentro de static/img/. Deja "" si aún no hay foto.
PARTICIPANTES = [
    {"nombre": "Angelica Rosa Olier Quiroga", "foto": "angelica.jpg"},
    {"nombre": "Johan Orlando Martinez Suarez", "foto": "johan.jpg"},
]


@app.context_processor
def inject_nav():
    """Deja las secciones disponibles en todas las plantillas (para el navbar)."""
    return {"etapa1_secciones": ETAPA1_SECCIONES, "proyecto": PROYECTO}


# --- Rutas ----------------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html", active="inicio")


@app.route("/participantes")
def participantes():
    return render_template(
        "participantes.html", participantes=PARTICIPANTES, active="participantes"
    )


@app.route("/etapa1/<slug>")
def etapa1_seccion(slug):
    seccion = next((s for s in ETAPA1_SECCIONES if s["slug"] == slug), None)
    if seccion is None:
        abort(404)

    # Mapeo de slugs a sus plantillas correspondientes
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

    for nombre in (alias.get(slug), f"etapa1/{slug}.html", "etapa1/seccion.html"):
        if not nombre:
            continue
        try:
            return render_template(nombre, **ctx)
        except TemplateNotFound:
            continue
    return render_template("etapa1/seccion.html", **ctx)

    template_a_renderizar = plantillas.get(slug, "etapa1/seccion.html")
    return render_template(
        template_a_renderizar, seccion=seccion, active=f"etapa1:{slug}"
    )


if __name__ == "__main__":
    app.run(debug=True)
