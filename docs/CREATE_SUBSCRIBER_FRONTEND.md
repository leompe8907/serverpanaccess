# Guía de Uso: Crear Suscriptor con Contactos

## Descripción

El endpoint `create-subscriber` permite crear un nuevo suscriptor en PanAccess con todos sus datos en una sola llamada. El backend se encarga automáticamente de:

1. Crear el suscriptor con nombre y apellido
2. Agregar el email como contacto (si se proporciona)
3. Agregar el teléfono como contacto (si se proporciona)

Todo esto se realiza en una **única petición HTTP**, sin necesidad de hacer múltiples llamadas desde el frontend.

## Endpoint

```
POST /wind/create-subscriber/
```

## Autenticación

No requiere autenticación (permission: `AllowAny`)

## Request Body

### Campos Requeridos

- `firstName` (string, max 100 caracteres): Nombre del suscriptor
- `lastName` (string, max 100 caracteres): Apellido del suscriptor

### Campos Opcionales

- `email` (string, formato email): Email del suscriptor
- `phone` (string, max 50 caracteres): Teléfono del suscriptor
- `hcId` (string, max 100 caracteres): ID del Health Center
- `comment` (string): Comentario adicional
- `countryCode` (string, default: "DO"): Código de país (ISO 2 letras)
- `regionId` (integer): ID de la región
- `technicalNotes` (string): Notas técnicas
- `caf` (string): Campo CAF

## Ejemplo de Request

```json
{
  "firstName": "Juan",
  "lastName": "Pérez",
  "email": "juan.perez@example.com",
  "phone": "+1-234-567-8900",
  "comment": "Cliente nuevo",
  "countryCode": "DO",
  "regionId": 588
}
```

## Response

### Respuesta Exitosa (201 Created)

```json
{
  "success": true,
  "message": "Suscriptor creado exitosamente",
  "subscriber_code": "AUTO12345",
  "data": {
    "code": "AUTO12345",
    "supervisor": "AUTOMATICO",
    "lastName": "Pérez",
    "firstName": "Juan",
    "hcId": null,
    "comment": "Cliente nuevo"
  },
  "contacts_added": [
    {
      "type": "email",
      "value": "juan.perez@example.com"
    },
    {
      "type": "phone",
      "value": "+1-234-567-8900"
    }
  ]
}
```

### Respuesta con Errores en Contactos

Si el suscriptor se crea exitosamente pero hay problemas al agregar contactos:

```json
{
  "success": true,
  "message": "Suscriptor creado exitosamente. Algunos contactos no pudieron agregarse.",
  "subscriber_code": "AUTO12345",
  "data": {
    "code": "AUTO12345",
    "supervisor": "AUTOMATICO",
    "lastName": "Pérez",
    "firstName": "Juan",
    "hcId": null,
    "comment": "Cliente nuevo"
  },
  "contacts_added": [
    {
      "type": "email",
      "value": "juan.perez@example.com"
    }
  ],
  "contacts_errors": [
    {
      "type": "phone",
      "error": "Error al agregar teléfono: Formato inválido"
    }
  ]
}
```

### Respuesta de Error (400 Bad Request)

```json
{
  "success": false,
  "message": "Datos inválidos",
  "errors": {
    "firstName": ["Este campo es requerido."],
    "email": ["Introduzca una dirección de correo electrónico válida."]
  }
}
```

### Respuesta de Error del Servidor (500 Internal Server Error)

```json
{
  "success": false,
  "error_type": "PanAccessException",
  "message": "Error al crear suscriptor: Código ya existe"
}
```

## Implementación en el Frontend

### Ejemplo con JavaScript/Fetch

```javascript
async function createSubscriber(formData) {
  try {
    const response = await fetch('/wind/create-subscriber/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        firstName: formData.firstName,
        lastName: formData.lastName,
        email: formData.email || null,
        phone: formData.phone || null,
        comment: formData.comment || null,
        countryCode: formData.countryCode || 'DO',
        regionId: formData.regionId || null
      })
    });

    const data = await response.json();

    if (data.success) {
      console.log('Suscriptor creado:', data.subscriber_code);
      
      // Verificar si se agregaron contactos
      if (data.contacts_added && data.contacts_added.length > 0) {
        console.log('Contactos agregados:', data.contacts_added);
      }
      
      // Verificar si hubo errores al agregar contactos
      if (data.contacts_errors && data.contacts_errors.length > 0) {
        console.warn('Errores al agregar contactos:', data.contacts_errors);
        // Mostrar advertencia al usuario pero no fallar
        alert('Suscriptor creado, pero algunos contactos no pudieron agregarse');
      }
      
      return data;
    } else {
      throw new Error(data.message || 'Error al crear suscriptor');
    }
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
}
```

### Ejemplo con React

