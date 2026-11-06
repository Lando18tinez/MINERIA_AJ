-- =============================================================================
-- Etapa 5 · Consultas de las cinco operaciones OLAP (SQLite)
-- Base: data/modelo/modelo_estrella.db · Código: olap.py · Vistas: /analisis-multidimensional/p1 a p4
--
-- Solo consulta (SELECT): no modifica la base. Se puede ejecutar directamente en SQLite.
--
-- Las consultas marcadas «olap.py» son las sentencias que olap.py ejecuta para cada selección,
-- copiadas de una traza de la conexión (sqlite3 set_trace_callback) al abrir la URL indicada.
-- En olap.py los valores se pasan como parámetros (?), aquí ya están sustituidos.
--
-- Las marcadas «complementaria» no las ejecuta olap.py: reproducen en SQL el cálculo que olap.py
-- o app.py hacen en Python (porcentajes, diferencias entre años, promedio y mediana), para poder
-- comprobar el resultado solo con SQLite.
--
-- Los vehículos se cuentan con SUM(cantidad), nunca contando filas. La ventana es 2015-2024.
-- No uses punto y coma dentro de los comentarios: cada consulta termina en el primer punto y coma.
-- =============================================================================


-- =============================================================================
-- 1. DRILL-DOWN (P1) · de clase a carrocería
-- URL: /analisis-multidimensional/p1?clase=CAMIONETA&anio=2024&nivel=carroceria
-- =============================================================================

-- 1a · olap.py · consultar() composición del nivel de partida (nivel clase)
-- Operación:   drill-down, antes de bajar
-- Vista:       P1
-- Dimensiones: tiempo (anio), combustible (familia), vehículo (clase)
-- Medida:      vehículos registrados = SUM(cantidad)
-- Filtros:     familia = Eléctrico, anio = 2024, clase = CAMIONETA
-- Nivel:       clase
-- Esperado:    CAMIONETA 5.798
SELECT v.clase, SUM(h.cantidad) AS veh
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE c.familia IN ('Eléctrico') AND t.anio IN (2024) AND v.clase IN ('CAMIONETA') GROUP BY v.clase ORDER BY veh DESC, v.clase;

-- 1b · olap.py · consultar() composición después del drill-down (nivel carrocería)
-- Operación:   drill-down
-- Vista:       P1
-- Dimensiones: tiempo (anio), combustible (familia), vehículo (clase → carroceria)
-- Medida:      vehículos registrados = SUM(cantidad)
-- Filtros:     familia = Eléctrico, anio = 2024, clase = CAMIONETA
-- Nivel:       clase · carrocería
-- Esperado:    CAMIONETA · WAGON 5.435 (primera fila)
SELECT v.clase, v.carroceria, SUM(h.cantidad) AS veh
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE c.familia IN ('Eléctrico') AND t.anio IN (2024) AND v.clase IN ('CAMIONETA') GROUP BY v.clase, v.carroceria ORDER BY veh DESC, v.clase, v.carroceria;

-- 1c · olap.py · total() denominador de la participación
-- Operación:   drill-down
-- Vista:       P1
-- Dimensiones: tiempo, combustible, vehículo
-- Medida:      vehículos registrados = SUM(cantidad) y grupos de registro = COUNT(*)
-- Filtros:     familia = Eléctrico, anio = 2024, clase = CAMIONETA
-- Nivel:       toda la selección
-- Esperado:    5.798 vehículos
SELECT COALESCE(SUM(h.cantidad), 0), COUNT(*)
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE c.familia IN ('Eléctrico') AND t.anio IN (2024) AND v.clase IN ('CAMIONETA');

