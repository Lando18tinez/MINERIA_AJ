# Transición hacia la Movilidad Sostenible en Bogotá

Proyecto de **Minería de Datos** que analiza la adopción de vehículos híbridos y eléctricos en Bogotá D.C. y Colombia (2014–2024), y cuantifica su impacto en la reducción de la huella de carbono del transporte. La aplicación web (Flask) documenta todo el proceso metodológico por etapas: comprensión del negocio y los datos, y auditoría/remediación de la calidad de los datos.

## Equipo

| Integrante |
|---|
| Angelica Rosa Olier Quiroga |
| Johan Orlando Martinez Suarez |

## Contenido de la aplicación

La barra de navegación tiene dos menús desplegables, uno por etapa del proyecto.

### Etapa 1 · Comprensión del negocio y de los datos

| # | Sección | Ruta |
|---|---|---|
| 1 | Problema y contexto | `/etapa1/problema-contexto` |
| 2 | Pregunta principal y preguntas secundarias | `/etapa1/preguntas` |
| 3 | Necesidades de información | `/etapa1/necesidades-informacion` |
| 4 | Fuentes de datos | `/etapa1/fuentes-datos` |
| 5 | Dataset | `/etapa1/dataset` |
| 6 | Diccionario de datos | `/etapa1/diccionario-datos` |
| 7 | Calidad inicial de los datos | `/etapa1/calidad-inicial` |
| 8 | Limitaciones y consideraciones | `/etapa1/limitaciones` |

### Etapa 2 · Calidad de datos

| # | Sección | Ruta |
|---|---|---|
| 1 | Propósito y requisitos de calidad | `/etapa2/proposito-requisitos` |
| 2 | Perfilamiento del dataset | `/etapa2/perfilamiento` |
| 3 | Dimensiones y métricas de calidad | `/etapa2/dimensiones-metricas` |
| 4 | Inventario de problemas y causas | `/etapa2/inventario-problemas` |
| 5 | Plan de tratamiento y homologación | `/etapa2/plan-tratamiento` |
| 6 | Comparación antes y después | `/etapa2/comparacion-antes-despues` |

### Etapa 3 · Preparación de los datos (ETL)

| # | Sección | Ruta |
|---|---|---|
| 1 | ETL: Extracción, Transformación y Carga (PDF embebido + enlace al video) | `/etapa3/etl` |

### Etapa 4 · Análisis exploratorio de la población

| # | Dimensión | Ruta |
|---|---|---|
| 1 | Poblacional | `/etapa4/poblacional` |
| 2 | Territorial | `/etapa4/territorial` |

Otras páginas: **Inicio** (`/`) y **Participantes** (`/participantes`).

### Evidencia: datos y código

| Ruta | Contenido |
|---|---|
| `/datos/vehiculos_electricos_hibridos_runt.csv` | Dataset descargado de datos.gov.co (fuente única) |
| `/datos/FUENTE.json` | Procedencia: identificador, URL, fecha de descarga |
| `/datos/resultados_eda.json` | Todos los resultados calculados que muestra la app |
| `/codigo/calidad_etapa2.py` | Script que genera esos resultados |
| `/datos/resultados_etapa4.json` | Resultados del análisis exploratorio (Etapa 4) |
| `/codigo/eda_etapa4.py` | Script que genera los resultados de la Etapa 4 |

## Tecnologías

