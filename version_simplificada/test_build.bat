@echo off
echo 🔨 Construyendo imagen Docker mejorada...

REM Detener contenedores previos
docker stop factura-processor 2>nul
docker rm factura-processor 2>nul

REM Construir nueva imagen
echo Construyendo imagen...
docker build -t factura-processor-improved .

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Error en la construcción
    pause
    exit /b 1
)

echo ✅ Imagen construida exitosamente

REM Ejecutar contenedor de prueba
echo 🚀 Ejecutando contenedor de prueba...
docker run -d ^
    --name factura-processor ^
    -p 5000:5000 ^
    -e SECRET_KEY=test-key-local ^
    -e FLASK_DEBUG=1 ^
    factura-processor-improved

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Error al ejecutar contenedor
    pause
    exit /b 1
)

echo ✅ Contenedor ejecutándose en http://localhost:5000

REM Mostrar logs de inicio
echo 📋 Logs de inicio (primeros 10 segundos):
timeout /t 3 /nobreak >nul
docker logs factura-processor

echo.
echo 🔍 Para ver logs en tiempo real: docker logs -f factura-processor
echo 🛑 Para detener: docker stop factura-processor
echo 🌐 Aplicación disponible en: http://localhost:5000
echo.
pause
