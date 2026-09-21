# Pipeline de movimientos financieros

De acuerdo al enunciado se desarrolló un pipeline que ingiere los cortes diarios de movimientos financieros y los consolida en una
base DuckDB consultable, conservando la historia de cada movimiento entre cortes.

## Cómo ejecutarlo

Con Docker (no requiere nada instalado aparte de Docker):

```bash
docker compose up --build
```

Esto procesa los cortes disponibles en `data/raw/` donde se encuentra la información dada, genera la base en
`data/output/movimientos.duckdb` y escribe el reporte en `reports/insights.md`.
Volver a ejecutarlo no duplica datos: los cortes ya procesados se omiten.

## Estructura

```text
data/raw/        cortes entregados (.parquet)
data/output/     base DuckDB generada (no versionada)
src/pipeline.py  orquestación del proceso
src/reporte.py   generación del reporte de insights
src/sql/         transformaciones, numeradas en orden de ejecución ( se agregó vistas para una consulta más fácil)
scripts/         exploración inicial de los datos
tests/           pruebas automáticas
reports/         reporte generado
```

## Arquitectura

El pipeline sigue una arquitectura por capas (equivalente a bronze, silver y gold):

| Capa | Tabla | Contenido |
|---|---|---|
| Raw | `raw_movimientos` | Copia original de cada corte, sin transformar |
| Staging | `stg_movimientos` | Datos normalizados con alertas de calidad por fila |
| Histórico | `movimientos_historico` | Todas las versiones de cada movimiento (SCD tipo 2) |
| Consulta | `movimientos_actuales` | Vista con el estado vigente |
| Control | `control_cortes`, `resumen_cortes` | Trazabilidad y monitoreo de cada ejecución |

Al manejar este tipo de arquitectura, cada capa solo depende de la anterior, así que cualquiera se puede reconstruir sin
volver a pedir los archivos.

## Decisiones

### Los archivos no traen un identificador de transacción

El glosario pasado en el caso menciona un campo `id` que identifica la transacción, pero los archivos traen
`id_cliente`: 3.000 valores distintos para 50.000 filas (unos 17 movimientos por cliente).
No existe una llave que identifique un movimiento entre cortes, por lo que se decidió manejar de la siguiente manera:

1. **Coincidencia exacta.** Se compara el contenido normalizado completo mediante un hash.
   Si coincide, es el mismo movimiento sin cambios. Las filas idénticas repetidas se
   emparejan una a una para que el cruce no multiplique registros.
2. **Corrección inferida.** Con lo que no coincidió, se agrupa por una llave candidata
   (cliente, fecha, producto, tipo, fondo y entidad). Solo cuando queda exactamente una
   fila de cada lado se infiere una corrección. Si quedan varias, no se fuerza ninguna
   correspondencia, en este caso se marcan como ambiguas.

Lo que sobra es nuevo (solo en el corte actual) o eliminado (solo en lo vigente).

**Limitación conocida:** una corrección que modifique un campo de la llave candidata se
verá como una eliminación más un registro nuevo. Sin un identificador estable no hay forma
de distinguirlo. La solución de fondo en una etapa de producción es poder agregar el campo de id de transacción para una trazabilidad más segura y sencilla. 

### Historia con SCD tipo 2

Cada movimiento recibe un `movimiento_id` propio y cada fila del histórico es una versión
suya, con `corte_desde`, `corte_hasta` y `vigente`. Una corrección cierra la versión
anterior y abre una nueva, en este caso una eliminación solo cierra. De esta manera se garantiza que 
nunca se borre ni se sobrescribe contenido, así que se puede reconstruir el estado de cualquier corte.

Durante el desarrollo, se definió que los cortes completos deben conservarse en raw y staging para auditoría, sin embargo, SCD2 evita repetir en la capa de consulta las versiones que no cambiaron.

### Calidad de datos

Dados los múltiples resultados para un mismo campo, se aplicó la siguiente regla, **se estandariza el formato cuando el significado es evidente, pero no se inventan valores**. Lo que no se puede interpretar queda nulo y marcado con una alerta.

