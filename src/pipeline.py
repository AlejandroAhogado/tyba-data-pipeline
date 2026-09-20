"""
Pipeline para procesar los cortes diarios en orden y consolidarlos consolida en una base DuckDB
"""
import hashlib
import logging
from datetime import datetime
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
RUTA_RAW = RAIZ / "data" / "raw"
RUTA_DB = RAIZ / "data" / "output" / "movimientos.duckdb"
RUTA_SQL = RAIZ / "src" / "sql"

# Orden de procesamiento de los cortes, afecta el orden porque se compara contra el anterior
CORTES = [
    (1, "movimientos_dia_T.parquet"),
    (2, "movimientos_dia_T1.parquet"),
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")


def leer_sql(nombre):
    return (RUTA_SQL / nombre).read_text(encoding="utf-8")


def calcular_hash(ruta):
    """Huella del archivo: si el contenido cambia, el hash cambia."""
    sha = hashlib.sha256()
    with open(ruta, "rb") as f:
        while True:
            bloque = f.read(1024 * 1024)  
            if not bloque:                
                break
            sha.update(bloque)           
    return sha.hexdigest()


def corte_ya_procesado(con, corte_id, hash_archivo):
    fila = con.execute(
        "SELECT hash_archivo FROM control_cortes WHERE corte_id = ?", [corte_id]
    ).fetchone()
    if fila is None:
        return False
    if fila[0] != hash_archivo:
        raise ValueError(
            f"El corte {corte_id} ya fue procesado con otro contenido. "
            "No se sobrescribe para no romper la historia."
        )
    return True


def procesar_corte(con, corte_id, archivo):
    ruta = RUTA_RAW / archivo
    hash_archivo = calcular_hash(ruta)

    if corte_ya_procesado(con, corte_id, hash_archivo):
        log.info("Corte %s (%s) ya procesado, se omite", corte_id, archivo)
        return

    log.info("Procesando corte %s (%s)", corte_id, archivo)

    # Todo el corte se procesa en una transacción, o queda completo o no queda nada.
    con.begin()
    try:
        con.execute(leer_sql("02_cargar_raw.sql"), {"corte_id": corte_id, "ruta": str(ruta)})
        filas = con.execute(
            "SELECT COUNT(*) FROM raw_movimientos WHERE corte_id = ?", [corte_id]
        ).fetchone()[0]

        con.execute(
            "INSERT INTO control_cortes VALUES (?, ?, ?, ?, ?)",
            [corte_id, archivo, hash_archivo, filas, datetime.now()],
        )
        con.commit()
    except Exception:
        con.rollback()
        raise

    log.info("Corte %s cargado: %s filas", corte_id, filas)


def main():
    RUTA_DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(RUTA_DB))
    con.execute(leer_sql("01_esquema.sql"))

    for corte_id, archivo in CORTES:
        procesar_corte(con, corte_id, archivo)

    con.close()
    log.info("Pipeline terminado")


if __name__ == "__main__":
    main()