-- 1d · complementaria · participación = vehículos de la carrocería / vehículos de la selección × 100
-- (olap.consultar la calcula en Python con los resultados de 1b y 1c)
-- Esperado:    WAGON 5.435 de 5.798 = 93,74 %
SELECT v.carroceria,
       SUM(h.cantidad) AS veh,
       (SELECT SUM(h2.cantidad) FROM hechos_registros h2
          JOIN dim_combustible c2 ON c2.id_combustible = h2.id_combustible
          JOIN dim_tiempo      t2 ON t2.id_tiempo      = h2.id_tiempo
          JOIN dim_vehiculo    v2 ON v2.id_vehiculo    = h2.id_vehiculo
         WHERE c2.familia = 'Eléctrico' AND t2.anio = 2024 AND v2.clase = 'CAMIONETA') AS denominador,
       ROUND(SUM(h.cantidad) * 100.0 /
             (SELECT SUM(h2.cantidad) FROM hechos_registros h2
                JOIN dim_combustible c2 ON c2.id_combustible = h2.id_combustible
                JOIN dim_tiempo      t2 ON t2.id_tiempo      = h2.id_tiempo
                JOIN dim_vehiculo    v2 ON v2.id_vehiculo    = h2.id_vehiculo
               WHERE c2.familia = 'Eléctrico' AND t2.anio = 2024 AND v2.clase = 'CAMIONETA'), 2) AS pct
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
 WHERE c.familia = 'Eléctrico' AND t.anio = 2024 AND v.clase = 'CAMIONETA' AND v.carroceria = 'WAGON'
 GROUP BY v.carroceria;


-- =============================================================================
-- 2. ROLL-UP (P2) · de municipio a departamento
-- URL municipio:    /analisis-multidimensional/p2?departamento=ANTIOQUIA&anio=2021&anio=2024&nivel=municipio
-- URL departamento: /analisis-multidimensional/p2?departamento=ANTIOQUIA&anio=2021&anio=2024
-- =============================================================================

-- 2a · olap.py · consultar() celdas de la matriz municipio × año
-- Operación:   roll-up, nivel de partida
-- Vista:       P2
-- Dimensiones: tiempo (anio), territorio (departamento → municipio), combustible (familia)
-- Medida:      vehículos registrados = SUM(cantidad)
-- Filtros:     familia = Eléctrico, anio = 2021 y 2024, departamento = ANTIOQUIA
-- Nivel:       municipio (llave territorio)
-- Esperado:    una fila por municipio y año. MEDELLIN 215 → 845
SELECT r.territorio, t.anio, SUM(h.cantidad)
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE c.familia IN ('Eléctrico') AND t.anio IN (2021, 2024) AND r.departamento IN ('ANTIOQUIA') GROUP BY r.territorio, t.anio;

-- 2b · olap.py · consultar() serie anual (fila «Total» de la matriz municipio × año)
-- Operación:   roll-up, nivel de partida
-- Vista:       P2
-- Dimensiones: tiempo, territorio, combustible
-- Medida:      vehículos registrados = SUM(cantidad)
-- Filtros:     familia = Eléctrico, anio = 2021 y 2024, departamento = ANTIOQUIA
-- Nivel:       municipio (suma de todos los municipios)
-- Esperado:    2021 = 1.051, 2024 = 1.880 (aumento de 829)
SELECT t.anio, SUM(h.cantidad)
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE c.familia IN ('Eléctrico') AND t.anio IN (2021, 2024) AND r.departamento IN ('ANTIOQUIA') GROUP BY t.anio;

-- 2c · olap.py · consultar() celdas de la matriz departamento × año, después del roll-up
-- Operación:   roll-up
-- Vista:       P2
-- Dimensiones: tiempo (anio), territorio (departamento), combustible (familia)
-- Medida:      vehículos registrados = SUM(cantidad)
-- Filtros:     familia = Eléctrico, anio = 2021 y 2024, departamento = ANTIOQUIA
-- Nivel:       departamento
-- Esperado:    ANTIOQUIA 2021 = 1.051, 2024 = 1.880 (aumento de 829)
SELECT r.departamento, t.anio, SUM(h.cantidad)
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE c.familia IN ('Eléctrico') AND t.anio IN (2021, 2024) AND r.departamento IN ('ANTIOQUIA') GROUP BY r.departamento, t.anio;

-- 2d · complementaria · aumento 2021 → 2024 calculado en los dos niveles
-- (app.py resta en Python los valores de 2024 y 2021 de las consultas anteriores)
-- Nivel municipio:    suma de los aumentos de cada municipio
-- Nivel departamento: aumento del total del departamento
-- Esperado:    829 en ambos niveles
SELECT 'municipio' AS nivel, SUM(aumento) AS aumento
FROM (SELECT r.territorio,
             SUM(CASE WHEN t.anio = 2024 THEN h.cantidad ELSE 0 END)
           - SUM(CASE WHEN t.anio = 2021 THEN h.cantidad ELSE 0 END) AS aumento
        FROM hechos_registros h
        JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
        JOIN dim_combustible c ON c.id_combustible = h.id_combustible
        JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
       WHERE c.familia = 'Eléctrico' AND t.anio IN (2021, 2024) AND r.departamento = 'ANTIOQUIA'
       GROUP BY r.territorio)
