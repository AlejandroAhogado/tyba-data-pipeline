-- Abre las versiones nuevas del corte:
--   CORREGIDO -> mismo movimiento_id, versión siguiente.
--   NUEVO     -> movimiento_id nuevo, versión 1.
INSERT INTO movimientos_historico

-- Versión más alta que ya tiene cada movimiento corregido.
WITH version_previa AS (
    SELECT h.movimiento_id, MAX(h.version) AS version
    FROM movimientos_historico h
    JOIN comparacion c USING (movimiento_id)
    WHERE c.resultado = 'CORREGIDO'
    GROUP BY h.movimiento_id
),
correcciones AS (
    SELECT c.fila, c.resultado, c.movimiento_id, v.version + 1 AS version
    FROM comparacion c
    JOIN version_previa v USING (movimiento_id)
    WHERE c.resultado = 'CORREGIDO'
),
-- Los movimientos nuevos reciben ids consecutivos a partir del último usado
nuevos AS (
    SELECT c.fila, c.resultado,
           (SELECT COALESCE(MAX(movimiento_id), 0) FROM movimientos_historico)
               + ROW_NUMBER() OVER (ORDER BY c.fila) AS movimiento_id,
           1 AS version
    FROM comparacion c
    WHERE c.resultado IN ('NUEVO', 'NUEVO_AMBIGUO')
),
versiones AS (
    SELECT * FROM correcciones
    UNION ALL
    SELECT * FROM nuevos
)

SELECT
    v.movimiento_id,
    v.version,
    s.id_cliente, s.fecha, s.producto, s.tipo, s.fondo, s.monto, s.descripcion, s.entidad,
    s.hash_contenido,
    s.hash_llave,
    $corte_id   AS corte_desde,
    s.fila      AS fila_origen,
    v.resultado AS motivo_apertura,
    NULL        AS corte_hasta,
    NULL        AS motivo_cierre,
    TRUE        AS vigente
FROM versiones v
JOIN stg_movimientos s
  ON s.corte_id = $corte_id
 AND s.fila = v.fila;