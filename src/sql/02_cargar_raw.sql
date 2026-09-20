-- Carga un archivo parquet completo a la capa raw
-- file_row_number guarda la posición original de cada fila en el archivo
INSERT INTO raw_movimientos
SELECT
    $corte_id        AS corte_id,
    file_row_number  AS fila,
    id_cliente,
    date,
    product,
    type,
    fund,
    amount,
    description,
    commercial_name
FROM read_parquet($ruta, file_row_number = true);