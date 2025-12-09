"""
Vista para sincronizar suscriptores desde PanAccess.

Endpoint que ejecuta el proceso de sincronización completo de suscriptores.
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.functions.getSubscriber import (
    sync_subscribers,
    fetch_all_subscribers,
    download_subscribers_since_last,
    compare_and_update_all_subscribers,
    DataBaseEmpty,
    LastSubscriber
)
from wind.exceptions import PanAccessException

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def sync_subscribers_view(request):
    """
    Vista para sincronizar suscriptores desde PanAccess.
    
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
        
        logger.info(f"🔄 Iniciando sincronización de suscriptores - Modo: {mode}, Limit: {limit}")
        
        # Ejecutar según el modo
        if mode == 'full':
            logger.info("📥 Modo: Descarga completa")
            result = fetch_all_subscribers(session_id=None, limit=limit)
            message = "Descarga completa de suscriptores completada"
            
        elif mode == 'incremental':
            logger.info("📥 Modo: Descarga incremental (solo nuevos)")
            if DataBaseEmpty():
                return Response({
                    'success': False,
                    'message': 'La base de datos está vacía. Use mode=full para descarga completa.',
                    'suggestion': 'Use ?mode=full para realizar una descarga completa primero'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            result = download_subscribers_since_last(session_id=None, limit=limit)
            message = "Descarga incremental de suscriptores completada"
            
        elif mode == 'update':
            logger.info("🔄 Modo: Actualización de existentes")
            if DataBaseEmpty():
                return Response({
                    'success': False,
                    'message': 'La base de datos está vacía. No hay registros para actualizar.',
                    'suggestion': 'Use ?mode=full para realizar una descarga completa primero'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            compare_and_update_all_subscribers(session_id=None, limit=limit)
            result = None
            message = "Actualización de suscriptores existentes completada"
            
        else:  # mode == 'sync' (default)
            logger.info("🔄 Modo: Sincronización completa (nuevos + actualización)")
            result = sync_subscribers(session_id=None, limit=limit)
            message = "Sincronización completa de suscriptores completada"
        
        # Obtener estadísticas
        total_in_db = LastSubscriber()
        total_count = total_in_db.code if total_in_db else None
        
        logger.info(f"✅ {message}")
        
        return Response({
            'success': True,
            'message': message,
            'mode': mode,
            'limit_used': limit,
            'last_subscriber_code': total_count,
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

