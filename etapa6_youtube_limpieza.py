"""
Etapa 6 · Limpieza de los comentarios de YouTube (entrada del flujo de Orange 03_comentarios_youtube.ows).

Lee data/raw/youtube/comentarios_crudos.csv (generado por etapa6_youtube_extraer.py) y aplica, EN ESTE ORDEN,
las reglas de calidad. Cada regla cuenta cuántos comentarios elimina para que el informe pueda reportarlo:

    1. vacios            sin texto o sin letras después de limpiar (solo emojis, signos o espacios)
    2. publicidad        spam/promoción (WhatsApp, Telegram, inversión, sorteos, «suscríbete», cripto…)
    3. muy_cortos        menos de MIN_PALABRAS palabras (p. ej. «Excelente video»): no aportan tema
    4. duplicados        mismo texto (sin mayúsculas, tildes ni signos) repetido: se conserva la primera aparición
    5. otro_idioma       idioma detectado distinto de español con probabilidad >= 0,90 (langdetect, semilla fija)

Además, ANTES de contar, se transforma el texto para proteger a las personas: se eliminan URL, correos,
@menciones y celulares colombianos (10 dígitos que empiezan por 3), y se unifican saltos de línea y espacios.

Los comentarios que no mencionan ninguna palabra del tema (vehículo, eléctrico, híbrido, batería, carga,
precio…) NO se eliminan, pero se marcan (`menciona_tema` = no) y se reporta su proporción: descartar por
tema sería un juicio humano que conviene auditar, no automatizar.

Tratamiento del idioma: el análisis se hace en español (stopwords y stemmer en español). Los comentarios en
otros idiomas se excluyen, no se traducen.

Salidas
    data/processed/etapa6/comentarios_limpios.tab          (formato Orange; ¡NO se publica! está en .gitignore)
    data/processed/etapa6/resultados_youtube_limpieza.json  (conteos por regla; sí se publica)

Uso (Python de Orange o entorno con pandas y langdetect):
    python etapa6_youtube_limpieza.py
    python etapa6_youtube_limpieza.py --raw otra_ruta.csv --salida otra_carpeta
"""

import argparse
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from langdetect import DetectorFactory, detect_langs

RAIZ = Path(__file__).resolve().parent
RAW = RAIZ / "data" / "raw" / "youtube" / "comentarios_crudos.csv"
SALIDA = RAIZ / "data" / "processed" / "etapa6"

MIN_PALABRAS = 4
UMBRAL_IDIOMA = 0.90
MIN_PALABRAS_IDIOMA = 6  # con menos palabras la detección de idioma no es fiable: se conserva

RE_URL = re.compile(r"(https?://\S+|www\.\S+|\b\S+\.(com|co|net|org|be|ly)(/\S*)?\b)", re.I)
RE_CORREO = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
RE_MENCION = re.compile(r"@[\w.\-]+")
# Celular colombiano: 10 dígitos que empiezan por 3 (con o sin +57 y separadores). No toca precios como «120 000 000».
RE_TELEFONO = re.compile(r"(?<!\d)(\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)")
RE_ESPACIOS = re.compile(r"\s+")
RE_PUBLICIDAD = re.compile(
    r"whats\s?app|wa\.me|telegram|inversi[oó]n(es)?\b|ganar dinero|gana dinero|sorteo|\bsuscr[ií]be|"
    r"cripto|bitcoin|forex|ingresos? pasivos?|escr[ií]beme|cont[aá]ctame|mi canal|visita mi|📲|📞", re.I)
RE_TEMA = re.compile(
    r"carro|auto\b|autos\b|autom[oó]vil|veh[ií]culo|el[eé]ctric|h[ií]brid|bater[ií]a|carga|cargador|"
    r"gasolina|combusti|diesel|di[eé]sel|motor|tesla|byd|toyota|renault|kia|moto\b|motos\b|precio|"
    r"cuesta|costo|caro\b|barato|aut[oó]nom|kil[oó]metro|\bkm\b|impuesto|pico y placa|mantenimiento", re.I)


def sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def clave_duplicado(t):
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes(t.lower())).strip()


def limpiar_texto(t):
    t = html.unescape(str(t))
    t = re.sub(r"<[^>]+>", " ", t)
    t = RE_URL.sub(" ", t)
    t = RE_CORREO.sub(" ", t)
    t = RE_MENCION.sub(" ", t)
    t = RE_TELEFONO.sub(" ", t)
    return RE_ESPACIOS.sub(" ", t).strip()


