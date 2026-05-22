import logging
from django.db import transaction
from wind.models import (
    ListOfSubscriber,
    SubscriberLoginInfo,
    SubscriberEmailRegistry,
    SubscriberDocumentRegistry,
    SubscriberInfo
)
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


def _get_dateutil_parser():
    try:
        from dateutil import parser as date_parser
        return date_parser
    except ImportError:
        logger.warning("python-dateutil no está instalado, las fechas pueden no parsearse correctamente")
        return None


def _parse_subscriber_datetime(value, parser):
    if not value:
        return None
    try:
        if parser:
            return parser.parse(value)
        return value
    except Exception as e:
        logger.warning("Error parseando fecha %s: %s", value, e)
        return None


def extended_subscriber_row_to_data(row, parser=None):
    """
    Convierte una fila de getListOfExtendedSubscribers al dict usado por ListOfSubscriber.
    """
    subscriber_code = row.get("subscriberCode")
    if not subscriber_code or not str(subscriber_code).strip():
        return None

    if parser is None:
        parser = _get_dateutil_parser()

    return {
        "id": subscriber_code,
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
        "created": _parse_subscriber_datetime(row.get("created"), parser),
        "firstOrderTime": _parse_subscriber_datetime(row.get("firstOrderTime"), parser),
        "lastExpiryTime": _parse_subscriber_datetime(row.get("lastExpiryTime"), parser),
    }


def _update_subscriber_from_row(local_obj, row, parser=None):
    """Actualiza un suscriptor local si difiere de la fila remota. Retorna True si guardó cambios."""
    if parser is None:
        parser = _get_dateutil_parser()

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
        "created": _parse_subscriber_datetime(row.get("created"), parser),
        "firstOrderTime": _parse_subscriber_datetime(row.get("firstOrderTime"), parser),
        "lastExpiryTime": _parse_subscriber_datetime(row.get("lastExpiryTime"), parser),
    }

    changed_fields = []
    for key, val in field_mapping.items():
        if not hasattr(local_obj, key):
            continue
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

    if not changed_fields:
        return False

    try:
        local_obj.save(update_fields=changed_fields)
        return True
    except Exception as e:
        logger.error("Error actualizando suscriptor %s: %s", local_obj.code, e)
        return False


def _delete_local_subscribers_not_in_remote(local_codes, remote_codes):
    """Elimina suscriptores locales y credenciales que no existen en PanAccess."""
    codes_to_delete = local_codes - remote_codes
    total_deleted = 0
    credentials_deleted = {}

    if codes_to_delete:
        try:
            credentials_deleted = delete_subscriber_credentials(codes_to_delete)
            total_deleted = ListOfSubscriber.objects.filter(code__in=codes_to_delete).delete()[0]
            logger.info(
                "Eliminados %s suscriptores que ya no existen en PanAccess (muestra): %s",
                total_deleted,
                list(codes_to_delete)[:10],
            )
        except Exception as e:
            logger.error("Error eliminando suscriptores sobrantes: %s", e)

    return {
        "deleted": total_deleted,
        "codes_to_delete_count": len(codes_to_delete),
        "credentials_deleted": credentials_deleted,
    }


def _cleanup_invalid_local_subscribers():
    """Borra filas locales inválidas (code/id vacíos)."""
    invalid_deleted = 0
    try:
        invalid_deleted += ListOfSubscriber.objects.filter(code__isnull=True).delete()[0]
        invalid_deleted += ListOfSubscriber.objects.filter(code="").delete()[0]
        invalid_deleted += ListOfSubscriber.objects.filter(id="").delete()[0]
        if invalid_deleted:
            logger.info("Eliminados %s suscriptores locales inválidos (code/id vacíos)", invalid_deleted)
    except Exception as e:
        logger.error("Error limpiando suscriptores inválidos: %s", e)
    return invalid_deleted


def DataBaseEmpty():
    """
    Verifica si la tabla ListOfSubscriber está vacía.
    """
    return not ListOfSubscriber.objects.exists()