- **[Flask](https://flask.palletsprojects.com/)** (Python) — backend y renderizado de plantillas con Jinja2.
- **Bootstrap 5.3.3** + **Bootstrap Icons** — interfaz, vía CDN.
- **Google Fonts (Plus Jakarta Sans)** — tipografía.
- **[Chart.js 4](https://www.chartjs.org/)** — gráficas de perfilamiento, dimensiones de calidad, inventario de problemas y plan de tratamiento (Etapa 2), vía CDN.
- **Gunicorn** — servidor WSGI para despliegue en producción.

## Estructura del proyecto

```
MINERIA_AJ-1/
├── app.py                        # Rutas, datos de las secciones y contexto Jinja2
├── calidad_etapa2.py                 # Perfilamiento, calidad y tratamiento (pandas) -> data/processed/resultados_eda.json
├── eda_etapa4.py                 # Análisis exploratorio (pandas) -> data/processed/resultados_etapa4.json
├── requirements-dev.txt          # Dependencias para regenerar los resultados (pandas, numpy)
├── data/
│   ├── raw/                      # CSV descargado de datos.gov.co (ntxy-q9ix) + FUENTE.json (procedencia)
│   └── processed/                # resultados_eda.json (lo único que lee la app)
├── auditoria_calidad_etapa2.py   # (obsoleto) borrador previo: apuntaba a un dataset de 18 variables que la fuente no contiene
├── requirements.txt
├── static/
│   ├── css/styles.css            # Sistema de diseño "Green Energy" (paleta, componentes, navbar)
│   └── img/                      # Fotos del equipo
└── templates/
    ├── base.html                 # Layout base: navbar, footer, bloques Jinja2
    ├── index.html                # Portada
    ├── participantes.html
    ├── etapa1/                   # Plantillas de la Etapa 1 (una por sección + seccion.html genérica)
    └── etapa2/                   # Plantillas de la Etapa 2 (una por sección + seccion.html genérica)
```

Cada plantilla de sección extiende `etapaN/seccion.html` (breadcrumb, encabezado y navegación), que a su vez extiende `base.html`. Las rutas `/etapa1/<slug>` y `/etapa2/<slug>` resuelven la plantilla a partir de un diccionario en `app.py`; si una sección aún no tiene plantilla propia, se muestra una vista genérica de "contenido en construcción" en lugar de un error.

## Instalación y ejecución local

```bash
git clone https://github.com/Lando18tinez/MINERIA_AJ.git
cd MINERIA_AJ
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
python app.py
```

La aplicación queda disponible en `http://127.0.0.1:5000`.

### Reproducir los resultados

Todas las cifras de las Etapas 2 y 4 salen de `data/processed/resultados_eda.json` y `resultados_etapa4.json`, generados a partir del CSV de `data/raw/`:

```bash
pip install -r requirements-dev.txt
python calidad_etapa2.py   # Etapa 2 -> resultados_eda.json
python eda_etapa4.py       # Etapa 4 -> resultados_etapa4.json (requiere el paso anterior)
```

El CSV se descargó de `https://www.datos.gov.co/resource/ntxy-q9ix.csv?$limit=50000&$order=:id` (ver `data/raw/FUENTE.json`).
Es un dataset **agregado**: cada fila es un grupo de vehículos y `cantidad` indica cuántos son, por eso los porcentajes se ponderan por `cantidad`.

## Flujo de trabajo con Git

El desarrollo se organiza por etapas, cada una en su propia rama:

- `main` — versión estable/entregada.
- `feature/etapa-1` — Etapa 1 (comprensión del negocio y los datos).
- `feature/etapa-2` — Etapa 2 (calidad de datos).

Al cerrar cada etapa se abre un **Pull Request** hacia `main` para integrar los cambios.

## Fuente de datos

El análisis usa **una única fuente**: *Vehículos eléctricos e híbridos matriculados en Colombia - RUNT 2.0*
([datos.gov.co · `ntxy-q9ix`](https://www.datos.gov.co/Transporte/VEH-CULOS-EL-CTRICOS-E-H-BRIDOS-MATRICULADOS-EN-CO/ntxy-q9ix/about_data)).
Trae 8 variables (`combustible`, `modelo`, `a_o_registro`, `clase`, `carroceria`, `municipio`, `departamento`, `cantidad`): 10.748 filas que resumen 332.901 vehículos
registrados entre 2015 y 2026 (2026 parcial).

Las variables previstas en el diccionario de datos que esta fuente **no incluye** (potencia, cilindraje, marca, códigos DIVIPOLA, población, etc.) se conservan documentadas
como *no disponibles* en la Etapa 2, sin reportar resultados sobre ellas.

## Estado del proyecto

- ✅ Etapas 1 a 4 implementadas en la aplicación (contenido, tablas y gráficas).
- ✅ Etapa 2 corregida: perfilamiento y métricas recalculados sobre el dataset real, con datos, código y resultados descargables.
- ⚠️ Pendiente: alinear el texto de la Etapa 1 (dataset, diccionario, calidad inicial) con el esquema real de la fuente.
- ⏳ Despliegue en producción (Render) pendiente de configurar.
- ⏳ Informe técnico del proceso (documento aparte, con evidencias incrustadas).

---
Proyecto académico — Minería de Datos, Universidad de Cundinamarca.
