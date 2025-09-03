#!/bin/bash
# Script para instalar poppler si no está disponible

echo "🔍 Verificando poppler..."

if command -v pdftoppm &> /dev/null; then
    echo "✅ Poppler ya está instalado"
    pdftoppm -v 2>&1 | head -1
    exit 0
fi

echo "❌ Poppler no encontrado, instalando..."

# Actualizar repositorios
apt-get update

# Instalar poppler
apt-get install -y poppler-utils libpoppler-cpp-dev libpoppler-dev poppler-data

# Verificar instalación
if command -v pdftoppm &> /dev/null; then
    echo "✅ Poppler instalado correctamente"
    pdftoppm -v 2>&1 | head -1
else
    echo "❌ Error: No se pudo instalar poppler"
    exit 1
fi

# Limpiar cache
rm -rf /var/lib/apt/lists/*
