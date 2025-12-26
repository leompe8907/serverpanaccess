"""
Utilidades para generar códigos únicos de suscriptores.
"""
import random
import string
import logging
from datetime import datetime
from wind.models import ListOfSubscriber
from wind.services import get_panaccess
from wind.exceptions import PanAccessException

logger = logging.getLogger(__name__)


def generate_unique_subscriber_code(prefix='SUB', max_attempts=10):
    """
    Genera un código único de suscriptor.
    
    Formato: PREFIX + TIMESTAMP + RANDOM (ej: SUB20251226123456789ABC)
    
    Args:
        prefix: Prefijo para el código (default: 'SUB')
        max_attempts: Número máximo de intentos para generar un código único
    
    Returns:
        Código único de suscriptor
    
    Raises:
        Exception: Si no se puede generar un código único después de max_attempts
    """
    for attempt in range(max_attempts):
        # Generar timestamp (año + mes + día + hora + minuto + segundo)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Generar 3 caracteres aleatorios (letras mayúsculas y números)
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
        
        # Combinar: PREFIX + TIMESTAMP + RANDOM
        code = f"{prefix}{timestamp}{random_suffix}"
        
        # Verificar que no exista en la base de datos local
        if not ListOfSubscriber.objects.filter(code=code).exists():
            # Verificar que no exista en PanAccess (opcional pero recomendado)
            if not _code_exists_in_panaccess(code):
                logger.info(f"Código único generado: {code}")
                return code
            else:
                logger.warning(f"Código {code} existe en PanAccess, intentando otro...")
        else:
            logger.warning(f"Código {code} existe en BD local, intentando otro...")
    
    # Si llegamos aquí, no se pudo generar un código único
    raise Exception(f"No se pudo generar un código único después de {max_attempts} intentos")


def _code_exists_in_panaccess(code):
    """
    Verifica si un código de suscriptor existe en PanAccess.
    
    Args:
        code: Código del suscriptor a verificar
    
    Returns:
        True si existe, False si no existe o hay error
    """
    try:
        panaccess = get_panaccess()
        
        # Intentar obtener el suscriptor usando getSubscriber o similar
        # Si la función existe, usarla; si no, asumir que no existe
        try:
            # Nota: Esta función puede no existir en todas las versiones de PanAccess
            # Si no existe, simplemente retornamos False (asumimos que no existe)
            response = panaccess.call('getSubscriber', {'subscriberCode': code})
            
            if response.get('success'):
                # Si la respuesta es exitosa, el suscriptor existe
                return True
            else:
                # Si hay error, probablemente no existe
                return False
        except PanAccessException:
            # Si hay excepción, asumimos que no existe (o la función no está disponible)
            return False
        except Exception:
            # Cualquier otro error, asumimos que no existe
            return False
            
    except Exception as e:
        logger.warning(f"Error verificando código en PanAccess: {str(e)}. Asumiendo que no existe.")
        return False


def validate_subscriber_code_uniqueness(code):
    """
    Valida que un código de suscriptor sea único.
    
    Verifica tanto en la base de datos local como en PanAccess.
    
    Args:
        code: Código del suscriptor a validar
    
    Returns:
        True si es único, False si ya existe
    """
    # Verificar en BD local
    if ListOfSubscriber.objects.filter(code=code).exists():
        return False
    
    # Verificar en PanAccess
    if _code_exists_in_panaccess(code):
        return False
    
    return True

