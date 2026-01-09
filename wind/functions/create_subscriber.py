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
from wind.utils.subscriber_code_generator import generate_unique_subscriber_code, validate_subscriber_code_uniqueness
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
    
    El código del suscriptor puede ser proporcionado por el usuario (normalmente el documento)
    o generado automáticamente con formato AUTO + número.
    El supervisor se fija automáticamente a "AUTOMATICO".
    
    Valida email para prevenir múltiples cuentas duplicadas.
    Si se proporcionan email o teléfono, se agregan automáticamente como contactos.
    
    Body (JSON):
    {
        "code": "123456789",            // Opcional - código personalizado (documento). Si no se proporciona, se genera automáticamente
        "lastName": "Pérez",            // Requerido
        "firstName": "Juan",            // Requerido
        "email": "juan@example.com",    // Requerido
        "phone": "+1234567890",         // Opcional
        "hcId": "HC123",                // Opcional
        "countryCode": "DO",            // Opcional (default: "DO")
        "comment": "Comentario",        // Opcional
        "regionId": 588,                // Opcional
        "technicalNotes": "...",        // Opcional
        "caf": "..."                    // Opcional
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
    logger.info(f"Datos recibidos y validados: {list(data.keys())}")
    
    # 2. Validar campos requeridos
    email = data.get('email')
    if not email:
        return Response({
            'success': False,
            'message': 'El email es requerido para el registro',
            'errors': {'email': ['Este campo es requerido.']}
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Normalizar email
    email_normalized = email.lower().strip()
    logger.info(f"Validando email normalizado: '{email_normalized}'")
    
    # 3. Validar code Y email en paralelo contra la base de datos
    from wind.models import ListOfSubscriber
    errors = {}
    
    # 3.1 Validar code (solo si se proporciona)
    user_provided_code = data.get('code')
    if user_provided_code and user_provided_code.strip():
        subscriber_code_provided = user_provided_code.strip()
        logger.info(f"Validando código proporcionado: '{subscriber_code_provided}'")
        
        if not validate_subscriber_code_uniqueness(subscriber_code_provided):
            errors['code'] = [f'El código "{subscriber_code_provided}" ya está en uso. Por favor, elija otro.']
            logger.warning(f"Código '{subscriber_code_provided}' ya existe en BD")
    
    # 3.2 Validar email (siempre)
    # Primero en SubscriberEmailRegistry
    is_valid, validation_message, email_registry = validate_email_for_registration(email_normalized)
    logger.info(f"Validación en SubscriberEmailRegistry: is_valid={is_valid}, message='{validation_message}'")
    
    if not is_valid:
        errors['email'] = [validation_message]
        logger.warning(f"Email '{email_normalized}' no válido según SubscriberEmailRegistry")
    
    # Luego en ListOfSubscriber
    email_exists = ListOfSubscriber.objects.filter(emails__iexact=email_normalized).exists()
    logger.info(f"Buscando email en ListOfSubscriber: '{email_normalized}', existe={email_exists}")
    
    if email_exists:
        subscriber_with_email = ListOfSubscriber.objects.filter(emails__iexact=email_normalized).first()
        logger.warning(f"Email '{email_normalized}' ya existe en suscriptor: code={subscriber_with_email.code if subscriber_with_email else 'N/A'}, id={subscriber_with_email.id if subscriber_with_email else 'N/A'}")
        errors['email'] = ['Este email ya está en uso por otro suscriptor.']
    
    # 3.3 Si hay errores, detener el flujo
    if errors:
        return Response({
            'success': False,
            'message': 'Los parámetros proporcionados ya existen en la base de datos',
            'error_type': 'DuplicateData',
            'errors': errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 4. Si ambos son únicos (o code no se proporcionó y email es único), continuar
    try:
        panaccess = get_panaccess()
        
        # Determinar el código del suscriptor
        if user_provided_code and user_provided_code.strip():
            subscriber_code = user_provided_code.strip()
            logger.info(f"Usando código proporcionado: {subscriber_code}")
        else:
            # Generar código único automáticamente (formato AUTO + número)
            logger.info("Generando código único de suscriptor automáticamente...")
            subscriber_code = generate_unique_subscriber_code(prefix='AUTO')
            logger.info(f"Código generado automáticamente: {subscriber_code}")
        
        # Crear el suscriptor
        logger.info(f"Creando suscriptor: {subscriber_code}")
        # PanAccess requiere parámetros anidados con notación de corchetes
        # Formato esperado: subscriber[code], subscriber[hcId], subscriber[supervisor], etc.
        subscriber_params = {
            'subscriber[code]': subscriber_code,  # Usar el código determinado arriba
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
        
        # Agregar email como contacto
        try:
            logger.info(f"Agregando email {email_normalized} al suscriptor {subscriber_code}")
            contact_params = {
                'code': subscriber_code,  # PanAccess espera 'code', no 'subscriberCode'
                'contact[type]': 'email',
                'contact[isBusiness]': False,
                'contact[contact]': email_normalized
            }
            contact_response = panaccess.call('addContactToSubscriber', contact_params)
            
            if contact_response.get('success'):
                contacts_added.append({'type': 'email', 'value': email_normalized})
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
                    'code': subscriber_code,  # PanAccess espera 'code', no 'subscriberCode'
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

