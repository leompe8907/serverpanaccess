"""
Vista para crear nuevos suscriptores en PanAccess.

El código del suscriptor se genera automáticamente con formato AUTO + número.
El supervisor se fija automáticamente a "AUTOMATICO".
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.serializers import CreateSubscriberSerializer
from wind.services import get_panaccess
from wind.exceptions import PanAccessException
from wind.utils.subscriber_code_generator import generate_unique_subscriber_code

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_subscriber_view(request):
    """
    Crea un nuevo suscriptor en PanAccess.
    
    El código del suscriptor se genera automáticamente con formato AUTO + número.
    El supervisor se fija automáticamente a "AUTOMATICO".
    
    Body (JSON):
    {
        "hcId": "HC123",        // Requerido
        "lastName": "Pérez",    // Requerido
        "firstName": "Juan",     // Requerido
        "comment": "Comentario"  // Opcional
    }
    """
    serializer = CreateSubscriberSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': 'Datos inválidos',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    panaccess = get_panaccess()
    
    try:
        # Generar código único automáticamente (formato AUTO + número)
        logger.info("Generando código único de suscriptor...")
        subscriber_code = generate_unique_subscriber_code(prefix='AUTO')
        logger.info(f"Código generado: {subscriber_code}")
        
        # Crear el suscriptor
        logger.info(f"Creando suscriptor: {subscriber_code}")
        # PanAccess requiere el parámetro 'subscriber' como objeto
        subscriber_obj = {
            'code': subscriber_code,
            'hcId': data['hcId'],
            'supervisor': 'AUTOMATICO',  # Fijo
            'lastName': data['lastName'],
            'firstName': data['firstName'],
            'countryCode': 'US',  # Valor por defecto
        }
        
        # Agregar comment solo si tiene valor
        if data.get('comment'):
            subscriber_obj['comment'] = data.get('comment')
        
        subscriber_params = {
            'subscriber': subscriber_obj
        }
        
        response = panaccess.call('addSubscriber', subscriber_obj)
        
        if not response.get('success'):
            error_message = response.get('errorMessage', 'Error desconocido al crear suscriptor')
            logger.error(f"Error al crear suscriptor: {error_message}")
            raise PanAccessException(error_message)
        
        # Verificar que el código retornado coincida
        returned_code = response.get('answer')
        if returned_code and returned_code != subscriber_code:
            logger.warning(f"Código retornado ({returned_code}) difiere del enviado ({subscriber_code})")
            subscriber_code = returned_code
        
        logger.info(f"Suscriptor {subscriber_code} creado exitosamente")
        
        return Response({
            'success': True,
            'message': 'Suscriptor creado exitosamente',
            'subscriber_code': subscriber_code,
            'data': {
                'code': subscriber_code,
                'hcId': data['hcId'],
                'supervisor': 'AUTOMATICO',
                'lastName': data['lastName'],
                'firstName': data['firstName'],
                'comment': data.get('comment')
            }
        }, status=status.HTTP_201_CREATED)
        
    except PanAccessException as e:
        logger.error(f"Error de PanAccess: {str(e)}")
        return Response({
            'success': False,
            'error_type': 'PanAccessException',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

