-- =============================================================================
-- Etapa 5 · Validaciones del modelo estrella (SQLite)
-- Modelo: sql/01_crear_modelo.sql · Base: data/modelo/modelo_estrella.db
--
-- Solo consulta (SELECT): no modifica la base. Lo ejecuta validar_modelo.py.
--
-- Formato: cada consulta devuelve UNA fila con cinco columnas:
--   id            código de la comprobación
--   grupo         bloque al que pertenece
--   comprobacion  qué se mide
--   tipo          'debe_ser_cero' (cualquier valor distinto de 0 es un error)
--                 o 'informativo' (se reporta, no se juzga)
--   valor         resultado de la consulta
-- No uses punto y coma dentro de los comentarios: el lector separa las
-- consultas por el punto y coma final de cada una.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Unicidad de las claves primarias (cuenta cuántos valores aparecen repetidos)
-- -----------------------------------------------------------------------------
SELECT 'PK01' AS id, 'Unicidad de claves primarias' AS grupo, 'dim_tiempo.id_tiempo: valores repetidos' AS comprobacion, 'debe_ser_cero' AS tipo, COUNT(*) AS valor
FROM (SELECT id_tiempo FROM dim_tiempo GROUP BY id_tiempo HAVING COUNT(*) > 1);

SELECT 'PK02', 'Unicidad de claves primarias', 'dim_territorio.id_territorio: valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT id_territorio FROM dim_territorio GROUP BY id_territorio HAVING COUNT(*) > 1);

SELECT 'PK03', 'Unicidad de claves primarias', 'dim_combustible.id_combustible: valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT id_combustible FROM dim_combustible GROUP BY id_combustible HAVING COUNT(*) > 1);

SELECT 'PK04', 'Unicidad de claves primarias', 'dim_vehiculo.id_vehiculo: valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT id_vehiculo FROM dim_vehiculo GROUP BY id_vehiculo HAVING COUNT(*) > 1);

SELECT 'PK05', 'Unicidad de claves primarias', 'dim_modelo.id_modelo: valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT id_modelo FROM dim_modelo GROUP BY id_modelo HAVING COUNT(*) > 1);

SELECT 'PK06', 'Unicidad de claves primarias', 'hechos_registros.id_hecho: valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT id_hecho FROM hechos_registros GROUP BY id_hecho HAVING COUNT(*) > 1);

-- -----------------------------------------------------------------------------
-- 2. Unicidad de la llave natural de cada dimensión
-- -----------------------------------------------------------------------------
SELECT 'NK01', 'Unicidad de llaves naturales', 'dim_tiempo (anio): valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT anio FROM dim_tiempo GROUP BY anio HAVING COUNT(*) > 1);

SELECT 'NK02', 'Unicidad de llaves naturales', 'dim_territorio (territorio): valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT territorio FROM dim_territorio GROUP BY territorio HAVING COUNT(*) > 1);

SELECT 'NK03', 'Unicidad de llaves naturales', 'dim_combustible (codigo): valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT codigo FROM dim_combustible GROUP BY codigo HAVING COUNT(*) > 1);

SELECT 'NK04', 'Unicidad de llaves naturales', 'dim_vehiculo (clase, carroceria): parejas repetidas', 'debe_ser_cero', COUNT(*)
FROM (SELECT clase, carroceria FROM dim_vehiculo GROUP BY clase, carroceria HAVING COUNT(*) > 1);

SELECT 'NK05', 'Unicidad de llaves naturales', 'dim_modelo (anio_modelo): valores repetidos', 'debe_ser_cero', COUNT(*)
FROM (SELECT anio_modelo FROM dim_modelo GROUP BY anio_modelo HAVING COUNT(*) > 1);

-- -----------------------------------------------------------------------------
-- 3. Correspondencia de las claves foráneas de hechos_registros
--    (filas de hechos cuya clave no existe en su dimensión)
-- -----------------------------------------------------------------------------
SELECT 'FK01', 'Correspondencia de claves foráneas', 'hechos_registros.id_tiempo sin pareja en dim_tiempo', 'debe_ser_cero', COUNT(*)
FROM hechos_registros h LEFT JOIN dim_tiempo d ON d.id_tiempo = h.id_tiempo
WHERE d.id_tiempo IS NULL;

SELECT 'FK02', 'Correspondencia de claves foráneas', 'hechos_registros.id_territorio sin pareja en dim_territorio', 'debe_ser_cero', COUNT(*)
FROM hechos_registros h LEFT JOIN dim_territorio d ON d.id_territorio = h.id_territorio
WHERE d.id_territorio IS NULL;

SELECT 'FK03', 'Correspondencia de claves foráneas', 'hechos_registros.id_combustible sin pareja en dim_combustible', 'debe_ser_cero', COUNT(*)
FROM hechos_registros h LEFT JOIN dim_combustible d ON d.id_combustible = h.id_combustible
WHERE d.id_combustible IS NULL;

