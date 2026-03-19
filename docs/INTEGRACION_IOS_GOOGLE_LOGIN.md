# Integracion iOS: Login Social con Google

Guia para integrar en iOS el login con Google y autenticarse contra el backend de este proyecto.

---

## 1) Objetivo del flujo

La app iOS debe:

1. Obtener un **ID Token** de Google.
2. Enviarlo al backend:
   - `POST /wind/auth/google/`
3. Recibir tokens de API y credenciales PanAccess.
4. Guardar de forma segura los datos de sesion.

---

## 2) Requisitos previos

- Proyecto iOS en Swift.
- Google Cloud OAuth configurado.
- `GoogleService-Info.plist` y URL schemes correctos.
- Backend accesible desde el dispositivo.

Endpoint principal:

- `https://TU_BACKEND/wind/auth/google/`

---

## 3) Dependencia Google Sign-In

Con Swift Package Manager:

- Package: `https://github.com/google/GoogleSignIn-iOS`

---

## 4) Configurar Google Sign-In en iOS

Ejemplo simplificado:

```swift
import GoogleSignIn
import UIKit

func signInWithGoogle(from viewController: UIViewController) {
    guard let clientID = Bundle.main.object(forInfoDictionaryKey: "GIDClientID") as? String else {
        return
    }

    let config = GIDConfiguration(clientID: clientID)
    GIDSignIn.sharedInstance.configuration = config

    GIDSignIn.sharedInstance.signIn(withPresenting: viewController) { result, error in
        if let error = error {
            print("Google Sign-In error: \(error)")
            return
        }

        guard
            let user = result?.user,
            let idToken = user.idToken?.tokenString
        else {
            return
        }

        Task {
            do {
                let response = try await AuthService.shared.loginWithGoogle(idToken: idToken)
                SessionStore.shared.save(response: response)
            } catch {
                print("Backend login error: \(error)")
            }
        }
    }
}
```

---

## 5) Llamada al backend (`/wind/auth/google/`)

### Request JSON

El backend actual espera:

```json
{
  "access_token": "<GOOGLE_ID_TOKEN>"
}
```

### Modelos Swift sugeridos

```swift
struct GoogleLoginRequest: Encodable {
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

struct GoogleLoginResponse: Decodable {
    let access: String
    let refresh: String?
    let user: UserDTO
    let panaccess_credentials: PanaccessCredentialsDTO?
    let subscriber_provisioning: [String: String]?
}
```

### Servicio con URLSession

```swift
final class AuthService {
    static let shared = AuthService()
    private init() {}

    func loginWithGoogle(idToken: String) async throws -> GoogleLoginResponse {
        guard let url = URL(string: "https://TU_BACKEND/wind/auth/google/") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            GoogleLoginRequest(access_token: idToken)
        )

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

        return try JSONDecoder().decode(GoogleLoginResponse.self, from: data)
    }
}
```

---

## 6) Que guardar en iOS

Guardar de forma segura:

- `access`
- `refresh` (si viene)
- `user` (`pk`, `email`, `subscriber_code`)
- `panaccess_credentials`

Recomendado:

- Tokens/credenciales en **Keychain**.
- Evitar imprimir contrasenas en logs.

---

## 7) Uso posterior en app iOS

### Llamadas autenticadas al backend

Agregar header:

```http
Authorization: Bearer <access>
```

### Integraciones que dependan de PanAccess

Tomar `panaccess_credentials` y usarlas segun el flujo mobile definido por negocio.

---

## 8) Manejo de errores recomendado

- Si falla Google Sign-In: mostrar mensaje de autenticacion.
- Si falla backend (`/wind/auth/google/`):
  - Mostrar error amigable.
  - Registrar codigo HTTP y body sin secretos.
  - Permitir reintento de login.
- Si `panaccess_credentials` viene `nil`, restringir funciones que dependan de PanAccess.

---

## 9) Comportamiento funcional esperado del backend

- Si el correo ya existe: devuelve credenciales existentes.
- Si no existe: crea suscriptor, ejecuta flujo de license block, asigna SN, aplica producto y devuelve credenciales.

iOS consume siempre el mismo endpoint y misma estructura base de respuesta.

---

## 10) Checklist rapido para QA iOS

- [ ] Login Google devuelve `access` y `user`.
- [ ] `panaccess_credentials` llega correctamente en escenario valido.
- [ ] Llamadas a API usan `Authorization: Bearer`.
- [ ] Sesion se restaura tras reinicio de app.
- [ ] Logout limpia Keychain y estado local.

