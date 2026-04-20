FROM python:3.12-slim

# Instalar dependencias del sistema para Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar dependencias primero (cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código y assets
COPY bot.py .
COPY fonts/ fonts/
COPY brand/ brand/

# Health check — verifica que Python pueda importar el bot
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "import bot" || exit 1

CMD ["python", "bot.py"]