def delete_subscriber_credentials(subscriber_codes):
    """
    Elimina todas las credenciales relacionadas con los códigos de suscriptores proporcionados.
    
    Args:
        subscriber_codes: Lista o conjunto de códigos de suscriptores a eliminar
    
    Returns:
        Diccionario con estadísticas de eliminación
    """
    if not subscriber_codes:
        logger.info("delete_subscriber_credentials: No hay códigos para eliminar")
        return {
            'login_info': 0,
            'email_registry': 0,
            'document_registry': 0,
            'subscriber_info': 0
        }
    
    codes_list = list(subscriber_codes) if isinstance(subscriber_codes, set) else subscriber_codes
    
    # Filtrar códigos vacíos o None
    codes_list = [code for code in codes_list if code]
    
    if not codes_list:
        logger.warning("delete_subscriber_credentials: Todos los códigos están vacíos o son None")
        return {
            'login_info': 0,
            'email_registry': 0,
            'document_registry': 0,
            'subscriber_info': 0
        }
    
    logger.info(f"delete_subscriber_credentials: Eliminando credenciales para {len(codes_list)} códigos: {codes_list[:10]}...")
    
    # Verificar cuántos registros hay antes de eliminar
    email_count_before = SubscriberEmailRegistry.objects.filter(subscriber_code__in=codes_list).count()
    logger.info(f"delete_subscriber_credentials: Encontrados {email_count_before} registros en SubscriberEmailRegistry antes de eliminar")
    
    # Eliminar SubscriberLoginInfo
    login_info_deleted = SubscriberLoginInfo.objects.filter(subscriberCode__in=codes_list).delete()[0]
    
    # Eliminar SubscriberEmailRegistry
    email_registry_deleted = SubscriberEmailRegistry.objects.filter(subscriber_code__in=codes_list).delete()[0]
    
    # Eliminar SubscriberDocumentRegistry
    document_registry_deleted = SubscriberDocumentRegistry.objects.filter(subscriber_code__in=codes_list).delete()[0]
    
    # Eliminar SubscriberInfo
    subscriber_info_deleted = SubscriberInfo.objects.filter(subscriber_code__in=codes_list).delete()[0]
    
    # Verificar que se eliminaron correctamente
    email_count_after = SubscriberEmailRegistry.objects.filter(subscriber_code__in=codes_list).count()
    if email_count_after > 0:
        logger.warning(f"delete_subscriber_credentials: ADVERTENCIA - Aún quedan {email_count_after} registros en SubscriberEmailRegistry después de eliminar")
        # Intentar eliminar nuevamente con un filtro más específico
        remaining_emails = SubscriberEmailRegistry.objects.filter(subscriber_code__in=codes_list)
        logger.warning(f"delete_subscriber_credentials: Registros restantes: {list(remaining_emails.values_list('subscriber_code', 'email')[:10])}")
        # Eliminar manualmente los restantes
        additional_deleted = remaining_emails.delete()[0]
        if additional_deleted > 0:
            email_registry_deleted += additional_deleted
            logger.info(f"delete_subscriber_credentials: Eliminados {additional_deleted} registros adicionales de SubscriberEmailRegistry")
    
    logger.info(f"Credenciales eliminadas - LoginInfo: {login_info_deleted}, EmailRegistry: {email_registry_deleted}, "
                f"DocumentRegistry: {document_registry_deleted}, SubscriberInfo: {subscriber_info_deleted}")
    
    return {
        'login_info': login_info_deleted,
        'email_registry': email_registry_deleted,
        'document_registry': document_registry_deleted,
        'subscriber_info': subscriber_info_deleted
    }

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
            if not subscriber_code or not str(subscriber_code).strip():
                # Evitar crear registros locales "fantasma" (id/code vacíos)
                continue
            
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
    
    if fetch_login_info_for_subscriber and all_data:
        from wind.functions.getSubscriberLoginInfo import fetch_login_info_for_codes

        codes = [item.get("code") for item in all_data if item.get("code")]
        li_result = fetch_login_info_for_codes(codes)
        if li_result.get("success"):
            logger.info(
                "Login info (paralelo) tras carga completa: %s/%s",
                li_result.get("success"),
                li_result.get("total"),
            )

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

            # No almacenar filas sin identificadores (pueden venir vacías desde PanAccess)
            if not code or not str(code).strip() or not subscriber_id or not str(subscriber_id).strip():
                total_errors += 1
                logger.warning(f"Suscriptor inválido (id/code vacíos). Datos: {item}")
                continue
            
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
            if not code or not str(code).strip():
                continue
            
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
    
    if fetch_login_info_for_subscriber and new_data:
        from wind.functions.getSubscriberLoginInfo import fetch_login_info_for_codes

        codes = [item.get("code") for item in new_data if item.get("code")]
        li_result = fetch_login_info_for_codes(codes)
        if li_result.get("success"):
            logger.info(
                "Login info (paralelo) tras altas nuevas: %s/%s",
                li_result.get("success"),
                li_result.get("total"),
            )

    return result

