"""
Utilidades para generar códigos únicos de suscriptores.
"""
import logging
from wind.models import ListOfSubscriber
from wind.services import get_panaccess
from wind.exceptions import PanAccessException

logger = logging.getLogger(__name__)


def generate_unique_subscriber_code(prefix='AUTO', max_attempts=10):
    """
    Genera un código único de suscriptor con formato AUTO + número secuencial.
    
    Formato: AUTO + NÚMERO (ej: AUTO1, AUTO2, AUTO100)
    
    Args:
        prefix: Prefijo para el código (default: 'AUTO')
        max_attempts: Número máximo de intentos para generar un código único
    
    Returns:
        Código único de suscriptor
    
    Raises:
        Exception: Si no se puede generar un código único después de max_attempts
    """
    # Obtener el último número usado
    last_code = ListOfSubscriber.objects.filter(
        code__startswith=prefix
    ).order_by('-code').first()
    
    if last_code:
        # Extraer el número del último código
        try:
            last_number = int(last_code.code.replace(prefix, ''))
            next_number = last_number + 1
        except (ValueError, AttributeError):
            # Si no se puede extraer el número, empezar desde 1
            next_number = 1
    else:
        # Si no hay códigos previos, empezar desde 1
        next_number = 1
    
    # Intentar generar un código único
    for attempt in range(max_attempts):
        code = f"{prefix}{next_number}"
        
        # Verificar que no exista en la base de datos local
        if not ListOfSubscriber.objects.filter(code=code).exists():
            # Verificar que no exista en PanAccess (opcional pero recomendado)
            if not _code_exists_in_panaccess(code):
                logger.info(f"Código único generado: {code}")
                return code
            else:
                logger.warning(f"Código {code} existe en PanAccess, intentando siguiente...")
        
        # Si existe, intentar con el siguiente número
        next_number += 1
    
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
            response = panaccess.call('getSubscriber', {'code': code})
            
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

