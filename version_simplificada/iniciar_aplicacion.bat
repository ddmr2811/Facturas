@echo off
echo ========================================
echo    INICIANDO PROCESADOR DE FACTURAS
echo           VERSION SIMPLIFICADA
echo ========================================
echo.

:: Comprobar si Python está instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python no está instalado o no se encuentra en el PATH.
    echo Por favor, instala Python desde https://www.python.org/downloads/
    echo y asegúrate de marcarlo para añadir al PATH durante la instalación.
    pause
    exit /b 1
)

:: Comprobar si pip está instalado
where pip >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: pip no está instalado o no se encuentra en el PATH.
    echo Por favor, reinstala Python y asegúrate de incluir pip.
    pause
    exit /b 1
)

echo Instalando dependencias...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: No se pudieron instalar las dependencias.
    pause
    exit /b 1
)

echo.
echo Iniciando el servidor web...
echo.
echo INFORMACIÓN: El servidor estará disponible en: http://localhost:5000
echo Para detener el servidor, presiona CTRL+C
echo.
echo Abriendo navegador...

:: Esperar 2 segundos y luego abrir el navegador
timeout /t 2 >nul
start http://localhost:5000

:: Iniciar la aplicación
python run.py

pause
