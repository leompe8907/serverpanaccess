"""
Vista para crear nuevos suscriptores en PanAccess.

Procesa un solo formulario que puede incluir:
- Datos del suscriptor
- Contactos (múltiples)
- Direcciones (múltiples)

Hace las llamadas secuenciales:
1. addSubscriber
2. AddContactToSubscriber (por cada contacto)
3. AddAddressToSubscriber (por cada dirección)
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
    
    El código del suscriptor se genera automáticamente si no se proporciona.
    
    Body (JSON):
    {
        "code": "SUB001",  // Opcional - se genera automáticamente si no se proporciona
        "hcId": "HC123",   // Requerido
        "countryCode": "US",  // Requerido (2 letras)
        "supervisor": "SUP001",  // Opcional
        "lastName": "Pérez",  // Opcional
        "firstName": "Juan",  // Opcional
        "comment": "Comentario",  // Opcional
        "technicalNotes": "Notas técnicas",  // Opcional
        "contacts": [  // Opcional
            {
                "type": "email",
                "isBusiness": false,
                "contact": "juan@example.com"
            }
        ],
        "addresses": [  // Opcional
            {
                "type": "private",
                "country": "US",
                "city": "New York",
                "zip": "10001",
                "street": "123 Main St"
            }
        ]
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
        # Generar código único si no se proporcionó
        subscriber_code = data.get('code')
        if not subscriber_code:
            logger.info("Generando código único de suscriptor...")
            subscriber_code = generate_unique_subscriber_code()
            logger.info(f"Código generado: {subscriber_code}")
        else:
            logger.info(f"Usando código proporcionado: {subscriber_code}")
        
        # 1. Crear el suscriptor
        logger.info(f"Creando suscriptor: {subscriber_code}")
        subscriber_params = {
            'subscriber': {
                'code': subscriber_code,
                'hcId': data['hcId'],
                'supervisor': data.get('supervisor'),
                'lastName': data.get('lastName'),
                'firstName': data.get('firstName'),
                'comment': data.get('comment'),
                'technicalNotes': data.get('technicalNotes'),
                'countryCode': data['countryCode'],
                'contacts': []  # Los contactos se agregan después
            }
        }
        
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
        
        logger.info(f"✅ Suscriptor {subscriber_code} creado exitosamente")
        
        results = {
            'subscriber_code': subscriber_code,
            'contacts': [],
            'addresses': []
        }
        
        # 2. Agregar contactos (si hay)
        contacts = data.get('contacts', [])
        if contacts:
            logger.info(f"Agregando {len(contacts)} contacto(s) al suscriptor {subscriber_code}")
        
        for idx, contact in enumerate(contacts):
            try:
                logger.info(f"Agregando contacto {idx+1}/{len(contacts)}: {contact['type']} = {contact['contact']}")
                contact_params = {
                    'code': subscriber_code,
                    'type': contact['type'],
                    'isBusiness': contact['isBusiness'],
                    'contact': contact['contact']
                }
                
                contact_response = panaccess.call('addContactToSubscriber', contact_params)
                
                if contact_response.get('success'):
                    contact_id = contact_response.get('answer')
                    results['contacts'].append({
                        'type': contact['type'],
                        'contact': contact['contact'],
                        'isBusiness': contact['isBusiness'],
                        'id': contact_id,
                        'success': True
                    })
                    logger.info(f"✅ Contacto agregado con ID: {contact_id}")
                else:
                    error_msg = contact_response.get('errorMessage', 'Error desconocido')
                    results['contacts'].append({
                        'type': contact['type'],
                        'contact': contact['contact'],
                        'success': False,
                        'error': error_msg
                    })
                    logger.warning(f"❌ Error agregando contacto: {error_msg}")
                    
            except Exception as e:
                logger.error(f"❌ Error agregando contacto: {str(e)}", exc_info=True)
                results['contacts'].append({
                    'type': contact['type'],
                    'contact': contact['contact'],
                    'success': False,
                    'error': str(e)
                })
        
        # 3. Agregar direcciones (si hay)
        addresses = data.get('addresses', [])
        if addresses:
            logger.info(f"Agregando {len(addresses)} dirección(es) al suscriptor {subscriber_code}")
        
        for idx, address in enumerate(addresses):
            try:
                logger.info(f"Agregando dirección {idx+1}/{len(addresses)}: tipo {address['type']}")
                address_params = {
                    'code': subscriber_code,
                    'address': {
                        'type': address['type'],
                        'name': address.get('name'),
                        'country': address['country'],
                        'city': address.get('city'),
                        'zip': address.get('zip'),
                        'street': address.get('street'),
                        'addition': address.get('addition'),
                        'addition2': address.get('addition2'),
                        'addition3': address.get('addition3'),
                        'zone': address.get('zone'),
                        'district': address.get('district'),
                        'ownership': address.get('ownership', 0),
                        'ownerName': address.get('ownerName'),
                        'ownerPhone': address.get('ownerPhone')
                    }
                }
                
                address_response = panaccess.call('addAddressToSubscriber', address_params)
                
                if address_response.get('success'):
                    address_id = address_response.get('answer')
                    results['addresses'].append({
                        'type': address['type'],
                        'id': address_id,
                        'success': True
                    })
                    logger.info(f"✅ Dirección agregada con ID: {address_id}")
                else:
                    error_msg = address_response.get('errorMessage', 'Error desconocido')
                    results['addresses'].append({
                        'type': address['type'],
                        'success': False,
                        'error': error_msg
                    })
                    logger.warning(f"❌ Error agregando dirección: {error_msg}")
                    
            except Exception as e:
                logger.error(f"❌ Error agregando dirección: {str(e)}", exc_info=True)
                results['addresses'].append({
                    'type': address['type'],
                    'success': False,
                    'error': str(e)
                })
        
        # Resumen final
        contacts_success = sum(1 for c in results['contacts'] if c.get('success'))
        addresses_success = sum(1 for a in results['addresses'] if a.get('success'))
        
        logger.info(f"✅ Proceso completado - Suscriptor: {subscriber_code}, "
                   f"Contactos: {contacts_success}/{len(contacts)}, "
                   f"Direcciones: {addresses_success}/{len(addresses)}")
        
        return Response({
            'success': True,
            'message': 'Suscriptor creado exitosamente',
            'subscriber_code': subscriber_code,
            'results': results,
            'summary': {
                'contacts_added': contacts_success,
                'contacts_total': len(contacts),
                'addresses_added': addresses_success,
                'addresses_total': len(addresses)
            }
        }, status=status.HTTP_201_CREATED)
        
    except PanAccessException as e:
        logger.error(f"❌ Error de PanAccess: {str(e)}")
        return Response({
            'success': False,
            'error_type': 'PanAccessException',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"💥 Error inesperado: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

