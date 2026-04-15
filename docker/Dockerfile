FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# OpenCV headless requiere estas librerías del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# (Opcional) certificados corporativos — descomentar si el entorno los requiere
# COPY docker/certs/rootca.crt /usr/local/share/ca-certificates/rootca.crt
# RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
#     && update-ca-certificates \
#     && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

# Código fuente
COPY . /usr/src/app

# Directorios de datos persistentes (SQLite + baselines + logs)
# En producción montar estos como volúmenes Docker para no perder datos al redeploy
RUN mkdir -p /var/lib/healing/baselines /var/lib/healing/logs

EXPOSE 8765

# Entrypoint: uvicorn apunta a main:app (main.py está en la raíz del proyecto)
CMD ["uvicorn", "main:app", "--host=0.0.0.0", "--port=8765"]
