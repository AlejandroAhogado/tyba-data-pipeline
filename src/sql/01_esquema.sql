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


-- Capa silver, datos limpios y normalizados, con alertas de calidad por fila
-- (corte_id, fila) apunta a la fila original en raw_movimientos
CREATE TABLE IF NOT EXISTS stg_movimientos (
    corte_id                 INTEGER NOT NULL,
    fila                     BIGINT  NOT NULL,
    id_cliente               VARCHAR,
    fecha                    DATE,
    producto                 VARCHAR,
    tipo                     VARCHAR,
    fondo                    VARCHAR,
    monto                    DECIMAL(18, 2),
    descripcion              VARCHAR,
    entidad                  VARCHAR,
    alerta_fecha_invalida    BOOLEAN,
    alerta_tipo_desconocido  BOOLEAN,
    alerta_fondo_desconocido BOOLEAN,
    alerta_monto_nulo        BOOLEAN,
    alerta_monto_negativo    BOOLEAN,
    alerta_monto_cero        BOOLEAN,
    alerta_descripcion_nula  BOOLEAN,
    alerta_entidad_nula      BOOLEAN,
    hash_contenido            VARCHAR NOT NULL,
    hash_llave                VARCHAR NOT NULL,
    PRIMARY KEY (corte_id, fila)
);


-- Capa gold, historia de cada movimiento (SCD tipo 2)
-- Cada fila es una VERSIÓN de un movimiento.
--  Cuando un movimiento se corrige, su versión vigente se cierra y se abre una nueva con el mismo movimiento_id
-- Una versión es válida desde corte_desde hasta antes de corte_hasta.
CREATE TABLE IF NOT EXISTS movimientos_historico (
    movimiento_id     BIGINT  NOT NULL,
    version           INTEGER NOT NULL,
    id_cliente        VARCHAR,
    fecha             DATE,
    producto          VARCHAR,
    tipo              VARCHAR,
    fondo             VARCHAR,
    monto             DECIMAL(18, 2),
    descripcion       VARCHAR,
    entidad           VARCHAR,
    hash_contenido    VARCHAR NOT NULL,
    hash_llave        VARCHAR NOT NULL,
    corte_desde       INTEGER NOT NULL,
    fila_origen       BIGINT  NOT NULL,   -- fila del corte donde apareció esta versión
    motivo_apertura   VARCHAR NOT NULL,   -- NUEVO, CORREGIDO o NUEVO_AMBIGUO
    corte_hasta       INTEGER,            -- NULL mientras la versión esté vigente
    motivo_cierre     VARCHAR,            -- CORREGIDO, ELIMINADO o ELIMINADO_AMBIGUO
    vigente           BOOLEAN NOT NULL,
    PRIMARY KEY (movimiento_id, version)
);

-- Resumen de lo que pasó en cada corte, para monitoreo y conciliación
CREATE TABLE IF NOT EXISTS resumen_cortes (
    corte_id            INTEGER PRIMARY KEY,
    filas_corte         INTEGER NOT NULL,
    sin_cambio          INTEGER NOT NULL,
    corregidos          INTEGER NOT NULL,
    nuevos              INTEGER NOT NULL,
    eliminados          INTEGER NOT NULL,
    nuevos_ambiguos     INTEGER NOT NULL,
    eliminados_ambiguos INTEGER NOT NULL
);