# Guía: Workers y Deployment

## 📊 Recomendación de Workers

### Fórmula General
```
Workers = (2 × CPU cores) + 1
```

### Ejemplos según Hardware

| CPU Cores | Workers Recomendados | Explicación |
|-----------|----------------------|-------------|
| 1 core    | 3 workers            | Mínimo para tener redundancia |
| 2 cores   | 5 workers            | Buen balance para desarrollo |
| 4 cores   | 9 workers            | Producción pequeña/mediana |
| 8 cores   | 17 workers           | Producción mediana |
| 16 cores  | 33 workers           | Producción grande |

### Consideraciones Especiales

#### Para este proyecto (con PanAccess Singleton):

**Recomendación inicial: 3-5 workers**

**Razones:**
1. ✅ **Sesión compartida**: Todos los workers comparten la misma sesión de PanAccess
2. ✅ **Thread-safe**: El singleton maneja la concurrencia correctamente
3. ✅ **Rate limiting**: Menos workers = menos riesgo de exceder límites de PanAccess
4. ✅ **Simplicidad**: Fácil de monitorear y debuggear

**Cuándo aumentar workers:**
- Si tienes mucho tráfico concurrente
- Si los requests son principalmente I/O (llamadas a PanAccess)
- Si necesitas procesar múltiples requests simultáneamente

**Cuándo mantener pocos workers:**
- Si PanAccess tiene límites estrictos de rate limiting
- Si quieres minimizar el número de sesiones activas
- Si el servidor tiene recursos limitados

---

## 🚀 Configuración de Gunicorn

### Configuración Básica (Recomendada)

```bash
gunicorn serverpanaccess.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

### Explicación de Parámetros

- `--workers 3`: 3 procesos worker (recomendado para empezar)
- `--threads 2`: 2 threads por worker (total: 6 threads concurrentes)
- `--timeout 120`: Timeout de 2 minutos (importante para llamadas a PanAccess)
- `--access-logfile -`: Logs de acceso a stdout
- `--error-logfile -`: Logs de error a stdout

### Configuración para Producción

```bash
gunicorn serverpanaccess.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 5 \
    --threads 2 \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --preload \
    --access-logfile /var/log/gunicorn/access.log \
    --error-logfile /var/log/gunicorn/error.log \
    --log-level info
```

**Parámetros adicionales:**
- `--max-requests 1000`: Reinicia workers después de 1000 requests (previene memory leaks)
- `--max-requests-jitter 50`: Variación aleatoria para evitar reinicios simultáneos
- `--preload`: Carga la app antes de fork (mejor para singleton)
- `--log-level info`: Nivel de logging

---

## 🔄 Cómo Funciona el Singleton con Múltiples Workers

### Escenario: 3 Workers

```
Worker 1 ──┐
Worker 2 ──┼──> PanAccessSingleton (cada worker tiene su propia instancia)
Worker 3 ──┘

Cada worker:
- Tiene su propia instancia del singleton en memoria
- Comparte la misma lógica de thread-safety
- Mantiene su propia sesión de PanAccess
```

### ⚠️ Importante: Sesiones por Worker

**Cada worker mantiene su propia sesión**, pero:
- ✅ El singleton garantiza que dentro de cada worker, todos los threads comparten la misma sesión
- ✅ El auto-refresh funciona correctamente en cada worker
- ✅ No hay conflictos entre workers (cada uno es independiente)

**Resultado**: Si tienes 3 workers, tendrás máximo 3 sesiones activas con PanAccess (una por worker).

---

## 📈 Monitoreo y Ajuste

### Métricas a Monitorear

1. **Tiempo de respuesta de PanAccess**
   - Si es alto (>2s), considera aumentar workers
   - Si es bajo (<500ms), puedes reducir workers

2. **Rate limiting de PanAccess**
   - Si recibes errores de rate limit, reduce workers
   - Monitorea cuántos logins se hacen por minuto

3. **Uso de CPU**
   - Si CPU < 50%, puedes aumentar workers
   - Si CPU > 80%, reduce workers

4. **Memoria**
   - Cada worker consume ~50-100MB
   - Asegúrate de tener suficiente RAM

### Ajuste Dinámico

```bash
# Empezar con 3 workers
gunicorn ... --workers 3

# Si el tráfico aumenta, aumentar a 5
gunicorn ... --workers 5

# Si hay problemas de rate limiting, reducir a 2
gunicorn ... --workers 2
```

---

## 🐳 Docker (Opcional)

Si usas Docker, puedes configurar workers con variables de entorno:

```dockerfile
# Dockerfile
FROM python:3.12
...
CMD gunicorn serverpanaccess.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --threads ${GUNICORN_THREADS:-2}
```

```yaml
# docker-compose.yml
services:
  web:
    build: .
    environment:
      - GUNICORN_WORKERS=3
      - GUNICORN_THREADS=2
```

---

## ✅ Checklist de Deployment

- [ ] Configurar número de workers según CPU
- [ ] Configurar timeout adecuado (≥120s para PanAccess)
- [ ] Habilitar logs de acceso y error
- [ ] Configurar `--preload` para mejor rendimiento con singleton
- [ ] Monitorear rate limiting de PanAccess
- [ ] Configurar reinicio automático de workers (systemd/supervisor)
- [ ] Probar con carga para verificar comportamiento

---

## 🎯 Recomendación Final

**Para empezar:**
```bash
gunicorn serverpanaccess.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --preload
```

**Ajustar según:**
- Tráfico real
- Límites de PanAccess
- Recursos del servidor
- Tiempo de respuesta

**Monitorear y ajustar gradualmente.**