| Hallazgo | Decisión |
|---|---|
| `type` con 10 variantes de escritura | Unificado a `ENTRADA` / `SALIDA` |
| `fund` con 23 variantes (mayúsculas, espacios) | Limpieza y mapeo a los 7 fondos reales |
| Fechas en dos formatos (`yyyy-mm-dd` y `dd/mm/yyyy`) | Ambos se parsean a tipo fecha |
| Montos nulos (~3%) | Se conservan nulos y se excluyen de los agregados |
| Montos negativos (~2%, todos en entradas) | Se conservan con su signo y se reportan |
| Montos en cero (~2%) | Se conservan y se marcan |
| `description` y `commercial_name` nulos (9% y 17%) | Se conservan nulos y se marcan |
| Descripciones incoherentes con el tipo | Se reportan, no se corrigen |

Los montos se guardan como `DECIMAL(18,2)` y no como `DOUBLE`, para evitar errores de
redondeo al sumar. Se verificó que ningún monto trae más de dos decimales.

### DuckDB en lugar de PostgreSQL

DuckDB lee Parquet de forma nativa y también al ser columnar, es más adecuado para analítica. Además, permite procesar
volúmenes mayores que la memoria disponible y no requiere un servidor, lo que permite que
`docker compose up --build` funcione sin configuración adicional. Con PostgreSQL habría que pevantar un servicio aparte, con usuario, contraseña, volumen propio y una espera hasta que la base esté lista. Esta complejidad se justificaría si hubieran muchos consumidores concurrentes, en este caso, no. 

### Diseño para escala

- Todas las transformaciones se ejecutan en SQL sobre conjuntos, no se realizan recorridos fila a
  fila en Python.
- Los Parquet se leen directamente desde DuckDB, sin cargarlos completos en memoria.
- La comparación entre cortes se hace con cruces por hash, no con comparaciones campo a
  campo.
- El hash de archivo se calcula por bloques de 1 MB.

Con volúmenes de millones de filas diarias, si se contara con metadatos del origen que indiquen 
qué fechas cambiaron, se podría comparar solo esas particiones.

### Robustez

- **Idempotencia:** cada corte se registra con el hash de su archivo. Reejecutar no
  duplica nada.
- **Detección de cambios silenciosos:** si un corte ya procesado llega con contenido
  distinto, el pipeline se detiene en lugar de sobrescribir la historia.
- **Orden de llegada:** un corte anterior al último procesado se rechaza.
- **Transaccionalidad:** cada corte se aplica dentro de una transacción, ante cualquier
  error se revierte completo.
- **Conciliaciones:** se valida que staging tenga las mismas filas que raw, y que después
  de aplicar un corte lo vigente coincida exactamente con las filas recibidas.

## Pruebas

```bash
pytest -v
```

Se configuraron siete pruebas sobre cortes pequeños construidos a mano, normalización, conservación de
montos negativos y nulos, las cuatro clasificaciones entre cortes, el caso ambiguo (que no
aparece en los datos entregados), el emparejamiento de filas idénticas sin duplicarlas,
la idempotencia y el rechazo de cortes fuera de orden.

## Resultados con los datos entregados

| Corte | Filas | Sin cambio | Correcciones Inferidas | Nuevos | Eliminados |
|---|---|---|---|---|---|
| T | 50.000 | 0 | 0 | 50.000 | 0 |
| T+1 | 49.000 | 35.159 | 3.842 | 9.999 | 10.999 |

Se validaron las cuentas para ver que todo este correcto y estas cuadran por ambos lados (35.159 + 3.842 + 9.999 = 49.000 filas recibidas), y (35.159 + 3.842 + 10.999 = 50.000) filas del corte anterior. 
Los hallazgos de negocio y de calidad están en `reports/insights.md`.

## Supuestos

- Cada archivo es el estado **completo** de movimientos ese día, por eso la
  ausencia de un registro se interpreta como eliminación. Si se llega a tener archivos con cortes parciales este
  supuesto no aplica.
- El orden de los cortes se toma del nombre del archivo (`movimientos_dia_T`, `T1`, `T2`),
  no de las fechas de los movimientos, porque llegan registros con fecha anterior.
- Las fechas en formato `dd/mm/yyyy` se interpretan como día/mes/año, lo que se confirma
  con valores como `16/09/2024`.
- Los montos no traen moneda por lo que los totales se presentan sin asumir unidad.

## Qué haría con más tiempo

- Ver si es posible obtener en el origen un id de transacción, que eliminaría toda la inferencia.
- Migraciones de esquema, para poder cambiar tablas sin recrear la base.
- Benchmark con millones de filas por corte y particionado por fecha.
- Alertas sobre variaciones anómalas de volumen entre cortes.
