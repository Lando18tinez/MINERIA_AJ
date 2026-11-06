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
        "endpoint": "analisis_p2",
        "pregunta": "¿El crecimiento anual de los eléctricos es homogéneo entre territorios?",
        "dimensiones": "dim_tiempo, dim_territorio, dim_combustible",
        "medidas": "Vehículos registrados por año y territorio, Territorios distintos, Participación %",
    },
    {
        "id": "P3",
        "endpoint": "analisis_p3",
        "pregunta": (
            "¿Cómo cambia la distribución de los vehículos registrados por clase y año del modelo a lo largo "
            "del tiempo?"
        ),
        "dimensiones": "dim_tiempo, dim_vehiculo, dim_modelo",
        "medidas": "Vehículos registrados, Participación % (denominador: el año de registro)",
    },
    {
        "id": "P4",
        "endpoint": "analisis_p4",
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


# --- Vistas OLAP (P1-P4): controles comunes ---------------------------------
# Cada vista declara sus filtros de análisis, la jerarquía que usa como filas y, opcional, otras jerarquías
# («extras», cada una con su parámetro GET). La lectura de parámetros GET, las URLs canónicas, el slice, el
# dice, el drill-down, el roll-up y el pivot son los mismos para todas.

FAMILIA_INICIAL = "Eléctrico"   # filtro inicial de las preguntas P1 y P2 (P3 y P4 empiezan sin filtro: «todas»)
TODAS = "todas"                 # valor de «familia» que quita ese filtro
P1_FAMILIA_INICIAL = FAMILIA_INICIAL
ETIQUETA_DIMENSION = {"tiempo": "tiempo", "vehiculo": "vehículo", "territorio": "territorio",
                      "combustible": "combustible", "modelo": "modelo"}
NOMBRE_NIVEL = {"categoria": "categoría", "clase": "clase", "carroceria": "carrocería",
                "departamento": "departamento", "municipio": "municipio",
                "rango_modelo": "rango del modelo", "anio_modelo": "año del modelo",
                "familia": "familia", "combustible": "combustible"}
# Al hacer drill-down sobre un miembro se filtra ese miembro con este filtro (los niveles hoja no tienen).
FILTRO_DE_NIVEL = {"categoria": "categoria", "clase": "clase", "departamento": "departamento",
                   "rango_modelo": "rango_modelo", "familia": "familia"}
# Filtros con un solo valor (selector). «anio» admite varios valores (casillas).
FILTROS_UNICOS = ("periodo", "categoria", "clase", "departamento", "municipio", "rango_modelo", "anio_modelo",
                  "combustible")

VISTAS_OLAP = {
    "p1": {
        "endpoint": "analisis_p1",
        "filtros": ("periodo", "anio", "categoria", "clase"),
        "niveles": olap.ORDEN_NIVELES,
        "dimension": "vehiculo",
        "texto_todo": "Se ven todos los años y todos los tipos de vehículo.",
        "miembro_texto": "un tipo de vehículo",
        "eje_texto": "tipo de vehículo",
        "ejemplo_sin_datos": ("una clase que no pertenece a la categoría elegida o un tipo de vehículo sin "
                              "registros en esos años"),
        # (filtro superior, filtro inferior, grupos del inferior en valores_permitidos)
        "dice": ("categoria", "clase", "clases_por_categoria"),
    },
    "p2": {
        "endpoint": "analisis_p2",
        "filtros": ("periodo", "anio", "departamento", "municipio"),
        "niveles": olap.ORDEN_NIVELES_TERRITORIO,
        "dimension": "territorio",
        "texto_todo": "Se ven todos los años y todos los territorios.",
        "miembro_texto": "un departamento",
        "eje_texto": "territorio",
        "ejemplo_sin_datos": ("un municipio que no pertenece al departamento elegido o un territorio sin "
                              "registros en esos años"),
        "dice": ("departamento", "municipio", "municipios_por_departamento"),
    },
    "p3": {
        "endpoint": "analisis_p3",
        "familia_inicial": TODAS,
        "filtros": ("periodo", "anio", "categoria", "clase", "rango_modelo", "anio_modelo"),
        "niveles": olap.ORDEN_NIVELES,
        "dimension": "vehiculo",
        # Segunda jerarquía: año del modelo (parámetro GET «nivel_modelo»).
        "extras": ({"param": "nivel_modelo", "niveles": olap.ORDEN_NIVELES_MODELO, "dimension": "modelo"},),
        "texto_todo": "Se ven todos los años de registro, todos los tipos de vehículo y todos los años del modelo.",
        "miembro_texto": "un tipo de vehículo (o un rango del modelo, en la tabla de la gráfica por modelo)",
        "eje_texto": "tipo de vehículo",
        "ejemplo_sin_datos": ("una clase que no pertenece a la categoría elegida, un año del modelo fuera del "
                              "rango elegido o un tipo de vehículo sin registros en esos años"),
        "dice": [("categoria", "clase", "clases_por_categoria"),
                 ("rango_modelo", "anio_modelo", "anios_modelo_por_rango")],
    },
    "p4": {
        "endpoint": "analisis_p4",
        "familia_inicial": TODAS,
        "familia_analisis": True,   # la familia es un filtro de la dimensión combustible (slice, dice)
        "tiempo": False,            # P4 no filtra por tiempo: usa los 10 años de registro
        "filtros": ("combustible", "categoria", "clase", "departamento"),
        "niveles": ("categoria", "clase"),
        "dimension": "vehiculo",
        # Jerarquías adicionales: combustible (columnas de la matriz) y territorio (nivel de cálculo).
        "extras": (
            {"param": "nivel_combustible", "niveles": olap.ORDEN_NIVELES_COMBUSTIBLE, "dimension": "combustible"},
            {"param": "nivel_territorio", "niveles": olap.ORDEN_NIVELES_TERRITORIO, "dimension": "territorio",
             "inicial": "municipio"},
        ),
        "texto_todo": "Se ven todos los combustibles, todos los tipos de vehículo y todos los territorios.",
        "miembro_texto": "un tipo de vehículo o una familia de combustible",
        "eje_texto": "tipo de vehículo",
        "eje_columnas": "combustible",
        "ejemplo_sin_datos": ("una clase que no pertenece a la categoría elegida, un combustible de otra familia "
                              "o un departamento sin registros de ese tipo de vehículo"),
        "dice": [("categoria", "clase", "clases_por_categoria"),
                 (None, "combustible", "combustibles_por_familia"),
                 ("departamento", None, None)],
    },
}


def _extras(vista):
    """Jerarquías adicionales de la vista, con su nivel inicial."""
    return [{**ex, "inicial": ex.get("inicial", ex["niveles"][0])} for ex in vista.get("extras", ())]


def _dimensiones(vista):
    """Dimensiones de análisis de la vista (sin contar el tiempo)."""
    return (vista["dimension"],) + tuple(ex["dimension"] for ex in _extras(vista))


def _permitido(perm, nombre, valor):
    """Valor de la lista cerrada que corresponde al texto «valor» (con su tipo original), o None."""
    return {str(v): v for v in perm[nombre]}.get(valor)


def _olap_leer_estado(vista, args, perm):
    """Convierte los parámetros GET en un estado válido. Lo que no está en las listas cerradas se ignora y avisa."""
    avisos = []

    def uno(nombre):
        valor = args.get(nombre, "").strip()
        if not valor:
            return ""
        elegido = _permitido(perm, nombre, valor)
        if elegido is None:
            avisos.append(f"Se ignoró «{valor}» en {olap.FILTROS[nombre][2].lower()}: no existe en el modelo.")
            return ""
        return elegido

    inicial = vista.get("familia_inicial", FAMILIA_INICIAL)
    familia = args.get("familia", inicial).strip() or inicial
    if familia != TODAS and familia not in perm["familia"]:
        avisos.append(f"Se ignoró «{familia}» en familia de combustible: no existe en el modelo.")
        familia = inicial

    if not vista.get("tiempo", True) and any(args.get(n, "").strip() for n in ("anio", "periodo")):
        avisos.append("Se ignoraron el año y el periodo: esta vista no filtra por tiempo y usa los 10 años de registro.")
    anios = []
    for valor in (args.getlist("anio") if vista.get("tiempo", True) else []):
        try:
            anio = int(valor)
        except ValueError:
            anio = None
        if anio in perm["anio"]:
            anios.append(anio)
        elif valor.strip():
            avisos.append(f"Se ignoró «{valor}» en año de registro: no existe en el modelo.")

    niveles = vista["niveles"]
    nivel = args.get("nivel", niveles[0])
    if nivel not in niveles:
        validos = [NOMBRE_NIVEL[n] for n in niveles]
        lista = ", ".join(validos[:-1]) + " y " + validos[-1]
        avisos.append(f"Se ignoró el nivel «{nivel}»: los niveles válidos son {lista}.")
        nivel = niveles[0]

    estado = {"familia": familia, "anio": sorted(set(anios)), "nivel": nivel, "pivot": args.get("pivot") == "1"}

    # Jerarquías adicionales (opcionales), cada una con su propio parámetro GET.
    for ex in _extras(vista):
        nivel_extra = args.get(ex["param"], ex["inicial"])
        if nivel_extra not in ex["niveles"]:
            validos = [NOMBRE_NIVEL[n] for n in ex["niveles"]]
            dim_extra = ETIQUETA_DIMENSION[ex["dimension"]]
            avisos.append(f"Se ignoró el nivel «{nivel_extra}» del {dim_extra}: "
                          f"los niveles válidos son {', '.join(validos[:-1])} y {validos[-1]}.")
            nivel_extra = ex["inicial"]
        estado[ex["param"]] = nivel_extra
    for nombre in vista["filtros"]:
        if nombre in FILTROS_UNICOS:
            estado[nombre] = uno(nombre)
    return estado, avisos


def _olap_url(vista, estado, **cambios):
    """URL canónica de un estado: cada selección tiene su propia dirección (solo se escriben valores no iniciales)."""
    e = {**estado, **cambios}
    params = {}
    if e["familia"] != vista.get("familia_inicial", FAMILIA_INICIAL):
        params["familia"] = e["familia"]
    for nombre in vista["filtros"]:
        if nombre in FILTROS_UNICOS and e[nombre]:
            params[nombre] = e[nombre]
    if e["anio"]:
        params["anio"] = e["anio"]
    if e["nivel"] != vista["niveles"][0]:
        params["nivel"] = e["nivel"]
    for ex in _extras(vista):
        if e[ex["param"]] != ex["inicial"]:
            params[ex["param"]] = e[ex["param"]]
    if e["pivot"]:
        params["pivot"] = "1"
    return url_for(vista["endpoint"], **params)


def _olap_filtros(vista, estado):
    """Estado -> filtros para olap.py ({nombre: [valores]})."""
    filtros = {"familia": [] if estado["familia"] == TODAS else [estado["familia"]], "anio": estado["anio"]}
    for nombre in vista["filtros"]:
        if nombre in FILTROS_UNICOS:
            filtros[nombre] = [estado[nombre]] if estado[nombre] else []
    return filtros


def _olap_operacion(vista, estado):
    """Nombre de la operación que describe los filtros de análisis (tiempo y la dimensión de la vista)."""
    valores = {}
    if vista.get("tiempo", True):
        valores["tiempo"] = ([estado["periodo"]] if estado["periodo"] else []) + estado["anio"]
    for dim in _dimensiones(vista):
        valores[dim] = [estado[n] for n in vista["filtros"] if olap.FILTROS[n][1] == dim and estado[n]]
    if vista.get("familia_analisis") and estado["familia"] != TODAS:
        valores["combustible"] = [estado["familia"]] + valores.get("combustible", [])
    activas = {d: v for d, v in valores.items() if v}
    if not activas:
        return "Sin filtros de análisis", vista["texto_todo"]
    if len(activas) >= 2:
        nombres = [ETIQUETA_DIMENSION[d] for d in activas]
        return "Dice", f"Filtros combinados en las dimensiones {', '.join(nombres[:-1])} y {nombres[-1]}."
    (d, vals), = activas.items()
    if len(vals) == 1:
        return "Slice", f"Un solo valor de la dimensión {ETIQUETA_DIMENSION[d]}."
    return "Filtro en una dimensión", f"Varios valores de la dimensión {ETIQUETA_DIMENSION[d]}."


def _olap_contexto(vista, con, args):
    """Flujo común de una vista OLAP. Devuelve (url_de_redirección, None) o (None, contexto para la plantilla)."""
    perm = olap.valores_permitidos(con)
    estado, avisos = _olap_leer_estado(vista, args, perm)
    unicos = [n for n in vista["filtros"] if n in FILTROS_UNICOS]

    def url(base=None, **cambios):
        return _olap_url(vista, estado if base is None else base, **cambios)

    # Slice: un solo valor de una dimensión de análisis. Se quitan los demás filtros de análisis
    # y se redirige a la URL canónica de esa selección.
    if "slice" in args:
        dim, _, valor = args.get("slice", "").partition(":")
        limpio = {**estado, "anio": [], **{n: "" for n in unicos}}
        if vista.get("familia_analisis"):
            limpio["familia"] = TODAS
            if dim == "familia" and valor in perm["familia"]:
                return url(limpio, familia=valor), None
        if dim == "anio" and valor.isdigit() and int(valor) in perm["anio"]:
            return url(limpio, anio=[int(valor)]), None
        if dim in unicos and _permitido(perm, dim, valor) is not None:
            return url(limpio, **{dim: _permitido(perm, dim, valor)}), None
        avisos.append("Se ignoró el slice elegido: la dimensión o el valor no son válidos.")

    # Años visibles: los del periodo y los años elegidos (si hay). Son el eje temporal de la vista.
    anios = [a for a in perm["anio"]
             if (not estado.get("periodo") or perm["periodo_de_anio"][a] == estado["periodo"])
             and (not estado["anio"] or a in estado["anio"])]

    filtros = _olap_filtros(vista, estado)
    cubo = olap.consultar(con, filtros, estado["nivel"], anios) if anios else None
    niveles_rollup = tuple(vista["niveles"]) + tuple(n for ex in _extras(vista) for n in ex["niveles"])
    rollup = {n: olap.total_por_nivel(con, filtros, n) for n in niveles_rollup} if cubo else None

    niveles = vista["niveles"]
    i = niveles.index(estado["nivel"])
    siguiente = niveles[i + 1] if i + 1 < len(niveles) else None
    anterior = niveles[i - 1] if i > 0 else None

    # Drill-down sobre un miembro: se filtra ese miembro y se baja un nivel.
    def url_drill_miembro(llave):
        filtro = FILTRO_DE_NIVEL.get(estado["nivel"])
        if filtro is None or siguiente is None:
            return None
        return url(**{filtro: llave[0], "nivel": siguiente})

    # Filtros activos, cada uno con la URL que lo quita.
    familia_inicial = vista.get("familia_inicial", FAMILIA_INICIAL)
    activos = [("Familia de combustible",
                "Todas" if estado["familia"] == TODAS else estado["familia"],
                url(familia=TODAS) if estado["familia"] != TODAS else None)]
    for nombre in vista["filtros"]:
        etiqueta = olap.FILTROS[nombre][2]
        if nombre == "anio":
            if estado["anio"]:
                activos.append((etiqueta, ", ".join(map(str, estado["anio"])), url(anio=[])))
        elif estado[nombre]:
            activos.append((etiqueta, estado[nombre], url(**{nombre: ""})))

    # Opciones del slice (un valor de una dimensión) y campos del dice (filtros combinados).
    slice_grupos = []
    if vista.get("familia_analisis"):
        slice_grupos.append(("Combustible · familia", "familia", perm["familia"]))
    for nombre in vista["filtros"]:
        _, dim, etiqueta = olap.FILTROS[nombre]
        titulo = f"{ETIQUETA_DIMENSION[dim].capitalize()} · {NOMBRE_NIVEL.get(nombre, etiqueta.split(' ')[0].lower())}"
        slice_grupos.append((titulo, nombre, perm[nombre]))
    # Campos del dice: pares (superior, inferior agrupado); cualquiera de los dos puede faltar (None).
    dice_pares = []
    entradas = vista["dice"] if isinstance(vista["dice"], list) else [vista["dice"]]
    for superior, inferior, grupos in entradas:
        dice_pares.append(((superior, olap.FILTROS[superior][2], perm[superior]) if superior else None,
                           (inferior, olap.FILTROS[inferior][2], perm[grupos]) if inferior else None))
    dims_slice = (["tiempo"] if vista.get("tiempo", True) else []) + [ETIQUETA_DIMENSION[d] for d in _dimensiones(vista)]

    # Jerarquías adicionales: drill-down y roll-up propios.
    jerarquias_extra = []
    for ex in _extras(vista):
        orden, param = ex["niveles"], ex["param"]
        j = orden.index(estado[param])
        jerarquias_extra.append({
            "niveles": orden,
            "param": param,
            "inicial": ex["inicial"],
            "dimension": ETIQUETA_DIMENSION[ex["dimension"]],
            "nivel": estado[param],
            "nivel_siguiente": orden[j + 1] if j + 1 < len(orden) else None,
            "nivel_anterior": orden[j - 1] if j > 0 else None,
            "url_drill": url(**{param: orden[j + 1]}) if j + 1 < len(orden) else None,
            "url_rollup": url(**{param: orden[j - 1]}) if j > 0 else None,
        })

    return None, {
        "perm": perm,
        "estado": estado,
        "avisos": avisos,
        "anios": anios,
        "filtros": filtros,
        "cubo": cubo,
        "rollup": rollup,
        "activos": activos,
        "operacion": _olap_operacion(vista, estado),
        "niveles": olap.NIVELES,
        "orden_niveles": niveles,
        "vista": vista,
        "endpoint": vista["endpoint"],
        "url_drill": url(nivel=siguiente) if siguiente else None,
        "url_rollup": url(nivel=anterior) if anterior else None,
        "url_pivot": url(pivot=not estado["pivot"]),
        "url_limpiar": url({**estado, "familia": familia_inicial, "anio": [], "nivel": niveles[0], "pivot": False,
                            **{ex["param"]: ex["inicial"] for ex in _extras(vista)},
                            **{n: "" for n in unicos}}),
        "url_drill_miembro": url_drill_miembro,
        "nivel_siguiente": siguiente,
        "nivel_anterior": anterior,
        "todas": TODAS,
        "familia_inicial": familia_inicial,
        "slice_grupos": slice_grupos,
        "slice_dimensiones": ", ".join(dims_slice[:-1]) + " y " + dims_slice[-1],
        "dice_pares": dice_pares,
        "niveles_rollup": niveles_rollup,
        "niveles_activos": [estado["nivel"]] + [j["nivel"] for j in jerarquias_extra],
        "jerarquias_extra": jerarquias_extra,
    }


def _olap_error(plantilla, pregunta, exc):
    """Página de la vista con un aviso cuando el modelo estrella no se puede abrir."""
    return render_template(plantilla, active="multidimensional", q=pregunta,
                           error_modelo=f"No se pudo abrir el modelo estrella: {exc}")


# --- Vista P1: tendencia de los eléctricos y tipos de vehículo ---------------

# Cifras citadas en los conocimientos de P1: (conocimiento, cifra, valor del texto, decimales con que se cita).
# Cada una se compara en cada carga con el valor recalculado desde el modelo (_p1_conocimientos).
P1_CIFRAS_TEXTO = [
    (1, "Eléctricos registrados en 2019", 3242, 0),
    (1, "Eléctricos registrados en 2024", 11298, 0),
    (1, "Aumento de eléctricos 2019 → 2024", 8056, 0),
    (1, "Aumento de camionetas 2019 → 2024", 5724, 0),
    (1, "Participación de camionetas 2019 (%)", 2.28, 2),
    (1, "Participación de camionetas 2024 (%)", 51.32, 2),
    (1, "Aumento de automóviles 2019 → 2024", 2564, 0),
    (1, "Cambio de ciclomotores 2019 → 2024", -795, 0),
    (1, "Participación de ciclomotores 2019 (%)", 69.90, 2),
    (1, "Participación de ciclomotores 2024 (%)", 13.02, 2),
    (1, "Camionetas eléctricas 2024", 5798, 0),
    (1, "Camionetas wagon 2024", 5435, 0),
    (1, "Participación de wagon en camionetas 2024 (%)", 93.74, 2),
    (2, "Buses eléctricos 2022", 1006, 0),
    (2, "Participación de buses en eléctricos 2022 (%)", 16.74, 2),
    (2, "Buses eléctricos 2022 en Bogotá", 998, 0),
    (2, "Variación 2022 con buses (%)", 49.4, 1),
    (2, "Variación 2023 con buses (%)", 4.5, 1),
    (2, "Variación 2022 sin buses (%)", 27.6, 1),
    (2, "Variación 2023 sin buses (%)", 25.4, 1),
]
P1_K2_ANIOS = [2021, 2022, 2023, 2024]


def _p1_conocimientos(con):
    """Recalcula desde el modelo las cifras de los conocimientos de P1 y las compara con el texto."""
    electrico = {"familia": [P1_FAMILIA_INICIAL]}

    # Conocimiento 1: clases 2019 vs 2024 y carrocerías de CAMIONETA en 2024.
    k1 = olap.consultar(con, {**electrico, "anio": [2019, 2024]}, "clase", [2019, 2024])
    anual = {s["anio"]: s["vehiculos"] for s in k1["serie"]}

    def clase(nombre, anio):
        return k1["celdas"].get(((nombre,), anio), 0)

    camionetas = olap.consultar(con, {**electrico, "anio": [2024], "clase": ["CAMIONETA"]}, "carroceria", [2024])
    wagon = next((m["vehiculos"] for m in camionetas["composicion"] if m["llave"] == ("CAMIONETA", "WAGON")), 0)

    # Conocimiento 2: serie con buses, sin buses (NOT IN BUS) y solo buses; territorio de los buses de 2022.
    con_buses = olap.serie_anual(con, electrico, P1_K2_ANIOS)
    sin_buses = olap.serie_anual(con, electrico, P1_K2_ANIOS, excluir={"clase": ["BUS"]})
    buses = olap.serie_anual(con, {**electrico, "clase": ["BUS"]}, P1_K2_ANIOS)
    territorios_buses = olap.por_territorio(con, {**electrico, "clase": ["BUS"], "anio": [2022]}, limite=3)
    k2_tabla = [
        {"anio": c["anio"], "con": c["vehiculos"], "pct_con": c["pct"], "buses": b["vehiculos"],
         "sin": s["vehiculos"], "pct_sin": s["pct"]}
        for c, s, b in zip(con_buses, sin_buses, buses)
    ]
    por_anio = {fila["anio"]: fila for fila in k2_tabla}
    bogota = next((t["vehiculos"] for t in territorios_buses if t["departamento"] == "BOGOTA D.C."), 0)

    modelo = [
        anual[2019], anual[2024], anual[2024] - anual[2019],
        clase("CAMIONETA", 2024) - clase("CAMIONETA", 2019),
        clase("CAMIONETA", 2019) / anual[2019] * 100 if anual[2019] else None,
        clase("CAMIONETA", 2024) / anual[2024] * 100 if anual[2024] else None,
        clase("AUTOMOVIL", 2024) - clase("AUTOMOVIL", 2019),
        clase("CICLOMOTOR", 2024) - clase("CICLOMOTOR", 2019),
        clase("CICLOMOTOR", 2019) / anual[2019] * 100 if anual[2019] else None,
        clase("CICLOMOTOR", 2024) / anual[2024] * 100 if anual[2024] else None,
        camionetas["vehiculos"], wagon,
        wagon / camionetas["vehiculos"] * 100 if camionetas["vehiculos"] else None,
        por_anio[2022]["buses"],
        por_anio[2022]["buses"] / por_anio[2022]["con"] * 100 if por_anio[2022]["con"] else None,
        bogota,
        por_anio[2022]["pct_con"], por_anio[2023]["pct_con"],
        por_anio[2022]["pct_sin"], por_anio[2023]["pct_sin"],
    ]
    comprobaciones = [
        {"k": k, "cifra": cifra, "texto": texto, "decimales": dec, "modelo": valor,
         "ok": valor is not None and round(valor, dec) == texto}
        for (k, cifra, texto, dec), valor in zip(P1_CIFRAS_TEXTO, modelo)
    ]
    return {
        "k2_tabla": k2_tabla,
        "k2": por_anio,
        "territorios_buses": territorios_buses,
        "comprobaciones": comprobaciones,
        "todas_ok": all(c["ok"] for c in comprobaciones),
    }


@app.route("/analisis-multidimensional/p1")
def analisis_p1():
    pregunta = MODELO_PREGUNTAS[0]
    try:
        con = olap.conectar()
    except (FileNotFoundError, sqlite3.Error) as exc:
        return _olap_error("etapa5/p1.html", pregunta, exc)

    with closing(con):
        destino, ctx = _olap_contexto(VISTAS_OLAP["p1"], con, request.args)
        if destino:
            return redirect(destino)
        conocimientos = _p1_conocimientos(con)

    return render_template(
        "etapa5/p1.html",
        active="multidimensional",
        q=pregunta,
        error_modelo=None,
        kc=conocimientos,
        k_urls={
            "k1_clases": url_for("analisis_p1", anio=[2019, 2024], nivel="clase"),
            "k1_camioneta": url_for("analisis_p1", clase="CAMIONETA", anio=[2024], nivel="carroceria"),
            "k2_clases": url_for("analisis_p1", anio=P1_K2_ANIOS, nivel="clase"),
            "k2_buses": url_for("analisis_p1", clase="BUS", anio=P1_K2_ANIOS),
        },
        **ctx,
    )


# --- Vista P2: homogeneidad territorial del crecimiento ----------------------

P2_BASE_PEQUENA = 30   # con menos vehículos en el año anterior, la variación % se marca «base pequeña»
P2_TOP_LINEAS = 5      # territorios en la gráfica de líneas
P2_TOP_BARRAS = 10     # territorios en la gráfica de variación
P2_K_ANIOS = [2021, 2024]
P2_BOGOTA = "BOGOTA D.C."
P2_UMBRAL_POCOS = 10   # «menos de 10 eléctricos» en el conocimiento 2

# Cifras citadas en los conocimientos de P2: (conocimiento, cifra, valor del texto, decimales con que se cita).
# Cada una se compara en cada carga con el valor recalculado desde el modelo (_p2_conocimientos).
P2_CIFRAS_TEXTO = [
    (1, "Eléctricos registrados en 2021", 4022, 0),
    (1, "Eléctricos registrados en 2024", 11298, 0),
    (1, "Aumento de eléctricos 2021 → 2024", 7276, 0),
    (1, "Eléctricos de Bogotá 2021", 571, 0),
    (1, "Eléctricos de Bogotá 2024", 5381, 0),
    (1, "Aumento de Bogotá 2021 → 2024", 4810, 0),
    (1, "Parte del aumento nacional aportada por Bogotá (%)", 66.11, 2),
    (1, "Participación de Bogotá 2021 (%)", 14.2, 1),
    (1, "Participación de Bogotá 2024 (%)", 47.6, 1),
    (1, "Resto del país 2021", 3451, 0),
    (1, "Resto del país 2024", 5917, 0),
    (1, "Resto del país: 2024 ÷ 2021 (veces)", 1.71, 2),
    (2, "Aumento de Antioquia 2021 → 2024", 829, 0),
    (2, "Aumento de Medellín 2021 → 2024", 630, 0),
    (2, "Parte del aumento de Antioquia aportada por Medellín (%)", 76.0, 1),
    (2, "Eléctricos de Bello 2021", 87, 0),
    (2, "Eléctricos de Bello 2024", 12, 0),
    (2, "Cambio de Bello 2021 → 2024", -75, 0),
    (2, "Cambio de La Estrella 2021 → 2024", -18, 0),
    (2, "Cambio de Sabaneta 2021 → 2024", -15, 0),
    (2, "Aumento de Cundinamarca 2021 → 2024", 868, 0),
    (2, "Aumento de Funza, Chía y Mosquera 2021 → 2024", 774, 0),
    (2, "Parte del aumento de Cundinamarca aportada por Funza, Chía y Mosquera (%)", 89.2, 1),
    (2, "Territorios con menos de 10 eléctricos en 2024", 91, 0),
    (2, "Territorios con eléctricos en 2024", 140, 0),
]


def _p2_conocimientos(con):
    """Recalcula desde el modelo las cifras de los conocimientos de P2 y las compara con el texto."""
    electrico = {"familia": [FAMILIA_INICIAL]}
    a0, a1 = P2_K_ANIOS

    # Conocimiento 1: departamentos 2021 vs 2024.
    dep = olap.consultar(con, {**electrico, "anio": P2_K_ANIOS}, "departamento", P2_K_ANIOS)
    nac = {s["anio"]: s["vehiculos"] for s in dep["serie"]}
    bog = {a: dep["celdas"].get(((P2_BOGOTA,), a), 0) for a in P2_K_ANIOS}
    aumento_nac = nac[a1] - nac[a0]
    resto = {a: nac[a] - bog[a] for a in P2_K_ANIOS}

    # Conocimiento 2: drill-down a municipio en Antioquia y Cundinamarca; territorios de 2024.
    def municipios(departamento):
        cubo = olap.consultar(con, {**electrico, "anio": P2_K_ANIOS, "departamento": [departamento]},
                              "municipio", P2_K_ANIOS)
        tot = {s["anio"]: s["vehiculos"] for s in cubo["serie"]}

        def valor(municipio, anio):
            return cubo["celdas"].get(((f"{municipio} ({departamento})",), anio), 0)

        def cambio(municipio):
            return valor(municipio, a1) - valor(municipio, a0)
        return tot[a1] - tot[a0], cambio, valor

    ant, cambio_ant, valor_ant = municipios("ANTIOQUIA")
    cun, cambio_cun, _ = municipios("CUNDINAMARCA")
    tres_cun = sum(cambio_cun(m) for m in ("FUNZA", "CHIA", "MOSQUERA"))
    mun_2024 = olap.consultar(con, {**electrico, "anio": [a1]}, "municipio", [a1])
    pocos = sum(1 for m in mun_2024["composicion"] if m["vehiculos"] < P2_UMBRAL_POCOS)

    modelo = [
        nac[a0], nac[a1], aumento_nac,
        bog[a0], bog[a1], bog[a1] - bog[a0],
        (bog[a1] - bog[a0]) / aumento_nac * 100 if aumento_nac else None,
        bog[a0] / nac[a0] * 100 if nac[a0] else None,
        bog[a1] / nac[a1] * 100 if nac[a1] else None,
        resto[a0], resto[a1],
        resto[a1] / resto[a0] if resto[a0] else None,
        ant, cambio_ant("MEDELLIN"),
        cambio_ant("MEDELLIN") / ant * 100 if ant else None,
        valor_ant("BELLO", a0), valor_ant("BELLO", a1), cambio_ant("BELLO"),
        cambio_ant("LA ESTRELLA"), cambio_ant("SABANETA"),
        cun, tres_cun,
        tres_cun / cun * 100 if cun else None,
        pocos, mun_2024["territorios"],
    ]
    comprobaciones = [
        {"k": k, "cifra": cifra, "texto": texto, "decimales": dec, "modelo": valor,
         "ok": valor is not None and round(valor, dec) == texto}
        for (k, cifra, texto, dec), valor in zip(P2_CIFRAS_TEXTO, modelo)
    ]
    return {
        "comprobaciones": comprobaciones,
        "todas_ok": all(c["ok"] for c in comprobaciones),
    }


@app.route("/analisis-multidimensional/p2")
def analisis_p2():
    pregunta = MODELO_PREGUNTAS[1]
    try:
        con = olap.conectar()
    except (FileNotFoundError, sqlite3.Error) as exc:
        return _olap_error("etapa5/p2.html", pregunta, exc)

    with closing(con):
        destino, ctx = _olap_contexto(VISTAS_OLAP["p2"], con, request.args)
        if destino:
            return redirect(destino)
        conocimientos = _p2_conocimientos(con)

    cubo, anios = ctx["cubo"], ctx["anios"]
    p2 = None
    if cubo and cubo["vehiculos"]:
        def celda(llave, anio):
            return cubo["celdas"].get((llave, anio), 0)

        # Variación de cada año frente al año anterior de la selección (la columna anterior de la matriz).
        pares = list(zip(anios, anios[1:]))
        variaciones = {
            (m["llave"], anio): olap.variacion(celda(m["llave"], previo), celda(m["llave"], anio), P2_BASE_PEQUENA)
            for m in cubo["composicion"] for previo, anio in pares
        }
        totales = {s["anio"]: s["vehiculos"] for s in cubo["serie"]}
        variacion_total = {anio: olap.variacion(totales[previo], totales[anio], P2_BASE_PEQUENA)
                           for previo, anio in pares}

        # Líneas: los territorios con más vehículos en la selección.
        lineas = [{"miembro": m["miembro"], "datos": [celda(m["llave"], a) for a in anios]}
                  for m in cubo["composicion"][:P2_TOP_LINEAS]]

        # Barras: variación del último año frente al anterior; los de base 0 se listan aparte («no definido»).
        barras, sin_definir = [], []
        if pares:
            for m in cubo["composicion"][:P2_TOP_BARRAS]:
                v = variaciones[(m["llave"], anios[-1])]
                (barras if v["pct"] is not None else sin_definir).append({"miembro": m["miembro"], **v})

        p2 = {
            "variaciones": variaciones,
            "variacion_total": variacion_total,
            "lineas": lineas,
            "barras": barras,
            "sin_definir": sin_definir,
            "anio_final": anios[-1],
            "anio_previo": anios[-2] if pares else None,
        }

    return render_template(
        "etapa5/p2.html",
        active="multidimensional",
        q=pregunta,
        error_modelo=None,
        p2=p2,
        kc=conocimientos,
        k_urls={
            "k1_departamentos": url_for("analisis_p2", anio=P2_K_ANIOS),
            "k2_antioquia": url_for("analisis_p2", departamento="ANTIOQUIA", anio=P2_K_ANIOS, nivel="municipio"),
            "k2_cundinamarca": url_for("analisis_p2", departamento="CUNDINAMARCA", anio=P2_K_ANIOS, nivel="municipio"),
        },
        base_pequena=P2_BASE_PEQUENA,
        top_lineas=P2_TOP_LINEAS,
        top_barras=P2_TOP_BARRAS,
        **ctx,
    )


# --- Vista P3: distribución por tipo de vehículo y año del modelo -----------

P3_TOP_APILADAS = 7    # tipos de vehículo con serie propia en las barras apiladas (el resto se agrupa en «Otros»)
P3_K_ANIOS = [2019, 2024]
P3_K2_CLASES = ["CAMIONETA", "AUTOMOVIL", "CICLOMOTOR"]   # clases citadas en el conocimiento 2

# Cifras citadas en los conocimientos de P3: (conocimiento, cifra, valor del texto, decimales con que se cita).
# Cada una se compara en cada carga con el valor recalculado desde el modelo (_p3_conocimientos).
P3_CIFRAS_TEXTO = [
    (1, "Participación de Liviano 2019 (%)", 51.5, 1),
    (1, "Participación de Liviano 2024 (%)", 95.6, 1),
    (1, "Camionetas 2019", 1367, 0),
    (1, "Participación de camionetas 2019 (%)", 25.2, 1),
    (1, "Camionetas 2024", 39121, 0),
    (1, "Participación de camionetas 2024 (%)", 72.5, 1),
    (1, "Ciclomotores 2019", 2266, 0),
    (1, "Participación de ciclomotores 2019 (%)", 41.7, 1),
    (1, "Ciclomotores 2024", 1471, 0),
    (1, "Participación de ciclomotores 2024 (%)", 2.7, 1),
    (1, "Camionetas wagon 2024", 38425, 0),
    (1, "Participación de wagon en camionetas 2024 (%)", 98.2, 1),
    (2, "% con modelo ≥ año de registro 2024", 93.2, 1),
    (2, "Vehículos con modelo ≥ año de registro 2024", 50250, 0),
    (2, "Vehículos registrados 2024", 53934, 0),
    (2, "Vehículos con modelo anterior 2024", 3684, 0),
    (2, "% con modelo ≥ año de registro: camionetas 2024", 95.3, 1),
    (2, "% con modelo ≥ año de registro: automóviles 2024", 96.7, 1),
    (2, "% con modelo ≥ año de registro: ciclomotores 2019", 91.9, 1),
    (2, "% con modelo ≥ año de registro: ciclomotores 2024", 39.6, 1),
    (2, "Ciclomotores con modelo ≥ año de registro 2024", 582, 0),
    (2, "Ciclomotores registrados 2024", 1471, 0),
]


def _p3_conocimientos(con):
    """Recalcula desde el modelo las cifras de los conocimientos de P3 y las compara con el texto."""
    todos = {"familia": [], "anio": P3_K_ANIOS}
    a0, a1 = P3_K_ANIOS

    # Conocimiento 1: categorías y clases 2019 vs 2024; carrocerías de CAMIONETA en 2024.
    cat = olap.consultar(con, todos, "categoria", P3_K_ANIOS)
    cla = olap.consultar(con, todos, "clase", P3_K_ANIOS)
    tot = {s["anio"]: s["vehiculos"] for s in cat["serie"]}

    def celda(cubo, miembro, anio):
        return cubo["celdas"].get(((miembro,), anio), 0)

    def pct(cubo, miembro, anio):
        return celda(cubo, miembro, anio) / tot[anio] * 100 if tot[anio] else None

    camionetas = olap.consultar(con, {"familia": [], "anio": [a1], "clase": ["CAMIONETA"]}, "carroceria", [a1])
    wagon = next((m["vehiculos"] for m in camionetas["composicion"] if m["llave"] == ("CAMIONETA", "WAGON")), 0)

    # Conocimiento 2: % con modelo ≥ año de registro, en total y por clase.
    def reciente(clase=None):
        filtros = {**todos, **({"clase": [clase]} if clase else {})}
        return {s["anio"]: s for s in olap.modelo_reciente(con, filtros, P3_K_ANIOS)["serie"]}

    general = reciente()
    por_clase = {c: reciente(c) for c in P3_K2_CLASES}
    k2_tabla = [{"miembro": "Todas las clases", **{a: general[a] for a in P3_K_ANIOS}}] + [
        {"miembro": c, **{a: por_clase[c][a] for a in P3_K_ANIOS}} for c in P3_K2_CLASES
    ]

    modelo = [
        pct(cat, "Liviano", a0), pct(cat, "Liviano", a1),
        celda(cla, "CAMIONETA", a0), pct(cla, "CAMIONETA", a0),
        celda(cla, "CAMIONETA", a1), pct(cla, "CAMIONETA", a1),
        celda(cla, "CICLOMOTOR", a0), pct(cla, "CICLOMOTOR", a0),
        celda(cla, "CICLOMOTOR", a1), pct(cla, "CICLOMOTOR", a1),
        wagon, wagon / camionetas["vehiculos"] * 100 if camionetas["vehiculos"] else None,
        general[a1]["pct"], general[a1]["recientes"], general[a1]["vehiculos"],
        general[a1]["vehiculos"] - general[a1]["recientes"],
        por_clase["CAMIONETA"][a1]["pct"], por_clase["AUTOMOVIL"][a1]["pct"],
        por_clase["CICLOMOTOR"][a0]["pct"], por_clase["CICLOMOTOR"][a1]["pct"],
        por_clase["CICLOMOTOR"][a1]["recientes"], por_clase["CICLOMOTOR"][a1]["vehiculos"],
    ]
    comprobaciones = [
        {"k": k, "cifra": cifra, "texto": texto, "decimales": dec, "modelo": valor,
         "ok": valor is not None and round(valor, dec) == texto}
        for (k, cifra, texto, dec), valor in zip(P3_CIFRAS_TEXTO, modelo)
    ]
    return {
        "totales": tot,
        "k2_tabla": k2_tabla,
        "comprobaciones": comprobaciones,
        "todas_ok": all(c["ok"] for c in comprobaciones),
    }


@app.route("/analisis-multidimensional/p3")
def analisis_p3():
    pregunta = MODELO_PREGUNTAS[2]
    vista = VISTAS_OLAP["p3"]
    try:
        con = olap.conectar()
    except (FileNotFoundError, sqlite3.Error) as exc:
        return _olap_error("etapa5/p3.html", pregunta, exc)

    with closing(con):
        destino, ctx = _olap_contexto(vista, con, request.args)
        if destino:
            return redirect(destino)

        cubo, anios, estado = ctx["cubo"], ctx["anios"], ctx["estado"]
        hay_datos = bool(cubo and cubo["vehiculos"])
        if hay_datos:
            reciente = olap.modelo_reciente(con, ctx["filtros"], anios)
            por_modelo = olap.por_modelo(con, ctx["filtros"], estado["nivel_modelo"])
        conocimientos = _p3_conocimientos(con)

    p3 = None
    if hay_datos:
        totales = {s["anio"]: s["vehiculos"] for s in cubo["serie"]}

        def celda(llave, anio):
            return cubo["celdas"].get((llave, anio), 0)

        # Participación % dentro de cada año de registro (denominador: total de ese año).
        pct_anio = {
            (m["llave"], a): (celda(m["llave"], a) / totales[a] * 100 if totales[a] else None)
            for m in cubo["composicion"] for a in anios
        }

        # Barras apiladas al 100 %: los tipos con más vehículos y el resto en «Otros».
        principales = cubo["composicion"][:P3_TOP_APILADAS]
        apiladas = [{"miembro": m["miembro"], "datos": [pct_anio[(m["llave"], a)] for a in anios]}
                    for m in principales]
        resto = cubo["composicion"][P3_TOP_APILADAS:]
        if resto:
            apiladas.append({
                "miembro": f"Otros ({len(resto)} tipos)",
                "datos": [sum(celda(m["llave"], a) for m in resto) / totales[a] * 100 if totales[a] else None
                          for a in anios],
            })

        # Barras por año del modelo; drill-down de un rango a sus años del modelo.
        en_rango = estado["nivel_modelo"] == "rango_modelo"
        barras_modelo = [
            {**b, "miembro": str(b["miembro"]), "pct": b["vehiculos"] / cubo["vehiculos"] * 100,
             "drill": _olap_url(vista, estado, rango_modelo=b["miembro"], nivel_modelo="anio_modelo") if en_rango else None}
            for b in por_modelo
        ]

        p3 = {
            "totales": totales,
            "pct_anio": pct_anio,
            "apiladas": apiladas,
            "barras_modelo": barras_modelo,
            "reciente": reciente,
            "reciente_por_anio": {s["anio"]: s for s in reciente["serie"]},
        }

    return render_template(
        "etapa5/p3.html",
        active="multidimensional",
        q=pregunta,
        error_modelo=None,
        p3=p3,
        kc=conocimientos,
        k_urls={
            "k1_categorias": url_for("analisis_p3", anio=P3_K_ANIOS),
            "k1_clases": url_for("analisis_p3", anio=P3_K_ANIOS, nivel="clase"),
            "k1_camioneta": url_for("analisis_p3", clase="CAMIONETA", anio=[2024], nivel="carroceria"),
            "k2_clases": url_for("analisis_p3", anio=P3_K_ANIOS, nivel="clase"),
            "k2_por_clase": [(c, url_for("analisis_p3", clase=c, anio=P3_K_ANIOS, nivel="clase"))
                             for c in P3_K2_CLASES],
        },
        top_apiladas=P3_TOP_APILADAS,
        **ctx,
    )


# --- Vista P4: promedio, mediana y concentración por territorio -------------

P4_TOP = 5   # territorios del indicador de concentración


@app.route("/analisis-multidimensional/p4")
def analisis_p4():
    pregunta = MODELO_PREGUNTAS[3]
    vista = VISTAS_OLAP["p4"]
    try:
        con = olap.conectar()
    except (FileNotFoundError, sqlite3.Error) as exc:
        return _olap_error("etapa5/p4.html", pregunta, exc)

    with closing(con):
        destino, ctx = _olap_contexto(vista, con, request.args)
        if destino:
            return redirect(destino)

        cubo, estado, filtros = ctx["cubo"], ctx["estado"], ctx["filtros"]
        nv, nc, nt = estado["nivel"], estado["nivel_combustible"], estado["nivel_territorio"]
        hay_datos = bool(cubo and cubo["vehiculos"])
        if hay_datos:
            # Totales de cada territorio del nivel elegido: en la selección, por grupo de vehículo,
            # por grupo de combustible y por celda de la matriz.
            general = olap.totales_por_territorio(con, filtros, nt).get((), [])
            por_vehiculo = olap.totales_por_territorio(con, filtros, nt, (nv,))
            por_combustible = olap.totales_por_territorio(con, filtros, nt, (nc,))
            por_celda = olap.totales_por_territorio(con, filtros, nt, (nv, nc))

    p4 = None
    if hay_datos:
        resumen = olap.resumen_territorial(general, P4_TOP)

        def grupos(totales, drill=None):
            filas = [{"llave": llave[0], "miembro": llave[0][0], **olap.resumen_territorial(t, P4_TOP)}
                     for llave, t in totales.items()]
            filas.sort(key=lambda f: (-f["vehiculos"], f["miembro"]))
            for f in filas:
                f["drill"] = drill(f["miembro"]) if drill else None
            return filas

        # Drill-down sobre una familia: se filtra esa familia y se baja al nivel combustible.
        drill_familia = ((lambda m: _olap_url(vista, estado, familia=m, nivel_combustible="combustible"))
                         if nc == "familia" else None)
        filas = grupos(por_vehiculo)
        columnas = grupos(por_combustible, drill_familia)
        celdas = {(llave[0], llave[1]): olap.resumen_territorial(t, P4_TOP) for llave, t in por_celda.items()}

        # Curva de concentración: participación acumulada de los territorios ordenados de mayor a menor.
        acumulado, curva = 0, []
        for territorio, veh in general:
            acumulado += veh
            curva.append({"territorio": territorio, "vehiculos": veh, "acumulado": acumulado / resumen["vehiculos"] * 100})

        p4 = {
            "resumen": resumen,
            "top": [{"territorio": t, "vehiculos": v, "pct": v / resumen["vehiculos"] * 100} for t, v in general[:P4_TOP]],
            "filas": filas,
            "columnas": columnas,
            "celdas": celdas,
            "curva": curva,
        }

    return render_template(
        "etapa5/p4.html",
        active="multidimensional",
        q=pregunta,
        error_modelo=None,
        p4=p4,
        top=P4_TOP,
        **ctx,
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