"""
Genera reports/insights.md consultando la base ya construida

Se ejecuta después del pipeline (solo lee datos, no los modifica.
Para agregar una sección al reporte, basta con agregarla a SECCIONES.
"""
import logging
from datetime import datetime
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
RUTA_DB = RAIZ / "data" / "output" / "movimientos.duckdb"
RUTA_REPORTE = RAIZ / "reports" / "insights.md"

log = logging.getLogger("pipeline.reporte")

# Cada sección tiene título, nota que explica cómo leerla, y la consulta
SECCIONES = [
    (
        "Cortes procesados",
        "",
        "SELECT corte_id, archivo, filas FROM control_cortes ORDER BY corte_id",
    ),
    (
        "Qué cambió entre cortes",
        "Las correcciones son inferidas, sin un id de transacción, dos filas se "
        "emparejan por llave candidata solo cuando queda una de cada lado.",
        """SELECT corte_id, filas_corte, sin_cambio, corregidos, nuevos, eliminados,
                  nuevos_ambiguos, eliminados_ambiguos
           FROM resumen_cortes ORDER BY corte_id""",
    ),
    (
        "Calidad de los datos por corte",
        "Ninguna fila se descarta ni se corrige, los problemas se marcan y se conservan.",
        """SELECT corte_id,
                  COUNT(*)                                   AS filas,
                  COUNT(*) FILTER (alerta_monto_nulo)        AS monto_nulo,
                  COUNT(*) FILTER (alerta_monto_negativo)    AS monto_negativo,
                  COUNT(*) FILTER (alerta_monto_cero)        AS monto_cero,
                  COUNT(*) FILTER (alerta_descripcion_nula)  AS sin_descripcion,
                  COUNT(*) FILTER (alerta_entidad_nula)      AS sin_entidad,
                  COUNT(*) FILTER (alerta_fecha_invalida)    AS fecha_invalida,
                  COUNT(*) FILTER (alerta_tipo_desconocido)  AS tipo_desconocido,
                  COUNT(*) FILTER (alerta_fondo_desconocido) AS fondo_desconocido
           FROM stg_movimientos GROUP BY corte_id ORDER BY corte_id""",
    ),
    (
        "Montos negativos según tipo de movimiento",
        "Todos los montos negativos están en movimientos de entrada. No se corrigen "
        "porque no se sabe si son reversos, ajustes o errores de origen.",
        """SELECT tipo,
                  COUNT(*) FILTER (monto < 0) AS negativos,
                  COUNT(*) FILTER (monto > 0) AS positivos,
                  COUNT(*) FILTER (monto = 0) AS en_cero
           FROM movimientos_actuales GROUP BY tipo ORDER BY tipo""",
    ),
    (
        "Volumen y monto por producto",
        "Entradas y salidas van por separado y con su signo original, sin una "
        "convención contable confirmada, restarlas no daría un saldo.",
        """SELECT producto,
                  COUNT(*)                                            AS movimientos,
                  ROUND(SUM(monto) FILTER (tipo = 'ENTRADA'))::BIGINT AS total_entradas,
                  ROUND(SUM(monto) FILTER (tipo = 'SALIDA'))::BIGINT  AS total_salidas,
                  COUNT(*) FILTER (monto IS NULL)                     AS sin_monto
           FROM movimientos_actuales GROUP BY producto ORDER BY movimientos DESC""",
    ),
    (
        "Volumen y monto por fondo",
        "",
        """SELECT fondo,
                  COUNT(*)                                            AS movimientos,
                  ROUND(SUM(monto) FILTER (tipo = 'ENTRADA'))::BIGINT AS total_entradas,
                  ROUND(SUM(monto) FILTER (tipo = 'SALIDA'))::BIGINT  AS total_salidas
           FROM movimientos_actuales GROUP BY fondo ORDER BY movimientos DESC""",
    ),
    (
        "Concentración por entidad",
        "La entidad falta en una de cada seis filas, así que el reparto está incompleto.",
        """SELECT COALESCE(entidad, 'Sin entidad') AS entidad,
                  COUNT(*) AS movimientos,
                  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS porcentaje
           FROM movimientos_actuales GROUP BY entidad ORDER BY movimientos DESC""",
    ),
    (
        "Movimientos por fecha (últimos 10 días)",
        "El último corte agrega un día nuevo, pero la mayoría de los registros nuevos "
        "traen fechas anteriores, son datos que llegan tarde.",
        """SELECT fecha, COUNT(*) AS movimientos
           FROM movimientos_actuales GROUP BY fecha ORDER BY fecha DESC LIMIT 10""",
    ),
]

LIMITACIONES = """## Limitaciones

- **Sin id de transacción.** El archivo trae `id_cliente`, que identifica al cliente y
  no al movimiento. Las correcciones se infieren por llave candidata, si una corrección
  cambia un campo de esa llave, se ve como una eliminación más un registro nuevo.
- **Sin moneda.** Los montos no traen unidad, así que los totales son comparables entre
  sí pero no representan un valor monetario confirmado.
- **Sin convención de signos.** Entradas y salidas se reportan por separado y con su
  signo original.
- **Incoherencias semánticas.** Hay descripciones que no concuerdan con el tipo (por
  ejemplo, "Retiro parcial" en entradas). Se reportan, no se corrigen.
"""


def tabla_markdown(resultado):
    """Convierte el resultado de una consulta en una tabla de Markdown."""
    encabezado = "| " + " | ".join(resultado.columns) + " |"
    separador = "|" + "|".join(["---"] * len(resultado.columns)) + "|"
    filas = []
    for fila in resultado.fetchall():
        valores = [f"{v:,}" if isinstance(v, int) else str(v) for v in fila]
        filas.append("| " + " | ".join(valores) + " |")
    return "\n".join([encabezado, separador] + filas)


def generar(ruta_db=RUTA_DB, ruta_reporte=RUTA_REPORTE):
    con = duckdb.connect(str(ruta_db), read_only=True)

    partes = ["# Insights de movimientos financieros",
              f"Generado el {datetime.now():%Y-%m-%d %H:%M}."]

    for titulo, nota, sql in SECCIONES:
        partes.append(f"## {titulo}")
        if nota:
            partes.append(nota)
        partes.append(tabla_markdown(con.sql(sql)))

    partes.append(LIMITACIONES)
    con.close()

    ruta_reporte.parent.mkdir(parents=True, exist_ok=True)
    ruta_reporte.write_text("\n\n".join(partes), encoding="utf-8")
    log.info("Reporte escrito en %s", ruta_reporte)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    generar()