SELECT 'FK04', 'Correspondencia de claves foráneas', 'hechos_registros.id_vehiculo sin pareja en dim_vehiculo', 'debe_ser_cero', COUNT(*)
FROM hechos_registros h LEFT JOIN dim_vehiculo d ON d.id_vehiculo = h.id_vehiculo
WHERE d.id_vehiculo IS NULL;

SELECT 'FK05', 'Correspondencia de claves foráneas', 'hechos_registros.id_modelo sin pareja en dim_modelo', 'debe_ser_cero', COUNT(*)
FROM hechos_registros h LEFT JOIN dim_modelo d ON d.id_modelo = h.id_modelo
WHERE d.id_modelo IS NULL;

SELECT 'FK06', 'Correspondencia de claves foráneas', 'PRAGMA foreign_key_check: violaciones en toda la base', 'debe_ser_cero', COUNT(*)
FROM pragma_foreign_key_check;

-- -----------------------------------------------------------------------------
-- 4. Duplicados en las 5 claves foráneas (protege la granularidad)
-- -----------------------------------------------------------------------------
SELECT 'DU01', 'Duplicados en las 5 claves foráneas', 'combinaciones (id_tiempo, id_territorio, id_combustible, id_vehiculo, id_modelo) repetidas', 'debe_ser_cero', COUNT(*)
FROM (
    SELECT 1
    FROM hechos_registros
    GROUP BY id_tiempo, id_territorio, id_combustible, id_vehiculo, id_modelo
    HAVING COUNT(*) > 1
);

-- -----------------------------------------------------------------------------
-- 5. Ausencia de NULL en las claves foráneas y en cantidad
-- -----------------------------------------------------------------------------
SELECT 'NU01', 'Ausencia de NULL', 'hechos_registros.id_tiempo NULL', 'debe_ser_cero', COUNT(*)
FROM hechos_registros WHERE id_tiempo IS NULL;

SELECT 'NU02', 'Ausencia de NULL', 'hechos_registros.id_territorio NULL', 'debe_ser_cero', COUNT(*)
FROM hechos_registros WHERE id_territorio IS NULL;

SELECT 'NU03', 'Ausencia de NULL', 'hechos_registros.id_combustible NULL', 'debe_ser_cero', COUNT(*)
FROM hechos_registros WHERE id_combustible IS NULL;

SELECT 'NU04', 'Ausencia de NULL', 'hechos_registros.id_vehiculo NULL', 'debe_ser_cero', COUNT(*)
FROM hechos_registros WHERE id_vehiculo IS NULL;

SELECT 'NU05', 'Ausencia de NULL', 'hechos_registros.id_modelo NULL', 'debe_ser_cero', COUNT(*)
FROM hechos_registros WHERE id_modelo IS NULL;

SELECT 'NU06', 'Ausencia de NULL', 'hechos_registros.cantidad NULL', 'debe_ser_cero', COUNT(*)
FROM hechos_registros WHERE cantidad IS NULL;

-- -----------------------------------------------------------------------------
-- 6. Conteo de SIN DATO (faltante de la fuente) y SIN CARROCERIA (no aplicable)
--    Son categorías distintas y se conservan tal como vienen en la fuente.
-- -----------------------------------------------------------------------------
SELECT 'SD01', 'SIN DATO y SIN CARROCERIA', 'SIN DATO: miembros en dim_vehiculo', 'informativo', COUNT(*)
FROM dim_vehiculo WHERE carroceria = 'SIN DATO';

SELECT 'SD02', 'SIN DATO y SIN CARROCERIA', 'SIN DATO: grupos en hechos_registros', 'informativo', COUNT(*)
FROM hechos_registros h JOIN dim_vehiculo v ON v.id_vehiculo = h.id_vehiculo
WHERE v.carroceria = 'SIN DATO';

SELECT 'SD03', 'SIN DATO y SIN CARROCERIA', 'SIN DATO: vehículos (SUM de cantidad)', 'informativo', COALESCE(SUM(h.cantidad), 0)
FROM hechos_registros h JOIN dim_vehiculo v ON v.id_vehiculo = h.id_vehiculo
WHERE v.carroceria = 'SIN DATO';

SELECT 'SC01', 'SIN DATO y SIN CARROCERIA', 'SIN CARROCERIA: miembros en dim_vehiculo', 'informativo', COUNT(*)
FROM dim_vehiculo WHERE carroceria = 'SIN CARROCERIA';

SELECT 'SC02', 'SIN DATO y SIN CARROCERIA', 'SIN CARROCERIA: grupos en hechos_registros', 'informativo', COUNT(*)
FROM hechos_registros h JOIN dim_vehiculo v ON v.id_vehiculo = h.id_vehiculo
WHERE v.carroceria = 'SIN CARROCERIA';

SELECT 'SC03', 'SIN DATO y SIN CARROCERIA', 'SIN CARROCERIA: vehículos (SUM de cantidad)', 'informativo', COALESCE(SUM(h.cantidad), 0)
FROM hechos_registros h JOIN dim_vehiculo v ON v.id_vehiculo = h.id_vehiculo
WHERE v.carroceria = 'SIN CARROCERIA';
