# Procesador de Facturas

Aplicación Flask para procesamiento automático de facturas con reconocimiento de texto y asignación de cuentas contables.

## Características

- ✅ Subida y procesamiento de archivos PDF
- ✅ Reconocimiento automático de direcciones y comunidades
- ✅ Asignación inteligente de cuentas contables
- ✅ Interfaz web responsive con diseño corporativo
- ✅ Descarga de facturas con nombres renombrados
- ✅ Sistema de checkboxes para seguimiento de procesado
- ✅ Copia al portapapeles de movimientos contables

## Despliegue con Docker

### Variables de entorno para Dockploy

Configurar estas variables de entorno en Dockploy:

- `PORT=5000`
- `FLASK_ENV=production`
- `FLASK_DEBUG=false`

### Con Docker Compose

```bash
docker-compose up -d
```

### Con Docker manual

```bash
docker build -t facturas-app .
docker run -p 5000:5000 facturas-app
```

### Para Dockploy

1. Conectar repositorio GitHub: `https://github.com/ddmr2811/Facturas.git`
2. Configurar variables de entorno:
   - `PORT=5000`
   - `FLASK_ENV=production`
   - `FLASK_DEBUG=false`
3. Usar puerto 5000
4. **No especificar Build Path** (usar raíz del repositorio)

## Uso

1. Acceder a la aplicación en el puerto configurado
2. Subir archivos PDF de facturas
3. El sistema procesará automáticamente y asignará cuentas
4. Usar checkboxes para marcar facturas procesadas
5. Descargar facturas con nombres renombrados

## Estructura del proyecto

- `/version_simplificada/` - Código fuente de la aplicación
- `Dockerfile` - Configuración de Docker
- `docker-compose.yml` - Para despliegue local
- `.dockerignore` - Archivos excluidos del build
