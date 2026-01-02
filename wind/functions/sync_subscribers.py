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
    
    La función sync_subscribers() valida automáticamente la base de datos:
    - Si está vacía, realiza descarga completa
    - Si tiene datos, realiza descarga incremental + actualización
    
    Parámetros opcionales (GET o POST):
    - limit: Cantidad de registros por página (default: 100, máximo: 1000)
    
    Returns:
        Respuesta con estadísticas de la sincronización
    """
    try:
        # Obtener parámetros
        if request.method == 'GET':
            limit = int(request.query_params.get('limit', 100))
        else:
            limit = int(request.data.get('limit', 100))
        
        if limit > 1000:
            limit = 1000
        
        result = sync_subscribers(session_id=None, limit=limit)
        last_subscriber = LastSubscriber()
        last_subscriber_code = last_subscriber.code if last_subscriber else None
        
        return Response({
            'success': True,
            'message': 'Sincronización completada',
            'limit_used': limit,
            'last_subscriber_code': last_subscriber_code,
            'database_empty': DataBaseEmpty(),
            'result': result
        }, status=status.HTTP_200_OK)
        
    except PanAccessException as e:
        logger.error(f"Error PanAccess: {str(e)}")
        return Response({
            'success': False,
            'error_type': type(e).__name__,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except ValueError as e:
        logger.error(f"Error parámetros: {str(e)}")
        return Response({
            'success': False,
            'error_type': 'ValueError',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

