-- Guarda cuántos movimientos cayeron en cada categoría en este corte
INSERT INTO resumen_cortes
SELECT
    $corte_id,
    (SELECT COUNT(*) FROM stg_movimientos WHERE corte_id = $corte_id),
    COUNT(*) FILTER (resultado = 'SIN_CAMBIO'),
    COUNT(*) FILTER (resultado = 'CORREGIDO'),
    COUNT(*) FILTER (resultado = 'NUEVO'),
    COUNT(*) FILTER (resultado = 'ELIMINADO'),
    COUNT(*) FILTER (resultado = 'NUEVO_AMBIGUO'),
    COUNT(*) FILTER (resultado = 'ELIMINADO_AMBIGUO')
FROM comparacion;