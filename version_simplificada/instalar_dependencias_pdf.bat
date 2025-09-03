@echo off
echo =====================================================
echo INSTALACION DE DEPENDENCIAS PARA VISOR DE PDF
echo =====================================================
echo.

:: Comprobar si Python está instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: Python no está instalado o no se encuentra en el PATH.
    pause
    exit /b 1
)

:: Activar entorno virtual si existe
if exist .venv (
    echo Activando entorno virtual...
    call .venv\Scripts\activate.bat
)

echo Instalando dependencias para procesamiento de PDF...
pip install PyPDF2==3.0.1
pip install pillow==9.5.0

:: Intentar instalar pdf2image (opcional pero recomendado)
echo.
echo Intentando instalar pdf2image para vista previa de PDFs...
pip install pdf2image==1.16.3

:: Mensaje sobre Poppler
echo.
echo NOTA IMPORTANTE SOBRE LA VISTA PREVIA DE PDF:
echo ----------------------------------------------
echo Para una vista previa completa de PDFs, se requiere Poppler.
echo Si las vistas previas de PDF no funcionan correctamente, por favor:
echo.
echo 1. Descargue Poppler para Windows desde:
echo    https://github.com/oschwartz10612/poppler-windows/releases
echo.
echo 2. Extraiga el contenido en C:\poppler-xx.xx.x
echo.
echo 3. Agregue C:\poppler-xx.xx.x\bin a la variable PATH del sistema
echo.
pause
