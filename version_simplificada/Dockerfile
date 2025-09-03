# Usar Python 3.11 como imagen base
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Variables de entorno para configuración
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/bin:/usr/local/bin:/bin:$PATH"

# Instalar dependencias del sistema en una sola capa
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    pkg-config \
    fontconfig \
    fonts-liberation \
    curl \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar poppler con verificación múltiple
RUN apt-get update && \
    apt-get install -y \
        poppler-utils \
        libpoppler-cpp-dev \
        libpoppler-dev \
        poppler-data \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && echo "Verificando instalación de poppler..." \
    && ls -la /usr/bin/pdf* || echo "No se encontraron binarios pdf*" \
    && which pdftoppm || echo "pdftoppm no está en PATH" \
    && pdftoppm -v 2>&1 | head -1 || echo "Error al ejecutar pdftoppm -v" \
    && pdftoppm -h >/dev/null 2>&1 && echo "✅ pdftoppm funciona correctamente" || echo "❌ pdftoppm no funciona" \
    && echo "PATH actual: $PATH"

# Copiar script de instalación de poppler y script de inicio
COPY install_poppler.sh /usr/local/bin/
COPY start.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/install_poppler.sh && chmod +x /usr/local/bin/start.sh

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Crear directorio de uploads
RUN mkdir -p uploads

# Ejecutar script de verificación/instalación de poppler al inicio
RUN /usr/local/bin/install_poppler.sh

# Exponer el puerto
EXPOSE 5000

# Variables de entorno por defecto
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0

# Comando para ejecutar la aplicación
CMD ["/usr/local/bin/start.sh"]
