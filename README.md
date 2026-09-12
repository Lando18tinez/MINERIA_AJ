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

Otras páginas: **Inicio** (`/`) y **Participantes** (`/participantes`).

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
├── auditoria_calidad_etapa2.py   # Script de apoyo: calcula las métricas de calidad (Pandas) sobre el dataset crudo
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

## Flujo de trabajo con Git

El desarrollo se organiza por etapas, cada una en su propia rama:

- `main` — versión estable/entregada.
- `feature/etapa-1` — Etapa 1 (comprensión del negocio y los datos).
- `feature/etapa-2` — Etapa 2 (calidad de datos).

Al cerrar cada etapa se abre un **Pull Request** hacia `main` para integrar los cambios.

## Fuentes de datos

Los microdatos provienen de fuentes oficiales abiertas: **RUNT 2.0** (matrículas y parque automotor), **DANE** (proyecciones de población), **Datos Abiertos Bogotá / SIMUR** (transporte y movilidad), y factores de emisión de ciclo de vida *Well-to-Wheel* (**Ecoinvent / UPME / IEA**). El detalle de cada dataset —formato, granularidad y enlace directo— está documentado en **Etapa 1 → Sección 4 · Fuentes de datos**.

## Estado del proyecto

- ✅ Etapa 1 y Etapa 2 implementadas en la aplicación (contenido, tablas y gráficas).
- ⏳ Despliegue en producción (Render) pendiente de configurar.
- ⏳ Informe técnico del proceso (documento aparte, con evidencias incrustadas).

---
Proyecto académico — Minería de Datos, Universidad de Cundinamarca.
