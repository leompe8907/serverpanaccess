# Login social con Google – Guía de implementación

Este documento describe cómo implementar el inicio de sesión con Google para usuarios finales en las aplicaciones (iPhone, Android, TVs Samsung, LG, Android TV, Amazon). Incluye la idea general, el flujo, los pasos en Google Cloud, el diseño del backend y las consideraciones por plataforma.

---

## 1. Idea general

- **Objetivo**: que el usuario final abra la app, pulse "Iniciar sesión con Google", y si su correo ya existe como suscriptor en el sistema, quede logueado y use la app con normalidad.
- **Backend**: valida la identidad con Google (OAuth 2.0), busca al suscriptor por email en la base de datos y devuelve al cliente **un token de sesión** (o, solo para pruebas internas y de forma temporal, credenciales; ver sección de pruebas).
- **Cliente (app)**: no maneja contraseñas; solo recibe y guarda el token (o credenciales en modo prueba), lo envía en las peticiones siguientes y así "funciona normal".

El "usuario" en este backend es un **suscriptor** (`ListOfSubscriber` / `SubscriberEmailRegistry`). "El usuario existe" significa: existe un suscriptor cuyo email coincide con el email de la cuenta de Google.

---

## 2. Cómo funciona (flujo)

### 2.1 Flujo recomendado (token)

1. Usuario pulsa "Iniciar sesión con Google" en la app.
2. La app obtiene de Google un **código de autorización** (`code`) o un **id_token** (según plataforma; ver más abajo).
3. La app envía ese `code` o `id_token` al backend (por ejemplo `POST /auth/google` o `POST /auth/google/callback` según diseño).
4. El backend:
   - Intercambia el `code` por tokens con Google (o verifica el `id_token`).
   - Obtiene el **email** (y opcionalmente nombre) del usuario de Google.
   - Busca en la BD un suscriptor con ese email (`ListOfSubscriber.emails` o `SubscriberEmailRegistry.email`).
   - Si **no existe**: responde 401/404 con mensaje tipo "No hay cuenta asociada a este correo".
   - Si **existe**: genera un **token de sesión** asociado al `subscriber_code` (o ID del suscriptor) y lo devuelve en la respuesta.
5. La app guarda el token (p. ej. en almacenamiento seguro) y en cada petición envía `Authorization: Bearer <token>` (o el esquema que se defina).
6. El backend valida el token en cada request y obtiene el suscriptor; con eso la app "funciona normal".

### 2.2 Por qué usar token y no credenciales

- **Seguridad**: las credenciales (login/password) no deberían salir del backend. Si se filtra un token, se puede revocar o dejar que expire; si se filtran credenciales, el daño es mayor.
- **Responsabilidades**: el backend verifica identidad y crea sesión; el cliente solo demuestra sesión enviando el token.
- **Buenas prácticas**: OAuth y estándares recomiendan tokens con expiración y, si es posible, revocación.

Para **pruebas internas temporales** se puede, bajo condiciones controladas, devolver credenciales; debe estar documentado y acotado (ver sección 7).

---

## 3. Pasos en Google Cloud

Todo el login con Google requiere crear un proyecto y credenciales OAuth 2.0 en Google Cloud.

**Guía detallada paso a paso:** ver **`docs/GOOGLE_CLOUD_PASO_A_PASO.md`** (qué hacer en cada pantalla, qué campos rellenar y cómo guardar Client ID y Client Secret).

Resumen a continuación.

### 3.1 Acceso

