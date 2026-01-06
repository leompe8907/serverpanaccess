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
    return not ListOfSmartcards.objects.exists()

def LastSmartcard():
    """
    Retorna la última smartcard registrada en la base de datos según el campo 'sn'.
    """
    try:
        return ListOfSmartcards.objects.latest('sn')
    except ListOfSmartcards.DoesNotExist:
        return None

def store_all_smartcards_in_chunks(data_batch, chunk_size=100):
    """
    Almacena smartcards en la base de datos en bloques para mejorar el rendimiento.
    """
    total = len(data_batch)
    if total == 0:
        return
    logger.info(f"Almacenando {total} smartcards")
    
    # Obtener campos válidos del modelo
    model_fields = {f.name for f in ListOfSmartcards._meta.get_fields()}
    
    for i in range(0, total, chunk_size):
        chunk = data_batch[i:i + chunk_size]
        try:
            registros = []
            for item in chunk:
                # Filtrar solo campos que existen en el modelo
                filtered_item = {k: v for k, v in item.items() if k in model_fields}
                if filtered_item.get('sn'):  # Solo crear si tiene SN
                    registros.append(ListOfSmartcards(**filtered_item))
            
            if registros:
                ListOfSmartcards.objects.bulk_create(registros, ignore_conflicts=True)
        except Exception as e:
            logger.error(f"Error insertando chunk {i//chunk_size + 1}: {str(e)}")
    logger.info(f"Almacenados {total} smartcards")

def fetch_all_smartcards(session_id=None, limit=100):
    """
    Descarga todos los smartcards desde Panaccess y los almacena en la base de datos.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    logger.info("Descarga completa de smartcards")
    offset = 0
    all_data = []
    
    while True:
        result = CallListSmartcards(session_id, offset, limit)
        smartcard_entries = result.get("smartcardEntries", [])
        if not smartcard_entries:
            break
        
        for entry in smartcard_entries:
            if not isinstance(entry, dict) or 'sn' not in entry:
                continue
            all_data.append(entry)
        
        offset += limit
    
    logger.info(f"Descargados {len(all_data)} smartcards")
    return store_all_smartcards_in_chunks(all_data)

def download_smartcards_since_last(session_id=None, limit=100):
    """
    Descarga smartcards nuevos desde el último registrado (modo incremental).
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    last = LastSmartcard()
    if not last:
        return []
    
    highest_sn = last.sn
    logger.info(f"Descarga incremental desde SN: {highest_sn}")
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
                continue
            
            sn = entry.get('sn')
            if sn == highest_sn:
                found = True
                break
            new_data.append(entry)
        
        if found:
            break
        offset += limit
    
    logger.info(f"Nuevos smartcards descargados: {len(new_data)}")
    return store_all_smartcards_in_chunks(new_data)

def compare_and_update_all_smartcards(session_id=None, limit=100):
    """
    Compara todos los smartcards de Panaccess con los de la base local y actualiza si hay diferencias.
    
    Args:
        session_id: ID de sesión (opcional, se usa el singleton si no se proporciona)
        limit: Cantidad máxima de registros por página
    """
    logger.info("Actualizando smartcards existentes")
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
                except Exception as e:
                    logger.error(f"Error actualizando SN {sn}: {str(e)}")
        
        offset += limit
    
    logger.info(f"Actualizados {total_updated} smartcards")

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
    logger.info("Sincronizando smartcards")

    try:
        if DataBaseEmpty():
            return fetch_all_smartcards(session_id, limit)
        else:
            new_result = download_smartcards_since_last(session_id, limit)
            compare_and_update_all_smartcards(session_id, limit)
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
    try:
        panaccess = get_panaccess()
        parameters = {
            'offset': offset,
            'limit': limit,
            'orderDir': 'DESC',
            'orderBy': 'sn'
        }
        response = panaccess.call('getListOfSmartcards', parameters)

        if response.get('success'):
            return response.get('answer', {})
        else:
            error_message = response.get('errorMessage', 'Error desconocido al obtener smartcards')
            logger.error(f"Error PanAccess: {error_message}")
            raise PanAccessException(error_message)

    except PanAccessException:
        raise
    except Exception as e:
        logger.error(f"Error llamada API: {str(e)}", exc_info=True)
        raise

