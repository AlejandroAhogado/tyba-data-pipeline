-- Clasifica cada movimiento del corte que llega comparándolo con lo vigente
-- Solo decide, no modifica el histórico. Resultado: (movimiento_id, fila, resultado).
CREATE OR REPLACE TEMP TABLE comparacion AS

-- Filas del corte que llega. La ocurrencia numera las filas idénticas entre sí,
-- para poder emparejarlas una a una y no multiplicarlas en el JOIN.
WITH actual AS (
    SELECT fila, hash_contenido, hash_llave,
           ROW_NUMBER() OVER (PARTITION BY hash_contenido ORDER BY fila) AS ocurrencia
    FROM stg_movimientos
    WHERE corte_id = $corte_id
),
vigente AS (
    SELECT movimiento_id, hash_contenido, hash_llave,
           ROW_NUMBER() OVER (PARTITION BY hash_contenido ORDER BY movimiento_id) AS ocurrencia
    FROM movimientos_historico
    WHERE vigente
),

-- Etapa A: mismo contenido exacto.
iguales AS (
    SELECT v.movimiento_id, a.fila
    FROM actual a
    JOIN vigente v USING (hash_contenido, ocurrencia)
),
pendiente_actual AS (
    SELECT * FROM actual WHERE fila NOT IN (SELECT fila FROM iguales)
),
pendiente_vigente AS (
    SELECT * FROM vigente WHERE movimiento_id NOT IN (SELECT movimiento_id FROM iguales)
),

-- Etapa B: cuántas filas quedan de cada lado por llave candidata.
conteo_llave AS (
    SELECT hash_llave,
           COUNT(*) FILTER (lado = 'actual')  AS n_actual,
           COUNT(*) FILTER (lado = 'vigente') AS n_vigente
    FROM (
        SELECT hash_llave, 'actual'  AS lado FROM pendiente_actual
        UNION ALL
        SELECT hash_llave, 'vigente' AS lado FROM pendiente_vigente
    )
    GROUP BY hash_llave
),

-- Solo cuando queda una fila de cada lado se puede inferir una corrección.
llave_uno_a_uno AS (
    SELECT hash_llave FROM conteo_llave WHERE n_actual = 1 AND n_vigente = 1
)

SELECT movimiento_id, fila, 'SIN_CAMBIO' AS resultado
FROM iguales

UNION ALL
SELECT v.movimiento_id, a.fila, 'CORREGIDO'
FROM pendiente_actual a
JOIN pendiente_vigente v USING (hash_llave)
WHERE a.hash_llave IN (SELECT hash_llave FROM llave_uno_a_uno)

UNION ALL
SELECT NULL, a.fila,
       CASE WHEN c.n_vigente = 0 THEN 'NUEVO' ELSE 'NUEVO_AMBIGUO' END
FROM pendiente_actual a
JOIN conteo_llave c USING (hash_llave)
WHERE a.hash_llave NOT IN (SELECT hash_llave FROM llave_uno_a_uno)

UNION ALL
SELECT v.movimiento_id, NULL,
       CASE WHEN c.n_actual = 0 THEN 'ELIMINADO' ELSE 'ELIMINADO_AMBIGUO' END
FROM pendiente_vigente v
JOIN conteo_llave c USING (hash_llave)
WHERE v.hash_llave NOT IN (SELECT hash_llave FROM llave_uno_a_uno);