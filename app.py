import json
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for
from jinja2 import TemplateNotFound

import olap

app = Flask(__name__)

RAIZ = Path(__file__).resolve().parent

# --- Resultados verificables ---------------------------------------------------
# Todas las cifras de perfilamiento, calidad y tratamiento (Etapa 2) salen de este
# archivo, generado por calidad_etapa2.py a partir del CSV descargado de datos.gov.co
# (ntxy-q9ix). Para regenerarlo:  python calidad_etapa2.py
RESULTADOS = json.loads(
    (RAIZ / "data" / "processed" / "resultados_eda.json").read_text(encoding="utf-8")
)

# Cifras de apoyo de «Conocimiento evidente» (tableros de Power BI), generadas por
# conocimiento_evidente.py:  python conocimiento_evidente.py
CONOCIMIENTO = json.loads(
    (RAIZ / "data" / "processed" / "resultados_conocimiento_evidente.json").read_text(encoding="utf-8")
)

# Modelo estrella de la Etapa 5 (SQLite). La app solo lo lee: se abre con mode=ro (ver olap.py).
MODELO_DB = olap.MODELO_DB

# Archivos que la app permite descargar/consultar (evidencia de dónde salen los resultados).
DATOS_PUBLICOS = {
    "vehiculos_electricos_hibridos_runt.csv": RAIZ / "data" / "raw",
    "FUENTE.json": RAIZ / "data" / "raw",
    "resultados_eda.json": RAIZ / "data" / "processed",
    "resultados_conocimiento_evidente.json": RAIZ / "data" / "processed",
    "hechos_vehiculos.csv": RAIZ / "data" / "powerbi",
    "dim_territorio.csv": RAIZ / "data" / "powerbi",
    "dim_combustible.csv": RAIZ / "data" / "powerbi",
    "dim_anio.csv": RAIZ / "data" / "powerbi",
}
CODIGO_PUBLICO = {"calidad_etapa2.py": RAIZ, "conocimiento_evidente.py": RAIZ}


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

# Evidencias de la Etapa 3: documento de soporte (PDF) y video explicativo.
# Ajusta estos dos valores cuando tengas el archivo y el enlace definitivos.
ETAPA3_PDF = "docs/etl_proceso.pdf"  # ruta dentro de static/
ETAPA3_VIDEO_URL = "https://youtu.be/_kH2HUqA0tc"

# Informe de Power BI «Conocimiento evidente», publicado con «Publicar en la Web» (acceso público,
# sin iniciar sesión). Si se publica de nuevo, cambia solo esta URL; con "" la página muestra un aviso.
POWERBI_URL = (
    "https://app.powerbi.com/view?r=eyJrIjoiOTg0MTU3YTItYTgyNy00YzM3LTlhMTktOGE5NDg1MzczYjczIiwi"
    "dCI6IjA3ZGE2N2EwLTFmNDMtNGU4Yy05NzdmLTVmODhiNjQ3MGVlNiIsImMiOjR9"
)

