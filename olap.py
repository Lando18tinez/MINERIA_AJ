"""Consultas OLAP de solo lectura sobre el modelo estrella de la Etapa 5.

La base data/modelo/modelo_estrella.db se abre siempre con mode=ro. Las dimensiones, los niveles y los
filtros que se aceptan están en listas cerradas; los valores elegidos por el usuario se pasan a SQLite
solo como parámetros (?), nunca se pegan en el texto de la consulta.

Todas las medidas se recalculan desde hechos_registros en cada consulta. Los vehículos se cuentan con
SUM(cantidad), no contando filas.
"""

import sqlite3
import statistics
from contextlib import closing
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MODELO_DB = RAIZ / "data" / "modelo" / "modelo_estrella.db"

# --- Listas cerradas ---------------------------------------------------------

# Jerarquía de la dimensión vehículo (superior -> inferior). En «carroceria» el miembro hoja es la
# pareja clase-carrocería, porque una misma carrocería aparece en varias clases.
ORDEN_NIVELES = ("categoria", "clase", "carroceria")
NIVELES_VEHICULO = {
    "categoria": {"columnas": ("v.categoria",), "etiqueta": "Categoría"},
    "clase": {"columnas": ("v.clase",), "etiqueta": "Clase"},
    "carroceria": {"columnas": ("v.clase", "v.carroceria"), "etiqueta": "Clase · carrocería"},
}

# Jerarquía de la dimensión territorio (superior -> inferior). En «municipio» el miembro es la llave
# «territorio» («MUNICIPIO (DEPARTAMENTO)»), porque hay municipios homónimos en distintos departamentos.
ORDEN_NIVELES_TERRITORIO = ("departamento", "municipio")
NIVELES_TERRITORIO = {
    "departamento": {"columnas": ("r.departamento",), "etiqueta": "Departamento"},
    "municipio": {"columnas": ("r.territorio",), "etiqueta": "Municipio"},
}

# Jerarquía de la dimensión año del modelo (superior -> inferior).
ORDEN_NIVELES_MODELO = ("rango_modelo", "anio_modelo")
NIVELES_MODELO = {
    "rango_modelo": {"columnas": ("m.rango_modelo",), "etiqueta": "Rango del modelo"},
    "anio_modelo": {"columnas": ("m.anio_modelo",), "etiqueta": "Año del modelo"},
}

# Jerarquía de la dimensión combustible (superior -> inferior). El combustible se identifica por su etiqueta.
ORDEN_NIVELES_COMBUSTIBLE = ("familia", "combustible")
NIVELES_COMBUSTIBLE = {
    "familia": {"columnas": ("c.familia",), "etiqueta": "Familia de combustible"},
    "combustible": {"columnas": ("c.etiqueta",), "etiqueta": "Combustible"},
}

# Todos los niveles que se pueden usar como filas del cubo.
NIVELES = {**NIVELES_VEHICULO, **NIVELES_TERRITORIO, **NIVELES_MODELO, **NIVELES_COMBUSTIBLE}

# Filtros permitidos: nombre -> (columna SQL, dimensión a la que pertenece, etiqueta).
FILTROS = {
    "familia": ("c.familia", "combustible", "Familia de combustible"),
    "combustible": ("c.etiqueta", "combustible", "Combustible"),
    "periodo": ("t.periodo", "tiempo", "Periodo"),
    "anio": ("t.anio", "tiempo", "Año de registro"),
    "categoria": ("v.categoria", "vehiculo", "Categoría"),
    "clase": ("v.clase", "vehiculo", "Clase"),
    "departamento": ("r.departamento", "territorio", "Departamento"),
    "municipio": ("r.territorio", "territorio", "Municipio"),
    "rango_modelo": ("m.rango_modelo", "modelo", "Rango del modelo"),
    "anio_modelo": ("m.anio_modelo", "modelo", "Año del modelo"),
}

_FROM = """
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
"""


def conectar():
    """Abre el modelo estrella en solo lectura. Lanza FileNotFoundError si la base no existe."""
    if not MODELO_DB.is_file():
        raise FileNotFoundError(MODELO_DB)
    return sqlite3.connect(f"{MODELO_DB.as_uri()}?mode=ro", uri=True)


