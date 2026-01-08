import logging
from django.db import transaction
from wind.models import ListOfSubscriber
from wind.serializers import ListOfSubscriberSerializer

from wind.services import get_panaccess
from wind.exceptions import PanAccessException

# Importar función para obtener login info
try:
    from wind.functions.getSubscriberLoginInfo import fetch_login_info_for_subscriber
except ImportError:
    fetch_login_info_for_subscriber = None

logger = logging.getLogger(__name__)


def DataBaseEmpty():
    """
    Verifica si la tabla ListOfSubscriber está vacía.
    """
    return not ListOfSubscriber.objects.exists()

def LastSubscriber():
    """
    Retorna el último suscriptor registrado en la base de datos según el campo 'code'.
    """
    try:
        return ListOfSubscriber.objects.latest('code')
    except ListOfSubscriber.DoesNotExist:
        return None

def store_or_update_subscribers(data_batch):
    """
    Inserta nuevos suscriptores o actualiza los existentes si hay cambios.
    """
    chunk_size = 100
    total_new = 0
    total_invalid = 0

    for i in range(0, len(data_batch), chunk_size):
        chunk = data_batch[i:i + chunk_size]
        codes = {item['code'] for item in chunk if 'code' in item}
        existing = {
            obj.code: obj for obj in ListOfSubscriber.objects.filter(code__in=codes)
        }

        with transaction.atomic():
            new_objects = []
            for item in chunk:
                serializer = ListOfSubscriberSerializer(data=item)
                if not serializer.is_valid():
                    total_invalid += 1
                    continue

                validated = serializer.validated_data
                code = validated.get('code')

                if code in existing:
                    obj = existing[code]
                    changed = False
                    for key, val in validated.items():
                        if getattr(obj, key, None) != val:
                            setattr(obj, key, val)
                            changed = True
                    if changed:
                        obj.save(update_fields=list(validated.keys()))
                else:
                    new_objects.append(ListOfSubscriber(**validated))
                    total_new += 1

            if new_objects:
                ListOfSubscriber.objects.bulk_create(new_objects, ignore_conflicts=True)

    if total_invalid > 0:
        logger.warning(f"Suscriptores inválidos: {total_invalid}")
    return total_new, total_invalid

