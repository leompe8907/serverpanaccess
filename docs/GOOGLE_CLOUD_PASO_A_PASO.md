# Google Cloud – Paso a paso para Login con Google

Guía detallada para configurar en Google Cloud todo lo necesario para el login social con Google. Sigue los pasos en orden; al final tendrás el **Client ID** y el **Client Secret** para usar en el backend.

---

## Paso 1: Abrir Google Cloud Console

1. Abre el navegador y ve a: **https://console.cloud.google.com/**
2. Inicia sesión con la cuenta de Google que quieras usar para administrar el proyecto (puede ser tu correo corporativo o personal).
3. Si es la primera vez, acepta los términos si Google los muestra.

---

## Paso 2: Crear un proyecto nuevo

1. En la **barra superior**, junto al logo de Google Cloud, verás el **selector de proyectos** (dice "Seleccionar un proyecto" o el nombre del proyecto actual).
2. Haz clic en ese selector.
3. En la ventana que se abre, haz clic en **"Nuevo proyecto"** (arriba a la derecha).
4. **Nombre del proyecto**: escribe uno que identifique tu app, por ejemplo:
   - `Win App`
   - `Mi App Login`
   - `Win Login Google`
5. Opcional: si tienes organización, puedes elegir una en "Organización". Si no, déjalo por defecto.
6. Haz clic en **"Crear"**.
7. Espera unos segundos. Cuando termine, el proyecto se seleccionará automáticamente. Si no, en el selector de proyectos elige el que acabas de crear.

---

## Paso 3: Ir a la pantalla de consentimiento de OAuth

1. Abre el **menú de navegación** (icono de tres rayas horizontales, arriba a la izquierda).
2. Ve a **"APIs y servicios"** → **"Pantalla de consentimiento de OAuth"**.
   - Si no ves "Pantalla de consentimiento de OAuth", busca en "APIs y servicios" la opción **"OAuth"** o **"Credenciales"** y desde ahí suele haber un enlace a la pantalla de consentimiento.
3. Verás una pantalla que dice "Configurar la pantalla de consentimiento". Aquí es donde defines cómo se verá tu app cuando el usuario pulse "Iniciar sesión con Google".

---

## Paso 4: Elegir tipo de usuario (Externo o Interno)

1. Te preguntarán **"Tipo de usuario"**:
   - **Externo**: cualquier usuario con cuenta de Google puede intentar iniciar sesión. Necesario si tu app será usada por clientes finales. En modo "Prueba" solo podrán entrar los correos que añadas como "Usuarios de prueba".
   - **Solo interno**: solo cuentas de tu organización (Google Workspace). Útil si solo probáis dentro de la empresa.
2. Para una app de usuarios finales (móvil, TV), elige **"Externo"**.
3. Haz clic en **"Crear"**.

---

## Paso 5: Completar la información de la app (Página 1 – Información de la aplicación)

1. **Nombre de la aplicación** (obligatorio): el nombre que verá el usuario al autorizar, por ejemplo: `Win` o el nombre de tu producto.
2. **Correo electrónico de asistencia al usuario** (obligatorio): tu correo o el de soporte.
3. **Logo de la aplicación**: opcional; puedes subir un icono más adelante.
4. **Dominio de la aplicación** (opcional para pruebas):
   - En desarrollo puedes dejarlo vacío.
   - En producción añade tu dominio, por ejemplo: `https://tudominio.com`
5. **Dominios autorizados** (opcional para pruebas): si tienes dominio de producción, añádelo aquí.
6. **Información de contacto del desarrollador** (obligatorio): al menos un correo (puede ser el mismo que el de asistencia).
7. Haz clic en **"Guardar y continuar"**.

---

## Paso 6: Ámbitos / Permisos (Página 2)

1. En **"Ámbitos"** o **"Permisos"** debes asegurarte de tener los que necesitas para obtener el email y el perfil básico del usuario.
2. Haz clic en **"Añadir o quitar ámbitos"** (o similar).
3. En la lista, busca y marca:
   - **openid** (necesario para identificar al usuario).
   - **.../auth/userinfo.email** (para obtener el correo).
   - **.../auth/userinfo.profile** (para nombre, foto, etc.).
4. Si no encuentras los nombres exactos, busca "email" y "profile"; Google suele agruparlos. Asegúrate de que al menos aparezcan **email** y **profile** (o **userinfo.email** y **userinfo.profile**).
5. Haz clic en **"Actualizar"** (o "Listo") y luego **"Guardar y continuar"**.

