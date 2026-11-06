"""
Valida el modelo estrella de la Etapa 5 (data/modelo/modelo_estrella.db). Solo lectura: no modifica la base.

Qué hace:
    1. Abre la base en modo de solo lectura y ejecuta sql/02_validaciones.sql (unicidad de llaves,
       correspondencia de claves foráneas, duplicados, NULL y conteo de SIN DATO / SIN CARROCERIA).
    2. Compara el modelo con sus orígenes:
         A. filas y SUM(cantidad)       contra data/powerbi/hechos_vehiculos.csv
         B. vehículos por año           contra data/processed/resultados_conocimiento_evidente.json
         C. vehículos por combustible   contra ese mismo JSON
         D. vehículos por departamento  contra ese mismo JSON
    3. Escribe docs/etapa5/resultados_validacion.md con una tabla por comprobación
       (valor del modelo, valor de origen, diferencia y estado).

Si hay una diferencia, el script la muestra y NO la ajusta. Los vehículos se cuentan con SUM(cantidad).
Solo usa la biblioteca estándar.   Uso:   python validar_modelo.py
"""

import csv
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BASE = RAIZ / "data" / "modelo" / "modelo_estrella.db"
SQL_VALIDACIONES = RAIZ / "sql" / "02_validaciones.sql"
CSV_HECHOS = RAIZ / "data" / "powerbi" / "hechos_vehiculos.csv"
JSON_CIFRAS = RAIZ / "data" / "processed" / "resultados_conocimiento_evidente.json"
INFORME = RAIZ / "docs" / "etapa5" / "resultados_validacion.md"

OK, DIFERENCIA, INFORMATIVO, FALLA = "OK", "DIFERENCIA", "Informativo", "FALLA"


class ErrorDeValidacion(Exception):
    """No se pudo ejecutar la validación (entrada ausente, SQL inválido, estructura inesperada)."""


def miles(n):
    """Entero con punto de miles (es-CO): 155777 -> 155.777. None -> «—»."""
    return "—" if n is None else f"{int(n):,}".replace(",", ".")


def con_signo(n):
    return f"+{miles(n)}" if n > 0 else miles(n)


# ----------------------------------------------------------------------------- base y SQL
def abrir_solo_lectura():
    if not BASE.exists():
        raise ErrorDeValidacion(f"No existe {BASE.relative_to(RAIZ)}. Genérala primero con: python cargar_modelo.py")
    return sqlite3.connect(BASE.as_uri() + "?mode=ro", uri=True)


def separar_consultas(texto):
    """Divide el archivo SQL en consultas completas (sqlite3.complete_statement)."""
    consultas, buffer = [], ""
    for linea in texto.splitlines(keepends=True):
        buffer += linea
        if sqlite3.complete_statement(buffer):
            consultas.append(buffer.strip())
            buffer = ""
    resto = "\n".join(l for l in buffer.splitlines() if l.strip() and not l.strip().startswith("--"))
    if resto:
        raise ErrorDeValidacion(f"{SQL_VALIDACIONES.name}: hay texto sin terminar en «;» al final del archivo: {resto[:80]!r}")
    return consultas


def ejecutar_validaciones(con):
    """Ejecuta sql/02_validaciones.sql. Devuelve [{id, grupo, comprobacion, tipo, valor, estado}]."""
    if not SQL_VALIDACIONES.exists():
        raise ErrorDeValidacion(f"No existe {SQL_VALIDACIONES.relative_to(RAIZ)}.")
    resultados = []
    for consulta in separar_consultas(SQL_VALIDACIONES.read_text(encoding="utf-8")):
        try:
            filas = con.execute(consulta).fetchall()
        except sqlite3.Error as e:
            raise ErrorDeValidacion(f"Error al ejecutar una consulta de {SQL_VALIDACIONES.name}: {e}\n{consulta[:200]}") from e
        if len(filas) != 1 or len(filas[0]) != 5:
            raise ErrorDeValidacion(f"Cada consulta debe devolver una fila de 5 columnas; esta devolvió {len(filas)} fila(s):\n{consulta[:200]}")
        id_, grupo, comprobacion, tipo, valor = filas[0]
        if tipo == "informativo":
            estado = INFORMATIVO
        elif tipo == "debe_ser_cero":
            estado = OK if valor == 0 else FALLA
        else:
            raise ErrorDeValidacion(f"Tipo de comprobación desconocido en {id_}: {tipo!r}.")
        resultados.append({"id": id_, "grupo": grupo, "comprobacion": comprobacion, "tipo": tipo, "valor": valor, "estado": estado})
    return resultados


