"""
Reconstruye desde cero la base SQLite del modelo estrella (Etapa 5).

Diseño del modelo: docs/etapa5/modelo_multidimensional.md
Esquema:           sql/01_crear_modelo.sql
Entradas:          data/powerbi/hechos_vehiculos.csv, dim_territorio.csv, dim_combustible.csv
Salida:            data/modelo/modelo_estrella.db (reemplaza la anterior si existe)

Qué hace:
    1. Lee los tres CSV (utf-8-sig) y valida TODO en memoria antes de tocar la base: cada clase, combustible,
       año de registro y año del modelo debe tener una regla en el documento. Si alguno no la tiene, la
       carga se detiene con un error claro; el script nunca clasifica por su cuenta.
    2. Construye la base en un archivo temporal con el esquema de sql/01_crear_modelo.sql, activa
       PRAGMA foreign_keys = ON y carga todas las tablas en UNA sola transacción.
    3. Si todo sale bien, reemplaza la base anterior; si algo falla, la base anterior queda intacta.
    4. Imprime las filas de cada tabla y SUM(cantidad) (los vehículos se cuentan con SUM, no con COUNT(*)).

SIN DATO y SIN CARROCERIA se conservan tal como vienen en la fuente.

Solo usa la biblioteca estándar.   Uso:   python cargar_modelo.py
"""

import csv
import os
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CARPETA_CSV = RAIZ / "data" / "powerbi"
CSV_HECHOS = CARPETA_CSV / "hechos_vehiculos.csv"
CSV_TERRITORIO = CARPETA_CSV / "dim_territorio.csv"
CSV_COMBUSTIBLE = CARPETA_CSV / "dim_combustible.csv"
SQL_MODELO = RAIZ / "sql" / "01_crear_modelo.sql"
BASE = RAIZ / "data" / "modelo" / "modelo_estrella.db"
BASE_TEMPORAL = BASE.with_name(BASE.name + ".tmp")

# --- Reglas del documento (docs/etapa5/modelo_multidimensional.md) ---------------------------------
# §3.4 familia de cada combustible
FAMILIA_POR_COMBUSTIBLE = {
    "ELECTRICO": "Eléctrico",
    "GASO ELEC": "Híbrido",
    "DIES ELEC": "Híbrido",
    "HIDROGENO": "Otro",
}
# §3.5 categoría de cada clase (las 16 clases del dataset)
CATEGORIA_POR_CLASE = {
    "AUTOMOVIL": "Liviano",
    "CAMIONETA": "Liviano",
    "CAMPERO": "Liviano",
    "BUS": "Pasajeros",
    "BUSETA": "Pasajeros",
    "MICROBUS": "Pasajeros",
    "CAMION": "Carga",
    "TRACTOCAMION": "Carga",
    "VOLQUETA": "Carga",
    "CICLOMOTOR": "Motorizado ligero",
    "MOTOCICLETA": "Motorizado ligero",
    "MOTOCARRO": "Motorizado ligero",
    "TRICIMOTO": "Motorizado ligero",
    "MOTOTRICICLO": "Motorizado ligero",
    "CUADRICICLO": "Motorizado ligero",
    "CUATRIMOTO": "Motorizado ligero",
}
SI_NO = ("Sí", "No")
ANIO_MIN, ANIO_MAX = 2015, 2024   # ventana de análisis (§3.2)

# Resultado esperado según el documento y la tarea (se compara, nunca se ajusta).
ESPERADO = {
    "dim_tiempo": 10,
    "dim_territorio": 247,
    "dim_combustible": 4,
    "dim_vehiculo": 68,
    "dim_modelo": 25,
    "hechos_registros": 6772,
}
ESPERADO_VEHICULOS = 155777


class ErrorDeCarga(Exception):
    """Falla de validación o de carga: se muestra el mensaje y no se continúa."""


def miles(n):
    """Entero con punto de miles (es-CO): 6772 -> 6.772."""
    return f"{int(n):,}".replace(",", ".")


def periodo(anio):
    """§3.2: 2015-2019 si anio <= 2019; 2020-2024 en otro caso (dentro de la ventana 2015-2024)."""
    if ANIO_MIN <= anio <= 2019:
        return "2015-2019"
    if 2020 <= anio <= ANIO_MAX:
        return "2020-2024"
    raise ErrorDeCarga(f"Año de registro {anio} fuera de la ventana {ANIO_MIN}-{ANIO_MAX}: el documento no define su periodo.")


