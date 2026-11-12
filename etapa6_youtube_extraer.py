"""
Etapa 6 · Extracción de comentarios de YouTube (YouTube Data API v3).

Propósito del análisis (explícito): los datos del RUNT dicen CUÁNTOS vehículos eléctricos e híbridos se
registran y DÓNDE, pero no POR QUÉ la gente elige (o descarta) uno u otro. Los comentarios de videos
colombianos sobre estos vehículos permiten explorar percepciones, barreras y motivaciones (precio,
carga, incentivos, desconfianza, etc.) y contrastarlas con lo que muestran los datos.

Qué hace
    1. Busca videos con varias consultas en español (search.list; región CO, idioma es).
    2. Consulta estadísticas de cada video (videos.list) y selecciona los que tienen comentarios,
       limitando cuántos puede aportar un mismo canal (para que un solo canal no domine el corpus).
    3. Descarga los comentarios de primer nivel de cada video seleccionado (commentThreads.list).
    4. Guarda SOLO lo necesario: el texto, los «me gusta», la fecha y un identificador anónimo (hash).
       NO se guarda nombre, canal, foto ni enlace del autor del comentario.

Salidas
    data/raw/youtube/comentarios_crudos.csv           (¡NO se publica! está en .gitignore)
    data/raw/youtube/videos_consultados.csv           (metadatos públicos de los videos: título, enlace, fecha, conteos)
    data/processed/etapa6/resultados_youtube_extraccion.json   (fecha, criterios, cantidades, restricciones, cuota)

Credenciales
    La clave de API se lee de la variable de entorno YOUTUBE_API_KEY o de un archivo `.env` local
    (línea `YOUTUBE_API_KEY=...`). `.env` está en .gitignore. La clave NUNCA se imprime ni se guarda.
    Cómo obtenerla: Google Cloud Console -> crear proyecto -> habilitar «YouTube Data API v3» ->
    Credenciales -> Crear clave de API (restringirla a esa API).

Cuota (por defecto 10.000 unidades/día): search.list = 100, videos.list = 1, commentThreads.list = 1.
Con los valores por defecto el script usa ~ 8 x 100 + ~6 + (20 videos x 5 páginas) = ~ 900 unidades.

Uso:
    pip install requests
    set YOUTUBE_API_KEY=su_clave          (PowerShell: $env:YOUTUBE_API_KEY="su_clave")
    python etapa6_youtube_extraer.py
    python etapa6_youtube_extraer.py --simular     # muestra el plan y la cuota estimada sin llamar a la API
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent
CARPETA_RAW = RAIZ / "data" / "raw" / "youtube"
SALIDA_JSON = RAIZ / "data" / "processed" / "etapa6" / "resultados_youtube_extraccion.json"

API = "https://www.googleapis.com/youtube/v3"

# --- Criterios de búsqueda y selección (se documentan tal cual en el informe) -----------------
CONSULTAS = [
    "carros eléctricos Colombia",
    "carros híbridos Colombia",
    "carro eléctrico o híbrido cuál comprar Colombia",
    "cargadores carros eléctricos Colombia",
    "ventajas y desventajas carro eléctrico Colombia",
    "cuánto cuesta un carro eléctrico en Colombia",
    "carro eléctrico Bogotá cargar en casa",
    "híbrido enchufable Colombia reseña",
]
REGION = "CO"
IDIOMA = "es"
PUBLICADO_DESDE = "2020-01-01T00:00:00Z"   # el crecimiento fuerte de registros comienza en 2019-2021
RESULTADOS_POR_CONSULTA = 10
SOLO_CONTENIDO_COLOMBIANO = True          # canal con país declarado CO o título que menciona Colombia
PALABRAS_COLOMBIA = ("colombia", "colombian", "bogotá", "bogota", "medellín", "medellin")
MIN_COMENTARIOS_VIDEO = 50                 # videos con poca conversación aportan poco
MAX_VIDEOS = 20
MAX_VIDEOS_POR_CANAL = 3                   # evita que un solo canal domine el corpus
MAX_COMENTARIOS_POR_VIDEO = 500            # solo comentarios de primer nivel (sin respuestas)
ORDEN_COMENTARIOS = "relevance"
COSTO = {"search": 100, "videos": 1, "canales": 1, "comentarios": 1}


def cargar_clave():
    clave = os.environ.get("YOUTUBE_API_KEY", "").strip()
    env = RAIZ / ".env"
    if not clave and env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.strip().startswith("YOUTUBE_API_KEY="):
                clave = linea.split("=", 1)[1].strip().strip('"').strip("'")
    return clave


class Cliente:
    def __init__(self, clave):
        self.clave = clave
        self.cuota = 0
        self.errores = Counter()
        self.sesion = requests.Session()

    def get(self, recurso, costo, **params):
        params["key"] = self.clave
        for intento in range(3):
            r = self.sesion.get(f"{API}/{recurso}", params=params, timeout=30)
            if r.status_code == 200:
                self.cuota += costo
                return r.json()
            motivo = ""
            try:
                motivo = r.json()["error"]["errors"][0]["reason"]
            except Exception:
                motivo = f"http_{r.status_code}"
            self.errores[motivo] += 1
            if r.status_code in (500, 503) and intento < 2:
                time.sleep(2 ** intento)
                continue
            raise ErrorAPI(motivo, r.status_code)


class ErrorAPI(Exception):
    def __init__(self, motivo, codigo):
        super().__init__(f"{motivo} ({codigo})")
        self.motivo, self.codigo = motivo, codigo


def hash_id(texto):
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]


def buscar_videos(c):
    encontrados = {}
    for consulta in CONSULTAS:
        datos = c.get("search", COSTO["search"], part="snippet", q=consulta, type="video", regionCode=REGION,
                      relevanceLanguage=IDIOMA, order="relevance", maxResults=RESULTADOS_POR_CONSULTA,
                      publishedAfter=PUBLICADO_DESDE, videoCaption="any", safeSearch="none")
        for it in datos.get("items", []):
            vid = it["id"]["videoId"]
            encontrados.setdefault(vid, {"consultas": []})["consultas"].append(consulta)
    return encontrados


def estadisticas(c, ids):  # noqa: C901
    info = {}
    ids = list(ids)
    for i in range(0, len(ids), 50):
        datos = c.get("videos", COSTO["videos"], part="snippet,statistics", id=",".join(ids[i:i + 50]))
        for it in datos.get("items", []):
            s, e = it["snippet"], it.get("statistics", {})
            info[it["id"]] = {
                "titulo": s.get("title", ""),
                "canal": s.get("channelTitle", ""),
                "canal_id": s.get("channelId", ""),       # solo para limitar videos por canal; no se guarda
                "publicado": s.get("publishedAt", "")[:10],
                "vistas": int(e.get("viewCount", 0)),
                "comentarios_reportados": int(e.get("commentCount", 0)) if "commentCount" in e else None,
            }
    # País declarado por cada canal (channels.list). Muchos canales no lo declaran: por eso el criterio
    # también acepta títulos que mencionan Colombia.
    canales = sorted({d["canal_id"] for d in info.values() if d["canal_id"]})
    pais = {}
    for i in range(0, len(canales), 50):
        datos = c.get("channels", COSTO["canales"], part="snippet", id=",".join(canales[i:i + 50]))
        for it in datos.get("items", []):
            pais[it["id"]] = it["snippet"].get("country", "")
    for d in info.values():
        d["pais_canal"] = pais.get(d["canal_id"], "")
        d["es_colombiano"] = d["pais_canal"] == "CO" or any(p in d["titulo"].lower() for p in PALABRAS_COLOMBIA)
    return info


def seleccionar(info, encontrados):
    validos = [(v, d) for v, d in info.items()
               if d["comentarios_reportados"] is not None and d["comentarios_reportados"] >= MIN_COMENTARIOS_VIDEO]
    descartados_pocos = len(info) - len(validos)
    no_colombianos = 0
    if SOLO_CONTENIDO_COLOMBIANO:
        no_colombianos = sum(1 for _, d in validos if not d["es_colombiano"])
        validos = [(v, d) for v, d in validos if d["es_colombiano"]]
    validos.sort(key=lambda x: -x[1]["comentarios_reportados"])
    por_canal, elegidos = Counter(), []
    for v, d in validos:
        if por_canal[d["canal_id"]] >= MAX_VIDEOS_POR_CANAL:
            continue
        por_canal[d["canal_id"]] += 1
        elegidos.append(v)
        if len(elegidos) == MAX_VIDEOS:
            break
    return elegidos, descartados_pocos, len(validos), no_colombianos


def comentarios_de(c, video_id):
    """Comentarios de primer nivel. Devuelve (filas, motivo_de_parada)."""
    filas, token = [], None
    while len(filas) < MAX_COMENTARIOS_POR_VIDEO:
        params = dict(part="snippet", videoId=video_id, maxResults=100, order=ORDEN_COMENTARIOS, textFormat="plainText")
        if token:
            params["pageToken"] = token
        try:
            datos = c.get("commentThreads", COSTO["comentarios"], **params)
        except ErrorAPI as e:
            return filas, e.motivo  # p. ej. commentsDisabled, quotaExceeded
        for it in datos.get("items", []):
            s = it["snippet"]["topLevelComment"]["snippet"]
            texto = s.get("textDisplay", "")
            filas.append({
                "video_id": video_id,
                "id_hash": hash_id(it["id"]),
                "texto": texto,
                "me_gusta": int(s.get("likeCount", 0)),
                "fecha": s.get("publishedAt", "")[:10],
                "respuestas": int(it["snippet"].get("totalReplyCount", 0)),
            })
        token = datos.get("nextPageToken")
        if not token:
            return filas, "sin_mas_paginas"
    return filas[:MAX_COMENTARIOS_POR_VIDEO], "tope_por_video"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--simular", action="store_true", help="muestra el plan y la cuota sin llamar a la API")
    args = ap.parse_args()

    cuota_busqueda = len(CONSULTAS) * COSTO["search"]
    cuota_comentarios = MAX_VIDEOS * (MAX_COMENTARIOS_POR_VIDEO // 100) * COSTO["comentarios"]
    if args.simular:
        print(f"Consultas ({len(CONSULTAS)}): {CONSULTAS}")
        print(f"Región {REGION}, idioma {IDIOMA}, publicados desde {PUBLICADO_DESDE[:10]}")
        print(f"Cuota estimada: búsqueda {cuota_busqueda} + estadísticas ~3 + comentarios <= {cuota_comentarios}")
        return

    clave = cargar_clave()
    if not clave:
        sys.exit("Falta la clave: defina la variable de entorno YOUTUBE_API_KEY (o un archivo .env local). "
                 "Ver instrucciones en la cabecera de este script.")

    c = Cliente(clave)
    restricciones = []
    try:
        encontrados = buscar_videos(c)
        info = estadisticas(c, encontrados)
    except ErrorAPI as e:
        sys.exit(f"Error de la API en la búsqueda: {e}. Revise la clave, que la API esté habilitada y la cuota diaria.")

    elegidos, descartados_pocos, validos, no_colombianos = seleccionar(info, encontrados)
    todas, resumen_videos = [], []
    for vid in elegidos:
        filas, motivo = comentarios_de(c, vid)
        if motivo not in ("sin_mas_paginas", "tope_por_video"):
            restricciones.append(f"video {vid}: {motivo}")
        todas.extend(filas)
        d = info[vid]
        resumen_videos.append({
            "video_id": vid, "enlace": f"https://www.youtube.com/watch?v={vid}", "titulo": d["titulo"],
            "canal": d["canal"], "pais_canal": d["pais_canal"] or "no declarado", "publicado": d["publicado"], "vistas": d["vistas"],
            "comentarios_reportados": d["comentarios_reportados"], "comentarios_extraidos": len(filas),
            "motivo_parada": motivo, "consultas": " | ".join(sorted(set(encontrados[vid]["consultas"]))),
        })

    CARPETA_RAW.mkdir(parents=True, exist_ok=True)
    SALIDA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(CARPETA_RAW / "comentarios_crudos.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["video_id", "id_hash", "texto", "me_gusta", "fecha", "respuestas"])
        w.writeheader()
        w.writerows(todas)
    with open(CARPETA_RAW / "videos_consultados.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(resumen_videos[0].keys()) if resumen_videos else ["video_id"])
        w.writeheader()
        w.writerows(resumen_videos)

    resultado = {
        "fecha_extraccion": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "api": "YouTube Data API v3 (search.list, videos.list, commentThreads.list)",
        "proposito": "Contrastar lo que muestran los datos del RUNT (cuántos y dónde) con percepciones, barreras y motivaciones de usuarios.",
        "criterios": {
            "consultas": CONSULTAS, "region": REGION, "idioma_relevancia": IDIOMA, "publicados_desde": PUBLICADO_DESDE[:10],
            "resultados_por_consulta": RESULTADOS_POR_CONSULTA, "min_comentarios_por_video": MIN_COMENTARIOS_VIDEO,
            "max_videos": MAX_VIDEOS, "max_videos_por_canal": MAX_VIDEOS_POR_CANAL,
            "max_comentarios_por_video": MAX_COMENTARIOS_POR_VIDEO, "orden_comentarios": ORDEN_COMENTARIOS,
            "solo_comentarios_de_primer_nivel": True,
            "solo_contenido_colombiano": "canal con país declarado CO o título que menciona Colombia/Bogotá/Medellín",
        },
        "videos_encontrados": len(info),
        "videos_con_pocos_comentarios": descartados_pocos,
        "videos_descartados_por_no_ser_de_colombia": no_colombianos,
        "videos_validos": validos,
        "videos_consultados": len(elegidos),
        "comentarios_extraidos": len(todas),
        "videos": resumen_videos,
        "cuota_utilizada_unidades": c.cuota,
        "errores_api": dict(c.errores),
        "restricciones": restricciones + [
            "Solo comentarios de primer nivel: las respuestas no se descargan.",
            "Orden «relevance»: el tope por video (500) conserva los comentarios más relevantes, no una muestra aleatoria.",
            "La API no informa el país de quien comenta: aun en videos colombianos pueden comentar usuarios de otros países de habla hispana.",
            "La API no entrega todos los comentarios de un video con muchas respuestas ni los comentarios retenidos/eliminados.",
            "Cuota diaria de la API (10.000 unidades por proyecto): limita cuántas consultas y videos se pueden recolectar.",
        ],
        "privacidad": "No se almacenan nombres, canales, fotos ni enlaces de los autores; solo texto, me gusta, fecha y un hash del identificador del comentario.",
    }
    SALIDA_JSON.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Videos consultados: {len(elegidos)} · comentarios extraídos: {len(todas)} · cuota usada: {c.cuota}")
    print(f"Resumen: {SALIDA_JSON}")


if __name__ == "__main__":
    main()
