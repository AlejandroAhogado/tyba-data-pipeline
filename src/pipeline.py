"""
Pipeline para procesar los cortes diarios en orden y consolidarlos consolida en una base DuckDB
"""
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
RUTA_RAW = RAIZ / "data" / "raw"
RUTA_DB = RAIZ / "data" / "output" / "movimientos.duckdb"
RUTA_SQL = RAIZ / "src" / "sql"

# Nombre esperado de los archivos, movimientos_dia_T.parquet, movimientos_dia_T1.parquet,
# movimientos_dia_T2.parquet... el número después de la T indica el orden del corte
PATRON_ARCHIVO = re.compile(r"^movimientos_dia_T(\d*)\.parquet$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")


def leer_sql(nombre):
    return (RUTA_SQL / nombre).read_text(encoding="utf-8")

def descubrir_cortes():
    """Busca los parquet en data/raw y los devuelve ordenados como (corte_id, archivo)"""
    cortes = []
    for ruta in RUTA_RAW.glob("*.parquet"):
        coincidencia = PATRON_ARCHIVO.match(ruta.name)
        if coincidencia is None:
            log.warning("Archivo ignorado, el nombre no sigue el patrón: %s", ruta.name)
            continue
        numero = coincidencia.group(1)
        corte_id = int(numero) if numero else 0  # "T" sin número es el corte 0
        cortes.append((corte_id, ruta.name))
    return sorted(cortes)


def validar_orden(con, corte_id):
    """Un corte nuevo no puede ser anterior al último procesado."""
    ultimo = con.execute("SELECT MAX(corte_id) FROM control_cortes").fetchone()[0]
    if ultimo is not None and corte_id < ultimo:
        raise ValueError(
            f"El corte {corte_id} llegó después del corte {ultimo}. "
            "Procesarlo rompería el orden historico"
        )


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


def validar_conteo_staging(con, corte_id, filas_raw):
    """La limpieza no debe perder ni duplicar filas"""
    filas_stg = con.execute(
        "SELECT COUNT(*) FROM stg_movimientos WHERE corte_id = ?", [corte_id]
    ).fetchone()[0]
    if filas_stg != filas_raw:
        raise ValueError(
            f"Corte {corte_id}: raw tiene {filas_raw} filas y staging {filas_stg}."
        )

def procesar_corte(con, corte_id, archivo):
    ruta = RUTA_RAW / archivo
    hash_archivo = calcular_hash(ruta)

    if corte_ya_procesado(con, corte_id, hash_archivo):
        log.info("Corte %s (%s) ya procesado, se omite", corte_id, archivo)
        return

    validar_orden(con, corte_id)
    log.info("Procesando corte %s (%s)", corte_id, archivo)

    # Todo el corte se procesa en una transacción, o queda completo o no queda nada.
    con.begin()
    try:
        con.execute(leer_sql("02_cargar_raw.sql"), {"corte_id": corte_id, "ruta": str(ruta)})
        filas = con.execute(
            "SELECT COUNT(*) FROM raw_movimientos WHERE corte_id = ?", [corte_id]
        ).fetchone()[0]

        con.execute(leer_sql("03_staging.sql"), {"corte_id": corte_id})
        validar_conteo_staging(con, corte_id, filas)

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

    cortes = descubrir_cortes()
    if not cortes:
        log.warning("No se encontraron archivos para procesar en %s", RUTA_RAW)

    for corte_id, archivo in cortes:
        procesar_corte(con, corte_id, archivo)

    con.close()
    log.info("Pipeline terminado")


if __name__ == "__main__":
    main()