def compare_and_update_all_subscribers(session_id=None, limit=100):
    """
    Reconciliación correctiva de suscriptores contra PanAccess (full sync).

    1. Recorre todos los suscriptores remotos (paginado).
    2. Actualiza existentes, crea faltantes en local.
    3. Elimina locales que no aparecen en PanAccess (diff de conjuntos, no solo count).
    4. Limpia filas inválidas (code/id vacíos) y credenciales asociadas.

    Returns:
        dict con created, updated, deleted, remote_count, local_count, etc.
    """
    logger.info("Reconciliando suscriptores desde PanAccess (full sync correctivo)")

    parser = _get_dateutil_parser()
    local_valid_qs = ListOfSubscriber.objects.exclude(code__isnull=True).exclude(code="")
    local_data = {obj.code: obj for obj in local_valid_qs if obj.code}
    local_total_count = len(local_data)

    remote_codes = set()
    new_subscriber_rows = []
    offset = 0
    remote_total_count = None
    total_updated = 0

    while True:
        response = CallListExtendedSubscribers(session_id, offset, limit)
        if remote_total_count is None:
            remote_total_count = int(response.get("count") or 0)

        remote_list = (
            response.get("extendedSubscriberEntries")
            or response.get("subscriberEntries")
            or response.get("rows", [])
        )
        if not remote_list:
            break

        for row in remote_list:
            code = row.get("subscriberCode")
            if not code or not str(code).strip():
                continue

            remote_codes.add(code)

            if code in local_data:
                if _update_subscriber_from_row(local_data[code], row, parser):
                    total_updated += 1
            else:
                subscriber_data = extended_subscriber_row_to_data(row, parser)
                if subscriber_data:
                    new_subscriber_rows.append(subscriber_data)

        offset += limit
        if remote_total_count and len(remote_codes) >= remote_total_count:
            break

    total_created = 0
    create_errors = 0
    if new_subscriber_rows:
        total_created, create_errors = store_all_subscribers_in_chunks(new_subscriber_rows)
        logger.info(
            "Suscriptores creados en full sync: %s (errores validación/insert: %s)",
            total_created,
            create_errors,
        )

    delete_result = _delete_local_subscribers_not_in_remote(set(local_data.keys()), remote_codes)
    invalid_deleted = _cleanup_invalid_local_subscribers()

    login_deleted_not_in_remote = 0
    try:
        from wind.functions.getSubscriberLoginInfo import cleanup_login_info_not_in_remote
        login_deleted_not_in_remote = cleanup_login_info_not_in_remote(remote_codes)
    except Exception as e:
        logger.error("Error limpiando login info fuera de PanAccess: %s", e)

    logger.info(
        "Full sync suscriptores — remoto API count=%s, códigos remotos=%s, local antes=%s, "
        "actualizados=%s, creados=%s, eliminados=%s, inválidos=%s",
        remote_total_count,
        len(remote_codes),
        local_total_count,
        total_updated,
        total_created,
        delete_result["deleted"],
        invalid_deleted,
    )

    return {
        "updated": total_updated,
        "created": total_created,
        "create_errors": create_errors,
        "deleted": delete_result["deleted"],
        "codes_to_delete_count": delete_result["codes_to_delete_count"],
        "invalid_deleted": invalid_deleted,
        "credentials_deleted": delete_result["credentials_deleted"],
        "remote_count": len(remote_codes),
        "remote_api_count": remote_total_count,
        "local_count_before": local_total_count,
        "login_deleted_not_in_remote": login_deleted_not_in_remote,
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

def _normalize_subscriber_api_answer(answer, subscriber_code: str) -> dict | None:
    """Convierte la respuesta de getSubscriber / getExtendedSubscriber a fila extendida."""
    if answer is None:
        return None
    if isinstance(answer, list):
        if not answer:
            return None
        answer = answer[0]
    if not isinstance(answer, dict):
        return None

    row = answer
    for key in (
        "extendedSubscriberEntry",
        "subscriberEntry",
        "subscriber",
        "entry",
        "answer",
    ):
        nested = row.get(key)
        if isinstance(nested, dict):
            row = nested
            break

    code = row.get("subscriberCode") or row.get("code") or subscriber_code
    if not code or not str(code).strip():
        return None

    normalized = dict(row)
    normalized["subscriberCode"] = str(code).strip()
    normalized.setdefault("code", normalized["subscriberCode"])
    return normalized


def CallGetSubscriber(session_id=None, subscriber_code=None):
    """
    Obtiene un suscriptor por código (1 llamada PanAccess).

    Prueba getSubscriber / getExtendedSubscriber antes de listar catálogos.
    """
    del session_id  # singleton

    if not subscriber_code or not str(subscriber_code).strip():
        raise ValueError("subscriber_code es requerido")

    code = str(subscriber_code).strip()
    panaccess = get_panaccess()

    attempts = (
        ("getSubscriber", {"code": code}),
        ("getSubscriber", {"subscriberCode": code}),
        ("getExtendedSubscriber", {"subscriberCode": code}),
        ("getExtendedSubscriber", {"code": code}),
    )
    last_error = None

    for api_name, parameters in attempts:
        try:
            response = panaccess.call(api_name, parameters)
            if not response.get("success"):
                last_error = response.get("errorMessage", api_name)
                continue
            row = _normalize_subscriber_api_answer(response.get("answer"), code)
            if row:
                logger.info("Suscriptor %s obtenido vía %s", code, api_name)
                return row
        except PanAccessException as exc:
            last_error = str(exc)
            logger.debug("%s no disponible para %s: %s", api_name, code, exc)

    raise PanAccessException(
        last_error or f"No se pudo obtener el suscriptor {code} por API directa"
    )


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
            "orderBy": "created",
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