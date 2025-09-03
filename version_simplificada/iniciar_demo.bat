@echo off
cls
color 0A

echo ========================================================
echo                PROCESADOR DE FACTURAS
echo                    VERSION DEMO
echo ========================================================
echo.

:: Comprobar si Python está instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: Python no está instalado o no se encuentra en el PATH.
    echo Por favor, instala Python desde https://www.python.org/downloads/
    echo y asegúrate de marcarlo para añadir al PATH durante la instalación.
    pause
    exit /b 1
)

:: Comprobar si pip está instalado
where pip >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: pip no está instalado o no se encuentra en el PATH.
    echo Por favor, reinstala Python y asegúrate de incluir pip.
    pause
    exit /b 1
)

:: Crear entorno virtual si no existe
if not exist .venv (
    echo Creando entorno virtual...
    python -m venv .venv
)

:: Activar entorno virtual
echo Activando entorno virtual...
call .venv\Scripts\activate.bat

:: Instalar dependencias
echo Instalando dependencias necesarias...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: No se pudieron instalar las dependencias.
    pause
    exit /b 1
)

echo.
echo INICIANDO PROCESADOR DE FACTURAS...
echo.
echo INSTRUCCIONES:
echo  - Para subir facturas, use el botón "Subir Archivo"
echo  - Puede procesar PDFs con nombres como "factura_agua.pdf", "recibo_luz.pdf", etc.
echo  - La aplicación detectará automáticamente el tipo de factura por su nombre
echo.
echo La aplicación se abrirá automáticamente en su navegador.
echo Para detener el servidor, presione CTRL+C en esta ventana y confirme.

:: Iniciar la aplicación
python iniciar_demo.py

pause