UNION ALL
SELECT 'departamento',
       SUM(CASE WHEN t.anio = 2024 THEN h.cantidad ELSE 0 END)
     - SUM(CASE WHEN t.anio = 2021 THEN h.cantidad ELSE 0 END)
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
 WHERE c.familia = 'Eléctrico' AND t.anio IN (2021, 2024) AND r.departamento = 'ANTIOQUIA'
 GROUP BY r.departamento;


-- =============================================================================
-- 3. SLICE (P4) · un solo valor de la dimensión combustible
-- URL: /analisis-multidimensional/p4?familia=Eléctrico
--
-- Promedio y mediana: olap.totales_por_territorio() ejecuta la consulta 3a y devuelve los totales de cada
-- territorio. Después olap.resumen_territorial() calcula en Python:
--   promedio = suma de los totales / número de territorios (solo territorios con al menos un vehículo)
--   mediana  = statistics.median(totales): con un número par de territorios, el promedio de los dos centrales
-- SQLite no tiene función MEDIAN, pero la mediana se puede obtener con funciones de ventana (SQLite 3.25 o
-- posterior): la consulta 3b lo hace y debe dar el mismo valor que olap.py.
-- =============================================================================

-- 3a · olap.py · totales_por_territorio() totales por territorio, de mayor a menor
-- Operación:   slice
-- Vista:       P4
-- Dimensiones: combustible (familia), territorio (municipio)
-- Medida:      vehículos registrados por territorio = SUM(cantidad)
-- Filtros:     familia = Eléctrico (los 10 años de registro, sin filtro de tiempo)
-- Nivel:       municipio (llave territorio)
-- Esperado:    220 filas (territorios). Primera fila: BOGOTA (BOGOTA D.C.)
SELECT r.territorio, SUM(h.cantidad) AS veh
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE c.familia IN ('Eléctrico') GROUP BY r.territorio ORDER BY veh DESC, r.territorio;

-- 3b · complementaria · territorios, promedio y mediana a partir de los totales de 3a
-- Operación:   slice
-- Vista:       P4
-- Medida:      territorios distintos, promedio y mediana de vehículos por territorio
-- Filtros:     familia = Eléctrico
-- Nivel:       municipio
-- Esperado:    220 territorios, promedio 168,0, mediana 11
WITH totales AS (
  SELECT r.territorio, SUM(h.cantidad) AS veh
  FROM hechos_registros h
  JOIN dim_combustible c ON c.id_combustible = h.id_combustible
  JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
   WHERE c.familia = 'Eléctrico'
   GROUP BY r.territorio
), ordenados AS (
  SELECT veh, ROW_NUMBER() OVER (ORDER BY veh) AS fila, COUNT(*) OVER () AS n FROM totales
)
SELECT (SELECT COUNT(*) FROM totales) AS territorios,
       (SELECT SUM(veh) FROM totales) AS vehiculos,
       ROUND((SELECT SUM(veh) * 1.0 / COUNT(*) FROM totales), 1) AS promedio,
       (SELECT AVG(veh) FROM ordenados WHERE fila IN ((n + 1) / 2, (n + 2) / 2)) AS mediana;


-- =============================================================================
-- 4. DICE (P4) · filtros combinados en las dimensiones combustible y vehículo
-- URL: /analisis-multidimensional/p4?familia=Eléctrico&categoria=Liviano
-- El promedio y la mediana se calculan como en el slice (ver la explicación de la sección 3).
-- =============================================================================

