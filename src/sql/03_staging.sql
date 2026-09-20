-- Limpiar y normalizar un corte de raw_movimientos hacia stg_movimientos
-- Lo que no se puede interpretar queda en NULL con su alerta en TRUE
INSERT INTO stg_movimientos
WITH limpio AS (
    SELECT
        corte_id,
        fila,
        TRIM(id_cliente) AS id_cliente,

        -- Llegan dos formatos( yyyy-mm-dd y dd/mm/yyyy)
        -- TRY_STRPTIME devuelve NULL si el texto no tiene ese formato
        COALESCE(
            TRY_STRPTIME(TRIM(date), '%Y-%m-%d'),
            TRY_STRPTIME(TRIM(date), '%d/%m/%Y')
        )::DATE AS fecha,

        TRIM(product) AS producto,

        -- Diez variantes de escritura para dos valores reales
        CASE LOWER(TRIM(type))
            WHEN 'entrada' THEN 'ENTRADA'
            WHEN 'in'      THEN 'ENTRADA'
            WHEN 'salida'  THEN 'SALIDA'
            WHEN 'out'     THEN 'SALIDA'
        END AS tipo,

        -- Minúsculas, sin espacios en los extremos y sin espacios dobles,
        -- para poder compararlo contra el catálogo de fondos
        LOWER(TRIM(REGEXP_REPLACE(fund, '\s+', ' ', 'g'))) AS fondo_limpio,

        -- El signo se conserva tal como llegó
        CASE WHEN ISFINITE(amount) THEN amount::DECIMAL(18, 2) END AS monto,

        TRIM(description)     AS descripcion,
        TRIM(commercial_name) AS entidad
    FROM raw_movimientos
    WHERE corte_id = $corte_id
)
SELECT
    corte_id,
    fila,
    id_cliente,
    fecha,
    producto,
    tipo,
    CASE fondo_limpio
        WHEN 'balanceado'        THEN 'Balanceado'
        WHEN 'conservador'       THEN 'Conservador'
        WHEN 'crecimiento'       THEN 'Crecimiento'
        WHEN 'internacional'     THEN 'Internacional'
        WHEN 'mercado monetario' THEN 'Mercado Monetario'
        WHEN 'renta fija'        THEN 'Renta Fija'
        WHEN 'renta variable'    THEN 'Renta Variable'
    END AS fondo,
    monto,
    descripcion,
    entidad,

    -- Alertas de calidad, si está en  TRUE significa que la fila tiene ese problema
    fecha IS NULL                          AS alerta_fecha_invalida,
    tipo IS NULL                           AS alerta_tipo_desconocido,
    fondo IS NULL                          AS alerta_fondo_desconocido,
    monto IS NULL                          AS alerta_monto_nulo,
    COALESCE(monto < 0, FALSE)             AS alerta_monto_negativo,
    COALESCE(monto = 0, FALSE)             AS alerta_monto_cero,
    descripcion IS NULL                    AS alerta_descripcion_nula,
    entidad IS NULL                        AS alerta_entidad_nula
FROM limpio;