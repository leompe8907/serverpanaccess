# Integracion Android: Login Social con Google

Guia para integrar en Android el flujo de login social con Google y consumir el backend de este proyecto.

---

## 1) Objetivo del flujo

La app Android debe:

1. Obtener un **ID Token** de Google (JWT).
2. Enviar ese token al backend:
   - `POST /wind/auth/google/`
3. Recibir:
   - `access` (JWT de la API Django)
   - `refresh` (puede venir vacio segun configuracion actual)
   - `user` (incluye `subscriber_code`)
   - `panaccess_credentials` (`login1`, `password`, `login2`, `subscriberCode`)
4. Guardar esa informacion para uso posterior.

---

## 2) Requisitos previos

- Proyecto Android con Kotlin.
- Google Cloud configurado (OAuth consent + client ID).
- Backend funcionando y accesible desde el dispositivo Android.
- Endpoint disponible:
  - `https://TU_BACKEND/wind/auth/google/`

> En desarrollo local, `127.0.0.1` en el telefono NO apunta a tu PC. Usa IP local de tu maquina, emulador con bridge, o tunel.

---

## 3) Dependencias recomendadas

En `build.gradle` (modulo app), usar:

```gradle
implementation "com.google.android.gms:play-services-auth:21.2.0"
implementation "com.squareup.retrofit2:retrofit:2.11.0"
implementation "com.squareup.retrofit2:converter-gson:2.11.0"
implementation "com.squareup.okhttp3:logging-interceptor:4.12.0"
```

---

## 4) Obtener ID Token de Google en Android

Configura Google Sign-In solicitando `idToken`:

```kotlin
val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
    .requestEmail()
    .requestIdToken(getString(R.string.google_web_client_id))
    .build()

val googleSignInClient = GoogleSignIn.getClient(this, gso)
```

Despues del login exitoso:

```kotlin
val account = task.getResult(ApiException::class.java)
val idToken = account.idToken  // JWT de Google
```

> Usa el `web client id` en `google_web_client_id`.

---

## 5) Llamar al backend (`/wind/auth/google/`)

### Request JSON

El backend actual acepta el JWT de Google en `access_token`:

```json
{
  "access_token": "<GOOGLE_ID_TOKEN>"
}
```

### Modelos Kotlin sugeridos

```kotlin
data class GoogleLoginRequest(
    val access_token: String
)

data class UserDto(
    val pk: Int,
    val email: String,
    val first_name: String,
    val last_name: String,
    val subscriber_code: String?
)

data class PanaccessCredentialsDto(
    val login1: String?,
    val password: String?,
    val login2: String?,
    val subscriberCode: String?
)

data class GoogleLoginResponse(
    val access: String,
    val refresh: String?,
    val user: UserDto,
    val panaccess_credentials: PanaccessCredentialsDto?,
    val subscriber_provisioning: Map<String, Any>? = null
)
```

### Servicio Retrofit

```kotlin
interface AuthApi {
    @POST("wind/auth/google/")
    suspend fun googleLogin(
        @Body body: GoogleLoginRequest
    ): GoogleLoginResponse
}
```

### Uso

```kotlin
suspend fun loginWithGoogleToken(idToken: String, api: AuthApi): GoogleLoginResponse {
    return api.googleLogin(GoogleLoginRequest(access_token = idToken))
}
```

---

## 6) Que guardar en Android

Guardar de forma segura:

- `access` (JWT API)
- `refresh` (si llega no vacio)
- `user.pk`, `user.email`, `user.subscriber_code`
- `panaccess_credentials` completas

Recomendado:

- `EncryptedSharedPreferences` para datos sensibles.
- No loguear `password` de PanAccess en consola.

---

## 7) Uso despues del login

### Para llamadas a tu API Django

Enviar:

```http
Authorization: Bearer <access>
```

### Para flujo PanAccess en mobile

Usar `panaccess_credentials` para construir el login contra servicios que dependan de `login1/password/login2`.

---

## 8) Manejo de errores recomendado

Si backend devuelve 4xx/5xx:

1. Mostrar mensaje amigable al usuario.
2. Registrar codigo HTTP y body (sin secretos).
3. Si `panaccess_credentials` es `null`, bloquear funcionalidades que dependan de PanAccess hasta reintento.

Casos tipicos:

- Token Google invalido o expirado.
- Error temporal de backend.
- Usuario sin provisionamiento completado.

---

## 9) Flujo funcional esperado en backend (resumen)

- Si el correo ya existe: devuelve credenciales existentes.
- Si no existe: crea suscriptor, aplica flujo de license block, asignacion SN y producto, luego devuelve credenciales.

Android siempre consume el mismo endpoint y procesa la misma estructura de respuesta.

---

## 10) Checklist rapido para QA Android

- [ ] Login Google exitoso retorna `access` y `user`.
- [ ] `panaccess_credentials` llega con valores no nulos en caso valido.
- [ ] Sesion persiste al cerrar/reabrir app.
- [ ] Requests autenticadas usan `Authorization: Bearer`.
- [ ] Logout borra tokens y credenciales locales.

