"""
Script para iniciar la aplicación con datos de demostración y optimizaciones visuales
"""
import os
import sys
import webbrowser
from threading import Timer
from flask import Flask
from app import app

def open_browser():
    """Abrir el navegador automáticamente"""
    webbrowser.open_new('http://localhost:5000/')

if __name__ == '__main__':
    print("\033[92m" + "=" * 60 + "\033[0m")
    print("\033[92m" + " " * 15 + "PROCESADOR DE FACTURAS" + " " * 15 + "\033[0m")
    print("\033[92m" + " " * 18 + "VERSIÓN DEMO" + " " * 18 + "\033[0m")
    print("\033[92m" + "=" * 60 + "\033[0m")
    print("\n\033[93mIniciando servidor...\033[0m")
    
    # Mostrar instrucciones
    print("\033[97mEsta versión simula el procesamiento de facturas sin necesidad")
    print("de base de datos o autenticación. Ideal para demostraciones rápidas.")
    print("\nCaracterísticas:")
    print(" - Interfaz completamente funcional")
    print(" - Procesamiento simulado de facturas PDF")
    print(" - Reconocimiento de tipo de factura por nombre de archivo")
    print(" - Generación de movimientos contables")
    print(" - Visualización y descarga de facturas\033[0m")
    
    print("\n\033[94mAbriendo navegador automáticamente...")
    print("La aplicación estará disponible en: http://localhost:5000\033[0m")
    print("\n\033[91mPresiona Ctrl+C en esta ventana para detener el servidor\033[0m\n")
    
    # Abrir navegador después de 1 segundo
    Timer(1, open_browser).start()
    
    # Iniciar la aplicación
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
