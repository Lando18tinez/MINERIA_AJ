-- =============================================================================
-- Etapa 5 · Modelo multidimensional (estrella) para SQLite
-- Diseño: docs/etapa5/modelo_multidimensional.md
-- Dataset: vehículos eléctricos e híbridos matriculados en Colombia
--          (RUNT 2.0, datos.gov.co ntxy-q9ix), ventana de análisis 2015-2024.
--
-- Este script solo crea la estructura: no carga datos. Se puede ejecutar varias
-- veces porque borra las tablas antes de crearlas.
--
-- Granularidad de hechos_registros: una fila por combinación única de combustible,
-- clase, carrocería, año de registro, año del modelo y territorio. Cada fila es un
-- GRUPO de vehículos y `cantidad` dice cuántos tiene: los vehículos se cuentan con
-- SUM(cantidad) y COUNT(*) cuenta grupos.
-- =============================================================================

-- SQLite no valida las llaves foráneas si no se activa en cada conexión.
PRAGMA foreign_keys = ON;

-- Se borra primero la tabla de hechos porque referencia a las dimensiones.
DROP TABLE IF EXISTS hechos_registros;
DROP TABLE IF EXISTS dim_tiempo;
DROP TABLE IF EXISTS dim_territorio;
DROP TABLE IF EXISTS dim_combustible;
DROP TABLE IF EXISTS dim_vehiculo;
DROP TABLE IF EXISTS dim_modelo;

-- -----------------------------------------------------------------------------
-- Dimensiones. Llave natural de cada una: UNIQUE.
-- -----------------------------------------------------------------------------

-- Año de registro (2015-2024). Jerarquía: periodo -> anio. No hay mes: la fuente no lo trae.
CREATE TABLE dim_tiempo (
    id_tiempo   INTEGER PRIMARY KEY,
    anio        INTEGER NOT NULL,            -- llave natural
    periodo     TEXT    NOT NULL,            -- '2015-2019' o '2020-2024'
    UNIQUE (anio)
);

-- Territorio = municipio + departamento. La llave natural es `territorio`
-- («MUNICIPIO (DEPARTAMENTO)») y no `municipio`, porque hay nombres de municipio
-- repetidos en más de un departamento.
CREATE TABLE dim_territorio (
    id_territorio  INTEGER PRIMARY KEY,
    territorio     TEXT NOT NULL,            -- llave natural
    municipio      TEXT NOT NULL,
    departamento   TEXT NOT NULL,
    UNIQUE (territorio)
);

-- Combustible. Jerarquía: familia -> codigo. La fuente no distingue HEV de PHEV.
CREATE TABLE dim_combustible (
    id_combustible  INTEGER PRIMARY KEY,
    codigo          TEXT NOT NULL,           -- llave natural (ELECTRICO, GASO ELEC, DIES ELEC, HIDROGENO)
    etiqueta        TEXT NOT NULL,
    familia         TEXT NOT NULL,           -- Eléctrico, Híbrido u Otro
    UNIQUE (codigo)
);

-- Vehículo = clase + carrocería. Jerarquía: categoria -> clase -> carroceria.
-- «SIN DATO» (faltante de la fuente) y «SIN CARROCERIA» (no aplicable) son miembros
-- distintos de carroceria y no se mezclan.
CREATE TABLE dim_vehiculo (
    id_vehiculo  INTEGER PRIMARY KEY,
    categoria    TEXT NOT NULL,
    clase        TEXT NOT NULL,
    carroceria   TEXT NOT NULL,
    UNIQUE (clase, carroceria)               -- llave natural
);

-- Año del modelo, que no es el año de registro. Jerarquía: rango_modelo -> anio_modelo.
CREATE TABLE dim_modelo (
    id_modelo     INTEGER PRIMARY KEY,
    anio_modelo   INTEGER NOT NULL,          -- llave natural
    rango_modelo  TEXT    NOT NULL,
    UNIQUE (anio_modelo)
);

-- -----------------------------------------------------------------------------
-- Hechos
-- -----------------------------------------------------------------------------

CREATE TABLE hechos_registros (
    id_hecho        INTEGER PRIMARY KEY,
    id_tiempo       INTEGER NOT NULL,
    id_territorio   INTEGER NOT NULL,
    id_combustible  INTEGER NOT NULL,
    id_vehiculo     INTEGER NOT NULL,
    id_modelo       INTEGER NOT NULL,
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),   -- vehículos del grupo
    modelo_inusual  TEXT    NOT NULL,        -- 'Sí' si el año del modelo > año de registro + 1
    grupo_grande    TEXT    NOT NULL,        -- 'Sí' si cantidad > 16 (umbral IQR de la Etapa 2)

    FOREIGN KEY (id_tiempo)      REFERENCES dim_tiempo      (id_tiempo),
    FOREIGN KEY (id_territorio)  REFERENCES dim_territorio  (id_territorio),
    FOREIGN KEY (id_combustible) REFERENCES dim_combustible (id_combustible),
    FOREIGN KEY (id_vehiculo)    REFERENCES dim_vehiculo    (id_vehiculo),
    FOREIGN KEY (id_modelo)      REFERENCES dim_modelo      (id_modelo),

    -- Protege la granularidad: no puede haber dos grupos con la misma combinación.
    UNIQUE (id_tiempo, id_territorio, id_combustible, id_vehiculo, id_modelo)
);

-- Índices para las claves foráneas (acelera los cruces entre hechos y dimensiones).
CREATE INDEX idx_hechos_id_tiempo      ON hechos_registros (id_tiempo);
CREATE INDEX idx_hechos_id_territorio  ON hechos_registros (id_territorio);
CREATE INDEX idx_hechos_id_combustible ON hechos_registros (id_combustible);
CREATE INDEX idx_hechos_id_vehiculo    ON hechos_registros (id_vehiculo);
CREATE INDEX idx_hechos_id_modelo      ON hechos_registros (id_modelo);