```jsx
import { useState } from 'react';

function CreateSubscriberForm() {
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    comment: '',
    countryCode: 'DO'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch('/wind/create-subscriber/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          firstName: formData.firstName,
          lastName: formData.lastName,
          email: formData.email || null,
          phone: formData.phone || null,
          comment: formData.comment || null,
          countryCode: formData.countryCode
        })
      });

      const data = await response.json();

      if (data.success) {
        setSuccess({
          subscriberCode: data.subscriber_code,
          contactsAdded: data.contacts_added || [],
          contactsErrors: data.contacts_errors || []
        });
        
        // Resetear formulario
        setFormData({
          firstName: '',
          lastName: '',
          email: '',
          phone: '',
          comment: '',
          countryCode: 'DO'
        });
      } else {
        setError(data.message || 'Error al crear suscriptor');
      }
    } catch (err) {
      setError('Error de conexión: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>
          Nombre: *
          <input
            type="text"
            value={formData.firstName}
            onChange={(e) => setFormData({...formData, firstName: e.target.value})}
            required
          />
        </label>
      </div>

      <div>
        <label>
          Apellido: *
          <input
            type="text"
            value={formData.lastName}
            onChange={(e) => setFormData({...formData, lastName: e.target.value})}
            required
          />
        </label>
      </div>

      <div>
        <label>
          Email:
          <input
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({...formData, email: e.target.value})}
          />
        </label>
      </div>

      <div>
        <label>
          Teléfono:
          <input
            type="tel"
            value={formData.phone}
            onChange={(e) => setFormData({...formData, phone: e.target.value})}
          />
        </label>
      </div>

      <div>
        <label>
          Comentario:
          <textarea
            value={formData.comment}
            onChange={(e) => setFormData({...formData, comment: e.target.value})}
          />
        </label>
      </div>

      <button type="submit" disabled={loading}>
        {loading ? 'Creando...' : 'Crear Suscriptor'}
      </button>

      {error && <div className="error">{error}</div>}
      
      {success && (
        <div className="success">
          <p>Suscriptor creado exitosamente: {success.subscriberCode}</p>
          {success.contactsAdded.length > 0 && (
            <p>Contactos agregados: {success.contactsAdded.map(c => c.value).join(', ')}</p>
          )}
          {success.contactsErrors.length > 0 && (
            <p className="warning">
              Advertencia: Algunos contactos no pudieron agregarse
            </p>
          )}
        </div>
      )}
    </form>
  );
}

export default CreateSubscriberForm;
```

### Ejemplo con Axios

```javascript
import axios from 'axios';

async function createSubscriber(subscriberData) {
  try {
    const response = await axios.post('/wind/create-subscriber/', {
      firstName: subscriberData.firstName,
      lastName: subscriberData.lastName,
      email: subscriberData.email || null,
      phone: subscriberData.phone || null,
      comment: subscriberData.comment || null,
      countryCode: subscriberData.countryCode || 'DO',
      regionId: subscriberData.regionId || null
    });

    if (response.data.success) {
      return {
        subscriberCode: response.data.subscriber_code,
        contactsAdded: response.data.contacts_added || [],
        contactsErrors: response.data.contacts_errors || []
      };
    } else {
      throw new Error(response.data.message);
    }
  } catch (error) {
    if (error.response) {
      // Error de respuesta del servidor
      throw new Error(error.response.data.message || 'Error al crear suscriptor');
    } else if (error.request) {
      // Error de red
      throw new Error('Error de conexión con el servidor');
    } else {
      // Otro error
      throw error;
    }
  }
}
```

## Notas Importantes

1. **Campos Opcionales**: Los campos `email` y `phone` son completamente opcionales. Puedes enviar solo uno, ambos, o ninguno.

2. **Manejo de Errores en Contactos**: Si el suscriptor se crea exitosamente pero falla al agregar un contacto, la respuesta seguirá teniendo `success: true`, pero incluirá un array `contacts_errors` con los detalles. El suscriptor ya estará creado en PanAccess.

3. **Validación de Email**: El backend valida automáticamente el formato del email si se proporciona. Si el email no es válido, recibirás un error 400 antes de intentar crear el suscriptor.

4. **Código del Suscriptor**: El código se genera automáticamente con formato `AUTO` + número. No necesitas proporcionarlo.

5. **Supervisor**: Se fija automáticamente a "AUTOMATICO". No es necesario enviarlo.

## Flujo de Trabajo Recomendado

1. El usuario completa el formulario con todos los datos (nombre, apellido, email, teléfono, etc.)
2. Al enviar, se hace una única petición POST al endpoint
3. El backend:
   - Crea el suscriptor
   - Agrega el email (si se proporcionó)
   - Agrega el teléfono (si se proporcionó)
4. El frontend muestra el resultado:
   - Si todo fue exitoso: mostrar mensaje de éxito con el código del suscriptor
   - Si hubo errores en contactos: mostrar advertencia pero confirmar que el suscriptor fue creado
   - Si hubo error en la creación: mostrar error completo

## Preguntas Frecuentes

**P: ¿Puedo crear un suscriptor sin email ni teléfono?**
R: Sí, ambos campos son opcionales. Solo necesitas proporcionar `firstName` y `lastName`.

**P: ¿Qué pasa si el email es inválido?**
R: Recibirás un error 400 antes de intentar crear el suscriptor. El email debe tener un formato válido.

**P: ¿Qué pasa si falla agregar un contacto pero el suscriptor ya se creó?**
R: El suscriptor quedará creado en PanAccess. La respuesta incluirá `success: true` pero también `contacts_errors` con los detalles del error. Debes informar al usuario pero no es un error crítico.

**P: ¿Puedo agregar más contactos después de crear el suscriptor?**
R: Sí, pero necesitarías crear un endpoint separado para eso. Por ahora, este endpoint solo maneja email y teléfono durante la creación.
