"""
Vista para el singleton de PanAccess.

Endpoint que demuestra cómo usar el singleton que se inicializa al arrancar Django.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.services import get_panaccess
from wind.exceptions import PanAccessException


@api_view(['GET'])
@permission_classes([AllowAny])
def singleton(request):
    """
    Vista para el singleton de PanAccess.
    
    Demuestra cómo usar el singleton que se inicializa al arrancar Django.
    """
    try:
        # Obtener el singleton (se inicializa automáticamente al arrancar Django)
        panaccess = get_panaccess()
        
        # Hacer una llamada de prueba (el singleton maneja la sesión automáticamente)
        # Nota: Esta es una llamada de ejemplo, ajusta según la función que necesites
        result = panaccess.call("cvLoggedIn", {
            "sessionId": panaccess.client.session_id
        })
        
        return Response({
            'success': True,
            'message': 'Singleton funcionando correctamente',
            'has_session': panaccess.client.is_authenticated(),
            'session_id': panaccess.client.session_id[:20] + '...' if panaccess.client.session_id else None,
            'result': result
        }, status=status.HTTP_200_OK)
        
    except PanAccessException as e:
        return Response({
            'success': False,
            'error_type': type(e).__name__,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': f'Error inesperado: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

