-- Estado actual, una fila por movimiento vigente.
-- El histórico guarda todas las versiones, esta vista muestra solo las actuales
CREATE OR REPLACE VIEW movimientos_actuales AS
SELECT movimiento_id, id_cliente, fecha, producto, tipo, fondo,
       monto, descripcion, entidad
FROM movimientos_historico
WHERE vigente;