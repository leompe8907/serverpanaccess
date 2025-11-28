"""
Funciones de autenticación con PanAccess.

Este módulo proporciona funciones para autenticarse con la API de PanAccess
y obtener un sessionId para realizar llamadas posteriores.
"""
import hashlib
import requests
from urllib.parse import urlencode

from appConfig import PanaccessConfig
from wind.exceptions import (
    PanAccessAuthenticationError,
    PanAccessConnectionError,
    PanAccessTimeoutError,
    PanAccessAPIError
)


def hash_password(password: str, salt: str = None) -> str:
    """
    Genera un hash MD5 del password con sal.
    
    Uso específico requerido por PanAccess. No recomendado para otros 
    contextos de seguridad.
    
    Args:
        password: Contraseña en texto plano
        salt: Salt para el hash (por defecto usa el de la configuración)
    
    Returns:
        Hash MD5 hexadecimal del password + salt
    """
    if salt is None:
        salt = PanaccessConfig.SALT
    
    return hashlib.md5((password + salt).encode()).hexdigest()


def login() -> str:
    """
    Realiza login en PanAccess y retorna el sessionId.
    
    Autentica usando las credenciales configuradas en PanaccessConfig
    y retorna el sessionId encriptado para usar en llamadas posteriores.
    
    Nota: No hacer más de 20 logins en 5 minutos o se activará el rate limiter.
    
    Returns:
        sessionId encriptado para usar en llamadas posteriores
    
    Raises:
        PanAccessAuthenticationError: Si las credenciales son inválidas o 
            el API key está deshabilitado
        PanAccessConnectionError: Si hay problemas de conexión
        PanAccessTimeoutError: Si la petición excede el timeout
        PanAccessAPIError: Si hay un error genérico de la API
    """
    # Validar configuración
    PanaccessConfig.validate()
    
    username = PanaccessConfig.USERNAME
    password = PanaccessConfig.PASSWORD
    api_token = PanaccessConfig.API_TOKEN
    base_url = PanaccessConfig.PANACCESS
    
    if not username or not password or not api_token:
        raise PanAccessAuthenticationError(
            "Faltan credenciales de PanAccess en la configuración. "
            "Verifica las variables de entorno: username, password, api_token"
        )
    
    # Hashear contraseña
    hashed_password = hash_password(password)
    
    # Preparar payload
    payload = {
        "username": username,
        "password": hashed_password,
        "apiToken": api_token
    }
    
    # URL del endpoint
    url = f"{base_url}?f=login&requestMode=function"
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    param_string = urlencode(payload)
    
    try:
        response = requests.post(
            url,
            data=param_string,
            headers=headers,
            timeout=30
        )
        
        # Verificar status code
        if response.status_code != 200:
            raise PanAccessAPIError(
                f"Respuesta inesperada del servidor PanAccess: {response.status_code}",
                status_code=response.status_code
            )
        
        # Parsear respuesta JSON
        try:
            json_response = response.json()
        except ValueError as e:
            raise PanAccessAPIError(
                f"Respuesta inválida del servidor PanAccess: {response.text}",
                status_code=response.status_code
            )
        
        # Verificar si el login fue exitoso
        if not json_response.get("success"):
            error_message = json_response.get("errorMessage", "Login fallido sin mensaje explícito")
            
            # Si retorna 'false' como string, es error de autenticación
            if json_response.get("answer") == "false" or error_message:
                raise PanAccessAuthenticationError(
                    f"Error de autenticación: {error_message}"
                )
            
            raise PanAccessAPIError(
                f"Error en la respuesta de PanAccess: {error_message}",
                status_code=response.status_code
            )
        
        # Extraer sessionId
        session_id = json_response.get("answer")
        
        if not session_id:
            raise PanAccessAPIError(
                "Login exitoso pero no se recibió sessionId en la respuesta"
            )
        
        return session_id
        
    except requests.exceptions.Timeout:
        raise PanAccessTimeoutError(
            "Timeout al intentar conectarse con PanAccess. "
            "El servidor no respondió en 30 segundos."
        )
    except requests.exceptions.ConnectionError as e:
        raise PanAccessConnectionError(
            f"Error de conexión con PanAccess: {str(e)}"
        )
    except (PanAccessAuthenticationError, PanAccessAPIError, PanAccessTimeoutError, PanAccessConnectionError):
        # Re-lanzar nuestras excepciones personalizadas
        raise
    except Exception as e:
        raise PanAccessAPIError(
            f"Error inesperado al intentar login con PanAccess: {str(e)}"
        )

