"""
Vistas para la aplicación wind.
"""
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.utils.panaccess_auth import login
from wind.services import PanAccessClient
from wind.exceptions import (
    PanAccessAuthenticationError,
    PanAccessConnectionError,
    PanAccessTimeoutError,
    PanAccessAPIError,
    PanAccessException
)


@api_view(['GET'])
@permission_classes([AllowAny])
def test_login_direct(request):
    """
    Vista de prueba para la función login() directa.
    
    Prueba la autenticación usando la función login() directamente
    y retorna el sessionId obtenido.
    """
    try:
        session_id = login()
        
        return Response({
            'success': True,
            'message': 'Login exitoso',
            'session_id': session_id,
            'session_id_length': len(session_id) if session_id else 0
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
def test_login_client(request):
    """
    Vista de prueba para el cliente PanAccessClient.
    
    Prueba la autenticación usando el cliente y muestra
    información sobre el estado de la sesión.
    """
    client = PanAccessClient()
    
    try:
        # Autenticarse explícitamente
        session_id = client.authenticate()
        
        # Verificar estado de autenticación
        is_authenticated = client.is_authenticated()
        
        return Response({
            'success': True,
            'message': 'Login exitoso usando PanAccessClient',
            'session_id': session_id,
            'session_id_length': len(session_id) if session_id else 0,
            'is_authenticated': is_authenticated,
            'base_url': client.base_url
        }, status=status.HTTP_200_OK)
        
    except PanAccessAuthenticationError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessAuthenticationError',
            'message': str(e),
            'is_authenticated': client.is_authenticated()
        }, status=status.HTTP_401_UNAUTHORIZED)
        
    except PanAccessConnectionError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessConnectionError',
            'message': str(e),
            'is_authenticated': client.is_authenticated()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except PanAccessTimeoutError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessTimeoutError',
            'message': str(e),
            'is_authenticated': client.is_authenticated()
        }, status=status.HTTP_504_GATEWAY_TIMEOUT)
        
    except PanAccessAPIError as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessAPIError',
            'message': str(e),
            'status_code': e.status_code,
            'is_authenticated': client.is_authenticated()
        }, status=status.HTTP_502_BAD_GATEWAY)
        
    except PanAccessException as e:
        return Response({
            'success': False,
            'error_type': 'PanAccessException',
            'message': str(e),
            'is_authenticated': client.is_authenticated()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': f'Error inesperado: {str(e)}',
            'is_authenticated': client.is_authenticated()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def test_login_complete(request):
    """
    Vista de prueba completa que prueba ambas formas de autenticación.
    
    Prueba tanto la función login() directa como el cliente,
    y compara los resultados.
    """
    results = {
        'direct_login': None,
        'client_login': None,
        'comparison': None
    }
    
    # Prueba 1: Login directo
    try:
        session_id_direct = login()
        results['direct_login'] = {
            'success': True,
            'session_id': session_id_direct,
            'session_id_length': len(session_id_direct) if session_id_direct else 0
        }
    except Exception as e:
        results['direct_login'] = {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }
    
    # Prueba 2: Login con cliente
    client = PanAccessClient()
    try:
        session_id_client = client.authenticate()
        results['client_login'] = {
            'success': True,
            'session_id': session_id_client,
            'session_id_length': len(session_id_client) if session_id_client else 0,
            'is_authenticated': client.is_authenticated()
        }
    except Exception as e:
        results['client_login'] = {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'is_authenticated': client.is_authenticated()
        }
    
    # Comparación
    if results['direct_login'].get('success') and results['client_login'].get('success'):
        session_direct = results['direct_login'].get('session_id')
        session_client = results['client_login'].get('session_id')
        
        results['comparison'] = {
            'sessions_match': session_direct == session_client,
            'both_successful': True,
            'note': 'Ambas autenticaciones fueron exitosas'
        }
    else:
        results['comparison'] = {
            'sessions_match': False,
            'both_successful': False,
            'note': 'Una o ambas autenticaciones fallaron'
        }
    
    # Determinar status code
    if results['direct_login'].get('success') and results['client_login'].get('success'):
        http_status = status.HTTP_200_OK
    elif results['direct_login'].get('success') or results['client_login'].get('success'):
        http_status = status.HTTP_207_MULTI_STATUS
    else:
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    return Response({
        'success': results['comparison']['both_successful'],
        'results': results
    }, status=http_status)
