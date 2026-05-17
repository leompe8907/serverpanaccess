"""
Vista para la autenticación con PanAccess.

Usa el singleton del sistema (misma sesión que el resto del backend).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.services import get_panaccess
from wind.exceptions import (
    PanAccessAuthenticationError,
    PanAccessConnectionError,
    PanAccessTimeoutError,
    PanAccessAPIError,
    PanAccessException,
)


@api_view(['GET'])
@permission_classes([AllowAny])
def login(request):
    """
    Obtiene o renueva la sesión PanAccess del singleton (cuenta de servicio).
    """
    try:
        panaccess = get_panaccess()
        panaccess.ensure_session()
        session_id = panaccess.client.session_id

        return Response({
            'success': True,
            'message': 'Login exitoso',
            'session_id': session_id,
            'session_id_length': len(session_id) if session_id else 0,
            'is_authenticated': panaccess.client.is_authenticated(),
        }, status=status.HTTP_200_OK)

    except PanAccessAuthenticationError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessAuthenticationError',
            'message': str(e),
        }, status=status.HTTP_401_UNAUTHORIZED)

    except PanAccessConnectionError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessConnectionError',
            'message': str(e),
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    except PanAccessTimeoutError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessTimeoutError',
            'message': str(e),
        }, status=status.HTTP_504_GATEWAY_TIMEOUT)

    except PanAccessAPIError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessAPIError',
            'message': str(e),
            'status_code': e.status_code,
        }, status=status.HTTP_502_BAD_GATEWAY)

    except PanAccessException as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessException',
            'message': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': f'Error inesperado: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
