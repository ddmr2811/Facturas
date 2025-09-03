#!/bin/bash
# Script de inicio que verifica y configura el entorno antes de lanzar la app

echo "🚀 Iniciando aplicación de procesamiento de facturas..."

# Verificar poppler
echo "🔍 Verificando disponibilidad de poppler..."
if command -v pdftoppm &> /dev/null; then
    echo "✅ Poppler disponible: $(pdftoppm -v 2>&1 | head -1)"
else
    echo "❌ Poppler no encontrado, intentando instalar..."
    /usr/local/bin/install_poppler.sh
fi

# Verificar Python y dependencias críticas
echo "🐍 Verificando Python y dependencias..."
python --version
python -c "import PyPDF2; print('✅ PyPDF2 disponible')" 2>/dev/null || echo "❌ PyPDF2 no disponible"

# Intentar importar pdf2image
python -c "
try:
    from pdf2image import convert_from_path
    print('✅ pdf2image disponible')
    # Probar conversión básica si poppler está disponible
    import shutil
    if shutil.which('pdftoppm'):
        print('✅ pdf2image puede usar poppler')
    else:
        print('⚠️ pdf2image disponible pero poppler no funciona')
except ImportError as e:
    print(f'❌ pdf2image no disponible: {e}')
except Exception as e:
    print(f'⚠️ Error al verificar pdf2image: {e}')
"

# Verificar directorio de uploads
echo "📁 Verificando directorio de uploads..."
mkdir -p uploads
chmod 755 uploads
echo "✅ Directorio uploads configurado"

# Verificar variables de entorno críticas
echo "🔧 Verificando configuración..."
if [ -z "$SECRET_KEY" ]; then
    echo "⚠️ SECRET_KEY no definida, usando valor por defecto"
fi

echo "🎯 PATH actual: $PATH"
echo "🎯 Binarios poppler disponibles:"
ls -la /usr/bin/pdf* 2>/dev/null || echo "   Ninguno encontrado en /usr/bin"

echo "🚀 Iniciando Flask..."
exec python app.py
