"""
Cliente para interactuar con la API de PanAccess.

Este módulo proporciona una clase cliente para realizar llamadas a la API
de PanAccess, manejando automáticamente la autenticación y el sessionId.
"""
import logging
import requests
from urllib.parse import urlencode
from typing import Dict, Any, Optional

from appConfig import PanaccessConfig
from wind.utils.panaccess_auth import login, logged_in
from wind.exceptions import (
    PanAccessException,
    PanAccessConnectionError,
    PanAccessTimeoutError,
    PanAccessAPIError,
    PanAccessSessionError
)

logger = logging.getLogger(__name__)


class PanAccessClient:
    """
    Cliente para interactuar con la API de PanAccess.
    
    Maneja la autenticación y el sessionId automáticamente.
    Proporciona métodos para realizar llamadas a las funciones de la API.
    """
    
    def __init__(self, base_url: str = None):
        """
        Inicializa el cliente de PanAccess.
        
        Args:
            base_url: URL base de PanAccess (por defecto usa la de la configuración)
        """
        PanaccessConfig.validate()
        self.base_url = base_url or PanaccessConfig.PANACCESS
        self.session_id: Optional[str] = None
    
    def authenticate(self) -> str:
        """
        Realiza la autenticación con PanAccess y guarda el sessionId.
        
        Returns:
            sessionId obtenido de PanAccess
        
        Raises:
            PanAccessException: Si hay algún error en la autenticación
        """
        self.session_id = login()
        return self.session_id
    
    def _ensure_valid_session(self):
        """
        Asegura que haya una sesión válida.
        
        Si no hay sessionId, realiza un nuevo login automáticamente.
        NO valida la sesión antes de cada llamada para evitar logins innecesarios.
        La validación periódica del singleton se encarga de mantener la sesión activa.
        """
        # Si no hay sessionId, autenticar
        if not self.session_id:
            self.authenticate()
            return
        
        # NO validar la sesión aquí - confiar en la validación periódica del singleton
        # Esto evita logins innecesarios cuando la sesión es válida pero hay errores
        # temporales o de permisos en la validación
        # La validación periódica en background se encargará de refrescar si es necesario
    
    def call(self, func_name: str, parameters: Dict[str, Any] = None, timeout: int = 60) -> Dict[str, Any]:
        """
        Llama a una función remota del API PanAccess.
        
        Si no hay sessionId o si está caducado, intenta autenticarse/refrescar
        automáticamente antes de realizar la llamada (excepto para la función 'login').
        
        Args:
            func_name: Nombre de la función a llamar (ej: 'cvGetSubscriber')
            parameters: Diccionario con los parámetros de la función
            timeout: Timeout en segundos para la conexión (default: 60)
        
        Returns:
            Diccionario con la respuesta de la API
        
        Raises:
            PanAccessException: Si hay algún error en la llamada
        """
        if parameters is None:
            parameters = {}
        
        # Asegurar sesión válida antes de hacer la llamada (excepto para login)
        if func_name != 'login' and func_name != 'cvLoggedIn':
            self._ensure_valid_session()
        
        # Preparar parámetros para logging (ocultar sessionId por seguridad)
        log_parameters = parameters.copy()
        if 'sessionId' in log_parameters:
            session_id_value = log_parameters['sessionId']
            if session_id_value:
                log_parameters['sessionId'] = f"{session_id_value[:20]}..." if len(str(session_id_value)) > 20 else "[REDACTED]"
        
        # Agregar sessionId a los parámetros si existe y no es login
        if self.session_id and func_name != 'login' and func_name != 'cvLoggedIn':
            parameters['sessionId'] = self.session_id
        
        # Construir URL
        url = f"{self.base_url}?f={func_name}&requestMode=function"
        
        # Preparar headers y datos
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        param_string = urlencode(parameters)
        
        # Log de la petición
        logger.info(f"📞 [call] Llamando función '{func_name}' - URL: {url}")
        logger.info(f"📞 [call] Parámetros: {log_parameters}")
        logger.debug(f"📞 [call] Headers: {headers}")
        logger.debug(f"📞 [call] Timeout: {timeout}s")
        
        try:
            response = requests.post(
                url,
                data=param_string,
                headers=headers,
                timeout=timeout
            )
            
            # Log del status code
            logger.info(f"📡 [call] Respuesta recibida para '{func_name}' - Status Code: {response.status_code}")
            
            response.raise_for_status()
            
            # Parsear respuesta JSON
            try:
                json_response = response.json()
                logger.info(f"📦 [call] Respuesta JSON completa para '{func_name}': {json_response}")
            except ValueError as e:
                logger.error(f"❌ [call] Error al parsear JSON para '{func_name}': {str(e)}")
                logger.error(f"❌ [call] Respuesta raw: {response.text}")
                raise PanAccessAPIError(
                    f"Respuesta inválida del servidor PanAccess: {response.text}",
                    status_code=response.status_code
                )
            
            # Verificar si hay error en la respuesta
            success = json_response.get("success")
            logger.info(f"✅ [call] Campo 'success' para '{func_name}': {success}")
            
            if not success:
                error_message = json_response.get("errorMessage", "Error desconocido")
                answer = json_response.get("answer")
                logger.error(f"❌ [call] Llamada a '{func_name}' falló - Error: {error_message}")
                logger.error(f"❌ [call] Campo 'answer' para '{func_name}': {answer}")
                
                # Si el error es de sesión, limpiar sessionId
                if "session" in error_message.lower() or "logged" in error_message.lower():
                    logger.warning(f"⚠️ [call] Error de sesión detectado para '{func_name}', limpiando sessionId")
                    self.session_id = None
                    raise PanAccessSessionError(
                        f"Error de sesión: {error_message}"
                    )
                
                raise PanAccessAPIError(
                    f"Error en la respuesta de PanAccess: {error_message}",
                    status_code=response.status_code
                )
            
            # Log del resultado exitoso
            answer = json_response.get("answer")
            logger.info(f"✅ [call] Llamada a '{func_name}' exitosa")
            logger.info(f"📋 [call] Campo 'answer' para '{func_name}': {answer} (tipo: {type(answer).__name__})")
            
            return json_response
            
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ [call] Timeout al llamar a '{func_name}' ({timeout} segundos)")
            raise PanAccessTimeoutError(
                f"Timeout al llamar a {func_name}. "
                f"El servidor no respondió en {timeout} segundos."
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"🔌 [call] Error de conexión al llamar a '{func_name}': {str(e)}")
            raise PanAccessConnectionError(
                f"Error de conexión con PanAccess: {str(e)}"
            )
        except requests.exceptions.HTTPError as e:
            status_code = response.status_code if 'response' in locals() else None
            logger.error(f"❌ [call] Error HTTP al llamar a '{func_name}': {str(e)} (Status: {status_code})")
            if 'response' in locals():
                logger.error(f"❌ [call] Respuesta completa: {response.text}")
            raise PanAccessAPIError(
                f"Error HTTP al llamar a {func_name}: {str(e)}",
                status_code=status_code
            )
        except (PanAccessException, PanAccessAPIError, PanAccessTimeoutError, PanAccessConnectionError, PanAccessSessionError):
            # Re-lanzar nuestras excepciones personalizadas
            raise
        except Exception as e:
            logger.error(f"💥 [call] Error inesperado al llamar a '{func_name}': {str(e)}", exc_info=True)
            raise PanAccessAPIError(
                f"Error inesperado al llamar a {func_name}: {str(e)}"
            )
    
    def logout(self) -> bool:
        """
        Cierra la sesión actual en PanAccess.
        
        Returns:
            True si el logout fue exitoso, False en caso contrario
        
        Raises:
            PanAccessException: Si hay algún error al cerrar sesión
        """
        if not self.session_id:
            return True  # Ya no hay sesión activa
        
        try:
            result = self.call("cvLogout", {})
            self.session_id = None
            return result.get("success", False)
        except PanAccessException:
            # Limpiar sessionId incluso si hay error
            self.session_id = None
            raise
    
    def is_authenticated(self) -> bool:
        """
        Verifica si hay una sesión activa.
        
        Returns:
            True si hay sessionId, False en caso contrario
        """
        return self.session_id is not None
    
    def check_session(self) -> bool:
        """
        Verifica si la sesión actual sigue siendo válida.
        
        Returns:
            True si la sesión es válida, False si está caducada
        
        Raises:
            PanAccessException: Si hay algún error al verificar la sesión
        """
        if not self.session_id:
            return False
        
        try:
            return logged_in(self.session_id)
        except PanAccessException:
            # Si hay error al verificar, asumimos que la sesión no es válida
            self.session_id = None
            return False

