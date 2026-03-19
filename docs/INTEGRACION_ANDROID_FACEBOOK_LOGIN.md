# Integracion Android: Login Social con Facebook

Guia para integrar en Android el login con Facebook y autenticarse contra el backend de este proyecto.

---

## 1) Objetivo del flujo

La app Android debe:

1. Obtener el **access token de Facebook** desde el SDK.
2. Enviarlo al backend:
   - `POST /wind/auth/facebook/`
3. Recibir:
   - `access` (JWT de tu API Django)
   - `refresh` (puede venir vacio en la configuracion actual)
   - `user` (incluye `subscriber_code`)
   - `panaccess_credentials` (`login1`, `password`, `login2`, `subscriberCode`)
4. Guardar esos datos para usarlos en la app.

---

## 2) Requisitos previos

- App de Facebook creada en Meta for Developers.
- `FACEBOOK_APP_ID` y `FACEBOOK_APP_SECRET` configurados en el backend.
- `Facebook Login` habilitado (Client OAuth y Web OAuth ON).
- Backend corriendo y endpoint disponible:
  - `https://TU_BACKEND/wind/auth/facebook/`

> En local, si pruebas desde dispositivo fisico, `localhost` del telefono NO apunta a tu PC.

---

## 3) Dependencias Android (ejemplo)

En `build.gradle` (modulo app):

```gradle
implementation "com.facebook.android:facebook-login:17.0.2"
implementation "com.squareup.retrofit2:retrofit:2.11.0"
implementation "com.squareup.retrofit2:converter-gson:2.11.0"
implementation "com.squareup.okhttp3:logging-interceptor:4.12.0"
```

---

## 4) Configuracion inicial de Facebook SDK

1. En `AndroidManifest.xml`, agrega tu `Facebook App ID` y metadata del SDK.
2. Inicializa el SDK si tu setup lo requiere.
3. Configura `LoginButton` o flujo manual con `LoginManager`.

Permisos recomendados:

- `email`
- `public_profile`

Ejemplo con `LoginManager`:

```kotlin
LoginManager.getInstance().logInWithReadPermissions(
    this,
    listOf("email", "public_profile")
)
```

Cuando el login sea exitoso:

```kotlin
val facebookAccessToken = loginResult.accessToken.token
```

---

## 5) Llamada al backend (`/wind/auth/facebook/`)

### Request JSON

```json
{
  "access_token": "<FACEBOOK_ACCESS_TOKEN>"
}
```

### Modelos Kotlin sugeridos

```kotlin
data class FacebookLoginRequest(
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

data class FacebookLoginResponse(
    val access: String,
    val refresh: String?,
    val user: UserDto,
    val panaccess_credentials: PanaccessCredentialsDto?
)
```

### Servicio Retrofit

```kotlin
interface AuthApi {
    @POST("wind/auth/facebook/")
    suspend fun facebookLogin(
        @Body body: FacebookLoginRequest
    ): FacebookLoginResponse
}
```

### Uso

```kotlin
suspend fun loginWithFacebookToken(token: String, api: AuthApi): FacebookLoginResponse {
    return api.facebookLogin(FacebookLoginRequest(access_token = token))
}
```

---

## 6) Respuesta esperada del backend

Ejemplo real:

```json
{
  "access": "JWT_API",
  "refresh": "",
  "user": {
    "pk": 2,
    "email": "implementation.ios@networkbroadcast.net",
    "first_name": "Implementation",
    "last_name": "Bromteck",
    "subscriber_code": "AUTO2"
  },
  "panaccess_credentials": {
    "login1": 5629293,
    "password": "sZ7fCtjA",
    "login2": "nbr_26@AUTO2",
    "subscriberCode": "AUTO2"
  }
}
```

---

## 7) Que guardar en Android

Guardar de forma segura:

- `access`
- `refresh` (si viene no vacio)
- `user.email`, `user.subscriber_code`
- `panaccess_credentials`

Recomendado:

- `EncryptedSharedPreferences` para secretos.
- No imprimir `password` de PanAccess en logs.

---

## 8) Uso posterior

### Para tu API Django

Enviar en cada request:

```http
Authorization: Bearer <access>
```

### Para PanAccess

Usar `panaccess_credentials` en el flujo que necesite login PanAccess (`login1/login2/password`).

---

## 9) Manejo de errores recomendado

- Si Facebook login falla: mostrar mensaje y permitir reintento.
- Si backend responde 4xx/5xx: mostrar error amigable y log tecnico (sin secretos).
- Si `panaccess_credentials` viene `null`: bloquear funciones que dependan de PanAccess.

Errores comunes:

- El usuario de Facebook no entrega `email`.
- Token expirado/invalidado.
- App Facebook en modo desarrollo sin roles correctamente asignados.

---

## 10) Checklist QA Android

- [ ] Login Facebook retorna `access` y `user`.
- [ ] `panaccess_credentials` llega con datos validos.
- [ ] Requests autenticadas usan `Authorization: Bearer`.
- [ ] Sesion persiste al reiniciar app.
- [ ] Logout limpia tokens y credenciales locales.