def valores_permitidos(con):
    """Valores válidos de cada filtro, leídos de las dimensiones (la lista cerrada de valores)."""
    def columna(sql):
        return [fila[0] for fila in con.execute(sql)]

    categorias = columna("SELECT DISTINCT categoria FROM dim_vehiculo ORDER BY categoria")
    clases_por_categoria = []
    for cat in categorias:
        clases = [fila[0] for fila in con.execute(
            "SELECT DISTINCT clase FROM dim_vehiculo WHERE categoria = ? ORDER BY clase", (cat,))]
        clases_por_categoria.append((cat, clases))

    departamentos = columna("SELECT DISTINCT departamento FROM dim_territorio ORDER BY departamento")
    municipios_por_departamento = []
    for dep in departamentos:
        municipios = [fila[0] for fila in con.execute(
            "SELECT territorio FROM dim_territorio WHERE departamento = ? ORDER BY territorio", (dep,))]
        municipios_por_departamento.append((dep, municipios))

    # Rangos del modelo en orden cronológico (por el primer año del modelo de cada rango).
    rangos = columna("SELECT rango_modelo FROM dim_modelo GROUP BY rango_modelo ORDER BY MIN(anio_modelo)")
    anios_modelo_por_rango = [
        (rango, [fila[0] for fila in con.execute(
            "SELECT anio_modelo FROM dim_modelo WHERE rango_modelo = ? ORDER BY anio_modelo", (rango,))])
        for rango in rangos
    ]

    familias = columna("SELECT DISTINCT familia FROM dim_combustible ORDER BY familia")
    combustibles_por_familia = [
        (fam, [fila[0] for fila in con.execute(
            "SELECT etiqueta FROM dim_combustible WHERE familia = ? ORDER BY etiqueta", (fam,))])
        for fam in familias
    ]

    return {
        "combustible": columna("SELECT etiqueta FROM dim_combustible ORDER BY etiqueta"),
        "combustibles_por_familia": combustibles_por_familia,
        "rango_modelo": rangos,
        "anio_modelo": columna("SELECT anio_modelo FROM dim_modelo ORDER BY anio_modelo"),
        "anios_modelo_por_rango": anios_modelo_por_rango,
        "departamento": departamentos,
        "municipio": columna("SELECT territorio FROM dim_territorio ORDER BY territorio"),
        "municipios_por_departamento": municipios_por_departamento,
        "familia": columna("SELECT DISTINCT familia FROM dim_combustible ORDER BY familia"),
        "periodo": columna("SELECT DISTINCT periodo FROM dim_tiempo ORDER BY periodo"),
        "anio": columna("SELECT anio FROM dim_tiempo ORDER BY anio"),
        "categoria": categorias,
        "clase": columna("SELECT DISTINCT clase FROM dim_vehiculo ORDER BY clase"),
        "clases_por_categoria": clases_por_categoria,
        "periodo_de_anio": dict(con.execute("SELECT anio, periodo FROM dim_tiempo")),
    }


def _where(filtros, excluir=None):
    """Construye el WHERE con marcadores ?.

    «filtros» ({nombre: [valores]}) conserva solo esos valores (IN); «excluir» (mismo formato) los quita
    (NOT IN). Ambos aceptan solo nombres de FILTROS.
    """
    partes, params = [], []
    for operador, condiciones in (("IN", filtros), ("NOT IN", excluir or {})):
        for nombre, valores in condiciones.items():
            if nombre not in FILTROS:
                raise ValueError(f"Filtro no permitido: {nombre}")
            if not valores:
                continue
            columna = FILTROS[nombre][0]
            partes.append(f"{columna} {operador} ({', '.join('?' for _ in valores)})")
            params.extend(valores)
    return (" WHERE " + " AND ".join(partes) if partes else ""), params


def _miembro(fila, nivel):
    """Etiqueta legible de un miembro del nivel."""
    return " · ".join(fila) if nivel == "carroceria" else fila[0]


def total(con, filtros):
    """Vehículos registrados (SUM(cantidad)) y grupos de registro (COUNT(*)) en la selección."""
    where, params = _where(filtros)
    vehiculos, grupos = con.execute(f"SELECT COALESCE(SUM(h.cantidad), 0), COUNT(*) {_FROM}{where}", params).fetchone()
    return vehiculos, grupos


def territorios_distintos(con, filtros):
    """Territorios con al menos un registro en la selección: COUNT(DISTINCT id_territorio). No es aditiva."""
    where, params = _where(filtros)
    return con.execute(f"SELECT COUNT(DISTINCT h.id_territorio) {_FROM}{where}", params).fetchone()[0]


def variacion(anterior, actual, base_minima=30):
    """Variación de «anterior» a «actual».

    Si «anterior» es 0 la variación porcentual no está definida (pct = None). Si es menor que
    «base_minima» se marca como base pequeña: el porcentaje existe, pero es poco estable.
    """
    return {
        "anterior": anterior,
        "actual": actual,
        "absoluta": actual - anterior,
        "pct": (actual - anterior) / anterior * 100 if anterior else None,
        "base_pequena": 0 < anterior < base_minima,
    }


