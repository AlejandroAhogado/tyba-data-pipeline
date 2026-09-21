# Insights de movimientos financieros

Generado el 2026-09-21 00:39.

## Cortes procesados

| corte_id | archivo | filas |
|---|---|---|
| 0 | movimientos_dia_T.parquet | 50,000 |
| 1 | movimientos_dia_T1.parquet | 49,000 |

## Qué cambió entre cortes

Las correcciones son inferidas, sin un id de transacción, dos filas se emparejan por llave candidata solo cuando queda una de cada lado.

| corte_id | filas_corte | sin_cambio | corregidos | nuevos | eliminados | nuevos_ambiguos | eliminados_ambiguos |
|---|---|---|---|---|---|---|---|
| 0 | 50,000 | 0 | 0 | 50,000 | 0 | 0 | 0 |
| 1 | 49,000 | 35,159 | 3,842 | 9,999 | 10,999 | 0 | 0 |

## Calidad de los datos por corte

Ninguna fila se descarta ni se corrige, los problemas se marcan y se conservan.

| corte_id | filas | monto_nulo | monto_negativo | monto_cero | sin_descripcion | sin_entidad | fecha_invalida | tipo_desconocido | fondo_desconocido |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 50,000 | 1,543 | 1,034 | 940 | 4,563 | 8,307 | 0 | 0 | 0 |
| 1 | 49,000 | 1,440 | 989 | 903 | 4,485 | 8,167 | 0 | 0 | 0 |

## Montos negativos según tipo de movimiento

Todos los montos negativos están en movimientos de entrada. Distribución del signo del monto por tipo de movimiento los montos se conservan como llegaron

| tipo | negativos | positivos | en_cero |
|---|---|---|---|
| ENTRADA | 989 | 24,816 | 523 |
| SALIDA | 0 | 20,852 | 380 |

## Volumen y monto por producto

Entradas y salidas van por separado y con su signo original, sin una convención contable confirmada, restarlas no daría un saldo.

| producto | movimientos | total_entradas | total_salidas | sin_monto |
|---|---|---|---|---|
| Cuenta de Ahorro | 6,221 | 73,918,114,979 | 67,296,817,931 | 204 |
| CDT | 6,181 | 76,419,287,643 | 63,699,954,906 | 191 |
| Bonos | 6,169 | 75,886,923,817 | 64,889,050,401 | 170 |
| Divisas | 6,107 | 75,138,417,534 | 62,921,159,427 | 160 |
| Fondo de Inversión | 6,095 | 74,256,469,996 | 67,428,964,105 | 175 |
| Fondo de Pensión | 6,083 | 72,787,369,996 | 64,114,511,723 | 170 |
| Acciones | 6,079 | 72,745,479,337 | 64,713,897,170 | 178 |
| ETF | 6,065 | 73,906,186,583 | 63,183,236,434 | 192 |

## Volumen y monto por fondo

| fondo | movimientos | total_entradas | total_salidas |
|---|---|---|---|
| Renta Fija | 7,261 | 87,355,986,425 | 76,636,832,368 |
| Renta Variable | 7,242 | 87,884,714,509 | 76,361,316,019 |
| Internacional | 6,946 | 85,619,588,790 | 75,811,174,040 |
| Crecimiento | 6,927 | 82,949,291,340 | 72,945,529,686 |
| Conservador | 6,911 | 84,513,966,017 | 73,471,738,141 |
| Mercado Monetario | 6,888 | 83,848,723,741 | 71,493,762,305 |
| Balanceado | 6,825 | 82,885,979,063 | 71,527,239,538 |

## Concentración por entidad

La entidad puede venir vacía, esas filas se agrupan aparte

| entidad | movimientos | porcentaje |
|---|---|---|
| Sin entidad | 8,167 | 16.7 |
| Scotiabank | 4,196 | 8.6 |
| Valores Bancolombia | 4,157 | 8.5 |
| Davivienda | 4,148 | 8.5 |
| Itaú | 4,105 | 8.4 |
| Bancolombia | 4,071 | 8.3 |
| BBVA | 4,071 | 8.3 |
| Skandia | 4,067 | 8.3 |
| Corficolombiana | 4,061 | 8.3 |
| Fiduciaria Bogotá | 3,990 | 8.1 |
| BTG Pactual | 3,967 | 8.1 |

## Movimientos por fecha (últimos 10 días)

El último corte agrega un día nuevo, pero la mayoría de los registros nuevos traen fechas anteriores, son datos que llegan tarde.

| fecha | movimientos |
|---|---|
| 2024-10-16 | 312 |
| 2024-10-15 | 1,565 |
| 2024-10-14 | 1,599 |
| 2024-10-13 | 1,531 |
| 2024-10-12 | 1,554 |
| 2024-10-11 | 1,615 |
| 2024-10-10 | 1,629 |
| 2024-10-09 | 1,588 |
| 2024-10-08 | 1,521 |
| 2024-10-07 | 1,571 |

## Limitaciones

- **Sin id de transacción.** El archivo trae `id_cliente`, que identifica al cliente y
  no al movimiento. Las correcciones se infieren por llave candidata, si una corrección
  cambia un campo de esa llave, se ve como una eliminación más un registro nuevo.
- **Sin moneda.** Los montos no traen unidad, así que los totales son comparables entre
  sí pero no representan un valor monetario confirmado.
- **Sin convención de signos.** Entradas y salidas se reportan por separado y con su
  signo original.
- **Incoherencias semánticas.** Hay descripciones que no concuerdan con el tipo (por
  ejemplo, "Retiro parcial" en entradas). Se reportan, no se corrigen.