# Las 4 preguntas de análisis, una por página del informe. «pagina» es el identificador interno de
# la página en Power BI (parámetro pageName de la URL); los hallazgos coinciden con los tableros.
CONOCIMIENTO_PREGUNTAS = [
    {
        "num": 1,
        "dimension": "Dimensión poblacional",
        "icono": "bi-pie-chart-fill",
        "pagina": "d7146c4db9e6da6aacd3",
        "pregunta": (
            "¿Cómo se compone la población de vehículos eléctricos e híbridos registrados en Colombia "
            "entre 2015 y 2024, según su combustible, clase, carrocería y año del modelo?"
        ),
        "variables": "Combustible, clase, carrocería, año del modelo y cantidad de vehículos",
        "hallazgos": [
            "Los híbridos gasolina-eléctrico son tres de cada cuatro vehículos (75,31 %)",
            "Camioneta y automóvil concentran más del 80 %",
            "Ocho de cada diez vehículos son de modelo 2022 o posterior",
        ],
    },
    {
        "num": 2,
        "dimension": "Dimensión territorial",
        "icono": "bi-geo-alt-fill",
        "pagina": "11d92b563cbdfc7df2d3",
        "pregunta": (
            "¿Cómo se distribuyen territorialmente los vehículos eléctricos e híbridos registrados en "
            "Colombia entre 2015 y 2024, y qué departamentos y municipios concentran la mayor cantidad "
            "de registros?"
        ),
        "variables": "Departamento, municipio, latitud y longitud, combustible y cantidad de vehículos",
        "hallazgos": [
            "Tres departamentos concentran el 73,68 % de los vehículos",
            "Diez municipios concentran el 79,91 %",
            "Casi 4 de cada 10 territorios tienen menos de 10 vehículos",
        ],
    },
    {
        "num": 3,
        "dimension": "Dimensión temporal",
        "icono": "bi-graph-up-arrow",
        "pagina": "af7f388ebfe90ecefbd0",
        "pregunta": (
            "¿Cómo ha evolucionado la cantidad de vehículos eléctricos e híbridos registrados en "
            "Colombia entre 2015 y 2024?"
        ),
        "variables": "Año de registro, combustible, departamento y cantidad de vehículos",
        "hallazgos": [
            "El registro anual se multiplicó por 9,9 entre 2019 y 2024",
            "Los mayores saltos fueron 2018, 2019 y 2021; solo hubo caídas en 2016 y 2017",
            "Desde 2020 los híbridos superan a los eléctricos y mantienen cerca del 80 %",
        ],
    },
    {
        "num": 4,
        "dimension": "Dimensión multivariada",
        "icono": "bi-diagram-3-fill",
        "pagina": "47529fb7895904443302",
        "pregunta": (
            "¿Cómo se relacionan el tipo de combustible, el año del modelo y el departamento con la "
            "cantidad de vehículos eléctricos e híbridos registrados en Colombia entre 2015 y 2024?"
        ),
        "variables": "Combustible, año del modelo, departamento, año de registro, clase y cantidad de vehículos",
        "hallazgos": [
            "Los modelos nuevos son casi todos híbridos; los eléctricos dominan los antiguos",
            "La proporción de eléctricos va de 4,46 % a 33,42 % entre los cinco departamentos principales",
            "Pocos grupos grandes concentran el 88 % de los vehículos",
        ],
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
        "etapa3_secciones": ETAPA3_SECCIONES,
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


# --- Conocimiento evidente (tableros de Power BI) ---------------------------


@app.route("/conocimiento-evidente")
def conocimiento_evidente():
    return render_template(
        "conocimiento_evidente.html",
        active="conocimiento",
        powerbi_url=POWERBI_URL,
        preguntas=CONOCIMIENTO_PREGUNTAS,
        ce=CONOCIMIENTO,
    )


# --- Análisis multidimensional (Etapa 5: modelo estrella) -------------------

# Preguntas de análisis del modelo (docs/etapa5/modelo_multidimensional.md, sección 2).
# «endpoint» es la ruta de su vista; sin «endpoint» la pregunta se muestra «En construcción», sin enlace.
MODELO_PREGUNTAS = [
    {
        "id": "P1",
        "endpoint": "analisis_p1",
        "pregunta": (
            "¿Cuál es la tendencia de crecimiento de los vehículos eléctricos registrados entre 2015 y 2024, "
            "y qué tipos de vehículo la impulsan?"
        ),
        "dimensiones": "dim_tiempo, dim_combustible (familia = Eléctrico), dim_vehiculo",
        "medidas": "Vehículos registrados, Participación %",
    },
    {
        "id": "P2",
        "pregunta": "¿El crecimiento anual de los eléctricos es homogéneo entre territorios?",
        "dimensiones": "dim_tiempo, dim_territorio, dim_combustible",
        "medidas": "Vehículos registrados por año y territorio, Territorios distintos, Participación %",
    },
    {
        "id": "P3",
        "pregunta": (
            "¿Cómo cambia la distribución de los vehículos registrados por clase y año del modelo a lo largo "
            "del tiempo?"
        ),
        "dimensiones": "dim_tiempo, dim_vehiculo, dim_modelo",
        "medidas": "Vehículos registrados, Participación % (denominador: el año de registro)",
    },
    {
        "id": "P4",
        "pregunta": (
            "¿Qué diferencias muestran el promedio, la mediana y la concentración por combustible, tipo de "
            "vehículo y territorio?"
        ),
        "dimensiones": "dim_combustible, dim_vehiculo, dim_territorio",
        "medidas": "Promedio y Mediana de vehículos por territorio, Participación %, Grupos de registro",
    },
]

# Consultas de la portada. Los vehículos se cuentan con SUM(cantidad), no contando filas.
_CONSULTAS_MODELO = {
    "grupos": "SELECT COUNT(*) FROM hechos_registros",
    "vehiculos": "SELECT SUM(cantidad) FROM hechos_registros",
    "anio_min": "SELECT MIN(t.anio) FROM hechos_registros h JOIN dim_tiempo t USING (id_tiempo)",
    "anio_max": "SELECT MAX(t.anio) FROM hechos_registros h JOIN dim_tiempo t USING (id_tiempo)",
    "territorios": "SELECT COUNT(DISTINCT id_territorio) FROM hechos_registros",
    "departamentos": "SELECT COUNT(DISTINCT departamento) FROM dim_territorio",
    "filas_dim_tiempo": "SELECT COUNT(*) FROM dim_tiempo",
    "filas_dim_territorio": "SELECT COUNT(*) FROM dim_territorio",
    "filas_dim_combustible": "SELECT COUNT(*) FROM dim_combustible",
    "filas_dim_vehiculo": "SELECT COUNT(*) FROM dim_vehiculo",
    "filas_dim_modelo": "SELECT COUNT(*) FROM dim_modelo",
    "modelo_min": "SELECT MIN(anio_modelo) FROM dim_modelo",
    "modelo_max": "SELECT MAX(anio_modelo) FROM dim_modelo",
}


def _resumen_modelo():
    """Lee las cifras de la portada desde el modelo estrella, en modo de solo lectura.

    Devuelve (resumen, error). Si la base no existe o no se puede leer, resumen es None.
    """
    if not MODELO_DB.is_file():
        return None, f"No se encontró la base {MODELO_DB.relative_to(RAIZ).as_posix()}."
    try:
        con = sqlite3.connect(f"{MODELO_DB.as_uri()}?mode=ro", uri=True)
        try:
            resumen = {k: con.execute(sql).fetchone()[0] for k, sql in _CONSULTAS_MODELO.items()}
        finally:
            con.close()
    except sqlite3.Error as exc:
        return None, f"No se pudo leer el modelo estrella: {exc}"
    return resumen, None


@app.route("/analisis-multidimensional")
def analisis_multidimensional():
    resumen, error = _resumen_modelo()
    return render_template(
        "etapa5/analisis_multidimensional.html",
        active="multidimensional",
        m=resumen,
        error_modelo=error,
        preguntas=MODELO_PREGUNTAS,
        ce=CONOCIMIENTO,
    )


# --- Vista P1: tendencia de los eléctricos y tipos de vehículo ---------------

P1_FAMILIA_INICIAL = "Eléctrico"   # filtro inicial de la pregunta P1
TODAS = "todas"                    # valor de «familia» que quita ese filtro
NIVEL_INICIAL = olap.ORDEN_NIVELES[0]
ETIQUETA_DIMENSION = {"tiempo": "tiempo", "vehiculo": "vehículo", "combustible": "combustible"}


def _p1_leer_estado(args, perm):
    """Convierte los parámetros GET en un estado válido. Lo que no está en las listas cerradas se ignora y avisa."""
    avisos = []

    def uno(nombre):
        valor = args.get(nombre, "").strip()
        if valor and valor not in perm[nombre]:
            avisos.append(f"Se ignoró «{valor}» en {olap.FILTROS[nombre][2].lower()}: no existe en el modelo.")
            return ""
        return valor

    familia = args.get("familia", P1_FAMILIA_INICIAL).strip() or P1_FAMILIA_INICIAL
    if familia != TODAS and familia not in perm["familia"]:
        avisos.append(f"Se ignoró «{familia}» en familia de combustible: no existe en el modelo.")
        familia = P1_FAMILIA_INICIAL

    anios = []
    for valor in args.getlist("anio"):
        try:
            anio = int(valor)
        except ValueError:
            anio = None
        if anio in perm["anio"]:
            anios.append(anio)
        elif valor.strip():
            avisos.append(f"Se ignoró «{valor}» en año de registro: no existe en el modelo.")

    nivel = args.get("nivel", NIVEL_INICIAL)
    if nivel not in olap.NIVELES_VEHICULO:
        avisos.append(f"Se ignoró el nivel «{nivel}»: los niveles válidos son categoría, clase y carrocería.")
        nivel = NIVEL_INICIAL

    estado = {
        "familia": familia,
        "periodo": uno("periodo"),
        "anio": sorted(set(anios)),
        "categoria": uno("categoria"),
        "clase": uno("clase"),
        "nivel": nivel,
        "pivot": args.get("pivot") == "1",
    }
    return estado, avisos


def _p1_url(estado, **cambios):
    """URL canónica de un estado: cada selección tiene su propia dirección (solo se escriben valores no iniciales)."""
    e = {**estado, **cambios}
    params = {}
    if e["familia"] != P1_FAMILIA_INICIAL:
        params["familia"] = e["familia"]
    for nombre in ("periodo", "categoria", "clase"):
        if e[nombre]:
            params[nombre] = e[nombre]
    if e["anio"]:
        params["anio"] = e["anio"]
    if e["nivel"] != NIVEL_INICIAL:
        params["nivel"] = e["nivel"]
    if e["pivot"]:
        params["pivot"] = "1"
    return url_for("analisis_p1", **params)


def _p1_filtros(estado):
    """Estado -> filtros para olap.py ({nombre: [valores]})."""
    return {
        "familia": [] if estado["familia"] == TODAS else [estado["familia"]],
        "periodo": [estado["periodo"]] if estado["periodo"] else [],
        "anio": estado["anio"],
        "categoria": [estado["categoria"]] if estado["categoria"] else [],
        "clase": [estado["clase"]] if estado["clase"] else [],
    }


def _p1_operacion(estado):
    """Nombre de la operación que describe los filtros de análisis (tiempo y vehículo)."""
    valores = {
        "tiempo": ([estado["periodo"]] if estado["periodo"] else []) + estado["anio"],
        "vehiculo": [v for v in (estado["categoria"], estado["clase"]) if v],
    }
    activas = {d: v for d, v in valores.items() if v}
    if not activas:
        return "Sin filtros de análisis", "Se ven todos los años y todos los tipos de vehículo."
    if len(activas) >= 2:
        return "Dice", "Filtros combinados en las dimensiones tiempo y vehículo."
    (dim, vals), = activas.items()
    if len(vals) == 1:
        return "Slice", f"Un solo valor de la dimensión {ETIQUETA_DIMENSION[dim]}."
    return "Filtro en una dimensión", f"Varios valores de la dimensión {ETIQUETA_DIMENSION[dim]}."


@app.route("/analisis-multidimensional/p1")
def analisis_p1():
    pregunta = MODELO_PREGUNTAS[0]
    try:
        con = olap.conectar()
    except (FileNotFoundError, sqlite3.Error) as exc:
        return render_template("etapa5/p1.html", active="multidimensional", q=pregunta,
                               error_modelo=f"No se pudo abrir el modelo estrella: {exc}")

    with closing(con):
        perm = olap.valores_permitidos(con)
        estado, avisos = _p1_leer_estado(request.args, perm)

        # Slice: un solo valor de una dimensión de análisis. Se quitan los demás filtros de análisis
        # y se redirige a la URL canónica de esa selección.
        if "slice" in request.args:
            dim, _, valor = request.args.get("slice", "").partition(":")
            limpio = {**estado, "periodo": "", "anio": [], "categoria": "", "clase": ""}
            if dim == "anio" and valor.isdigit() and int(valor) in perm["anio"]:
                return redirect(_p1_url(limpio, anio=[int(valor)]))
            if dim in ("periodo", "categoria", "clase") and valor in perm[dim]:
                return redirect(_p1_url(limpio, **{dim: valor}))
            avisos.append("Se ignoró el slice elegido: la dimensión o el valor no son válidos.")

        # Años visibles: los del periodo y los años elegidos (si hay). Son el eje de la tendencia.
        anios = [a for a in perm["anio"]
                 if (not estado["periodo"] or perm["periodo_de_anio"][a] == estado["periodo"])
                 and (not estado["anio"] or a in estado["anio"])]

        filtros = _p1_filtros(estado)
        cubo = olap.consultar(con, filtros, estado["nivel"], anios) if anios else None
        rollup = {n: olap.total_por_nivel(con, filtros, n) for n in olap.ORDEN_NIVELES} if cubo else None

    i = olap.ORDEN_NIVELES.index(estado["nivel"])
    siguiente = olap.ORDEN_NIVELES[i + 1] if i + 1 < len(olap.ORDEN_NIVELES) else None
    anterior = olap.ORDEN_NIVELES[i - 1] if i > 0 else None

    # Drill-down sobre un miembro: se filtra ese miembro y se baja un nivel.
    def url_drill_miembro(llave):
        if estado["nivel"] == "categoria":
            return _p1_url(estado, categoria=llave[0], nivel="clase")
        if estado["nivel"] == "clase":
            return _p1_url(estado, clase=llave[0], nivel="carroceria")
        return None

    # Filtros activos, cada uno con la URL que lo quita.
    activos = [("Familia de combustible",
                "Todas" if estado["familia"] == TODAS else estado["familia"],
                _p1_url(estado, familia=TODAS) if estado["familia"] != TODAS else None)]
    if estado["periodo"]:
        activos.append(("Periodo", estado["periodo"], _p1_url(estado, periodo="")))
    if estado["anio"]:
        activos.append(("Año de registro", ", ".join(map(str, estado["anio"])), _p1_url(estado, anio=[])))
    if estado["categoria"]:
        activos.append(("Categoría", estado["categoria"], _p1_url(estado, categoria="")))
    if estado["clase"]:
        activos.append(("Clase", estado["clase"], _p1_url(estado, clase="")))

    return render_template(
        "etapa5/p1.html",
        active="multidimensional",
        q=pregunta,
        error_modelo=None,
        perm=perm,
        estado=estado,
        avisos=avisos,
        anios=anios,
        cubo=cubo,
        rollup=rollup,
        activos=activos,
        operacion=_p1_operacion(estado),
        niveles=olap.NIVELES_VEHICULO,
        orden_niveles=olap.ORDEN_NIVELES,
        url_drill=_p1_url(estado, nivel=siguiente) if siguiente else None,
        url_rollup=_p1_url(estado, nivel=anterior) if anterior else None,
        url_pivot=_p1_url(estado, pivot=not estado["pivot"]),
        url_limpiar=_p1_url({**estado, "familia": P1_FAMILIA_INICIAL, "periodo": "", "anio": [],
                             "categoria": "", "clase": "", "nivel": NIVEL_INICIAL, "pivot": False}),
        url_drill_miembro=url_drill_miembro,
        nivel_siguiente=siguiente,
        nivel_anterior=anterior,
        todas=TODAS,
    )


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