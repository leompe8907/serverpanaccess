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


def extract_first_email(emails_data):
    """
    Extrae el primer email de una lista o retorna None.
    
    Args:
        emails_data: Puede ser una lista, un string, o None
    
    Returns:
        str: El primer email normalizado (lowercase) o None
    """
    if not emails_data:
        return None
    
    if isinstance(emails_data, list):
        if len(emails_data) > 0 and emails_data[0]:
            return emails_data[0].lower().strip() if isinstance(emails_data[0], str) else None
        return None
    
    if isinstance(emails_data, str):
        return emails_data.lower().strip()
    
    return None

def extract_first_phone(phones_data):
    """
    Extrae el primer teléfono de una lista o retorna None.
    
    Args:
        phones_data: Puede ser una lista, un string, o None
    
    Returns:
        str: El primer teléfono o None
    """
    if not phones_data:
        return None
    
    if isinstance(phones_data, list):
        if len(phones_data) > 0 and phones_data[0]:
            return str(phones_data[0]).strip() if phones_data[0] else None
        return None
    
    if isinstance(phones_data, str):
        return phones_data.strip()
    
    return None

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
        # Log para debug: ver estructura de respuesta
        logger.info(f"Estructura de respuesta: keys={list(result.keys())}, count={result.get('count', 'N/A')}")
        
        rows = result.get("extendedSubscriberEntries") or result.get("subscriberEntries") or result.get("rows", [])
        if not rows:
            logger.warning(f"No se encontraron filas en la respuesta. Keys disponibles: {list(result.keys())}, count: {result.get('count', 'N/A')}")
            break
        
        logger.info(f"Procesando {len(rows)} filas")
        
        for row in rows:
            # Obtener subscriberCode (puede estar vacío según PanAccess)
            subscriber_code = row.get("subscriberCode")
            
            # Procesar cada suscriptor extendido
            subscriber_data = {
                "id": subscriber_code,  # Usar subscriberCode como id
                "code": subscriber_code,
                "lastName": row.get("lastName"),
                "firstName": row.get("firstName"),
                "smartcards": row.get("smartcards"),
                "regionId": row.get("regionId"),
                "countryCode": row.get("countryCode"),
                "caf": row.get("caf"),
                "supervisor": row.get("supervisor"),
                "comment": row.get("comment"),
                "ip": row.get("ip"),
                "emails": extract_first_email(row.get("emails")),
                "phones": extract_first_phone(row.get("phones")),
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
    Actualiza los existentes si ya están en la base de datos.
    """
    total = len(data_batch)
    if total == 0:
        logger.warning("No hay datos para almacenar")
        return (0, 0)
    logger.info(f"Almacenando {total} suscriptores")
    
    total_inserted = 0
    total_updated = 0
    total_errors = 0
    
    for i in range(0, total, chunk_size):
        chunk = data_batch[i:i + chunk_size]
        valid_objects = []
        
        # Obtener códigos e IDs de los suscriptores en este chunk
        codes = {item.get('code') for item in chunk if item.get('code')}
        ids = {item.get('id') for item in chunk if item.get('id')}
        
        # Buscar existentes por código e ID
        existing_by_code = {
            obj.code: obj for obj in ListOfSubscriber.objects.filter(code__in=codes) if obj.code
        }
        existing_by_id = {
            obj.id: obj for obj in ListOfSubscriber.objects.filter(id__in=ids) if obj.id
        }
        
        for item in chunk:
            # Validar con serializer
            serializer = ListOfSubscriberSerializer(data=item)
            if not serializer.is_valid():
                total_errors += 1
                logger.warning(f"Error validando suscriptor {item.get('code', 'N/A')}: {serializer.errors}")
                logger.debug(f"Datos del suscriptor inválido: {item}")
                continue
            
            validated = serializer.validated_data
            code = validated.get('code')
            subscriber_id = validated.get('id')
            
            # Verificar si existe por código o ID
            existing = None
            if code and code in existing_by_code:
                existing = existing_by_code[code]
            elif subscriber_id and subscriber_id in existing_by_id:
                existing = existing_by_id[subscriber_id]
            
            if existing:
                # Actualizar registro existente
                changed = False
                changed_fields = []
                for key, val in validated.items():
                    current_val = getattr(existing, key, None)
                    # Comparar valores considerando tipos
                    if isinstance(current_val, list) and isinstance(val, list):
                        if current_val != val:
                            setattr(existing, key, val)
                            changed = True
                            changed_fields.append(key)
                    elif isinstance(current_val, dict) and isinstance(val, dict):
                        if current_val != val:
                            setattr(existing, key, val)
                            changed = True
                            changed_fields.append(key)
                    elif str(current_val) != str(val):
                        setattr(existing, key, val)
                        changed = True
                        changed_fields.append(key)
                
                if changed:
                    try:
                        existing.save(update_fields=changed_fields)
                        total_updated += 1
                        logger.debug(f"Suscriptor {code or subscriber_id} actualizado: {changed_fields}")
                    except Exception as e:
                        logger.error(f"Error actualizando suscriptor {code or subscriber_id}: {str(e)}")
                        total_errors += 1
            else:
                # Nuevo registro
                valid_objects.append(ListOfSubscriber(**validated))
        
        # Insertar nuevos registros
        if valid_objects:
            try:
                created = ListOfSubscriber.objects.bulk_create(valid_objects, ignore_conflicts=True)
                total_inserted += len(created)
            except Exception as e:
                logger.error(f"Error insertando chunk {i//chunk_size + 1}: {str(e)}")
                total_errors += len(valid_objects)
    
    logger.info(f"Almacenados {total_inserted} nuevos, {total_updated} actualizados, {total_errors} errores")
    return total_inserted, total_errors

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
        rows = result.get("extendedSubscriberEntries") or result.get("subscriberEntries") or result.get("rows", [])
        if not rows:
            break
        
        for row in rows:
            code = row.get("subscriberCode")
            
            if code == highest_code:
                found = True
                break
            
            # Procesar cada suscriptor extendido
            subscriber_data = {
                "id": code,  # Usar subscriberCode como id
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
                "emails": extract_first_email(row.get("emails")),
                "phones": extract_first_phone(row.get("phones")),
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
        remote_list = response.get("extendedSubscriberEntries") or response.get("subscriberEntries") or response.get("rows", [])
        if not remote_list:
            break
            
        for row in remote_list:
            code = row.get("subscriberCode")
            
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
                    "emails": extract_first_email(row.get("emails")),
                    "phones": extract_first_phone(row.get("phones")),
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
            'orderBy': 'created'
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
            "orderBy": "code",
            "orderDir": "DESC"
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