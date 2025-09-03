@echo off
color 0A
echo ===============================================================
echo                 PROCESADOR DE FACTURAS
echo           VERSION SIMPLIFICADA SIN DEPENDENCIAS
echo ===============================================================
echo.
echo Esta version solo requiere Flask basico, sin dependencias adicionales
echo Ideal para demostraciones cuando hay problemas instalando paquetes.
echo.

:: Comprobar si Python está instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: Python no está instalado o no se encuentra en el PATH.
    pause
    exit /b 1
)

:: Instalar solo flask (mínimo necesario)
echo Instalando Flask (unica dependencia necesaria)...
pip install flask==2.2.3
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: No se pudo instalar Flask.
    echo.
    echo Intentando con pip3...
    pip3 install flask==2.2.3
    if %errorlevel% neq 0 (
        echo ERROR: Fallo al instalar dependencias.
        pause
        exit /b 1
    )
)

echo.
echo Iniciando aplicacion...
echo.
echo La aplicacion estara disponible en: http://localhost:5000
echo Para detener, presione CTRL+C en esta ventana
echo.

timeout /t 2 >nul
start http://localhost:5000

:: Ejecutar la aplicación simplificada
python app_simple.py

pause
