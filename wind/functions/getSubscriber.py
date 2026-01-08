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
    Descarga todos los suscriptores extendidos desde Panaccess y los almacena en la base de datos.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    logger.info("Descarga completa de suscriptores extendidos")
    offset = 0
    all_data = []
    
    try:
        from dateutil import parser
    except ImportError:
        logger.warning("python-dateutil no está instalado, las fechas pueden no parsearse correctamente")
        parser = None
    
    while True:
        result = CallListExtendedSubscribers(session_id, offset, limit)
        rows = result.get("rows", [])
        if not rows:
            break
        
        for row in rows:
            # Procesar cada suscriptor extendido
            subscriber_data = {
                "id": row.get("subscriberCode", ""),  # Usar subscriberCode como id
                "code": row.get("subscriberCode"),
                "lastName": row.get("lastName"),
                "firstName": row.get("firstName"),
                "smartcards": row.get("smartcards"),
                "regionId": row.get("regionId"),
                "countryCode": row.get("countryCode"),
                "caf": row.get("caf"),
                "supervisor": row.get("supervisor"),
                "comment": row.get("comment"),
                "ip": row.get("ip"),
                "emails": row.get("emails"),
                "phones": row.get("phones"),
                "faxes": row.get("faxes"),
                "skypes": row.get("skypes"),
                "mobiles": row.get("mobiles"),
                "custodians": row.get("custodians"),
                "address1": row.get("address1"),
                "address2": row.get("address2"),
                "address3": row.get("address3"),
                "addressCount": row.get("addressCount", 0),
                "newsletterAccepted": row.get("newsletterAccepted", False),
                "tags": row.get("tags"),
                "uniqueLogin": row.get("uniqueLogin"),
            }
            
            # Procesar fechas
            if row.get("created"):
                try:
                    if parser:
                        subscriber_data["created"] = parser.parse(row.get("created"))
                    else:
                        # Fallback simple si no hay parser
                        subscriber_data["created"] = row.get("created")
                except Exception as e:
                    logger.warning(f"Error parseando fecha created: {e}")
                    subscriber_data["created"] = None
            else:
                subscriber_data["created"] = None
            
            if row.get("firstOrderTime"):
                try:
                    if parser:
                        subscriber_data["firstOrderTime"] = parser.parse(row.get("firstOrderTime"))
                    else:
                        subscriber_data["firstOrderTime"] = row.get("firstOrderTime")
                except Exception as e:
                    logger.warning(f"Error parseando fecha firstOrderTime: {e}")
                    subscriber_data["firstOrderTime"] = None
            else:
                subscriber_data["firstOrderTime"] = None
            
            if row.get("lastExpiryTime"):
                try:
                    if parser:
                        subscriber_data["lastExpiryTime"] = parser.parse(row.get("lastExpiryTime"))
                    else:
                        subscriber_data["lastExpiryTime"] = row.get("lastExpiryTime")
                except Exception as e:
                    logger.warning(f"Error parseando fecha lastExpiryTime: {e}")
                    subscriber_data["lastExpiryTime"] = None
            else:
                subscriber_data["lastExpiryTime"] = None
            
            all_data.append(subscriber_data)
        
        offset += limit
    
    logger.info(f"Descargados {len(all_data)} suscriptores extendidos")
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
    Usa la API extendida para obtener información completa.
    
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
    
    try:
        from dateutil import parser
    except ImportError:
        logger.warning("python-dateutil no está instalado, las fechas pueden no parsearse correctamente")
        parser = None
    
    while True:
        result = CallListExtendedSubscribers(session_id, offset, limit)
        rows = result.get("rows", [])
        if not rows:
            break
        
        for row in rows:
            code = row.get("subscriberCode")
            if not code:
                continue
            
            if code == highest_code:
                found = True
                break
            
            # Procesar cada suscriptor extendido
            subscriber_data = {
                "id": code,
                "code": code,
                "lastName": row.get("lastName"),
                "firstName": row.get("firstName"),
                "smartcards": row.get("smartcards"),
                "regionId": row.get("regionId"),
                "countryCode": row.get("countryCode"),
                "caf": row.get("caf"),
                "supervisor": row.get("supervisor"),
                "comment": row.get("comment"),
                "ip": row.get("ip"),
                "emails": row.get("emails"),
                "phones": row.get("phones"),
                "faxes": row.get("faxes"),
                "skypes": row.get("skypes"),
                "mobiles": row.get("mobiles"),
                "custodians": row.get("custodians"),
                "address1": row.get("address1"),
                "address2": row.get("address2"),
                "address3": row.get("address3"),
                "addressCount": row.get("addressCount", 0),
                "newsletterAccepted": row.get("newsletterAccepted", False),
                "tags": row.get("tags"),
                "uniqueLogin": row.get("uniqueLogin"),
            }
            
            # Procesar fechas
            if row.get("created"):
                try:
                    if parser:
                        subscriber_data["created"] = parser.parse(row.get("created"))
                    else:
                        subscriber_data["created"] = row.get("created")
                except Exception as e:
                    logger.warning(f"Error parseando fecha created: {e}")
                    subscriber_data["created"] = None
            else:
                subscriber_data["created"] = None
            
            if row.get("firstOrderTime"):
                try:
                    if parser:
                        subscriber_data["firstOrderTime"] = parser.parse(row.get("firstOrderTime"))
                    else:
                        subscriber_data["firstOrderTime"] = row.get("firstOrderTime")
                except Exception as e:
                    logger.warning(f"Error parseando fecha firstOrderTime: {e}")
                    subscriber_data["firstOrderTime"] = None
            else:
                subscriber_data["firstOrderTime"] = None
            
            if row.get("lastExpiryTime"):
                try:
                    if parser:
                        subscriber_data["lastExpiryTime"] = parser.parse(row.get("lastExpiryTime"))
                    else:
                        subscriber_data["lastExpiryTime"] = row.get("lastExpiryTime")
                except Exception as e:
                    logger.warning(f"Error parseando fecha lastExpiryTime: {e}")
                    subscriber_data["lastExpiryTime"] = None
            else:
                subscriber_data["lastExpiryTime"] = None
            
            new_data.append(subscriber_data)
        
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
    Compara todos los suscriptores extendidos de Panaccess con los de la base local:
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
    
    try:
        from dateutil import parser
    except ImportError:
        logger.warning("python-dateutil no está instalado, las fechas pueden no parsearse correctamente")
        parser = None
    
    while True:
        response = CallListExtendedSubscribers(session_id, offset, limit)
        remote_list = response.get("rows", [])
        if not remote_list:
            break
            
        for row in remote_list:
            code = row.get("subscriberCode")
            if not code:
                continue
            
            # Agregar código a la lista de remotos
            remote_codes.add(code)
            
            # Si existe localmente, actualizarlo
            if code in local_data:
                local_obj = local_data[code]
                changed_fields = []
                
                # Mapear campos del formato extendido
                field_mapping = {
                    "lastName": row.get("lastName"),
                    "firstName": row.get("firstName"),
                    "smartcards": row.get("smartcards"),
                    "regionId": row.get("regionId"),
                    "countryCode": row.get("countryCode"),
                    "caf": row.get("caf"),
                    "supervisor": row.get("supervisor"),
                    "comment": row.get("comment"),
                    "ip": row.get("ip"),
                    "emails": row.get("emails"),
                    "phones": row.get("phones"),
                    "faxes": row.get("faxes"),
                    "skypes": row.get("skypes"),
                    "mobiles": row.get("mobiles"),
                    "custodians": row.get("custodians"),
                    "address1": row.get("address1"),
                    "address2": row.get("address2"),
                    "address3": row.get("address3"),
                    "addressCount": row.get("addressCount", 0),
                    "newsletterAccepted": row.get("newsletterAccepted", False),
                    "tags": row.get("tags"),
                    "uniqueLogin": row.get("uniqueLogin"),
                }
                
                # Procesar fechas
                if row.get("created"):
                    try:
                        if parser:
                            field_mapping["created"] = parser.parse(row.get("created"))
                        else:
                            field_mapping["created"] = row.get("created")
                    except Exception as e:
                        logger.warning(f"Error parseando fecha created: {e}")
                        field_mapping["created"] = None
                else:
                    field_mapping["created"] = None
                
                if row.get("firstOrderTime"):
                    try:
                        if parser:
                            field_mapping["firstOrderTime"] = parser.parse(row.get("firstOrderTime"))
                        else:
                            field_mapping["firstOrderTime"] = row.get("firstOrderTime")
                    except Exception as e:
                        logger.warning(f"Error parseando fecha firstOrderTime: {e}")
                        field_mapping["firstOrderTime"] = None
                else:
                    field_mapping["firstOrderTime"] = None
                
                if row.get("lastExpiryTime"):
                    try:
                        if parser:
                            field_mapping["lastExpiryTime"] = parser.parse(row.get("lastExpiryTime"))
                        else:
                            field_mapping["lastExpiryTime"] = row.get("lastExpiryTime")
                    except Exception as e:
                        logger.warning(f"Error parseando fecha lastExpiryTime: {e}")
                        field_mapping["lastExpiryTime"] = None
                else:
                    field_mapping["lastExpiryTime"] = None
                
                # Comparar y actualizar campos
                for key, val in field_mapping.items():
                    if hasattr(local_obj, key):
                        local_val = getattr(local_obj, key)
                        if isinstance(local_val, list) and isinstance(val, list):
                            if local_val != val:
                                setattr(local_obj, key, val)
                                changed_fields.append(key)
                        elif isinstance(local_val, dict) and isinstance(val, dict):
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

def CallListExtendedSubscribers(session_id=None, offset=0, limit=100):
    """
    Llama a la API de Panaccess para obtener la lista extendida de suscriptores.
    
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
            'usePrefixFlags': True,
            'offset': offset,
            'limit': limit,
            'orderBy': 'code',
        }
        response = panaccess.call('getListOfExtendedSubscribers', parameters)

        if response.get('success'):
            return response.get('answer', {})
        else:
            error_message = response.get('errorMessage', 'Error desconocido al obtener suscriptores extendidos')
            logger.error(f"Error PanAccess: {error_message}")
            raise PanAccessException(error_message)

    except PanAccessException:
        raise
    except Exception as e:
        logger.error(f"Error llamada API: {str(e)}", exc_info=True)
        raise