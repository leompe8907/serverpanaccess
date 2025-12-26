"""
Funciones para obtener y sincronizar smartcards desde PanAccess.
"""
import logging
from django.db import transaction
from wind.models import ListOfSmartcards
from wind.serializers import ListOfSmartcardsSerializer

from wind.services import get_panaccess
from wind.exceptions import PanAccessException

logger = logging.getLogger(__name__)


def DataBaseEmpty():
    """
    Verifica si la tabla ListOfSmartcards está vacía.
    """
    logger.info("Verificando si la base de datos de smartcards está vacía...")
    return not ListOfSmartcards.objects.exists()


def LastSmartcard():
    """
    Retorna la última smartcard registrada en la base de datos según el campo 'sn'.
    """
    logger.info("Buscando la última smartcard en la base de datos...")
    try:
        return ListOfSmartcards.objects.latest('sn')
    except ListOfSmartcards.DoesNotExist:
        logger.warning("No se encontró ninguna smartcard en la base de datos.")
        return None


def store_all_smartcards_in_chunks(data_batch, chunk_size=100):
    """
    Almacena smartcards en la base de datos en bloques para mejorar el rendimiento.
    """
    total = len(data_batch)
    logger.info(f"Almacenando {total} smartcards en chunks de {chunk_size}...")
    for i in range(0, total, chunk_size):
        chunk = data_batch[i:i + chunk_size]
        try:
            registros = [ListOfSmartcards(**item) for item in chunk]
            ListOfSmartcards.objects.bulk_create(registros, ignore_conflicts=True)
            logger.info(f"Chunk {i//chunk_size + 1}: insertadas {len(registros)} smartcards")
        except Exception as e:
            logger.error(f"Error insertando chunk desde {i} hasta {i+chunk_size}: {str(e)}")


def fetch_all_smartcards(session_id=None, limit=100):
    """
    Descarga todos los smartcards desde Panaccess y los almacena en la base de datos.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    logger.info("Iniciando descarga completa de smartcards desde Panaccess...")
    offset = 0
    all_data = []
    
    while True:
        result = CallListSmartcards(session_id, offset, limit)
        smartcard_entries = result.get("smartcardEntries", [])
        if not smartcard_entries:
            break
        
        for entry in smartcard_entries:
            # Validar que entry tenga la estructura esperada
            if not isinstance(entry, dict) or 'sn' not in entry:
                logger.warning(f"Entrada con estructura inválida, se omite: {entry.get('sn', 'unknown')}")
                continue
            
            all_data.append(entry)
        
        offset += limit
        logger.info(f"Procesados {len(all_data)} smartcards hasta ahora...")
    
    logger.info(f"Total de smartcards descargados: {len(all_data)}")
    return store_all_smartcards_in_chunks(all_data)


def download_smartcards_since_last(session_id=None, limit=100):
    """
    Descarga smartcards nuevos desde el último registrado (modo incremental).
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    logger.info("Iniciando descarga incremental de smartcards desde Panaccess...")
    last = LastSmartcard()
    if not last:
        logger.warning("No hay smartcards registradas. Se recomienda usar descarga total.")
        return []
    
    highest_sn = last.sn
    logger.info(f"Buscando smartcards posteriores al SN: {highest_sn}")
    offset = 0
    new_data = []
    found = False
    
    while True:
        result = CallListSmartcards(session_id, offset, limit)
        smartcard_entries = result.get("smartcardEntries", [])
        if not smartcard_entries:
            break
        
        for entry in smartcard_entries:
            if not isinstance(entry, dict) or 'sn' not in entry:
                logger.warning(f"Entrada con estructura inválida, se omite: {entry.get('sn', 'unknown')}")
                continue
            
            sn = entry.get('sn')
            
            if sn == highest_sn:
                found = True
                logger.info(f"SN {highest_sn} encontrado. Fin de descarga incremental.")
                break
            
            new_data.append(entry)
        
        if found:
            break
        offset += limit
        logger.info(f"Procesados {len(new_data)} smartcards nuevos hasta ahora...")
    
    logger.info(f"Total de smartcards nuevos descargados: {len(new_data)}")
    return store_all_smartcards_in_chunks(new_data)