def fetch_all_subscribers(session_id=None, limit=100):
    """
    Descarga todos los suscriptores desde Panaccess y los almacena en la base de datos.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    logger.info("Descarga completa de suscriptores")
    offset = 0
    all_data = []
    while True:
        result = CallListSubscribers(session_id, offset, limit)
        rows = result.get("rows", [])
        if not rows:
            break
        for row in rows:
            if not isinstance(row.get("cell"), list) or len(row.get("cell", [])) < 12:
                continue
            
            cell = row["cell"]
            all_data.append({
                "id": str(row.get("id")),
                "code": cell[0] if len(cell) > 0 and cell[0] else None,
                "lastName": cell[1] if len(cell) > 1 and cell[1] else None,
                "firstName": cell[2] if len(cell) > 2 and cell[2] else None,
                "smartcards": cell[3] if len(cell) > 3 and cell[3] else [],
                "hcId": cell[4] if len(cell) > 4 and cell[4] else None,
                "hcName": cell[5] if len(cell) > 5 and cell[5] else None,
                "country": cell[6] if len(cell) > 6 and cell[6] else None,
                "city": cell[7] if len(cell) > 7 and cell[7] else None,
                "zip": cell[8] if len(cell) > 8 and cell[8] else None,
                "address": cell[9] if len(cell) > 9 and cell[9] else None,
                "created": cell[10] if len(cell) > 10 and cell[10] else None,
                "modified": cell[11] if len(cell) > 11 and cell[11] else None,
            })
        offset += limit
    
    logger.info(f"Descargados {len(all_data)} suscriptores")
    result = store_all_subscribers_in_chunks(all_data)
    
    if fetch_login_info_for_subscriber:
        login_info_count = 0
        for item in all_data:
            subscriber_code = item.get('code')
            if subscriber_code:
                try:
                    if fetch_login_info_for_subscriber(session_id, subscriber_code):
                        login_info_count += 1
                except Exception:
                    pass
        if login_info_count > 0:
            logger.info(f"Login info obtenida: {login_info_count} suscriptores")
    
    return result

def store_all_subscribers_in_chunks(data_batch, chunk_size=100):
    """
    Almacena suscriptores en la base de datos en bloques para mejorar el rendimiento.
    """
    total = len(data_batch)
    if total == 0:
        return
    logger.info(f"Almacenando {total} suscriptores")
    for i in range(0, total, chunk_size):
        chunk = data_batch[i:i + chunk_size]
        try:
            registros = [ListOfSubscriber(**item) for item in chunk]
            ListOfSubscriber.objects.bulk_create(registros, ignore_conflicts=True)
        except Exception as e:
            logger.error(f"Error insertando chunk {i//chunk_size + 1}: {str(e)}")
    logger.info(f"Almacenados {total} suscriptores")

def download_subscribers_since_last(session_id=None, limit=100):
    """
    Descarga suscriptores nuevos desde el último registrado (modo incremental).
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    last = LastSubscriber()
    if not last:
        return []
    highest_code = last.code
    logger.info(f"Descarga incremental desde código: {highest_code}")
    offset = 0
    new_data = []
    found = False
    while True:
        result = CallListSubscribers(session_id, offset, limit)
        rows = result.get("rows", [])
        if not rows:
            break
        for row in rows:
            if not isinstance(row.get("cell"), list) or len(row.get("cell", [])) < 12:
                continue
            
            cell = row["cell"]
            code = cell[0] if len(cell) > 0 and cell[0] else None
            
            if code == highest_code:
                found = True
                break
            
            new_data.append({
                "id": str(row.get("id")),
                "code": code,
                "lastName": cell[1] if len(cell) > 1 and cell[1] else None,
                "firstName": cell[2] if len(cell) > 2 and cell[2] else None,
                "smartcards": cell[3] if len(cell) > 3 and cell[3] else [],
                "hcId": cell[4] if len(cell) > 4 and cell[4] else None,
                "hcName": cell[5] if len(cell) > 5 and cell[5] else None,
                "country": cell[6] if len(cell) > 6 and cell[6] else None,
                "city": cell[7] if len(cell) > 7 and cell[7] else None,
                "zip": cell[8] if len(cell) > 8 and cell[8] else None,
                "address": cell[9] if len(cell) > 9 and cell[9] else None,
                "created": cell[10] if len(cell) > 10 and cell[10] else None,
                "modified": cell[11] if len(cell) > 11 and cell[11] else None,
            })
        if found:
            break
        offset += limit
    
    logger.info(f"Nuevos suscriptores descargados: {len(new_data)}")
    result = store_all_subscribers_in_chunks(new_data)
    
    if fetch_login_info_for_subscriber:
        login_info_count = 0
        for item in new_data:
            subscriber_code = item.get('code')
            if subscriber_code:
                try:
                    if fetch_login_info_for_subscriber(session_id, subscriber_code):
                        login_info_count += 1
                except Exception:
                    pass
        if login_info_count > 0:
            logger.info(f"Login info obtenida: {login_info_count} suscriptores")
    
    return result