def rango_modelo(anio_modelo):
    """§3.6: Hasta 2017, 2018-2019, 2020-2021, 2022-2023 o 2024 o posterior."""
    if anio_modelo <= 2017:
        return "Hasta 2017"
    if anio_modelo <= 2019:
        return "2018-2019"
    if anio_modelo <= 2021:
        return "2020-2021"
    if anio_modelo <= 2023:
        return "2022-2023"
    return "2024 o posterior"


def leer_csv(ruta, columnas):
    """Lee un CSV (utf-8-sig) y devuelve [(numero_de_linea, fila_dict)]. Verifica que estén las columnas."""
    if not ruta.exists():
        raise ErrorDeCarga(f"No existe el archivo de entrada: {ruta.relative_to(RAIZ)}")
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        faltan = [c for c in columnas if c not in (lector.fieldnames or [])]
        if faltan:
            raise ErrorDeCarga(f"{ruta.name}: faltan las columnas {faltan}. Columnas encontradas: {lector.fieldnames}")
        return [(i, fila) for i, fila in enumerate(lector, start=2)]


def entero(texto, campo, ruta, linea):
    try:
        return int(texto)
    except (TypeError, ValueError):
        raise ErrorDeCarga(f"{ruta.name}, línea {linea}: «{campo}» no es un entero: {texto!r}.") from None


def validar_y_preparar():
    """Lee y valida todo en memoria. Devuelve las estructuras listas para insertar."""
    # --- dimensiones que vienen de CSV
    territorios = {}                                   # territorio -> (municipio, departamento), en orden de archivo
    for linea, f in leer_csv(CSV_TERRITORIO, ["territorio", "municipio", "departamento"]):
        if f["territorio"] in territorios:
            raise ErrorDeCarga(f"{CSV_TERRITORIO.name}, línea {linea}: territorio repetido: {f['territorio']!r}.")
        territorios[f["territorio"]] = (f["municipio"], f["departamento"])

    combustibles = {}                                  # codigo -> (etiqueta, familia), en orden de archivo
    for linea, f in leer_csv(CSV_COMBUSTIBLE, ["combustible", "combustible_etiqueta"]):
        codigo = f["combustible"]
        if codigo not in FAMILIA_POR_COMBUSTIBLE:
            raise ErrorDeCarga(
                f"{CSV_COMBUSTIBLE.name}, línea {linea}: el combustible {codigo!r} no tiene familia en el documento "
                f"(§3.4: {sorted(FAMILIA_POR_COMBUSTIBLE)}). No se clasifica por cuenta propia."
            )
        if codigo in combustibles:
            raise ErrorDeCarga(f"{CSV_COMBUSTIBLE.name}, línea {linea}: combustible repetido: {codigo!r}.")
        combustibles[codigo] = (f["combustible_etiqueta"], FAMILIA_POR_COMBUSTIBLE[codigo])

    # --- hechos: se valida fila por fila y se reúnen los miembros de las dimensiones derivadas
    columnas = ["combustible", "clase", "carroceria", "anio_registro", "modelo", "territorio", "cantidad",
                "modelo_inusual", "grupo_grande"]
    hechos = []
    anios, modelos, vehiculos = set(), set(), set()
    for linea, f in leer_csv(CSV_HECHOS, columnas):
        if f["combustible"] not in combustibles:
            raise ErrorDeCarga(f"{CSV_HECHOS.name}, línea {linea}: combustible {f['combustible']!r} no está en {CSV_COMBUSTIBLE.name}.")
        if f["territorio"] not in territorios:
            raise ErrorDeCarga(f"{CSV_HECHOS.name}, línea {linea}: territorio {f['territorio']!r} no está en {CSV_TERRITORIO.name}.")
        if f["clase"] not in CATEGORIA_POR_CLASE:
            raise ErrorDeCarga(
                f"{CSV_HECHOS.name}, línea {linea}: la clase {f['clase']!r} no tiene categoría en el documento "
                f"(§3.5). Agrega la regla al documento antes de cargar; no se clasifica por cuenta propia."
            )
        if f["carroceria"] == "":
            raise ErrorDeCarga(f"{CSV_HECHOS.name}, línea {linea}: carrocería vacía; la fuente usa SIN DATO o SIN CARROCERIA.")
        anio = entero(f["anio_registro"], "anio_registro", CSV_HECHOS, linea)
        periodo(anio)                                   # lanza ErrorDeCarga si no hay regla para ese año
        modelo = entero(f["modelo"], "modelo", CSV_HECHOS, linea)
        cantidad = entero(f["cantidad"], "cantidad", CSV_HECHOS, linea)
        if cantidad <= 0:
            raise ErrorDeCarga(f"{CSV_HECHOS.name}, línea {linea}: cantidad debe ser mayor que 0 (es {cantidad}).")
        for campo in ("modelo_inusual", "grupo_grande"):
            if f[campo] not in SI_NO:
                raise ErrorDeCarga(f"{CSV_HECHOS.name}, línea {linea}: {campo} debe ser 'Sí' o 'No' (es {f[campo]!r}).")

        anios.add(anio)
        modelos.add(modelo)
        vehiculos.add((f["clase"], f["carroceria"]))
        hechos.append((f["combustible"], f["clase"], f["carroceria"], anio, modelo, f["territorio"], cantidad,
                       f["modelo_inusual"], f["grupo_grande"]))

    return {"territorios": territorios, "combustibles": combustibles, "hechos": hechos,
            "anios": sorted(anios), "modelos": sorted(modelos), "vehiculos": sorted(vehiculos)}