-- 4a · olap.py · totales_por_territorio() totales por territorio, de mayor a menor
-- Operación:   dice
-- Vista:       P4
-- Dimensiones: combustible (familia), vehículo (categoria), territorio (municipio)
-- Medida:      vehículos registrados por territorio = SUM(cantidad)
-- Filtros:     familia = Eléctrico, categoria = Liviano (los 10 años de registro)
-- Nivel:       municipio (llave territorio)
-- Esperado:    106 filas. Primera fila: BOGOTA (BOGOTA D.C.) 9.448
SELECT r.territorio, SUM(h.cantidad) AS veh
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE c.familia IN ('Eléctrico') AND v.categoria IN ('Liviano') GROUP BY r.territorio ORDER BY veh DESC, r.territorio;

-- 4b · complementaria · vehículos, territorios, participación de Bogotá y mediana a partir de 4a
-- Operación:   dice
-- Vista:       P4
-- Medida:      vehículos, territorios distintos, participación del líder, mediana por territorio
-- Filtros:     familia = Eléctrico, categoria = Liviano
-- Nivel:       municipio
-- Esperado:    16.745 vehículos, 106 territorios, Bogotá 9.448 (56,42 %), mediana 3
WITH totales AS (
  SELECT r.territorio, SUM(h.cantidad) AS veh
  FROM hechos_registros h
  JOIN dim_combustible c ON c.id_combustible = h.id_combustible
  JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
  JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
   WHERE c.familia = 'Eléctrico' AND v.categoria = 'Liviano'
   GROUP BY r.territorio
), ordenados AS (
  SELECT veh, ROW_NUMBER() OVER (ORDER BY veh) AS fila, COUNT(*) OVER () AS n FROM totales
)
SELECT (SELECT SUM(veh) FROM totales) AS vehiculos,
       (SELECT COUNT(*) FROM totales) AS territorios,
       (SELECT veh FROM totales WHERE territorio = 'BOGOTA (BOGOTA D.C.)') AS bogota,
       ROUND((SELECT veh FROM totales WHERE territorio = 'BOGOTA (BOGOTA D.C.)') * 100.0
             / (SELECT SUM(veh) FROM totales), 2) AS pct_bogota,
       (SELECT AVG(veh) FROM ordenados WHERE fila IN ((n + 1) / 2, (n + 2) / 2)) AS mediana;


-- =============================================================================
-- 5. PIVOT (P3) · intercambio de filas y columnas de la matriz clase × año de registro
-- URL clase en filas: /analisis-multidimensional/p3?anio=2019&anio=2024&nivel=clase
-- URL año en filas:   /analisis-multidimensional/p3?anio=2019&anio=2024&nivel=clase&pivot=1
--
-- olap.py ejecuta las MISMAS consultas (5a y 5b) en las dos orientaciones: el pivot no cambia los datos,
-- solo cómo la plantilla p3.html dibuja la matriz. Las consultas 5c y 5d (complementarias) muestran las
-- dos orientaciones directamente en SQL. La participación % usa como denominador el total del año de registro.
-- =============================================================================

-- 5a · olap.py · consultar() serie anual (denominador de la participación dentro del año)
-- Operación:   pivot
-- Vista:       P3
-- Dimensiones: tiempo (anio)
-- Medida:      vehículos registrados = SUM(cantidad)
-- Filtros:     anio = 2019 y 2024 (todos los combustibles)
-- Nivel:       año de registro
-- Esperado:    2019 = 5.435, 2024 = 53.934
SELECT t.anio, SUM(h.cantidad)
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE t.anio IN (2019, 2024) GROUP BY t.anio;

-- 5b · olap.py · consultar() celdas de la matriz clase × año (las mismas con y sin pivot)
-- Operación:   pivot
-- Vista:       P3
-- Dimensiones: tiempo (anio), vehículo (clase)
-- Medida:      vehículos registrados = SUM(cantidad)
-- Filtros:     anio = 2019 y 2024 (todos los combustibles)
-- Nivel:       clase
-- Esperado:    CAMIONETA 2019 = 1.367, CAMIONETA 2024 = 39.121
SELECT v.clase, t.anio, SUM(h.cantidad)
FROM hechos_registros h
JOIN dim_tiempo      t ON t.id_tiempo      = h.id_tiempo
JOIN dim_combustible c ON c.id_combustible = h.id_combustible
JOIN dim_vehiculo    v ON v.id_vehiculo    = h.id_vehiculo
JOIN dim_territorio  r ON r.id_territorio  = h.id_territorio
JOIN dim_modelo      m ON m.id_modelo      = h.id_modelo
 WHERE t.anio IN (2019, 2024) GROUP BY v.clase, t.anio;

