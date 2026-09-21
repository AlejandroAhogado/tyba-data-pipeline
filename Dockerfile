# Imagen base ( Python 3.12 en su versión slim)
FROM python:3.12-slim

WORKDIR /app

# Las dependencias se copian e instalan antes que el código, para que Docker
# reutilice esta capa mientras requirements.txt no cambie
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["sh", "-c", "python src/pipeline.py && python src/reporte.py"]