---

## Paso 7: Usuarios de prueba (Página 3 – solo si elegiste Externo)

1. Si tu app está en modo **"Prueba"** (por defecto al crear), solo los correos que añadas aquí podrán iniciar sesión con Google.
2. Haz clic en **"+ Añadir usuarios"**.
3. Añade los correos de Google con los que vais a probar (tuyo y de tu equipo), uno por línea.
4. Haz clic en **"Guardar y continuar"**.
5. En la página de resumen, revisa y haz clic en **"Volver al panel"** (o "Guardar" si aparece).

---

## Paso 8: Crear credenciales OAuth 2.0

1. En el menú lateral ve a **"APIs y servicios"** → **"Credenciales"**.
2. En la parte superior haz clic en **"+ Crear credenciales"**.
3. En el desplegable elige **"ID de cliente de OAuth"** (no "Clave de API").
4. Si te pide configurar primero la pantalla de consentimiento, vuelve al Paso 3 y complétala; si ya la hiciste, continúa.

---

## Paso 9: Configurar el ID de cliente OAuth

1. **Tipo de aplicación**: selecciona **"Aplicación web"**.
   - No elijas "Aplicación de Android" ni "iOS" para este flujo; el backend recibirá el código, por eso es "Aplicación web".
2. **Nombre**: un nombre para identificar estas credenciales, por ejemplo: `Win Web Client` o `Login con Google Backend`.
3. **URIs de redirección autorizados** (muy importante):
   - Haz clic en **"+ Añadir URI"**.
   - Para **desarrollo local** (backend en tu PC), añade exactamente:
     ```
     http://127.0.0.1:8000/auth/google/callback/
     ```
     Ajusta el puerto si tu backend usa otro (por ejemplo `8080` en vez de `8000`). La ruta `/auth/google/callback/` debe coincidir con la que implementes en Django.
   - Para **producción**, añade otra URI con tu dominio real, por ejemplo:
     ```
     https://api.tudominio.com/auth/google/callback/
     ```
   - La URI debe coincidir **exactamente** con la que use tu backend (incluyendo barra final si la usas). Si no coincide, Google rechazará el redirect.
4. No es necesario rellenar "Orígenes de JavaScript autorizados" para el flujo backend que usamos.
5. Haz clic en **"Crear"**.

---

## Paso 10: Guardar Client ID y Client Secret

1. Aparecerá un cuadro con:
   - **Tu ID de cliente**: algo como `123456789-xxxxxx.apps.googleusercontent.com`
   - **Tu secreto de cliente**: una cadena de caracteres (guárdala; no se vuelve a mostrar completa después).
2. Haz clic en **"Descargar JSON"** si quieres una copia en archivo, o copia manualmente ambos valores.
3. **Guárdalos en un lugar seguro** (por ejemplo en el archivo `.env` de tu proyecto, nunca en el código):
   ```
   GOOGLE_CLIENT_ID=tu_client_id_aqui.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=tu_client_secret_aqui
   ```
4. Opcional: en el backend también usarás la **Redirect URI** que configuraste. Puedes guardarla como:
   ```
   GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/auth/google/callback/
   ```
   (o la de producción cuando la uses.)

---

## Resumen de lo que tienes ahora

| Valor | Uso |
|-------|-----|
| **Client ID** | Se usa en el backend para construir la URL de autorización de Google y para canjear el código. Puede estar en el frontend si solo construyes la URL (sin secret). |
| **Client Secret** | Solo en el backend. Se usa para canjear el `code` por tokens en una petición POST a Google. **No** ponerlo nunca en apps móviles ni en el frontend. |
| **Redirect URI** | La URL a la que Google redirige al usuario después de autorizar. Debe ser una ruta de tu backend que reciba el parámetro `code`. |

---

## Siguiente paso

Con el Client ID y el Client Secret en tu `.env`, el siguiente paso es implementar en Django el endpoint que:

1. Recibe el `code` (cuando Google redirige al usuario a tu Redirect URI).
2. Hace un POST a Google para canjear el `code` por tokens.
3. Obtiene el email del usuario y busca al suscriptor en tu base de datos.
4. Devuelve tu token (o credenciales en modo prueba) al cliente.

Ver la guía principal: **`docs/GOOGLE_LOGIN.md`** (sección 4 – Backend).

---

## Enlaces rápidos

- [Google Cloud Console](https://console.cloud.google.com/)
- [Documentación OAuth 2.0 de Google](https://developers.google.com/identity/protocols/oauth2)
