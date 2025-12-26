# 🔧 Solución: Solo se ejecuta una tarea

## ❌ Problema
Beat solo ejecuta `sync-subscribers` pero no `sync-smartcards`.

## 🔍 Causa
El archivo `celerybeat-schedule.dat` se creó antes de agregar la segunda tarea al schedule. Beat usa este archivo persistente y no detecta cambios en la configuración.

## ✅ Solución

### **PASO 1: Detener Beat**
Presiona `Ctrl+C` en la terminal donde corre Beat.

### **PASO 2: Borrar el schedule persistente**
```powershell
Get-ChildItem -Path . -Filter "celerybeat-schedule*" | Remove-Item -Force
```

O simplemente:
```powershell
del celerybeat-schedule*
```

### **PASO 3: Reiniciar Beat**
```powershell
.\start_celery_beat.ps1
```

O manualmente:
```powershell
celery -A serverpanaccess beat -l info
```

### **PASO 4: Verificar**
Ahora deberías ver ambas tareas ejecutándose:

```
[INFO] Scheduler: Sending due task sync-subscribers (wind.tasks.sync_subscribers_task)
[INFO] Scheduler: Sending due task sync-smartcards (wind.tasks.sync_smartcards_task)
```

## ⚠️ Nota sobre Intervalos

Si configuraste intervalos diferentes:
- `CELERY_SYNC_MINUTES=2` → suscriptores cada 2 minutos
- `CELERY_SMARTCARD_SYNC_MINUTES=10` → smartcards cada 10 minutos

Verás que `sync-subscribers` se ejecuta más frecuentemente que `sync-smartcards`, lo cual es normal.

## 📝 Regla de Oro

**SIEMPRE borra `celerybeat-schedule*` cuando:**
- Agregas una nueva tarea al schedule
- Cambias el intervalo de una tarea
- Modificas cualquier configuración del schedule


