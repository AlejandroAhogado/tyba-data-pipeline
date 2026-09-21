-- Cierra las versiones vigentes de los movimientos que se corrigieron o desaparecieron
-- No se borra nada, la versión queda en la historia con su motivo de cierre
UPDATE movimientos_historico h
SET vigente       = FALSE,
    corte_hasta   = $corte_id,
    motivo_cierre = c.resultado
FROM comparacion c
WHERE h.movimiento_id = c.movimiento_id
  AND h.vigente
  AND c.resultado IN ('CORREGIDO', 'ELIMINADO', 'ELIMINADO_AMBIGUO');