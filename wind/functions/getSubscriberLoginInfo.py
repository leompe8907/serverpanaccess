"""
Funciones para obtener y sincronizar información de login de suscriptores desde PanAccess.
"""
import logging
from django.db import transaction
from wind.models import SubscriberLoginInfo, ListOfSubscriber
from wind.serializers import SubscriberLoginInfoSerializer

from wind.services import get_panaccess
from wind.exceptions import PanAccessException

logger = logging.getLogger(__name__)


def DataBaseEmpty():
    """
    Verifica si la tabla SubscriberLoginInfo está vacía.
    """
    logger.info("Verificando si la base de datos de login info está vacía...")
    return not SubscriberLoginInfo.objects.exists()


def store_login_info_in_chunks(login_info_list, chunk_size=100):
    """
    Almacena información de login en la base de datos en bloques para mejorar el rendimiento.
    """
    total = len(login_info_list)
    logger.info(f"Almacenando {total} registros de login info en chunks de {chunk_size}...")
    
    for i in range(0, total, chunk_size):
        chunk = login_info_list[i:i + chunk_size]
        try:
            registros = [SubscriberLoginInfo(**item) for item in chunk]
            SubscriberLoginInfo.objects.bulk_create(registros, ignore_conflicts=True)
            logger.info(f"Chunk {i//chunk_size + 1}: insertados {len(registros)} registros de login info")
        except Exception as e:
            logger.error(f"Error insertando chunk desde {i} hasta {i+chunk_size}: {str(e)}")


def CallGetSubscriberLoginInfo(session_id=None, subscriber_code=None):
    """
    Llama a la API de Panaccess para obtener la información de login de un suscriptor.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        subscriber_code: Código del suscriptor
    
    Returns:
        Diccionario con la respuesta de PanAccess
    """
    if not subscriber_code:
        raise ValueError("subscriber_code es requerido")
    
    logger.info(f"Llamando API Panaccess GetSubscriberLoginInfo para suscriptor: {subscriber_code}")
    
    try:
        # Usar el singleton de PanAccess
        panaccess = get_panaccess()
        
        # Preparar parámetros
        parameters = {
            'subscriberCode': subscriber_code
        }
        
        # Hacer la llamada usando el singleton
        response = panaccess.call('getSubscriberLoginInfo', parameters)

        if response.get('success'):
            answer = response.get('answer', {})
            # Agregar el subscriberCode a los datos
            if isinstance(answer, dict):
                answer['subscriberCode'] = subscriber_code
            return answer
        else:
            error_message = response.get('errorMessage', 'Error desconocido al obtener login info')
            logger.error(f"Error en respuesta de PanAccess: {error_message}")
            raise PanAccessException(error_message)

    except PanAccessException:
        raise
    except Exception as e:
        logger.error(f"Fallo en la llamada a GetSubscriberLoginInfo: {str(e)}", exc_info=True)
        raise


def fetch_login_info_for_subscriber(session_id=None, subscriber_code=None):
    """
    Obtiene la información de login de un suscriptor específico y la almacena.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        subscriber_code: Código del suscriptor
    
    Returns:
        True si se obtuvo y almacenó correctamente, False en caso contrario
    """
    try:
        result = CallGetSubscriberLoginInfo(session_id, subscriber_code)
        
        if not result:
            logger.warning(f"No se obtuvo información de login para suscriptor {subscriber_code}")
            return False
        
        # Preparar datos para el modelo
        login_data = {
            'subscriberCode': subscriber_code,
            'login1': result.get('login1'),
            'login2': result.get('login2'),
            'additionalLogins': result.get('additionalLogins'),
            'password': result.get('password'),
            'licenses': result.get('licenses'),
        }
        
        # Usar update_or_create para actualizar si existe o crear si no
        SubscriberLoginInfo.objects.update_or_create(
            subscriberCode=subscriber_code,
            defaults=login_data
        )
        
        logger.debug(f"Login info actualizada para suscriptor {subscriber_code}")
        return True
        
    except PanAccessException as e:
        logger.error(f"Error de PanAccess obteniendo login info para {subscriber_code}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado obteniendo login info para {subscriber_code}: {str(e)}", exc_info=True)
        return False


def fetch_all_subscribers_login_info(session_id=None, limit=None):
    """
    Obtiene la información de login de todos los suscriptores en la base de datos.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de suscriptores a procesar (None = todos)
    
    Returns:
        Diccionario con estadísticas del proceso
    """
    logger.info("Iniciando obtención de login info para todos los suscriptores...")
    
    # Obtener todos los suscriptores con código
    subscribers = ListOfSubscriber.objects.exclude(code__isnull=True).exclude(code='')
    if limit:
        subscribers = subscribers[:limit]
    
    total_subscribers = subscribers.count()
    logger.info(f"Procesando login info para {total_subscribers} suscriptores...")
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for subscriber in subscribers:
        subscriber_code = subscriber.code
        if not subscriber_code:
            skipped_count += 1
            continue
        
        try:
            if fetch_login_info_for_subscriber(session_id, subscriber_code):
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Error procesando suscriptor {subscriber_code}: {str(e)}")
            error_count += 1
        
        # Log de progreso cada 100 suscriptores
        processed = success_count + error_count + skipped_count
        if processed % 100 == 0:
            logger.info(f"Progreso: {processed}/{total_subscribers} suscriptores procesados...")
    
    logger.info(f"Proceso completado: {success_count} exitosos, {error_count} errores, {skipped_count} omitidos")
    
    return {
        'total': total_subscribers,
        'success': success_count,
        'errors': error_count,
        'skipped': skipped_count
    }


def sync_subscribers_login_info(session_id=None, limit=None):
    """
    Sincroniza la información de login de todos los suscriptores.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de suscriptores a procesar (None = todos)
    
    Returns:
        Resultado de la sincronización
    """
    logger.info("Iniciando sincronización de login info de suscriptores")
    
    try:
        result = fetch_all_subscribers_login_info(session_id, limit)
        logger.info("✅ Sincronización de login info completada")
        return result
    except PanAccessException as e:
        logger.error(f"Error de PanAccess durante sincronización: {str(e)}")
        raise
    except (ConnectionError, ValueError) as e:
        logger.error(f"Error específico durante sincronización: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        raise

