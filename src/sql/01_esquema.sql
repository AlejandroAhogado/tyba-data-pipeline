-- Tablas base del pipeline. IF NOT EXISTS oara evitar errores al correr varias veces

-- Registro de cada corte procesado para evita cargar dos veces el mismo archivo
CREATE TABLE IF NOT EXISTS control_cortes (
    corte_id      INTEGER PRIMARY KEY,
    archivo       VARCHAR   NOT NULL,
    hash_archivo  VARCHAR   NOT NULL,
    filas         INTEGER   NOT NULL,
    procesado_en  TIMESTAMP NOT NULL
);

-- Copia de cada corte tal como llegó, nunca se modifica
CREATE TABLE IF NOT EXISTS raw_movimientos (
    corte_id         INTEGER NOT NULL,
    fila             BIGINT  NOT NULL,
    id_cliente       VARCHAR,
    date             VARCHAR,
    product          VARCHAR,
    type             VARCHAR,
    fund             VARCHAR,
    amount           DOUBLE,
    description      VARCHAR,
    commercial_name  VARCHAR,
    PRIMARY KEY (corte_id, fila)
);