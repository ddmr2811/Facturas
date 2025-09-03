# Usar Python 3.11 como imagen base
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema para PyPDF2, pdf2image y poppler
RUN apt-get update && apt-get install -y \
    gcc \
    poppler-utils \
    libpoppler-cpp-dev \
    libpoppler-dev \
    poppler-data \
    pkg-config \
    fontconfig \
    fonts-liberation \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Verificar que poppler está instalado correctamente
RUN which pdftoppm && pdftoppm -h || echo "Poppler instalado pero pdftoppm no encontrado"

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Crear directorio de uploads
RUN mkdir -p uploads

# Exponer el puerto
EXPOSE 5000

# Variables de entorno por defecto
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0

# Comando para ejecutar la aplicación
CMD ["python", "app.py"]
