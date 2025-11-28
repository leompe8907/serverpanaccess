# Documentación: Sistema de Autenticación con PanAccess

## 📋 Índice
1. [Resumen General](#resumen-general)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Componentes Implementados](#componentes-implementados)
4. [Flujo de Autenticación](#flujo-de-autenticación)
5. [Auto-Refresh de Sesión](#auto-refresh-de-sesión)
6. [Uso del Sistema](#uso-del-sistema)
7. [Manejo de Errores](#manejo-de-errores)

---

## Resumen General

Este proyecto implementa un sistema de autenticación como puente entre los usuarios y PanAccess (proveedor de servicios). El sistema permite:

- ✅ Autenticarse con PanAccess y obtener un `sessionId`
- ✅ Validar si un `sessionId` sigue siendo válido
- ✅ Refrescar automáticamente la sesión cuando caduca
- ✅ Manejar errores de forma robusta con excepciones personalizadas

---

## Arquitectura del Sistema

```
wind/
├── exceptions.py              # Excepciones personalizadas
├── utils/
│   ├── panaccess_auth.py      # Funciones de autenticación (login, logged_in)
│   └── __init__.py
├── services/
│   ├── panaccess_client.py    # Cliente principal con auto-refresh
│   └── __init__.py
└── views.py                   # Vistas de prueba
```

### Separación de Responsabilidades

- **`exceptions.py`**: Define todas las excepciones personalizadas para manejo de errores
- **`utils/panaccess_auth.py`**: Funciones puras de autenticación (sin estado)
- **`services/panaccess_client.py`**: Cliente con estado que maneja sesiones y auto-refresh
- **`views.py`**: Endpoints HTTP para testing y uso en producción

---

## Componentes Implementados

### 1. Excepciones Personalizadas (`wind/exceptions.py`)

Sistema completo de excepciones para manejo de errores:

```python
PanAccessException                    # Base para todas las excepciones
├── PanAccessAuthenticationError     # Credenciales inválidas
├── PanAccessSessionError            # Sesión expirada/inválida
├── PanAccessRateLimitError          # Rate limiting (20 logins/5min)
├── PanAccessConnectionError         # Problemas de conexión
├── PanAccessTimeoutError            # Timeouts
└── PanAccessAPIError                # Errores genéricos de la API
```

**Ventaja**: Permite manejar errores específicos de forma granular.

---

### 2. Funciones de Autenticación (`wind/utils/panaccess_auth.py`)

#### `login() -> str`
Realiza login en PanAccess y retorna el `sessionId`.

**Características**:
- Valida configuración antes de intentar login
- Hashea la contraseña con MD5 + salt (requerido por PanAccess)
- Maneja todos los tipos de errores con excepciones personalizadas
- Retorna solo el `sessionId` (string)

**Uso**:
```python
from wind.utils.panaccess_auth import login

try:
    session_id = login()
    print(f"SessionId: {session_id}")
except PanAccessAuthenticationError as e:
    print(f"Error de autenticación: {e}")
```

#### `logged_in(session_id: str) -> bool`
Verifica si un `sessionId` sigue siendo válido.

**Características**:
- Llama a `cvLoggedIn` de PanAccess
- Retorna `True` si la sesión es válida, `False` si está caducada
- Maneja respuestas booleanas y strings ("true"/"false")
- Lanza excepciones si hay errores de conexión/timeout

**Uso**:
```python
from wind.utils.panaccess_auth import logged_in

is_valid = logged_in(session_id)
if not is_valid:
    # Sesión caducada, hacer login nuevamente
    session_id = login()
```

---

### 3. Cliente PanAccess (`wind/services/panaccess_client.py`)

Clase principal para interactuar con la API de PanAccess.

#### Características Principales

1. **Autenticación Automática**: Se autentica automáticamente si no hay `sessionId`
2. **Auto-Refresh**: Verifica y refresca la sesión antes de cada llamada
3. **Manejo de Estado**: Mantiene el `sessionId` internamente
4. **Métodos Útiles**: `check_session()`, `logout()`, `is_authenticated()`

#### Métodos Principales

##### `authenticate() -> str`
Realiza login y guarda el `sessionId` internamente.

##### `call(func_name, parameters, timeout) -> Dict`
Llama a una función de la API. **Automáticamente**:
- Verifica si hay `sessionId`
- Valida si el `sessionId` está vigente
- Refresca la sesión si está caducada
- Agrega el `sessionId` a los parámetros

##### `check_session() -> bool`
Verifica si la sesión actual es válida usando `logged_in()`.

##### `is_authenticated() -> bool`
Verifica si hay un `sessionId` guardado (no valida si está vigente).

##### `logout() -> bool`
Cierra la sesión actual en PanAccess.

---

## Flujo de Autenticación

### Flujo Básico (sin auto-refresh)

```
1. Usuario llama a login()
   ↓
2. Sistema hashea password + salt
   ↓
3. Envía petición a PanAccess
   ↓
4. Recibe sessionId
   ↓
5. Usuario usa sessionId en llamadas posteriores
```

### Flujo con Auto-Refresh (recomendado)

```
1. Usuario crea PanAccessClient()
   ↓
2. Usuario llama a client.call("cvGetSubscriber", {...})
   ↓
3. Cliente verifica: ¿Hay sessionId?
   ├─ NO → client.authenticate() → Obtiene sessionId
   └─ SÍ → Continúa
   ↓
4. Cliente verifica: ¿sessionId está vigente?
   ├─ NO → client.authenticate() → Refresca sessionId
   └─ SÍ → Continúa
   ↓
5. Cliente agrega sessionId a parámetros
   ↓
6. Cliente realiza la llamada a PanAccess
   ↓
7. Retorna resultado
```

**Ventaja**: El usuario no necesita preocuparse por la gestión de sesiones.

---

## Auto-Refresh de Sesión

### ¿Cómo Funciona?

El método `_ensure_valid_session()` del cliente se ejecuta automáticamente antes de cada llamada (excepto `login` y `cvLoggedIn`):

```python
def _ensure_valid_session(self):
    # Si no hay sessionId, autenticar
    if not self.session_id:
        self.authenticate()
        return
    
    # Verificar si la sesión sigue siendo válida
    try:
        is_valid = logged_in(self.session_id)
        if not is_valid:
            # Sesión caducada, refrescar
            self.authenticate()
    except (PanAccessConnectionError, PanAccessTimeoutError, PanAccessAPIError):
        # Si hay error al verificar, intentar refrescar
        try:
            self.authenticate()
        except Exception:
            # Si el refresh también falla, limpiar sessionId
            self.session_id = None
            raise
```

### ¿Cuándo se Refresca?

1. **Automáticamente antes de cada llamada** a la API (excepto `login` y `cvLoggedIn`)
2. **Si el `sessionId` no existe**
3. **Si el `sessionId` está caducado** (verificado con `logged_in()`)
4. **Si hay error al verificar la sesión** (intenta refrescar)

### Ventajas

- ✅ **Transparente**: El usuario no necesita manejar la expiración manualmente
- ✅ **Robusto**: Maneja errores de red y timeouts
- ✅ **Eficiente**: Solo refresca cuando es necesario
- ✅ **Seguro**: Limpia el `sessionId` si hay errores críticos

---

## Uso del Sistema

### Opción 1: Función Directa (Simple)

```python
from wind.utils.panaccess_auth import login, logged_in

# Hacer login
session_id = login()

# Usar sessionId en llamadas manuales
# ... hacer llamadas ...

# Verificar si sigue vigente
if not logged_in(session_id):
    session_id = login()  # Refrescar
```

**Cuándo usar**: Cuando necesitas control total sobre cuándo hacer login.

### Opción 2: Cliente (Recomendado)

```python
from wind.services import PanAccessClient

client = PanAccessClient()

# El cliente se autentica automáticamente en la primera llamada
result = client.call("cvGetSubscriber", {
    "subscriberCode": "12345"
})

# El cliente refresca automáticamente si la sesión caduca
result2 = client.call("cvGetSubscriber", {
    "subscriberCode": "67890"
})
```

**Cuándo usar**: Para la mayoría de casos de uso. El cliente maneja todo automáticamente.

### Opción 3: Autenticación Explícita

```python
from wind.services import PanAccessClient

client = PanAccessClient()

# Autenticarse explícitamente
session_id = client.authenticate()

# Verificar sesión manualmente
if client.check_session():
    print("Sesión válida")
else:
    print("Sesión caducada, refrescando...")
    client.authenticate()
```

**Cuándo usar**: Cuando necesitas verificar el estado de la sesión antes de hacer llamadas.

---

## Manejo de Errores

### Tipos de Errores y Cómo Manejarlos

#### 1. `PanAccessAuthenticationError`
**Causa**: Credenciales inválidas o API key deshabilitado.

```python
try:
    session_id = login()
except PanAccessAuthenticationError as e:
    # Verificar credenciales en .env
    print(f"Error: {e}")
```

#### 2. `PanAccessSessionError`
**Causa**: Sesión expirada o inválida.

```python
try:
    result = client.call("cvGetSubscriber", {...})
except PanAccessSessionError as e:
    # El cliente ya intentó refrescar, pero falló
    # Re-autenticar manualmente
    client.authenticate()
    result = client.call("cvGetSubscriber", {...})
```

#### 3. `PanAccessRateLimitError`
**Causa**: Más de 20 logins en 5 minutos.

```python
try:
    session_id = login()
except PanAccessRateLimitError as e:
    # Esperar antes de intentar nuevamente
    import time
    time.sleep(60)  # Esperar 1 minuto
    session_id = login()
```

#### 4. `PanAccessConnectionError` / `PanAccessTimeoutError`
**Causa**: Problemas de red o timeout.

```python
try:
    result = client.call("cvGetSubscriber", {...})
except (PanAccessConnectionError, PanAccessTimeoutError) as e:
    # Reintentar después de un tiempo
    import time
    time.sleep(5)
    result = client.call("cvGetSubscriber", {...})
```

---

## Endpoints de Prueba

### `GET /wind/test/login/`
Prueba la autenticación básica.

**Respuesta exitosa**:
```json
{
    "success": true,
    "message": "Login exitoso",
    "session_id": "abc123...",
    "session_id_length": 32,
    "is_authenticated": true
}
```

### `GET /wind/test/logged-in/`
Prueba la validación de sesión.

**Respuesta exitosa**:
```json
{
    "success": true,
    "message": "Verificación de sesión exitosa",
    "session_id": "abc123...",
    "is_valid_direct": true,
    "is_valid_client": true,
    "both_match": true
}
```

---

## Notas Importantes

### Rate Limiting
PanAccess limita a **20 logins en 5 minutos**. El auto-refresh del cliente ayuda a evitar este límite al reutilizar sesiones válidas.

### SessionId Encriptado
Dependiendo de la configuración del API Token, el `sessionId` puede estar encriptado. El sistema maneja esto automáticamente.

### Timeouts
- Login: 30 segundos
- Llamadas API: 60 segundos (configurable)
- Verificación de sesión: 30 segundos

### Variables de Entorno Requeridas
```env
url_panaccess=https://cv01.panaccess.com
username=tu_usuario
password=tu_contraseña
api_token=tu_api_token
salt=tu_salt
ENCRYPTION_KEY=tu_encryption_key
```

---

## Próximos Pasos

1. ✅ Autenticación básica (`login`)
2. ✅ Validación de sesión (`logged_in`)
3. ✅ Auto-refresh de sesión
4. ⏭️ Implementar funciones específicas de PanAccess (ej: `cvGetSubscriber`)
5. ⏭️ Agregar logging detallado
6. ⏭️ Implementar caché de sesión (opcional)

---

## Resumen de Cambios Realizados

### Simplificación de Vistas
- ❌ Eliminadas: `test_login_direct`, `test_login_client`, `test_login_complete`
- ✅ Creada: `test_login` (vista única y simple)
- ✅ Creada: `test_logged_in` (prueba validación de sesión)

### Nueva Funcionalidad
- ✅ Función `logged_in()` para validar sesiones
- ✅ Método `check_session()` en el cliente
- ✅ Auto-refresh automático en `PanAccessClient.call()`
- ✅ Método `_ensure_valid_session()` para gestión interna

### Mejoras
- ✅ Manejo robusto de errores en validación de sesión
- ✅ Limpieza automática de `sessionId` en caso de errores críticos
- ✅ Documentación completa del sistema

---

**Fecha de creación**: 28 de Noviembre, 2025  
**Versión**: 1.0.0