def idioma_no_espanol(texto):
    if len(texto.split()) < MIN_PALABRAS_IDIOMA:
        return False
    try:
        top = detect_langs(texto)[0]
    except Exception:
        return False
    return top.lang != "es" and top.prob >= UMBRAL_IDIOMA


def escribir_tab(df, ruta):
    cols = ["texto", "id_hash", "video_id", "fecha", "me_gusta", "respuestas", "palabras", "menciona_tema"]
    tipos = {"texto": "s", "id_hash": "s", "video_id": "s", "fecha": "s", "me_gusta": "c", "respuestas": "c",
             "palabras": "c", "menciona_tema": "d"}
    roles = {"texto": "meta", "id_hash": "meta", "video_id": "meta", "fecha": "meta"}
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(cols) + "\n")
        f.write("\t".join(tipos[c] for c in cols) + "\n")
        f.write("\t".join(roles.get(c, "") for c in cols) + "\n")
        for fila in df[cols].itertuples(index=False):
            f.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in fila) + "\n")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Limpieza de comentarios de YouTube")
    ap.add_argument("--raw", default=str(RAW))
    ap.add_argument("--salida", default=str(SALIDA))
    args = ap.parse_args()
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    DetectorFactory.seed = 0  # resultados reproducibles

    crudo = pd.read_csv(args.raw, encoding="utf-8-sig", dtype={"texto": str}).fillna({"texto": ""})
    n0 = len(crudo)
    df = crudo.copy()
    df["texto"] = df["texto"].map(limpiar_texto)
    pasos = {"comentarios_crudos": n0}

    def aplicar(nombre, mascara_eliminar):
        nonlocal df
        n = int(mascara_eliminar.sum())
        df = df[~mascara_eliminar].copy()
        pasos[nombre] = n

    aplicar("vacios", ~df["texto"].str.contains(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", regex=True))
    aplicar("publicidad", df["texto"].str.contains(RE_PUBLICIDAD))
    df["palabras"] = df["texto"].str.split().str.len()
    aplicar("muy_cortos", df["palabras"] < MIN_PALABRAS)
    df["_clave"] = df["texto"].map(clave_duplicado)
    aplicar("duplicados", df["_clave"].duplicated(keep="first"))
    aplicar("otro_idioma", df["texto"].map(idioma_no_espanol))
    df["menciona_tema"] = df["texto"].str.contains(RE_TEMA).map({True: "si", False: "no"})
    df = df.drop(columns=["_clave"]).reset_index(drop=True)

    escribir_tab(df, salida / "comentarios_limpios.tab")
    comentarios_por_video = df.groupby("video_id").size().sort_values(ascending=False)
    resumen = {
        "entrada": args.raw if args.raw != str(RAW) else "data/raw/youtube/comentarios_crudos.csv",
        "reglas_en_orden": ["vacios", "publicidad", "muy_cortos", "duplicados", "otro_idioma"],
        "parametros": {"min_palabras": MIN_PALABRAS, "umbral_idioma": UMBRAL_IDIOMA,
                       "min_palabras_para_detectar_idioma": MIN_PALABRAS_IDIOMA},
        "eliminados_por_regla": {k: v for k, v in pasos.items() if k != "comentarios_crudos"},
        "comentarios_crudos": n0,
        "comentarios_limpios": int(len(df)),
        "pct_conservado": round(100 * len(df) / n0, 2) if n0 else None,
        "menciona_tema": {"si": int((df["menciona_tema"] == "si").sum()), "no": int((df["menciona_tema"] == "no").sum()),
                          "pct_si": round(100 * (df["menciona_tema"] == "si").mean(), 2) if len(df) else None},
        "palabras_por_comentario": {"mediana": float(df["palabras"].median()), "media": round(float(df["palabras"].mean()), 1)},
        "comentarios_por_video": {"videos": int(comentarios_por_video.size), "max": int(comentarios_por_video.max()),
                                  "min": int(comentarios_por_video.min())},
        "privacidad": "Se eliminan URL, correos, @menciones y celulares del texto. No se conserva nombre ni canal del autor.",
        "idioma": "Análisis en español; los comentarios en otro idioma se excluyen (no se traducen).",
    }
    (salida / "resultados_youtube_limpieza.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