def serie_anual(con, filtros, anios, excluir=None):
    """Vehículos registrados por año y variación % frente al año anterior de la lista.

    «excluir» quita valores de un filtro (por ejemplo {"clase": ["BUS"]} para la serie sin buses).
    """
    where, params = _where(filtros, excluir)
    por_anio = dict(con.execute(f"SELECT t.anio, SUM(h.cantidad) {_FROM}{where} GROUP BY t.anio", params).fetchall())
    serie, previo = [], None
    for anio in anios:
        veh = por_anio.get(anio, 0)
        serie.append({"anio": anio, "vehiculos": veh,
                      "pct": (veh - previo) / previo * 100 if previo else None})
        previo = veh
    return serie


def por_territorio(con, filtros, limite=5):
    """Territorios con más vehículos registrados en la selección (dim_territorio)."""
    if not isinstance(limite, int) or not 1 <= limite <= 50:
        raise ValueError("El límite debe ser un entero entre 1 y 50.")
    where, params = _where(filtros)
    filas = con.execute(
        f"SELECT r.territorio, r.departamento, SUM(h.cantidad) AS veh {_FROM}{where} "
        "GROUP BY r.id_territorio ORDER BY veh DESC, r.territorio LIMIT ?",
        params + [limite],
    ).fetchall()
    return [{"territorio": t, "departamento": d, "vehiculos": v} for t, d, v in filas]


def por_modelo(con, filtros, nivel):
    """Vehículos registrados por miembro de la jerarquía del año del modelo, en orden cronológico."""
    if nivel not in NIVELES_MODELO:
        raise ValueError(f"Nivel no permitido: {nivel}")
    col = NIVELES_MODELO[nivel]["columnas"][0]
    where, params = _where(filtros)
    filas = con.execute(
        f"SELECT {col}, SUM(h.cantidad) {_FROM}{where} GROUP BY {col} ORDER BY MIN(m.anio_modelo)", params
    ).fetchall()
    return [{"miembro": miembro, "vehiculos": veh} for miembro, veh in filas]


def modelo_reciente(con, filtros, anios):
    """Vehículos con año del modelo igual o posterior al año de registro, por año de registro y en total.

    Denominador: los vehículos de ese año de registro (o de toda la selección, en el total).
    """
    where, params = _where(filtros)
    por_anio = {
        anio: (recientes, veh) for anio, recientes, veh in con.execute(
            f"SELECT t.anio, SUM(CASE WHEN m.anio_modelo >= t.anio THEN h.cantidad ELSE 0 END), SUM(h.cantidad) "
            f"{_FROM}{where} GROUP BY t.anio", params)
    }
    serie = []
    for anio in anios:
        recientes, veh = por_anio.get(anio, (0, 0))
        serie.append({"anio": anio, "recientes": recientes, "vehiculos": veh,
                      "pct": recientes / veh * 100 if veh else None})
    recientes = sum(s["recientes"] for s in serie)
    veh = sum(s["vehiculos"] for s in serie)
    return {"serie": serie, "recientes": recientes, "vehiculos": veh, "pct": recientes / veh * 100 if veh else None}


def totales_por_territorio(con, filtros, nivel_territorio, agrupar=()):
    """Vehículos de cada territorio del nivel elegido, dentro de cada grupo.

    agrupar: niveles (de NIVELES, de una columna) que definen los grupos; vacío = un solo grupo, la selección.
    Devuelve {llave del grupo: [(territorio, vehículos), ...]} con los territorios de mayor a menor. La llave
    es una tupla con la llave de cada nivel (como en consultar), por ejemplo (("CAMIONETA",), ("Eléctrico",)).
    Solo aparecen los territorios con al menos un vehículo en el grupo.
    """
    if nivel_territorio not in NIVELES_TERRITORIO:
        raise ValueError(f"Nivel no permitido: {nivel_territorio}")
    for n in agrupar:
        if n not in NIVELES or len(NIVELES[n]["columnas"]) != 1:
            raise ValueError(f"Nivel no permitido para agrupar: {n}")
    cols_grupo = [NIVELES[n]["columnas"][0] for n in agrupar]
    col_ter = NIVELES_TERRITORIO[nivel_territorio]["columnas"][0]
    cols = ", ".join(cols_grupo + [col_ter])
    where, params = _where(filtros)
    grupos = {}
    for fila in con.execute(
        f"SELECT {cols}, SUM(h.cantidad) AS veh {_FROM}{where} GROUP BY {cols} ORDER BY veh DESC, {col_ter}", params
    ):
        llave = tuple((v,) for v in fila[:len(agrupar)])
        grupos.setdefault(llave, []).append((fila[-2], fila[-1]))
    return grupos