def compare_and_update_all_smartcards(session_id=None, limit=100):
    """
    Compara todos los smartcards de Panaccess con los de la base local y actualiza si hay diferencias.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    logger.info("Comparando smartcards de Panaccess con la base de datos...")
    local_data = {
        obj.sn: obj for obj in ListOfSmartcards.objects.all() if obj.sn
    }
    offset = 0
    total_updated = 0
    
    while True:
        response = CallListSmartcards(session_id, offset, limit)
        remote_list = response.get("smartcardEntries", [])
        if not remote_list:
            break
        
        for remote in remote_list:
            if not isinstance(remote, dict) or 'sn' not in remote:
                continue
            
            sn = remote.get('sn')
            if not sn or sn not in local_data:
                continue
            
            local_obj = local_data[sn]
            changed_fields = []
            
            for key, val in remote.items():
                if hasattr(local_obj, key):
                    local_val = getattr(local_obj, key)
                    # Comparar valores, manejando None y listas
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
                    logger.debug(f"SN {sn} actualizado. Campos: {changed_fields}")
                except Exception as e:
                    logger.error(f"Error actualizando SN {sn}: {str(e)}")
        
        offset += limit
        logger.info(f"Procesados {offset} registros, {total_updated} actualizados hasta ahora...")
    
    logger.info(f"Actualización completa. Total modificados: {total_updated}")


def sync_smartcards(session_id=None, limit=100):
    """
    Ejecuta el proceso de sincronización de smartcards:
    - Si la base está vacía, descarga todos los registros.
    - Si no, descarga solo los nuevos desde el último sn.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    
    Returns:
        Resultado de la sincronización
    """
    logger.info("Iniciando sincronización de smartcards")

    try:
        if DataBaseEmpty():
            logger.info("Base vacía: descarga completa")
            return fetch_all_smartcards(session_id, limit)
        else:
            last = LastSmartcard()
            highest_sn = last.sn if last else None
            logger.info(f"Último SN: {highest_sn}")
            
            logger.info("Base existente: descarga incremental + actualización")
            # 1. Nuevos registros
            logger.info("Inicio de Descarga de smartcards nuevos desde el último registrado")
            new_result = download_smartcards_since_last(session_id, limit)
            logger.info(f"Fin de Descarga de smartcards nuevos completada.")
            
            # 2. Actualizar existentes
            logger.info("Inicio de Actualización de smartcards existentes")
            compare_and_update_all_smartcards(session_id, limit)
            logger.info("Fin de Actualización de smartcards existentes completada.")

            return new_result

    except PanAccessException as e:
        logger.error(f"Error de PanAccess durante sincronización: {str(e)}")
        raise
    except (ConnectionError, ValueError) as e:
        logger.error(f"Error específico durante sincronización: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        raise


def CallListSmartcards(session_id=None, offset=0, limit=100):
    """
    Llama a la API de Panaccess para obtener la lista de smartcards.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        offset: Índice de inicio para paginación
        limit: Cantidad máxima de registros a obtener
    
    Returns:
        Diccionario con la respuesta de PanAccess
    """
    logger.info(f"Llamando API Panaccess: offset={offset}, limit={limit}")
    
    try:
        # Usar el singleton de PanAccess
        panaccess = get_panaccess()
        
        # Preparar parámetros
        parameters = {
            'offset': offset,
            'limit': limit,
            'orderDir': 'ASC',
            'orderBy': 'sn'
        }
        
        # Hacer la llamada usando el singleton
        response = panaccess.call('getListOfSmartcards', parameters)

        if response.get('success'):
            return response.get('answer', {})
        else:
            error_message = response.get('errorMessage', 'Error desconocido al obtener smartcards')
            logger.error(f"Error en respuesta de PanAccess: {error_message}")
            raise PanAccessException(error_message)

    except PanAccessException:
        raise
    except Exception as e:
        logger.error(f"Fallo en la llamada a getListOfSmartcards: {str(e)}", exc_info=True)
        raise