-- 5c · complementaria · orientación 1: clase en filas, año en columnas
-- Operación:   pivot (filas = clase)
-- Vista:       P3
-- Medida:      vehículos registrados y participación % dentro del año
-- Filtros:     anio = 2019 y 2024 (todos los combustibles)
-- Nivel:       clase
-- Esperado:    CAMIONETA 1.367 (25,2 %) en 2019 y 39.121 (72,5 %) en 2024
WITH celdas AS (
  SELECT v.clase, t.anio, SUM(h.cantidad) AS veh
  FROM hechos_registros h
  JOIN dim_tiempo   t ON t.id_tiempo   = h.id_tiempo
  JOIN dim_vehiculo v ON v.id_vehiculo = h.id_vehiculo
   WHERE t.anio IN (2019, 2024)
   GROUP BY v.clase, t.anio
), anual AS (
  SELECT anio, SUM(veh) AS total FROM celdas GROUP BY anio
)
SELECT c.clase,
       SUM(CASE WHEN c.anio = 2019 THEN c.veh ELSE 0 END) AS veh_2019,
       ROUND(SUM(CASE WHEN c.anio = 2019 THEN c.veh ELSE 0 END) * 100.0
             / (SELECT total FROM anual WHERE anio = 2019), 1) AS pct_2019,
       SUM(CASE WHEN c.anio = 2024 THEN c.veh ELSE 0 END) AS veh_2024,
       ROUND(SUM(CASE WHEN c.anio = 2024 THEN c.veh ELSE 0 END) * 100.0
             / (SELECT total FROM anual WHERE anio = 2024), 1) AS pct_2024
FROM celdas c
 GROUP BY c.clase
 ORDER BY SUM(c.veh) DESC, c.clase;

-- 5d · complementaria · orientación 2 (pivot): año en filas, clase en columnas
-- Operación:   pivot (filas = año de registro)
-- Vista:       P3
-- Medida:      vehículos registrados y participación % dentro del año
-- Filtros:     anio = 2019 y 2024 (todos los combustibles)
-- Nivel:       clase (las tres con más registros en columnas propias y el resto en «otras»)
-- Esperado:    2019 CAMIONETA 25,2 % · 2024 CAMIONETA 72,5 %
WITH celdas AS (
  SELECT v.clase, t.anio, SUM(h.cantidad) AS veh
  FROM hechos_registros h
  JOIN dim_tiempo   t ON t.id_tiempo   = h.id_tiempo
  JOIN dim_vehiculo v ON v.id_vehiculo = h.id_vehiculo
   WHERE t.anio IN (2019, 2024)
   GROUP BY v.clase, t.anio
)
SELECT anio,
       SUM(veh) AS total_anio,
       SUM(CASE WHEN clase = 'CAMIONETA' THEN veh ELSE 0 END) AS camioneta,
       ROUND(SUM(CASE WHEN clase = 'CAMIONETA' THEN veh ELSE 0 END) * 100.0 / SUM(veh), 1) AS pct_camioneta,
       SUM(CASE WHEN clase = 'AUTOMOVIL' THEN veh ELSE 0 END) AS automovil,
       ROUND(SUM(CASE WHEN clase = 'AUTOMOVIL' THEN veh ELSE 0 END) * 100.0 / SUM(veh), 1) AS pct_automovil,
       SUM(CASE WHEN clase = 'CICLOMOTOR' THEN veh ELSE 0 END) AS ciclomotor,
       ROUND(SUM(CASE WHEN clase = 'CICLOMOTOR' THEN veh ELSE 0 END) * 100.0 / SUM(veh), 1) AS pct_ciclomotor,
       SUM(CASE WHEN clase NOT IN ('CAMIONETA', 'AUTOMOVIL', 'CICLOMOTOR') THEN veh ELSE 0 END) AS otras,
       ROUND(SUM(CASE WHEN clase NOT IN ('CAMIONETA', 'AUTOMOVIL', 'CICLOMOTOR') THEN veh ELSE 0 END) * 100.0
             / SUM(veh), 1) AS pct_otras
FROM celdas
 GROUP BY anio
 ORDER BY anio;
