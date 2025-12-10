# 🚀 Guía de Inicio Rápido - Celery (Sincronización Automática)

## ⚙️ Configuración: Sincronización cada 2 minutos

## 📋 Pasos para Iniciar la Sincronización Automática

### **PASO 1: Verificar que Redis esté corriendo**

Abre una terminal PowerShell y ejecuta:

```powershell
docker ps
```

Si no ves Redis corriendo, inícialo:

```powershell
docker run -d --name redis -p 6379:6379 redis:7
```

---

### **PASO 2: Terminal 1 - Iniciar el Worker**

Abre una **nueva terminal PowerShell** y ejecuta:

```powershell
cd C:\Users\Leonard\Desktop\Win\win-backend
& .\env\Scripts\Activate.ps1
$env:REDIS_HOST = "localhost"
$env:CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
celery -A serverpanaccess worker -l info -Q sync_subscribers -P solo --concurrency 1
```

**IMPORTANTE:** Deja esta terminal abierta. El worker debe estar corriendo todo el tiempo.

Deberías ver:
```
celery@NB-LAmaya ready.
```

---

### **PASO 3: Terminal 2 - Iniciar Beat (Programador)**

Abre **otra terminal PowerShell** y ejecuta:

```powershell
cd C:\Users\Leonard\Desktop\Win\win-backend
& .\env\Scripts\Activate.ps1
$env:REDIS_HOST = "localhost"
$env:CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
$env:CELERY_SYNC_MINUTES = "2"
del celerybeat-schedule*
celery -A serverpanaccess beat -l info
```

**IMPORTANTE:** Deja esta terminal abierta también.

Deberías ver:
```
beat: Starting...
```

Y cada 2 minutos verás:
```
Scheduler: Sending due task sync-subscribers (wind.tasks.sync_subscribers_task)
```

---

### **PASO 4: Verificar que Funciona**

En la **Terminal 1 (Worker)**, cada 2 minutos deberías ver:

```
[INFO] Task wind.tasks.sync_subscribers_task[xxx-xxx-xxx] received
[INFO] 🔄 [Celery] Iniciando sync_subscribers_task con limit=200
[INFO] ✅ [Celery] Sincronización completada
```

---

## ✅ Estado Final

Tienes **2 terminales abiertas**:
- **Terminal 1:** Worker procesando tareas
- **Terminal 2:** Beat programando tareas cada 2 minutos

La sincronización se ejecutará **automáticamente cada 2 minutos**.

---

## 🔧 Cambiar el Intervalo

Si quieres cambiar el intervalo (ej: 5 minutos, 10 minutos):

1. Detén Beat (Ctrl+C en Terminal 2)
2. Cambia la variable: `$env:CELERY_SYNC_MINUTES = "5"`
3. Borra el schedule: `del celerybeat-schedule*`
4. Reinicia Beat: `celery -A serverpanaccess beat -l info`

---

## 🛑 Detener Todo

Para detener la sincronización automática:

1. En Terminal 2 (Beat): Presiona `Ctrl+C`
2. En Terminal 1 (Worker): Presiona `Ctrl+C`

---

## 📝 Notas Importantes

- **Redis debe estar corriendo** (Docker)
- **Ambas terminales deben estar abiertas** (Worker y Beat)
- **No cierres las terminales** mientras quieras que funcione automáticamente
- Los logs de sincronización aparecen en `logs/django.log` y `logs/panaccess.log`