def construir_base(datos):
    """Crea la base temporal con el esquema del SQL y carga todo en una sola transacción.
    Devuelve (filas_por_tabla, suma_cantidad, resultado_foreign_key_check, resultado_integrity_check)."""
    for ruta in (BASE_TEMPORAL, Path(str(BASE_TEMPORAL) + "-journal")):
        if ruta.exists():
            ruta.unlink()
    BASE.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(BASE_TEMPORAL)
    con.isolation_level = None                          # la transacción se controla a mano con BEGIN/COMMIT
    try:
        con.executescript(SQL_MODELO.read_text(encoding="utf-8"))
        con.execute("PRAGMA foreign_keys = ON")         # fuera de transacción, para que tenga efecto
        if con.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ErrorDeCarga("No se pudo activar PRAGMA foreign_keys = ON.")

        con.execute("BEGIN")
        try:
            id_tiempo = {a: i for i, a in enumerate(datos["anios"], start=1)}
            con.executemany("INSERT INTO dim_tiempo (id_tiempo, anio, periodo) VALUES (?, ?, ?)",
                            [(id_tiempo[a], a, periodo(a)) for a in datos["anios"]])

            id_territorio = {t: i for i, t in enumerate(datos["territorios"], start=1)}
            con.executemany("INSERT INTO dim_territorio (id_territorio, territorio, municipio, departamento) VALUES (?, ?, ?, ?)",
                            [(id_territorio[t], t, m, d) for t, (m, d) in datos["territorios"].items()])

            id_combustible = {c: i for i, c in enumerate(datos["combustibles"], start=1)}
            con.executemany("INSERT INTO dim_combustible (id_combustible, codigo, etiqueta, familia) VALUES (?, ?, ?, ?)",
                            [(id_combustible[c], c, e, fam) for c, (e, fam) in datos["combustibles"].items()])

            id_vehiculo = {v: i for i, v in enumerate(datos["vehiculos"], start=1)}
            con.executemany("INSERT INTO dim_vehiculo (id_vehiculo, categoria, clase, carroceria) VALUES (?, ?, ?, ?)",
                            [(id_vehiculo[(cl, ca)], CATEGORIA_POR_CLASE[cl], cl, ca) for cl, ca in datos["vehiculos"]])

            id_modelo = {m: i for i, m in enumerate(datos["modelos"], start=1)}
            con.executemany("INSERT INTO dim_modelo (id_modelo, anio_modelo, rango_modelo) VALUES (?, ?, ?)",
                            [(id_modelo[m], m, rango_modelo(m)) for m in datos["modelos"]])

            con.executemany(
                "INSERT INTO hechos_registros (id_hecho, id_tiempo, id_territorio, id_combustible, id_vehiculo, id_modelo, "
                "cantidad, modelo_inusual, grupo_grande) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(n, id_tiempo[anio], id_territorio[terr], id_combustible[comb], id_vehiculo[(clase, carro)],
                  id_modelo[modelo], cant, inusual, grande)
                 for n, (comb, clase, carro, anio, modelo, terr, cant, inusual, grande) in enumerate(datos["hechos"], start=1)],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

        filas = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ESPERADO}
        vehiculos = con.execute("SELECT SUM(cantidad) FROM hechos_registros").fetchone()[0]
        violaciones_fk = con.execute("PRAGMA foreign_key_check").fetchall()
        integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
        return filas, vehiculos, violaciones_fk, integridad
    except sqlite3.Error as e:
        raise ErrorDeCarga(f"SQLite rechazó la carga: {e}") from e
    finally:
        con.close()