# ----------------------------------------------------------------------------- orígenes
def leer_json():
    if not JSON_CIFRAS.exists():
        raise ErrorDeValidacion(f"No existe {JSON_CIFRAS.relative_to(RAIZ)}.")
    return json.loads(JSON_CIFRAS.read_text(encoding="utf-8"))


def tomar(datos, *ruta):
    """Navega el JSON y avisa con claridad si falta una clave."""
    actual = datos
    for clave in ruta:
        try:
            actual = actual[clave]
        except (KeyError, TypeError):
            raise ErrorDeValidacion(f"{JSON_CIFRAS.name}: no se encontró «{'.'.join(ruta)}».") from None
    return actual


def origen_csv():
    """Filas y SUM(cantidad) de hechos_vehiculos.csv."""
    if not CSV_HECHOS.exists():
        raise ErrorDeValidacion(f"No existe {CSV_HECHOS.relative_to(RAIZ)}.")
    filas = vehiculos = 0
    with CSV_HECHOS.open(encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            filas += 1
            vehiculos += int(fila["cantidad"])
    return filas, vehiculos


# ----------------------------------------------------------------------------- comparaciones
def comparar(modelo, origen, orden):
    """Compara dos diccionarios clave -> vehículos. Devuelve filas (clave, modelo, origen, diferencia, estado)
    en el orden indicado, más las claves que solo existan en el modelo, y una fila Total."""
    claves = list(orden) + [k for k in modelo if k not in orden]
    filas = []
    for k in claves:
        m, o = modelo.get(k), origen.get(k)
        dif = (m or 0) - (o or 0)
        filas.append((k, m, o, dif, OK if m == o else DIFERENCIA))
    tm, to = sum(modelo.values()), sum(origen.values())
    filas.append(("Total", tm, to, tm - to, OK if tm == to else DIFERENCIA))
    return filas


def comparacion_a(con):
    filas_m, veh_m = con.execute("SELECT COUNT(*), SUM(cantidad) FROM hechos_registros").fetchone()
    filas_o, veh_o = origen_csv()
    return [
        ("Filas (grupos de registro)", filas_m, filas_o, filas_m - filas_o, OK if filas_m == filas_o else DIFERENCIA),
        ("SUM(cantidad) (vehículos)", veh_m, veh_o, veh_m - veh_o, OK if veh_m == veh_o else DIFERENCIA),
    ]


def comparacion_b(con, cifras):
    serie = tomar(cifras, "p3_temporal", "serie_anual")
    origen = {int(x["anio"]): int(x["vehiculos"]) for x in serie}
    modelo = dict(con.execute(
        "SELECT t.anio, SUM(h.cantidad) FROM hechos_registros h JOIN dim_tiempo t ON t.id_tiempo = h.id_tiempo "
        "GROUP BY t.anio ORDER BY t.anio").fetchall())
    return comparar(modelo, origen, sorted(origen))


def comparacion_c(con, cifras):
    lista = tomar(cifras, "p1_composicion", "por_combustible")
    origen = {x["categoria"]: int(x["vehiculos"]) for x in lista}
    modelo = dict(con.execute(
        "SELECT c.codigo, SUM(h.cantidad) FROM hechos_registros h JOIN dim_combustible c ON c.id_combustible = h.id_combustible "
        "GROUP BY c.codigo").fetchall())
    return comparar(modelo, origen, [x["categoria"] for x in lista])


def comparacion_d(con, cifras):
    lista = tomar(cifras, "p2_territorial", "por_departamento")
    origen = {x["categoria"]: int(x["vehiculos"]) for x in lista}
    modelo = dict(con.execute(
        "SELECT t.departamento, SUM(h.cantidad) FROM hechos_registros h JOIN dim_territorio t ON t.id_territorio = h.id_territorio "
        "GROUP BY t.departamento").fetchall())
    return comparar(modelo, origen, [x["categoria"] for x in lista])


# ----------------------------------------------------------------------------- salida
def tabla_markdown(cabecera, filas, alineacion):
    """alineacion: cadena con 'l' (izquierda) o 'r' (derecha) por columna."""
    sep = ["---:" if a == "r" else "---" for a in alineacion]
    lineas = ["| " + " | ".join(cabecera) + " |", "| " + " | ".join(sep) + " |"]
    lineas += ["| " + " | ".join(str(c) for c in f) + " |" for f in filas]
    return "\n".join(lineas)


def filas_comparacion(filas):
    return [(k, miles(m), miles(o), con_signo(d), est) for k, m, o, d, est in filas]


def imprimir_comparacion(titulo, etiqueta, filas):
    print(f"\n{titulo}")
    ancho = max(len(etiqueta), *(len(str(f[0])) for f in filas))
    print(f"  {etiqueta:<{ancho}} {'Modelo':>10} {'Origen':>10} {'Diferencia':>11}  Estado")
    for k, m, o, d, est in filas:
        print(f"  {str(k):<{ancho}} {miles(m):>10} {miles(o):>10} {con_signo(d):>11}  {est}")


def escribir_informe(validaciones, comparaciones):
    """comparaciones: [(letra, titulo, origen_texto, etiqueta, filas)]"""
    n_val = sum(1 for v in validaciones if v["tipo"] == "debe_ser_cero")
    val_ok = sum(1 for v in validaciones if v["estado"] == OK)
    n_cmp = sum(len(c[4]) for c in comparaciones)
    cmp_ok = sum(1 for c in comparaciones for f in c[4] if f[4] == OK)
    diferencias = [(c[0], f) for c in comparaciones for f in c[4] if f[4] != OK]

    t = []
    t.append("# Resultados de validación del modelo estrella · Etapa 5\n")
    t.append(f"Generado por `validar_modelo.py` el {date.today().isoformat()}. La base se abre en **solo lectura**; este informe no la modifica.\n")
    t.append("**Base validada:** `data/modelo/modelo_estrella.db` · **Consultas:** `sql/02_validaciones.sql` · "
             "**Orígenes:** `data/powerbi/hechos_vehiculos.csv` y `data/processed/resultados_conocimiento_evidente.json`.\n")
    t.append("Los vehículos se cuentan con `SUM(cantidad)`. La diferencia es *modelo − origen*.\n")

    t.append("## Resumen\n")
    t.append(tabla_markdown(
        ["Bloque", "Comprobaciones", "Correctas", "Con diferencia o falla"],
        [("Validaciones del esquema (SQL, deben dar 0)", n_val, val_ok, n_val - val_ok),
         ("Comparaciones A–D con el origen (una por fila de cada tabla)", n_cmp, cmp_ok, n_cmp - cmp_ok)],
        "lrrr"))
    t.append("")

    t.append("## 1. Validaciones del esquema (`sql/02_validaciones.sql`)\n")
    t.append("Las comprobaciones «deben ser 0» cuentan los casos que incumplen la regla. Las informativas solo se reportan.\n")
    grupo_actual, bloque = None, []

    def volcar():
        if bloque:
            t.append(f"### {grupo_actual}\n")
            t.append(tabla_markdown(["Id", "Comprobación", "Valor", "Esperado", "Estado"], bloque, "llrrl"))
            t.append("")

    for v in validaciones:
        if v["grupo"] != grupo_actual:
            volcar()
            grupo_actual, bloque = v["grupo"], []
        esperado = "0" if v["tipo"] == "debe_ser_cero" else "—"
        bloque.append((v["id"], v["comprobacion"], miles(v["valor"]), esperado, v["estado"]))
    volcar()

    t.append("## 2. Comparaciones con el origen\n")
    for letra, titulo, origen_texto, etiqueta, filas in comparaciones:
        t.append(f"### {letra}. {titulo}\n")
        t.append(f"Origen: {origen_texto}\n")
        t.append(tabla_markdown([etiqueta, "Valor del modelo", "Valor de origen", "Diferencia", "Estado"],
                                filas_comparacion(filas), "lrrrl"))
        t.append("")

    t.append("## 3. Diferencias encontradas\n")
    if diferencias:
        t.append(tabla_markdown(["Comparación", "Clave", "Modelo", "Origen", "Diferencia"],
                                [(c, f[0], miles(f[1]), miles(f[2]), con_signo(f[3])) for c, f in diferencias], "llrrr"))
        t.append("\nNo se ajustó ninguna cifra.")
    else:
        t.append("Ninguna. Todas las comparaciones A–D coinciden con su origen y las validaciones del esquema dan 0.")
    t.append("")

    INFORME.parent.mkdir(parents=True, exist_ok=True)
    INFORME.write_text("\n".join(t), encoding="utf-8", newline="\n")
    return diferencias


def main():
    print("Validación del modelo estrella (Etapa 5), base abierta en solo lectura")
    print(f"  Base      : {BASE.relative_to(RAIZ)}")
    print(f"  Consultas : {SQL_VALIDACIONES.relative_to(RAIZ)}")
    print(f"  Orígenes  : {CSV_HECHOS.relative_to(RAIZ)}, {JSON_CIFRAS.relative_to(RAIZ)}")

    con = abrir_solo_lectura()
    try:
        validaciones = ejecutar_validaciones(con)
        cifras = leer_json()
        comparaciones = [
            ("A", "Filas y SUM(cantidad)", "`data/powerbi/hechos_vehiculos.csv` (filas y suma de `cantidad`)", "Concepto", comparacion_a(con)),
            ("B", "Vehículos por año", "`p3_temporal.serie_anual` del JSON", "Año de registro", comparacion_b(con, cifras)),
            ("C", "Vehículos por combustible", "`p1_composicion.por_combustible` del JSON", "Combustible", comparacion_c(con, cifras)),
            ("D", "Vehículos por departamento", "`p2_territorial.por_departamento` del JSON", "Departamento", comparacion_d(con, cifras)),
        ]
    finally:
        con.close()

    print("\nValidaciones del esquema (sql/02_validaciones.sql)")
    grupo_actual = None
    for v in validaciones:
        if v["grupo"] != grupo_actual:
            grupo_actual = v["grupo"]
            print(f"  [{grupo_actual}]")
        esperado = "(debe ser 0)" if v["tipo"] == "debe_ser_cero" else ""
        print(f"    {v['id']:<5} {v['comprobacion']:<92} {miles(v['valor']):>9} {esperado:<13} {v['estado']}")

    for letra, titulo, _, etiqueta, filas in comparaciones:
        imprimir_comparacion(f"{letra}. {titulo}", etiqueta, filas)

    diferencias = escribir_informe(validaciones, comparaciones)
    fallas = [v for v in validaciones if v["estado"] == FALLA]
    n_cmp = sum(len(c[4]) for c in comparaciones)
    print(f"\nInforme escrito en {INFORME.relative_to(RAIZ)}")
    print(f"Validaciones SQL con falla: {len(fallas)} · Comparaciones con diferencia: {len(diferencias)} de {n_cmp}")
    if fallas or diferencias:
        print("ATENCIÓN: hay diferencias o fallas; no se ajustó nada. Revisa el informe.")
        return 1
    print("Todo coincide con el origen.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ErrorDeValidacion as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        sys.exit(1)
