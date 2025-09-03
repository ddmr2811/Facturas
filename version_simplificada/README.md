# Procesador de Facturas

Aplicación web para procesamiento automático de facturas con autenticación y gestión de usuarios.

## 🚀 Características

- ✅ **Autenticación segura** con usuarios personalizables
- ✅ **Procesamiento de PDFs** con detección automática de datos
- ✅ **Reconocimiento inteligente** de tipos de factura (Agua, Luz, etc.)
- ✅ **Visualización en tiempo real** con vista previa de PDFs
- ✅ **Generación de movimientos contables**
- ✅ **Descarga y gestión** de archivos procesados

## 🔧 Configuración

### Variables de Entorno

Para configurar contraseñas seguras, crea las siguientes variables de entorno:

```bash
# Contraseñas de usuarios
DANI_PASSWORD=tu_contraseña_segura
PATRICIA_PASSWORD=tu_contraseña_segura  
JAVIER_PASSWORD=tu_contraseña_segura

# Configuración de la aplicación
SECRET_KEY=tu_clave_secreta_super_larga
FLASK_ENV=production
FLASK_DEBUG=false
```

### En Dokploy o Docker

Configura estas variables en tu panel de administración para mantener las contraseñas seguras.
```bash
pip install -r requirements.txt
python iniciar_demo.py
```

## Despliegue en Dokploy

Para desplegar esta aplicación en Dokploy:

1. Sube estos archivos a tu repositorio Git
2. Crea un nuevo servicio en Dokploy usando este repositorio
3. Configura las variables de entorno:
   - `PORT=5000`
   - `FLASK_ENV=production`
   - `FLASK_DEBUG=false`
4. Usa el puerto 5000
5. Build path: `/version_simplificada`

La aplicación usará automáticamente Docker para el despliegue.

### Variables de entorno disponibles:
- `PORT`: Puerto del servidor (por defecto: 5000)
- `FLASK_DEBUG`: Modo debug (por defecto: False)
- `FLASK_ENV`: Entorno de Flask (por defecto: production)

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
