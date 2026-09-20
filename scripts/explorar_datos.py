"""
Exploración inicial de los cortes de movimients, con el objetivo de entender 
la estructura y calidad de datos para diseñar pipeline
"""

import duckdb

ARCHIVOS = {
    "T": "data/raw/movimientos_dia_T.parquet",
    "T1": "data/raw/movimientos_dia_T1.parquet",
}

con = duckdb.connect()


def titulo(texto):
    print(f"\n{'=' * 70}\n{texto}\n{'=' * 70}")


for corte, ruta in ARCHIVOS.items():
    titulo(f"CORTE {corte}: {ruta}")

    # Vista temporal para no repetir read_parquet en cada consulta
    con.execute(f"CREATE OR REPLACE VIEW mov AS SELECT * FROM read_parquet('{ruta}')")

    print("\n-- Esquema")
    con.sql("DESCRIBE mov").show()

    print("\n-- Muestra de 5 filas")
    con.sql("SELECT * FROM mov LIMIT 5").show()

    print("\n-- Volumen")
    con.sql("""
        SELECT COUNT(*)                   AS filas,
               COUNT(DISTINCT id_cliente) AS clientes
        FROM mov
    """).show()

    print("\n-- Nulos por columna")
    con.sql("""
        SELECT COUNT(*) - COUNT(id_cliente)      AS id_cliente,
               COUNT(*) - COUNT(date)            AS date,
               COUNT(*) - COUNT(product)         AS product,
               COUNT(*) - COUNT(type)            AS type,
               COUNT(*) - COUNT(fund)            AS fund,
               COUNT(*) - COUNT(amount)          AS amount,
               COUNT(*) - COUNT(description)     AS description,
               COUNT(*) - COUNT(commercial_name) AS commercial_name
        FROM mov
    """).show()

    # Valores distintos de las columnas categóricas.
    # Las comillas permiten ver espacios al inicio o al final.
    for columna in ["type", "fund", "product"]:
        print(f"\n-- Valores de {columna}")
        con.sql(f"""
            SELECT '"' || {columna} || '"' AS valor, COUNT(*) AS filas
            FROM mov
            GROUP BY 1
            ORDER BY 2 DESC
        """).show(max_rows=30)

    print("\n-- Formatos de fecha")
    con.sql("""
        SELECT CASE
                 WHEN regexp_matches(date, '^\\d{4}-\\d{2}-\\d{2}$') THEN 'yyyy-mm-dd'
                 WHEN regexp_matches(date, '^\\d{2}/\\d{2}/\\d{4}$') THEN 'dd/mm/yyyy'
                 ELSE 'otro'
               END AS formato,
               COUNT(*) AS filas,
               MIN(date) AS ejemplo
        FROM mov
        GROUP BY 1
    """).show()

    print("\n-- Montos")
    con.sql("""
        SELECT MIN(amount)                    AS minimo,
               MAX(amount)                    AS maximo,
               ROUND(AVG(amount), 2)          AS promedio,
               COUNT(*) FILTER (amount < 0)   AS negativos,
               COUNT(*) FILTER (amount = 0)   AS ceros
        FROM mov
    """).show()

    print("\n-- Signo del monto según type")
    con.sql("""
        SELECT type,
               COUNT(*) FILTER (amount > 0)       AS positivos,
               COUNT(*) FILTER (amount < 0)       AS negativos,
               COUNT(*) FILTER (amount = 0)       AS ceros,
               COUNT(*) FILTER (amount IS NULL)   AS nulos
        FROM mov
        GROUP BY 1
        ORDER BY 1
    """).show()

    print("\n-- Hay filas completamente duplicadas?")
    con.sql("""
        SELECT COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM mov)) AS duplicadas
        FROM mov
    """).show()
