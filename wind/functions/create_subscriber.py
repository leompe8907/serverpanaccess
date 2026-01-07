"""
Vista para crear nuevos suscriptores en PanAccess.

El código del suscriptor (documento) se envía desde el frontend.
El supervisor se fija automáticamente a "AUTOMATICO".
Incluye validación de email y documento para prevenir cuentas duplicadas.
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from wind.serializers import CreateSubscriberSerializer
from wind.services import get_panaccess
from wind.exceptions import PanAccessException
from wind.utils.subscriber_code_generator import generate_unique_subscriber_code
from wind.models import SubscriberEmailRegistry
from wind.utils.email_validation import validate_email_for_registration

from appConfig import PanaccessConfig

PanaccessConfig.validate()
hcId = PanaccessConfig.HCID

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_subscriber_view(request):
    """
    Crea un nuevo suscriptor en PanAccess.
    
    El código del suscriptor se genera automáticamente con formato AUTO + número.
    El supervisor se fija automáticamente a "AUTOMATICO".
    
    Valida email para prevenir múltiples cuentas duplicadas.
    Si se proporcionan email o teléfono, se agregan automáticamente como contactos.
    
    Body (JSON):
    {
        "lastName": "Pérez",       // Requerido
        "firstName": "Juan",       // Requerido
        "email": "juan@example.com", // Requerido
        "phone": "+1234567890",     // Opcional
        "hcId": "HC123",           // Opcional
        "comment": "Comentario",   // Opcional
        "countryCode": "AR",       // Opcional (default: "DO")
        "regionId": 588,           // Opcional
        "technicalNotes": "...",   // Opcional
        "caf": "..."               // Opcional
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
    
    # VALIDACIÓN: Verificar email único
    email = data.get('email')
    
    if not email:
        return Response({
            'success': False,
            'message': 'El email es requerido para el registro',
            'errors': {'email': ['Este campo es requerido.']}
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Normalizar email (minúsculas, sin espacios)
    email_normalized = email.lower().strip()
    
    # Validar si el email puede usarse para registro
    is_valid, validation_message, email_registry = validate_email_for_registration(email_normalized)
    
    if not is_valid:
        return Response({
            'success': False,
            'message': validation_message,
            'error_type': 'EmailAlreadyRegistered',
            'errors': {
                'email': [validation_message]
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Generar código único automáticamente (formato AUTO + número)
        logger.info("Generando código único de suscriptor...")
        subscriber_code = generate_unique_subscriber_code(prefix='AUTO')
        logger.info(f"Código generado: {subscriber_code}")
        
        # Crear el suscriptor
        logger.info(f"Creando suscriptor: {subscriber_code}")
        # PanAccess requiere parámetros anidados con notación de corchetes
        # Formato esperado: subscriber[code], subscriber[hcId], subscriber[supervisor], etc.
        subscriber_params = {
            'subscriber[code]': subscriber_code,
            'subscriber[hcId]': hcId,  # Siempre enviar hcId, vacío si no se proporciona
            'subscriber[supervisor]': 'AUTOMATICO',  # Fijo
            'subscriber[lastName]': data['lastName'],
            'subscriber[firstName]': data['firstName'],
            'subscriber[countryCode]': request.data.get('countryCode', 'DO'),  # Usar el que viene o 'DO' por defecto
        }
        
        # Agregar regionId si está presente en el request
        if request.data.get('regionId'):
            subscriber_params['subscriber[regionId]'] = request.data.get('regionId')
        
        # Agregar comment solo si tiene valor
        if data.get('comment'):
            subscriber_params['subscriber[comment]'] = data.get('comment')
        
        # Agregar otros campos opcionales si vienen en el request
        optional_fields = ['technicalNotes', 'caf']
        for field in optional_fields:
            if request.data.get(field):
                subscriber_params[f'subscriber[{field}]'] = request.data.get(field)
        
        # Log de los parámetros que se enviarán (para debugging)
        logger.info(f"Parámetros a enviar a PanAccess: {subscriber_params}")
        
        response = panaccess.call('addSubscriber', subscriber_params)
        
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
        
        # Registrar email en el registro de validación
        email_registry, email_created = SubscriberEmailRegistry.objects.update_or_create(
            email=email_normalized,
            defaults={
                'subscriber_code': subscriber_code,
                'has_purchased': False,
            }
        )
        
        if email_created:
            logger.info(f"Registro de email creado: {email_normalized} -> {subscriber_code}")
        else:
            logger.info(f"Registro de email actualizado: {email_normalized} -> {subscriber_code}")
        
        # Agregar contactos si se proporcionaron
        contacts_added = []
        contacts_errors = []
        
        # Agregar email si está presente
        if data.get('email'):
            try:
                logger.info(f"Agregando email {data.get('email')} al suscriptor {subscriber_code}")
                contact_params = {
                    'subscriberCode': subscriber_code,
                    'contact[type]': 'email',
                    'contact[isBusiness]': False,
                    'contact[contact]': data.get('email')
                }
                contact_response = panaccess.call('addContactToSubscriber', contact_params)
                
                if contact_response.get('success'):
                    contacts_added.append({'type': 'email', 'value': data.get('email')})
                    logger.info(f"Email agregado exitosamente")
                else:
                    error_msg = contact_response.get('errorMessage', 'Error desconocido')
                    contacts_errors.append({'type': 'email', 'error': error_msg})
                    logger.error(f"Error al agregar email: {error_msg}")
            except Exception as e:
                contacts_errors.append({'type': 'email', 'error': str(e)})
                logger.error(f"Excepción al agregar email: {str(e)}", exc_info=True)
        
        # Agregar teléfono si está presente
        if data.get('phone'):
            try:
                logger.info(f"Agregando teléfono {data.get('phone')} al suscriptor {subscriber_code}")
                contact_params = {
                    'subscriberCode': subscriber_code,
                    'contact[type]': 'phone',
                    'contact[isBusiness]': False,
                    'contact[contact]': data.get('phone')
                }
                contact_response = panaccess.call('addContactToSubscriber', contact_params)
                
                if contact_response.get('success'):
                    contacts_added.append({'type': 'phone', 'value': data.get('phone')})
                    logger.info(f"Teléfono agregado exitosamente")
                else:
                    error_msg = contact_response.get('errorMessage', 'Error desconocido')
                    contacts_errors.append({'type': 'phone', 'error': error_msg})
                    logger.error(f"Error al agregar teléfono: {error_msg}")
            except Exception as e:
                contacts_errors.append({'type': 'phone', 'error': str(e)})
                logger.error(f"Excepción al agregar teléfono: {str(e)}", exc_info=True)
        
        # Preparar respuesta
        response_data = {
            'success': True,
            'message': 'Suscriptor creado exitosamente',
            'subscriber_code': subscriber_code,
            'data': {
                'code': subscriber_code,
                'supervisor': 'AUTOMATICO',
                'lastName': data['lastName'],
                'firstName': data['firstName'],
                'email': email_normalized,
                'hcId': data.get('hcId'),
                'comment': data.get('comment')
            }
        }
        
        # Agregar información de contactos a la respuesta
        if contacts_added:
            response_data['contacts_added'] = contacts_added
        if contacts_errors:
            response_data['contacts_errors'] = contacts_errors
            # Si hay errores en contactos, cambiar el mensaje pero mantener success=True
            # porque el suscriptor se creó correctamente
            response_data['message'] += '. Algunos contactos no pudieron agregarse.'
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
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