1. Ir a [Google Cloud Console](https://console.cloud.google.com/).
2. Iniciar sesión con la cuenta de Google que se usará para administrar el proyecto.

### 3.2 Crear proyecto

1. Selector de proyectos (arriba) → **Nuevo proyecto**.
2. Nombre, por ejemplo: `Win App` o `Mi App Login`.
3. **Crear** y seleccionar el proyecto como activo.

### 3.3 Pantalla de consentimiento OAuth

1. Menú → **APIs y servicios** → **Pantalla de consentimiento de OAuth**.
2. Tipo de usuario:
   - **Externo**: para que cualquier usuario final use "Iniciar sesión con Google" (cuando la app esté publicada).
   - Para pruebas internas puede bastar con usuarios de prueba en modo "Prueba".
3. Completar campos obligatorios:
   - Nombre de la aplicación.
   - Correo de asistencia.
   - Información de contacto del desarrollador.
4. En **Permisos / Ámbitos**, asegurar al menos:
   - `openid`
   - `email` (userinfo.email)
   - `profile` (userinfo.profile)
5. Si la app está en "Prueba", añadir en **Usuarios de prueba** los correos con los que se probará.
6. Guardar y continuar hasta volver al panel.

### 3.4 Credenciales OAuth 2.0

1. Menú → **APIs y servicios** → **Credenciales**.
2. **+ Crear credenciales** → **ID de cliente de OAuth**.
3. Tipo de aplicación: **Aplicación web**.
4. Nombre: por ejemplo `Win Web Client`.
5. **URIs de redirección autorizados** (deben coincidir exactamente con las que use el backend o el cliente):
   - Desarrollo: `http://127.0.0.1:8000/auth/google/callback/` (ajustar puerto y ruta según el backend).
   - Producción: `https://api.tudominio.com/auth/google/callback/` (ejemplo).
6. **Crear**.
7. Copiar y guardar de forma segura:
   - **ID de cliente** (Client ID).
   - **Secreto del cliente** (Client Secret).

Estos valores deben configurarse en el backend (por ejemplo en `.env`):

- `GOOGLE_CLIENT_ID=...`
- `GOOGLE_CLIENT_SECRET=...`

Nunca incluir el Client Secret en el código ni en el frontend.

### 3.5 Resumen de uso en el backend

- **Client ID**: para construir la URL de autorización de Google y para el intercambio del `code`.
- **Client Secret**: solo en el backend, para el intercambio del `code` por tokens (POST a Google).
- **Redirect URI**: la misma que se configuró en "URIs de redirección autorizados" y la misma ruta que exponga el backend (si se usa flujo con redirect).

---

## 4. Backend (Django) – Qué implementar

### 4.1 Enfoque único para todos los clientes

El backend puede ofrecer una API común para todas las plataformas (móvil y TV). La diferencia está en cómo cada cliente obtiene el `code` o el `id_token` y se lo envía al backend.

### 4.2 Endpoints sugeridos

| Endpoint | Método | Uso |
|----------|--------|-----|
| `GET /auth/google/` (opcional) | GET | Devuelve la URL de autorización de Google para que el cliente redirija al usuario. Si el cliente construye la URL, no es obligatorio. |
| `GET /auth/google/callback/` | GET | Recibe `code` (y opcionalmente `state`) en query. Canjea con Google, obtiene email, busca suscriptor, genera token (o credenciales en modo prueba) y responde o redirige al cliente con el resultado. |
| `POST /auth/google/` | POST | Recibe en el body `id_token` (o `code`). Valida con Google, obtiene email, busca suscriptor, genera token (o credenciales en modo prueba) y devuelve JSON. Útil para apps móviles que usan el SDK de Google y envían el id_token directamente. |

Se puede unificar en un solo endpoint que acepte tanto `code` (por query o body) como `id_token` (por body), según lo que envíe cada cliente.

### 4.3 Lógica del callback / POST (resumen)

1. Recibir `code` o `id_token`.
2. Si es `code`: POST a `https://oauth2.googleapis.com/token` con `grant_type=authorization_code`, `code`, `client_id`, `client_secret`, `redirect_uri`; de la respuesta usar `id_token` (JWT) o `access_token` para obtener el perfil (email, nombre).
3. Si es `id_token`: verificar firma/claims del JWT con Google (o librería `google-auth`) y extraer email (y nombre si se incluye).
4. Buscar suscriptor por email:
   - Por ejemplo en `ListOfSubscriber` (`emails`) o en `SubscriberEmailRegistry` (`email`).
   - Obtener `subscriber_code` (o `code` del suscriptor).
5. Si no hay suscriptor: responder 401/404 con mensaje claro.
6. Si hay suscriptor:
   - Generar token de sesión (JWT o sesión Django) asociado al `subscriber_code`.
   - (Opcional, solo pruebas internas): si está activado el modo "devolver credenciales", incluir también login/password en la respuesta; ver sección 7.
7. Responder JSON con `token` (y opcionalmente `subscriber_code`, `email`, `nombre`) o redirigir al frontend con el token en query/fragment para que la app lo guarde.

### 4.4 Validación del token en el resto de la API

- Los endpoints que requieran "usuario logueado" deben validar el token (JWT o sesión) y obtener el `subscriber_code`.
- Con ese `subscriber_code` se pueden cargar `SubscriberLoginInfo`, `SubscriberInfo`, etc., según la lógica de negocio existente.

### 4.5 Seguridad en el flujo OAuth

- **state**: al enviar al usuario a Google, generar un valor aleatorio, guardarlo (cookie o sesión) y en el callback comprobar que el `state` devuelto por Google sea el mismo (protección CSRF).
- **Client Secret**: solo en el servidor, nunca en apps ni en el frontend.
- **HTTPS** en producción para redirect_uri y para la API.

---

## 5. Clientes por plataforma

### 5.1 iPhone y Android

- **Recomendado**: usar el SDK nativo de Google Sign-In. El usuario inicia sesión en la app; Google devuelve un **id_token** (o access_token) a la app. La app envía ese **id_token** al backend (`POST /auth/google` con `{"id_token": "..."}`). El backend valida, busca suscriptor y devuelve el token de la aplicación. No hace falta que el backend tenga una "redirect URI" que abra el navegador; solo el endpoint que recibe el id_token.
- **Alternativa**: abrir WebView o navegador con la URL de Google; Google redirige a una URL del backend con `code`; el backend canjea y redirige al cliente con un custom scheme (p. ej. `miapp://login?token=...`) o App Link para que la app capture el token.

### 5.2 TVs (Samsung Tizen, LG webOS, Android TV, Amazon Fire TV)

En TVs suele usarse un flujo "segunda pantalla" o "dispositivo":

- En la TV se muestra un **código** (o QR) y una URL, por ejemplo: `https://tudominio.com/activate?device=ABC123`.
- El usuario abre esa URL en el móvil o PC, inicia sesión con Google (o con el mismo flujo de login); el backend asocia la sesión al `device=ABC123`.
- La TV hace **polling** a un endpoint tipo `GET /auth/device/<device_id>` hasta que el backend tenga un token asociado a ese dispositivo y lo devuelva.
- La TV guarda ese token y lo envía en las peticiones siguientes.

En este flujo las credenciales de Google no se manejan en la TV; solo se pasa el token de la aplicación.

---

## 6. Variables de entorno recomendadas

En el backend (por ejemplo en `.env`):

- `GOOGLE_CLIENT_ID`: ID de cliente OAuth 2.0.
- `GOOGLE_CLIENT_SECRET`: Secreto del cliente (solo backend).
- `GOOGLE_REDIRECT_URI`: URI de callback (debe coincidir con la configurada en Google Cloud).
- Opcional, para modo prueba con credenciales: `DEV_CREDENTIALS_RESPONSE=True` (o similar), solo en entornos de desarrollo/pruebas internas.

---

## 7. Pruebas internas temporales (devolver credenciales)

Si se decide, **solo para pruebas internas** y de forma temporal, devolver credenciales (login/password) en la respuesta del login con Google:

- **Condición**: que esto solo ocurra cuando una variable de entorno lo permita (por ejemplo `DEBUG=True` o `DEV_CREDENTIALS_RESPONSE=True`). En cualquier otro entorno no se deben enviar credenciales.
- **Logs**: no registrar el cuerpo de la respuesta que contiene password (evitar que las credenciales queden en logs o herramientas de monitoreo).
- **Documentación en código**: comentario tipo "Solo para pruebas internas; reemplazar por token antes de release o uso externo".
- **Al terminar las pruebas**: eliminar la rama o la opción que devuelve credenciales y usar solo token. En la app el cambio es mínimo: guardar y enviar el token en lugar de credenciales.

Contexto aceptable para este enfoque temporal: entorno interno, base de datos de pruebas que se reinicia, y borrado de las apps en los dispositivos de prueba al finalizar. Aun así, se recomienda pasar a token en cuanto se valide que el flujo funciona.

---

## 8. Resumen de pasos a seguir

1. **Google Cloud**: crear proyecto, configurar pantalla de consentimiento OAuth, crear credenciales OAuth 2.0 (tipo Aplicación web), configurar URIs de redirección y guardar Client ID y Client Secret en variables de entorno del backend.
2. **Backend**: implementar endpoint(s) que reciban `code` o `id_token`, canjeen/verifiquen con Google, obtengan email, busquen suscriptor por email y devuelvan token (y opcionalmente credenciales solo en modo prueba interna).
3. **Clientes móviles**: integrar Google Sign-In (SDK), obtener id_token y enviarlo al backend; guardar el token devuelto y usarlo en las peticiones.
4. **TVs**: implementar flujo segunda pantalla (código/QR + URL de activación, polling por device_id) y que la TV reciba solo el token de la aplicación.
5. **Resto de la API**: validar el token en cada request protegido y resolver el suscriptor a partir del token.
6. **Pruebas**: usar token desde el inicio si es posible; si se usa temporalmente respuesta con credenciales, acotar con variable de entorno y sin loguear la respuesta, y planificar el cambio a solo token.

---

## 9. Referencias útiles

- **Google Cloud paso a paso**: `docs/GOOGLE_CLOUD_PASO_A_PASO.md`
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [Google Sign-In para iOS/Android](https://developers.google.com/identity/sign-in)
- Documentación del proyecto: `docs/CREATE_SUBSCRIBER_FRONTEND.md` (flujo de suscriptores y endpoints existentes).

---

*Documento creado como guía de implementación del login social con Google. Actualizar según decisiones finales de diseño (rutas exactas, nombres de variables, formato del token).*
