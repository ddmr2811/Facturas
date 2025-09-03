#!/bin/bash

echo -e "\e[1;32m====================================================\e[0m"
echo -e "\e[1;32m              PROCESADOR DE FACTURAS               \e[0m"
echo -e "\e[1;32m                  VERSIÓN DEMO                     \e[0m"
echo -e "\e[1;32m====================================================\e[0m"
echo -e "\e[1;33m\nIniciando servidor...\e[0m"

# Verificar que Python está instalado
if ! command -v python3 &> /dev/null; then
    echo -e "\e[1;31mERROR: Python 3 no está instalado o no se encuentra en el PATH.\e[0m"
    echo "Por favor, instala Python desde https://www.python.org/downloads/"
    exit 1
fi

# Verificar que pip está instalado
if ! command -v pip3 &> /dev/null; then
    echo -e "\e[1;31mERROR: pip no está instalado o no se encuentra en el PATH.\e[0m"
    echo "Por favor, reinstala Python y asegúrate de incluir pip."
    exit 1
fi

# Instalar dependencias
echo -e "\e[1;34mInstalando dependencias necesarias...\e[0m"
pip3 install -r requirements.txt

# Si la instalación fue exitosa, iniciar la aplicación
if [ $? -eq 0 ]; then
    echo -e "\e[1;32m\nDependencias instaladas correctamente.\e[0m"
    echo -e "\e[1;34mIniciando la aplicación...\e[0m"
    python3 iniciar_demo.py
else
    echo -e "\e[1;31m\nError al instalar dependencias. Por favor, verifica tu conexión a internet y los permisos.\e[0m"
    exit 1
fi
