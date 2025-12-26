"""
Vista para sincronizar smartcards desde PanAccess.

Endpoint que ejecuta el proceso de sincronización completo de smartcards.
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.functions.getSmartcard import (
    sync_smartcards,
    fetch_all_smartcards,
    download_smartcards_since_last,
    compare_and_update_all_smartcards,
    CallListSmartcards,
    DataBaseEmpty,
    LastSmartcard
)
from wind.exceptions import PanAccessException

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def sync_smartcards_view(request):
    """
    Vista para sincronizar smartcards desde PanAccess.
    
    Parámetros opcionales (GET o POST):
    - mode: 'full' (descarga completa), 'incremental' (solo nuevos), 
            'update' (solo actualizar existentes), 'sync' (completo - default)
    - limit: Cantidad de registros por página (default: 100)
    
    Returns:
        Respuesta con estadísticas de la sincronización
    """
    try:
        # Obtener parámetros
        if request.method == 'GET':
            mode = request.query_params.get('mode', 'sync')
            limit = int(request.query_params.get('limit', 100))
        else:
            mode = request.data.get('mode', 'sync')
            limit = int(request.data.get('limit', 100))
        
        # Validar limit
        if limit > 1000:
            limit = 1000
            logger.warning("Limit ajustado a 1000 (máximo permitido)")
        
        logger.info(f"🔄 Iniciando sincronización de smartcards - Modo: {mode}, Limit: {limit}")
        
        # Ejecutar según el modo
        if mode == 'full':
            logger.info("📥 Modo: Descarga completa")
            result = fetch_all_smartcards(session_id=None, limit=limit)
            message = "Descarga completa de smartcards completada"
            
        elif mode == 'incremental':
            logger.info("📥 Modo: Descarga incremental (solo nuevos)")
            if DataBaseEmpty():
                return Response({
                    'success': False,
                    'message': 'La base de datos está vacía. Use mode=full para descarga completa.',
                    'suggestion': 'Use ?mode=full para realizar una descarga completa primero'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            result = download_smartcards_since_last(session_id=None, limit=limit)
            message = "Descarga incremental de smartcards completada"
            
        elif mode == 'update':
            logger.info("🔄 Modo: Actualización de existentes")
            if DataBaseEmpty():
                return Response({
                    'success': False,
                    'message': 'La base de datos está vacía. No hay registros para actualizar.',
                    'suggestion': 'Use ?mode=full para realizar una descarga completa primero'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            compare_and_update_all_smartcards(session_id=None, limit=limit)
            result = None
            message = "Actualización de smartcards existentes completada"
            
        else:  # mode == 'sync' (default)
            logger.info("🔄 Modo: Sincronización completa (nuevos + actualización)")
            result = sync_smartcards(session_id=None, limit=limit)
            message = "Sincronización completa de smartcards completada"
        
        # Obtener estadísticas
        last_smartcard = LastSmartcard()
        last_sn = last_smartcard.sn if last_smartcard else None
        
        logger.info(f"✅ {message}")
        
        return Response({
            'success': True,
            'message': message,
            'mode': mode,
            'limit_used': limit,
            'last_smartcard_sn': last_sn,
            'database_empty': DataBaseEmpty(),
            'result': result if result is not None else 'update_completed'
        }, status=status.HTTP_200_OK)
        
    except PanAccessException as e:
        error_msg = f"Error de PanAccess: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return Response({
            'success': False,
            'error_type': type(e).__name__,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ValueError as e:
        error_msg = f"Error de parámetros: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return Response({
            'success': False,
            'error_type': 'ValueError',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"
        logger.error(f"💥 {error_msg}", exc_info=True)
        
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def test_call_list_smartcards(request):
    """
    Vista de prueba para llamar directamente a getListOfSmartcards.
    
    Parámetros opcionales (GET o POST):
    - offset: Índice de inicio (default: 0)
    - limit: Cantidad máxima de registros (default: 100)
    
    Returns:
        Respuesta con los smartcards obtenidos de la API
    """
    try:
        # Obtener parámetros
        if request.method == 'GET':
            offset = int(request.query_params.get('offset', 0))
            limit = int(request.query_params.get('limit', 100))
        else:
            offset = int(request.data.get('offset', 0))
            limit = int(request.data.get('limit', 100))
        
        # Validar limit
        if limit > 1000:
            limit = 1000
            logger.warning("Limit ajustado a 1000 (máximo permitido)")
        
        logger.info(f"🧪 Probando getListOfSmartcards - offset={offset}, limit={limit}")
        
        # Llamar a la API
        result = CallListSmartcards(
            session_id=None,
            offset=offset,
            limit=limit
        )
        
        count = result.get('count', 0)
        rows = result.get('rows', [])
        
        logger.info(f"✅ Llamada exitosa - Total: {count}, Obtenidos: {len(rows)}")
        
        return Response({
            'success': True,
            'message': 'Llamada a getListOfSmartcards exitosa',
            'parameters': {
                'offset': offset,
                'limit': limit
            },
            'result': {
                'count': count,
                'rows_count': len(rows),
                'rows': rows[:10] if len(rows) > 10 else rows,  # Mostrar solo primeros 10
                'has_more': len(rows) > 10
            }
        }, status=status.HTTP_200_OK)
        
    except PanAccessException as e:
        error_msg = f"Error de PanAccess: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return Response({
            'success': False,
            'error_type': type(e).__name__,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ValueError as e:
        error_msg = f"Error de parámetros: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return Response({
            'success': False,
            'error_type': 'ValueError',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"
        logger.error(f"💥 {error_msg}", exc_info=True)
        
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def smartcards_stats_view(request):
    """
    Vista para obtener estadísticas de smartcards en la base de datos.
    
    Returns:
        Estadísticas de smartcards almacenados
    """
    try:
        from wind.models import ListOfSmartcards
        
        total_smartcards = ListOfSmartcards.objects.count()
        last_smartcard = LastSmartcard()
        database_empty = DataBaseEmpty()
        
        stats = {
            'success': True,
            'total_smartcards': total_smartcards,
            'database_empty': database_empty,
            'last_smartcard_sn': last_smartcard.sn if last_smartcard else None,
            'last_smartcard_name': f"{last_smartcard.firstName or ''} {last_smartcard.lastName or ''}".strip() if last_smartcard else None,
        }
        
        if not database_empty:
            # Estadísticas adicionales
            blacklisted_count = ListOfSmartcards.objects.filter(blacklisted=True).count()
            disabled_count = ListOfSmartcards.objects.filter(disabled=True).count()
            active_count = ListOfSmartcards.objects.filter(blacklisted=False, disabled=False).count()
            
            stats.update({
                'blacklisted_smartcards': blacklisted_count,
                'disabled_smartcards': disabled_count,
                'active_smartcards': active_count,
            })
        
        return Response(stats, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"💥 Error obteniendo estadísticas: {str(e)}", exc_info=True)
        
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

