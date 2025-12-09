"""
Vistas para la aplicación wind.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.utils.panaccess_auth import login, logged_in
from wind.services import PanAccessClient, get_panaccess
from wind.exceptions import (
    PanAccessAuthenticationError,
    PanAccessConnectionError,
    PanAccessTimeoutError,
    PanAccessAPIError,
    PanAccessException
)


@api_view(['GET'])
@permission_classes([AllowAny])
def test_login(request):
    """
    Vista de prueba para la autenticación con PanAccess.
    
    Prueba el login usando el cliente y retorna el sessionId obtenido.
    """
    client = PanAccessClient()
    
    try:
        session_id = client.authenticate()
        
        return Response({
            'success': True,
            'message': 'Login exitoso',
            'session_id': session_id,
            'session_id_length': len(session_id) if session_id else 0,
            'is_authenticated': client.is_authenticated()
        }, status=status.HTTP_200_OK)
        
    except PanAccessAuthenticationError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessAuthenticationError',
            'message': str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)
        
    except PanAccessConnectionError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessConnectionError',
            'message': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except PanAccessTimeoutError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessTimeoutError',
            'message': str(e)
        }, status=status.HTTP_504_GATEWAY_TIMEOUT)
        
    except PanAccessAPIError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessAPIError',
            'message': str(e),
            'status_code': e.status_code
        }, status=status.HTTP_502_BAD_GATEWAY)
        
    except PanAccessException as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessException',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': f'Error inesperado: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def test_singleton(request):
    """
    Vista de prueba para el singleton de PanAccess.
    
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


@api_view(['GET'])
@permission_classes([AllowAny])
def test_logged_in(request):
    """
    Vista de prueba para validar si un sessionId está vigente.
    
    Prueba la función logged_in() y el método check_session() del cliente.
    """
    client = PanAccessClient()
    
    try:
        # Primero autenticarse para obtener un sessionId
        session_id = client.authenticate()
        
        # Verificar si la sesión es válida usando la función directa
        is_valid_direct = logged_in(session_id)
        
        # Verificar usando el método del cliente
        is_valid_client = client.check_session()
        
        return Response({
            'success': True,
            'message': 'Verificación de sesión exitosa',
            'session_id': session_id,
            'is_valid_direct': is_valid_direct,
            'is_valid_client': is_valid_client,
            'both_match': is_valid_direct == is_valid_client
        }, status=status.HTTP_200_OK)
        
    except PanAccessAuthenticationError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessAuthenticationError',
            'message': str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)
        
    except PanAccessConnectionError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessConnectionError',
            'message': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except PanAccessTimeoutError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessTimeoutError',
            'message': str(e)
        }, status=status.HTTP_504_GATEWAY_TIMEOUT)
        
    except PanAccessAPIError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessAPIError',
            'message': str(e),
            'status_code': e.status_code
        }, status=status.HTTP_502_BAD_GATEWAY)
        
    except PanAccessException as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessException',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': f'Error inesperado: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