def compare_and_update_all_subscribers(session_id=None, limit=100):
    """
    Compara todos los suscriptores de Panaccess con los de la base local:
    - Actualiza los existentes si hay diferencias
    - Elimina los que ya no existen en PanAccess
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    
    Returns:
        Diccionario con estadísticas: {'updated': int, 'deleted': int}
    """
    logger.info("Actualizando suscriptores existentes y eliminando los que ya no existen en PanAccess")
    
    # Obtener todos los códigos locales
    local_data = {
        obj.code: obj for obj in ListOfSubscriber.objects.all() if obj.code
    }
    
    # Obtener todos los códigos remotos desde PanAccess
    remote_codes = set()
    offset = 0
    total_updated = 0
    
    while True:
        response = CallListSubscribers(session_id, offset, limit)
        remote_list = response.get("rows", [])
        if not remote_list:
            break
            
        for row in remote_list:
            if not isinstance(row.get("cell"), list) or len(row.get("cell", [])) < 12:
                continue
            
            cell = row["cell"]
            code = cell[0] if len(cell) > 0 and cell[0] else None
            if not code:
                continue
            
            # Agregar código a la lista de remotos
            remote_codes.add(code)
            
            # Si existe localmente, actualizarlo
            if code in local_data:
                remote = {
                    "lastName": cell[1] if len(cell) > 1 and cell[1] else None,
                    "firstName": cell[2] if len(cell) > 2 and cell[2] else None,
                    "smartcards": cell[3] if len(cell) > 3 and cell[3] else [],
                    "hcId": cell[4] if len(cell) > 4 and cell[4] else None,
                    "hcName": cell[5] if len(cell) > 5 and cell[5] else None,
                    "country": cell[6] if len(cell) > 6 and cell[6] else None,
                    "city": cell[7] if len(cell) > 7 and cell[7] else None,
                    "zip": cell[8] if len(cell) > 8 and cell[8] else None,
                    "address": cell[9] if len(cell) > 9 and cell[9] else None,
                    "created": cell[10] if len(cell) > 10 and cell[10] else None,
                    "modified": cell[11] if len(cell) > 11 and cell[11] else None,
                }
                local_obj = local_data[code]
                changed_fields = []
                for key, val in remote.items():
                    if hasattr(local_obj, key):
                        local_val = getattr(local_obj, key)
                        if isinstance(local_val, list) and isinstance(val, list):
                            if local_val != val:
                                setattr(local_obj, key, val)
                                changed_fields.append(key)
                        elif str(local_val) != str(val):
                            setattr(local_obj, key, val)
                            changed_fields.append(key)
                if changed_fields:
                    try:
                        local_obj.save(update_fields=changed_fields)
                        total_updated += 1
                        
                        if fetch_login_info_for_subscriber and code:
                            try:
                                fetch_login_info_for_subscriber(session_id, code)
                            except Exception:
                                pass
                    except Exception as e:
                        logger.error(f"Error actualizando código {code}: {str(e)}")
        
        offset += limit
    
    # Eliminar los que están en local pero no en PanAccess
    local_codes = set(local_data.keys())
    codes_to_delete = local_codes - remote_codes
    
    total_deleted = 0
    if codes_to_delete:
        try:
            deleted_count = ListOfSubscriber.objects.filter(code__in=codes_to_delete).delete()[0]
            total_deleted = deleted_count
            logger.info(f"Eliminados {total_deleted} suscriptores que ya no existen en PanAccess: {list(codes_to_delete)}")
        except Exception as e:
            logger.error(f"Error eliminando suscriptores: {str(e)}")
    
    logger.info(f"Actualizados {total_updated} suscriptores, eliminados {total_deleted} suscriptores")
    return {
        'updated': total_updated,
        'deleted': total_deleted
    }

def sync_subscribers(session_id=None, limit=100):
    """
    Ejecuta el proceso de sincronización de suscriptores:
    - Si la base está vacía, descarga todos los registros.
    - Si no, descarga solo los nuevos desde el último code.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    
    Returns:
        Resultado de la sincronización
    """
    logger.info("Sincronizando suscriptores")

    try:
        if DataBaseEmpty():
            return fetch_all_subscribers(session_id, limit)
        else:
            new_result = download_subscribers_since_last(session_id, limit)
            compare_and_update_all_subscribers(session_id, limit)
            return new_result

    except PanAccessException as e:
        logger.error(f"Error PanAccess: {str(e)}")
        raise
    except (ConnectionError, ValueError) as e:
        logger.error(f"Error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        raise

def CallListSubscribers(session_id=None, offset=0, limit=100):
    """
    Llama a la API de Panaccess para obtener la lista de suscriptores.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        offset: Índice de inicio para paginación
        limit: Cantidad máxima de registros a obtener
    
    Returns:
        Diccionario con la respuesta de PanAccess
    """
    try:
        panaccess = get_panaccess()
        parameters = {
            'offset': offset,
            'limit': limit,
            'orderDir': 'DESC',
            'orderBy': 'code'
        }
        response = panaccess.call('getListOfSubscribers', parameters)

        if response.get('success'):
            return response.get('answer', {})
        else:
            error_message = response.get('errorMessage', 'Error desconocido al obtener suscriptores')
            logger.error(f"Error PanAccess: {error_message}")
            raise PanAccessException(error_message)

    except PanAccessException:
        raise
    except Exception as e:
        logger.error(f"Error llamada API: {str(e)}", exc_info=True)
        raise