def resumen_territorial(filas, top=5):
    """Promedio, mediana y concentración de los totales por territorio [(territorio, vehículos)] (de mayor a menor).

    Promedio = vehículos / territorios con registros. Participación del top = vehículos de los «top» primeros /
    vehículos del grupo × 100. Ninguna de estas medidas es aditiva.
    """
    valores = [v for _, v in filas]
    total = sum(valores)
    if not valores:
        return {"vehiculos": 0, "territorios": 0, "promedio": None, "mediana": None, "top": top,
                "top_vehiculos": 0, "top_pct": None, "lider": None}
    return {
        "vehiculos": total,
        "territorios": len(valores),
        "promedio": total / len(valores),
        "mediana": statistics.median(valores),
        "top": top,
        "top_vehiculos": sum(valores[:top]),
        "top_pct": sum(valores[:top]) / total * 100,
        "lider": {"territorio": filas[0][0], "vehiculos": filas[0][1], "pct": filas[0][1] / total * 100},
    }


def total_por_nivel(con, filtros, nivel):
    """Suma de los subtotales de un nivel (sirve para comprobar que el roll-up conserva el total)."""
    if nivel not in NIVELES:
        raise ValueError(f"Nivel no permitido: {nivel}")
    cols = ", ".join(NIVELES[nivel]["columnas"])
    where, params = _where(filtros)
    fila = con.execute(
        f"SELECT COALESCE(SUM(sub), 0), COUNT(*) FROM (SELECT SUM(h.cantidad) AS sub {_FROM}{where} GROUP BY {cols})",
        params,
    ).fetchone()
    return {"vehiculos": fila[0], "miembros": fila[1]}


def consultar(con, filtros, nivel, anios):
    """Cubo nivel × año para la selección (el nivel puede ser de vehículo o de territorio).

    filtros: {nombre: [valores]} ya validados.
    nivel:   nivel de NIVELES usado como filas.
    anios:   años de registro que se muestran (columnas de la matriz y eje de la tendencia).
    """
    if nivel not in NIVELES:
        raise ValueError(f"Nivel no permitido: {nivel}")
    cols = NIVELES[nivel]["columnas"]
    lista_cols = ", ".join(cols)
    where, params = _where(filtros)

    vehiculos, grupos = total(con, filtros)

    # Tendencia anual: se completan con 0 los años seleccionados sin registros.
    por_anio = dict(con.execute(f"SELECT t.anio, SUM(h.cantidad) {_FROM}{where} GROUP BY t.anio", params).fetchall())
    serie = [{"anio": a, "vehiculos": por_anio.get(a, 0)} for a in anios]

    # Composición por tipo de vehículo en el nivel actual (denominador: vehículos de la selección).
    composicion = []
    for fila in con.execute(
        f"SELECT {lista_cols}, SUM(h.cantidad) AS veh {_FROM}{where} GROUP BY {lista_cols} ORDER BY veh DESC, {lista_cols}",
        params,
    ):
        llave, veh = tuple(fila[:-1]), fila[-1]
        composicion.append({
            "llave": llave,
            "miembro": _miembro(llave, nivel),
            "vehiculos": veh,
            "pct": veh / vehiculos * 100 if vehiculos else None,
        })

    # Matriz tipo de vehículo × año.
    celdas = {}
    for fila in con.execute(
        f"SELECT {lista_cols}, t.anio, SUM(h.cantidad) {_FROM}{where} GROUP BY {lista_cols}, t.anio", params
    ):
        celdas[(tuple(fila[:-2]), fila[-2])] = fila[-1]

    # Variación entre el primer y el último año seleccionados.
    extremos = None
    if len(anios) >= 2:
        inicial, final = por_anio.get(anios[0], 0), por_anio.get(anios[-1], 0)
        extremos = {
            "anio_inicial": anios[0],
            "anio_final": anios[-1],
            "inicial": inicial,
            "final": final,
            "absoluta": final - inicial,
            "pct": (final - inicial) / inicial * 100 if inicial else None,
        }

    return {
        "vehiculos": vehiculos,
        "grupos": grupos,
        "serie": serie,
        "composicion": composicion,
        "lider": composicion[0] if composicion else None,
        "celdas": celdas,
        "variacion": extremos,
        "territorios": territorios_distintos(con, filtros),
    }
