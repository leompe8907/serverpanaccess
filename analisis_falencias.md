# Análisis de Falencias y Estado del Proyecto — Backend Panaccess

> **Documento ampliado:** la auditoría completa actualizada está en **[AUDITORIA_FALENCIAS_Y_MEJORAS.md](./AUDITORIA_FALENCIAS_Y_MEJORAS.md)**.  
> **Despliegue unificado:** **[GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md](./GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md)**.

Este documento detalla el análisis técnico del backend Django, evaluando su preparación para entornos de producción, seguridad, dependencias e integraciones.

## 1. Seguridad
### Puntos Fuertes:
- **Gestión de Entorno:** Uso correcto de `.env` y carga mediante `appConfig.py`.
- **Protección de Rutas:** Middleware `SyncAdminIPRestrictionMiddleware` que restringe endpoints críticos por IP.
- **HTTPS:** Configuración robusta en `settings.py` (HSTS, Secure Cookies, SSL Redirect) activable mediante `PRODUCTION_HTTPS`.
- **CORS:** Configuración estricta que prohíbe `CORS_ALLOW_ALL_ORIGINS`.

### Falencias y Riesgos:
- **SECRET_KEY:** El archivo `.env.example` sugiere que la llave debe ser generada, pero no hay un script automático que valide su entropía en el despliegue.
- **ACCOUNT_EMAIL_VERIFICATION:** Está configurado como `'none'`. Si el sistema permite registro por email (además de social), esto podría facilitar la creación de cuentas falsas o SPAM.
- **Tokens JWT:** `ACCESS_TOKEN_LIFETIME` es de 60 minutos. Para aplicaciones de alta seguridad, se recomienda reducirlo a 5-15 minutos y apoyarse en el `REFRESH_TOKEN` (que ya está configurado con rotación).

## 2. Dependencias (`requirements.txt`)
- **Django 6.0.5:** ⚠️ **Crítico.** Django 6.0 no ha sido lanzado oficialmente (la versión estable actual es 5.x). Esto sugiere una dependencia de una rama de desarrollo inestable o un error tipográfico que podría causar incompatibilidades con otras librerías.
- **psycopg[binary]:** Se utiliza la versión `binary`. En producción (Ubuntu), se recomienda usar `psycopg` (sin el sufijo binary) para compilar contra las librerías de sistema local, garantizando mejor estabilidad y soporte de seguridad (libssl).
- **Librerías faltantes:**
    - `setproctitle`: Recomendado para que los procesos de Celery/Gunicorn aparezcan con nombres claros en `htop`/`ps`.

## 3. Configuración Django
- **Manejo de Archivos:** WhiteNoise está configurado correctamente para servir estáticos, pero no se observa configuración para archivos `MEDIA` (subidas de usuarios). Si el proyecto permite subir archivos (ej. fotos de perfil), se requerirá configurar Nginx para servirlos o un almacenamiento en la nube (S3/GCS).
- **Logging:** Excelente configuración de logs rotativos. Sin embargo, no se observa un sistema de limpieza de logs antiguos fuera de los 5 backups configurados; podría llenar el disco en sincronizaciones muy verbosas.

## 4. Integración Panaccess
- **Timeouts:** Las tareas de Celery tienen un `soft_time_limit` de 540s y `hard` de 600s. Si la cantidad de suscriptores a sincronizar crece masivamente, estas tareas fallarán sistemáticamente.
- **Dependencia de Redis:** La arquitectura es "Redis-dependiente" para el bloqueo de tareas (`task_lock`). Si Redis cae, las tareas podrían ejecutarse en paralelo causando inconsistencias de datos.
- **Error Handling:** Existe un `PanaccessException`, pero el sistema de reintentos (`autoretry_for`) es agresivo (5 reintentos con backoff). Debe monitorearse para no bloquear la cuenta de API de Panaccess por demasiadas peticiones fallidas seguidas.

## 5. Base de Datos
- **Migraciones:** El proyecto tiene migraciones iniciales (`0001`, `0002`). Es vital asegurar que el entorno de producción corra `migrate` antes de iniciar Gunicorn.
- **Pooling:** Se usa `CONN_MAX_AGE`, lo cual es excelente para rendimiento.
- **Réplica:** El código ya soporta lectura desde réplica, lo cual es una gran ventaja para la escalabilidad.

## 6. Escalabilidad y Rendimiento
- **Queries N+1:** No se observan optimizaciones explícitas de `select_related` o `prefetch_related` en los serializers mostrados. Dado que los suscriptores tienen relaciones complejas, esto podría degradar el rendimiento rápidamente.
- **Caché:** Se usa `django-redis` para caché de fragmentos y sesiones, lo cual es óptimo.

## 7. Lista Priorizada para Producción (Checklist)
1. [ ] **Corregir versión de Django:** Bajar a 5.1 LTS o la versión estable más reciente.
2. [ ] **Cambiar psycopg:** Usar `psycopg` compilado en lugar de `psycopg[binary]`.
3. [ ] **Auditoría de Social Auth:** Verificar que las URLs de redirección en Google/Facebook Console coincidan exactamente con el dominio de producción.
4. [ ] **Verificación de SMTP:** Si se activa la verificación de email, configurar un servicio como SendGrid o Mailgun.
5. [ ] **Ajuste de Throttling:** Revisar si los límites (ej. 60/min para anon) son muy estrictos para la carga real esperada.
6. [ ] **Monitoreo:** Configurar Sentry con el DSN real.
