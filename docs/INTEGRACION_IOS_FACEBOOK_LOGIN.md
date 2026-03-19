# Integracion iOS: Login Social con Facebook

Guia para integrar en iOS el login con Facebook y autenticarse contra el backend de este proyecto.

---

## 1) Objetivo del flujo

La app iOS debe:

1. Obtener el **access token** de Facebook.
2. Enviarlo al backend:
   - `POST /wind/auth/facebook/`
3. Recibir JWT de la API + credenciales PanAccess.
4. Guardar los datos de sesion de forma segura.

---

## 2) Requisitos previos

- App configurada en Meta for Developers.
- `Facebook Login` habilitado.
- `FACEBOOK_APP_ID` y `FACEBOOK_APP_SECRET` configurados en backend.
- Backend accesible desde iOS.

Endpoint a consumir:

- `https://TU_BACKEND/wind/auth/facebook/`

---

## 3) Dependencias iOS (SPM)

Usa Swift Package Manager con:

- `https://github.com/facebook/facebook-ios-sdk`

Modulo principal:

- `FacebookLogin`

---

## 4) Configuracion base iOS

1. Agrega `FacebookAppID` en `Info.plist`.
2. Agrega URL Schemes requeridos por el SDK.
3. Configura `ApplicationDelegate` de Facebook en App lifecycle (AppDelegate/SceneDelegate segun arquitectura).

Permisos recomendados:

- `public_profile`
- `email`

---

## 5) Obtener token de Facebook en iOS

Ejemplo simplificado con `LoginManager`:

```swift
import FacebookLogin

func loginWithFacebook(from viewController: UIViewController) {
    let manager = LoginManager()
    manager.logIn(permissions: ["public_profile", "email"], from: viewController) { result, error in
        if let error = error {
            print("Facebook login error: \(error)")
            return
        }

        guard let result = result, !result.isCancelled else {
            print("Facebook login cancelado")
            return
        }

        guard let token = AccessToken.current?.tokenString else {
            print("No se obtuvo access token")
            return
        }

        Task {
            do {
                let response = try await AuthService.shared.loginWithFacebook(token: token)
                SessionStore.shared.save(response: response)
            } catch {
                print("Backend login error: \(error)")
            }
        }
    }
}
```

---

## 6) Llamar al backend (`/wind/auth/facebook/`)

### Request JSON

```json
{
  "access_token": "<FACEBOOK_ACCESS_TOKEN>"
}
```

### Modelos Swift sugeridos

```swift
struct FacebookLoginRequest: Encodable {
    let access_token: String
}

struct UserDTO: Decodable {
    let pk: Int
    let email: String
    let first_name: String
    let last_name: String
    let subscriber_code: String?
}

struct PanaccessCredentialsDTO: Decodable {
    let login1: String?
    let password: String?
    let login2: String?
    let subscriberCode: String?
}

struct FacebookLoginResponse: Decodable {
    let access: String
    let refresh: String?
    let user: UserDTO
    let panaccess_credentials: PanaccessCredentialsDTO?
}
```

### Servicio con URLSession

```swift
final class AuthService {
    static let shared = AuthService()
    private init() {}

    func loginWithFacebook(token: String) async throws -> FacebookLoginResponse {
        guard let url = URL(string: "https://TU_BACKEND/wind/auth/facebook/") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(FacebookLoginRequest(access_token: token))

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw NSError(domain: "AuthService", code: http.statusCode, userInfo: [
                NSLocalizedDescriptionKey: "HTTP \(http.statusCode): \(body)"
            ])
        }

        return try JSONDecoder().decode(FacebookLoginResponse.self, from: data)
    }
}
```

---

## 7) Respuesta esperada del backend

El backend retorna:

- `access`
- `refresh` (puede ser vacio en la config actual)
- `user` con `subscriber_code`
- `panaccess_credentials` con login para PanAccess

---

## 8) Que guardar en iOS

Guardar de forma segura:

- `access`
- `refresh` (si aplica)
- `user` (`email`, `subscriber_code`)
- `panaccess_credentials`

Recomendado:

- Guardar secretos en **Keychain**.
- Evitar logs con credenciales en texto plano.

---

## 9) Uso posterior

### Llamadas a API Django

Enviar:

```http
Authorization: Bearer <access>
```

### Integraciones PanAccess

Usar `panaccess_credentials.login1/login2/password` en el flujo que requiera session/login PanAccess.

---

## 10) Manejo de errores recomendado

- Si falla el login con Facebook:
  - Mostrar mensaje al usuario.
  - Permitir reintento.
- Si falla backend:
  - Mostrar error amigable.
  - Registrar HTTP code y body sin secretos.
- Si `panaccess_credentials` viene `nil`:
  - Bloquear temporalmente funciones dependientes de PanAccess.

---

## 11) Checklist QA iOS

- [ ] Login Facebook exitoso retorna `access` y `user`.
- [ ] `panaccess_credentials` llega completa.
- [ ] Requests a API usan `Authorization: Bearer`.
- [ ] Sesion persiste tras reiniciar app.
- [ ] Logout elimina tokens/credenciales del Keychain.

