"""
Pruebas del pipeline con cortes pequeños hechos a mano.

Cada prueba arma uno o dos cortes de pocas filas, corre el pipeline completo
sobre una carpeta temporal y verifica el resultado contra lo esperado.
"""
import duckdb
import pytest

import pipeline

MOVIMIENTO_BASE = {
    "id_cliente": "CLI000001",
    "date": "2024-09-20",
    "product": "CDT",
    "type": "entrada",
    "fund": "Renta Fija",
    "amount": 100.0,
    "description": "Depósito inicial",
    "commercial_name": "Bancolombia",
}


def movimiento(**cambios):
    """Un movimiento base con los campos que se quieran cambiar."""
    return {**MOVIMIENTO_BASE, **cambios}


def escribir_corte(carpeta, nombre, movimientos):
    """Crea un parquet con los movimientos dados."""
    con = duckdb.connect()
    con.execute("CREATE TABLE corte (id_cliente VARCHAR, date VARCHAR, product VARCHAR, "
                "type VARCHAR, fund VARCHAR, amount DOUBLE, description VARCHAR, "
                "commercial_name VARCHAR)")
    con.executemany("INSERT INTO corte VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [list(m.values()) for m in movimientos])
    con.execute(f"COPY corte TO '{carpeta / nombre}' (FORMAT PARQUET)")
    con.close()


def consultar(ruta_db, sql, parametros=None):
    """Ejecuta una consulta sobre la base generada y devuelve la primera fila."""
    con = duckdb.connect(str(ruta_db), read_only=True)
    fila = con.execute(sql, parametros or []).fetchone()
    con.close()
    return fila


def resumen(ruta_db, corte_id):
    """Clasificación guardada para un corte."""
    fila = consultar(
        ruta_db,
        """SELECT sin_cambio, corregidos, nuevos, eliminados,
                  nuevos_ambiguos, eliminados_ambiguos
           FROM resumen_cortes WHERE corte_id = ?""",
        [corte_id],
    )
    return dict(zip(
        ["sin_cambio", "corregidos", "nuevos", "eliminados",
         "nuevos_ambiguos", "eliminados_ambiguos"], fila))


@pytest.fixture
def entorno(tmp_path):
    """Carpeta de cortes y base de datos propias de cada prueba."""
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw, tmp_path / "movimientos.duckdb"


def test_normaliza_tipo_fondo_y_fecha(entorno):
    raw, db = entorno
    escribir_corte(raw, "movimientos_dia_T.parquet", [
        movimiento(type="OUT", fund="  renta  fija ", date="16/09/2024"),
    ])
    pipeline.main(raw, db)

    tipo, fondo, fecha = consultar(db, "SELECT tipo, fondo, fecha FROM stg_movimientos")

    assert tipo == "SALIDA"
    assert fondo == "Renta Fija"
    assert str(fecha) == "2024-09-16"


def test_conserva_montos_negativos_y_nulos(entorno):
    raw, db = entorno
    escribir_corte(raw, "movimientos_dia_T.parquet", [
        movimiento(id_cliente="CLI000001", amount=-50.0),
        movimiento(id_cliente="CLI000002", amount=None),
    ])
    pipeline.main(raw, db)

    montos = consultar(db, """SELECT list(monto ORDER BY id_cliente)
                              FROM stg_movimientos""")[0]
    negativos, nulos = consultar(db, """SELECT COUNT(*) FILTER (alerta_monto_negativo),
                                               COUNT(*) FILTER (alerta_monto_nulo)
                                        FROM stg_movimientos""")

    assert montos == [-50.0, None]        # el signo se conserva, el nulo no se rellena
    assert (negativos, nulos) == (1, 1)


def test_clasifica_los_cuatro_casos(entorno):
    raw, db = entorno
    escribir_corte(raw, "movimientos_dia_T.parquet", [
        movimiento(id_cliente="CLI000001"),                 # se queda igual
        movimiento(id_cliente="CLI000002", amount=200.0),   # le corrigen el monto
        movimiento(id_cliente="CLI000003"),                 # desaparece
    ])
    escribir_corte(raw, "movimientos_dia_T1.parquet", [
        movimiento(id_cliente="CLI000001"),
        movimiento(id_cliente="CLI000002", amount=250.0),
        movimiento(id_cliente="CLI000004"),                 # llega nuevo
    ])
    pipeline.main(raw, db)

    assert resumen(db, 1) == {
        "sin_cambio": 1, "corregidos": 1, "nuevos": 1, "eliminados": 1,
        "nuevos_ambiguos": 0, "eliminados_ambiguos": 0,
    }


def test_marca_ambiguo_en_vez_de_adivinar(entorno):
    raw, db = entorno
    # Dos movimientos con la misma llave candidata y montos distintos.
    # Si ambos cambian, no hay forma de saber cuál corresponde a cuál
    escribir_corte(raw, "movimientos_dia_T.parquet", [
        movimiento(amount=100.0),
        movimiento(amount=200.0),
    ])
    escribir_corte(raw, "movimientos_dia_T1.parquet", [
        movimiento(amount=150.0),
        movimiento(amount=250.0),
    ])
    pipeline.main(raw, db)

    assert resumen(db, 1) == {
        "sin_cambio": 0, "corregidos": 0, "nuevos": 0, "eliminados": 0,
        "nuevos_ambiguos": 2, "eliminados_ambiguos": 2,
    }


def test_empareja_filas_identicas_sin_duplicarlas(entorno):
    raw, db = entorno
    # Dos filas exactamente iguales en ambos cortes: deben quedar dos vigentes,
    # no cuatro. Existe riesgo de Join 
    escribir_corte(raw, "movimientos_dia_T.parquet", [movimiento(), movimiento()])
    escribir_corte(raw, "movimientos_dia_T1.parquet", [movimiento(), movimiento()])
    pipeline.main(raw, db)

    vigentes = consultar(db, """SELECT COUNT(*) FROM movimientos_historico
                                WHERE vigente""")[0]

    assert vigentes == 2
    assert resumen(db, 1)["sin_cambio"] == 2


def test_no_duplica_al_correr_dos_veces(entorno):
    raw, db = entorno
    escribir_corte(raw, "movimientos_dia_T.parquet", [movimiento()])
    pipeline.main(raw, db)
    pipeline.main(raw, db)   # la segunda corrida no debe cambiar nada

    versiones, cortes = consultar(db, """SELECT (SELECT COUNT(*) FROM movimientos_historico),
                                                (SELECT COUNT(*) FROM control_cortes)""")

    assert (versiones, cortes) == (1, 1)


def test_rechaza_corte_fuera_de_orden(entorno):
    raw, db = entorno
    escribir_corte(raw, "movimientos_dia_T1.parquet", [movimiento()])
    pipeline.main(raw, db)

    # El corte anterior llega tarde, procesarlo rompería el orden de la historia
    escribir_corte(raw, "movimientos_dia_T.parquet", [movimiento()])
    with pytest.raises(ValueError, match="orden"):
        pipeline.main(raw, db)