def reemplazar_base():
    """Sustituye la base anterior por la recién construida."""
    try:
        os.replace(BASE_TEMPORAL, BASE)
    except PermissionError:
        raise ErrorDeCarga(
            f"No se pudo reemplazar {BASE.relative_to(RAIZ)}: otro programa la tiene abierta. "
            "Ciérralo y vuelve a ejecutar."
        ) from None


def main():
    print("Reconstrucción del modelo estrella (Etapa 5)")
    print(f"  Esquema : {SQL_MODELO.relative_to(RAIZ)}")
    print(f"  Entradas: {CSV_HECHOS.relative_to(RAIZ)}, {CSV_TERRITORIO.name}, {CSV_COMBUSTIBLE.name}")
    print(f"  Salida  : {BASE.relative_to(RAIZ)}\n")

    datos = validar_y_preparar()
    print("Validación (todas las reglas del documento se cumplen, nada se clasificó por cuenta propia):")
    print(f"  - {miles(len(datos['hechos']))} filas de hechos leídas; clases, combustibles, años y modelos con regla.")
    print(f"  - {len(CATEGORIA_POR_CLASE)} clases -> categoría; {len(FAMILIA_POR_COMBUSTIBLE)} combustibles -> familia.")
    print("  - modelo_inusual y grupo_grande: solo 'Sí' o 'No'.")
    carrocerias = {c for _, c in datos["vehiculos"]}
    print(f"  - SIN DATO presente: {'SIN DATO' in carrocerias}; SIN CARROCERIA presente: {'SIN CARROCERIA' in carrocerias} (se conservan tal cual).\n")

    filas, vehiculos, violaciones_fk, integridad = construir_base(datos)
    reemplazar_base()

    print("Carga terminada en una sola transacción, con PRAGMA foreign_keys = ON.\n")
    print(f"{'Tabla':<20}{'Filas':>10}{'Esperado':>10}   Resultado")
    hay_diferencias = False
    for tabla, esperado in ESPERADO.items():
        ok = filas[tabla] == esperado
        hay_diferencias |= not ok
        print(f"{tabla:<20}{miles(filas[tabla]):>10}{miles(esperado):>10}   {'OK' if ok else 'DIFERENCIA (' + str(filas[tabla] - esperado) + ')'}")
    ok = vehiculos == ESPERADO_VEHICULOS
    hay_diferencias |= not ok
    print(f"{'SUM(cantidad)':<20}{miles(vehiculos):>10}{miles(ESPERADO_VEHICULOS):>10}   {'OK' if ok else 'DIFERENCIA (' + str(vehiculos - ESPERADO_VEHICULOS) + ')'}")

    print(f"\nPRAGMA foreign_key_check : {'sin violaciones' if not violaciones_fk else str(len(violaciones_fk)) + ' violaciones'}")
    print(f"PRAGMA integrity_check   : {integridad}")
    print(f"Base escrita en          : {BASE.relative_to(RAIZ)} ({BASE.stat().st_size / 1024:.0f} KB)")
    if hay_diferencias or violaciones_fk or integridad != "ok":
        print("\nATENCIÓN: hay diferencias con lo esperado; no se ajustó nada.")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ErrorDeCarga as error:
        for ruta in (BASE_TEMPORAL, Path(str(BASE_TEMPORAL) + "-journal")):
            if ruta.exists():
                ruta.unlink()
        print(f"\nERROR: {error}\nLa carga se detuvo; la base anterior (si existía) no se modificó.", file=sys.stderr)
        sys.exit(1)
