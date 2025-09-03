# Version Simplificada del Procesador de Facturas

Esta es una versión simplificada del Procesador de Facturas, diseñada para ser desplegada rápidamente en producción sin necesidad de base de datos o autenticación.

## Características

- ✅ **Interfaz web completa** similar a la versión original
- ✅ **Simulación del procesamiento de facturas** con feedback visual
- ✅ **Reconocimiento automático** del tipo de factura por su nombre
- ✅ **Generación realista de movimientos contables**
- ✅ **Visualización y descarga** de facturas
- ✅ **Sin requisitos de base de datos**

## Requisitos

- Python 3.6 o superior
- Dependencias listadas en `requirements.txt`

## Inicio Rápido

### En Windows:
Simplemente ejecuta el archivo `iniciar_demo.bat` y la aplicación se iniciará automáticamente.

### En Linux/Mac:
```bash
chmod +x iniciar_demo.sh
./iniciar_demo.sh
```

### Manualmente:
```bash
pip install -r requirements.txt
python iniciar_demo.py
```

## Despliegue en Dokploy

Para desplegar esta aplicación en Dokploy:

1. Sube estos archivos a tu repositorio Git
2. Crea un nuevo servicio en Dokploy usando este repositorio
3. La aplicación usará automáticamente el archivo `Procfile` incluido

No se requiere configuración adicional de base de datos o variables de entorno.

## Uso de la Aplicación

1. **Cargar facturas**: Usa el botón "Subir Archivo" para cargar PDFs
   - Prueba nombres como "factura_agua.pdf", "recibo_luz.pdf", "gastos_gas.pdf"
   - La aplicación detectará automáticamente el tipo basado en el nombre

2. **Visualizar facturas**: La tabla muestra todas las facturas procesadas
   - Usa los botones de acciones para interactuar con cada factura

3. **Copiar movimientos contables**: El botón verde permite copiar la información del movimiento contable

## Notas Importantes

- Esta versión está diseñada para demostraciones y pruebas
- Los datos están en memoria y no persisten entre reinicios
- No tiene autenticación de usuarios

---

Creado para demostración rápida del Procesador de Facturas.
