"""
Vista para crear nuevos suscriptores en PanAccess.

El código del suscriptor (documento) se envía desde el frontend.
El supervisor se fija automáticamente a "AUTOMATICO".
Incluye validación de email y documento para prevenir cuentas duplicadas.

Seguridad (roadmap #7): registro público sin JWT, pero con throttling estricto
y posibilidad de desactivar el endpoint HTTP en prod (flujo social usa bypass interno).
"""
import logging
import base64

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from wind.throttles import RegisterThrottle
from django.utils import timezone
from django.core.signing import TimestampSigner

from wind.serializers import CreateSubscriberSerializer
from wind.services import get_panaccess
from wind.exceptions import PanAccessException, PanAccessAPIError
from wind.utils.subscriber_code_generator import generate_unique_subscriber_code, validate_subscriber_code_uniqueness
from wind.models import SubscriberEmailRegistry
from wind.utils.email_validation import validate_email_for_registration
from wind.utils.phone_validation import normalize_phone

from appConfig import FeatureConfig, PanaccessConfig

PanaccessConfig.validate()
hcId = PanaccessConfig.HCID

logger = logging.getLogger(__name__)


def _parse_contact_id(answer) -> int | None:
    """Extrae contactId de la respuesta de addContactToSubscriber."""
    if answer is None:
        return None
    if isinstance(answer, bool):
        return None
    if isinstance(answer, int):
        return answer
    if isinstance(answer, str):
        stripped = answer.strip()
        if stripped.isdigit():
            return int(stripped)
        return None
    if isinstance(answer, dict):
        for key in ("contactId", "contact_id", "id", "contactID"):
            value = answer.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None


def _contact_value_matches(item: dict, target: str) -> bool:
    for key in ("contact", "email", "value", "address"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.lower().strip() == target:
            return True
    return False


def _find_email_contact_id_in_subscriber(subscriber_row: dict | None, email_normalized: str) -> int | None:
    """Busca contactId del email en la fila devuelta por getSubscriber / getExtendedSubscriber."""
    if not subscriber_row:
        return None

    target = email_normalized.lower().strip()
    emails = subscriber_row.get("emails")
    if not emails:
        return None

    items = emails if isinstance(emails, list) else [emails]
    for item in items:
        if isinstance(item, dict) and _contact_value_matches(item, target):
            contact_id = _parse_contact_id(item)
            if contact_id is not None:
                return contact_id
    return None


def _resolve_email_contact_id(panaccess, subscriber_code: str, add_contact_response: dict, email_normalized: str) -> int | None:
    """Obtiene contactId desde addContact o, en su defecto, consultando el suscriptor en PanAccess."""
    contact_id = _parse_contact_id((add_contact_response or {}).get("answer"))
    if contact_id is not None:
        logger.info(
            "[ValidateContact] contactId=%s obtenido de addContactToSubscriber (subscriber=%s)",
            contact_id,
            subscriber_code,
        )
        return contact_id

    logger.warning(
        "[ValidateContact] addContactToSubscriber no devolvió contactId utilizable "
        "(subscriber=%s, email=%s, answer=%r). Consultando suscriptor en PanAccess...",
        subscriber_code,
        email_normalized,
        (add_contact_response or {}).get("answer"),
    )
    try:
        from wind.functions.getSubscriber import CallGetSubscriber

        row = CallGetSubscriber(subscriber_code=subscriber_code)
        contact_id = _find_email_contact_id_in_subscriber(row, email_normalized)
        if contact_id is not None:
            logger.info(
                "[ValidateContact] contactId=%s obtenido vía getSubscriber (subscriber=%s)",
                contact_id,
                subscriber_code,
            )
        else:
            logger.error(
                "[ValidateContact] No se encontró contactId del email en getSubscriber "
                "(subscriber=%s, email=%s, emails=%r)",
                subscriber_code,
                email_normalized,
                row.get("emails") if row else None,
            )
        return contact_id
    except Exception as exc:
        logger.error(
            "[ValidateContact] Error resolviendo contactId vía getSubscriber "
            "(subscriber=%s, email=%s): %s",
            subscriber_code,
            email_normalized,
            exc,
            exc_info=True,
        )
        return None


def _validate_email_contact_of_subscriber(
    panaccess,
    subscriber_code: str,
    contact_id: int,
    email_normalized: str,
) -> tuple[bool, str | None]:
    """
    Marca el email como validado y opcionalmente como login alternativo (asLogin=True).
    Retorna (ok, mensaje_error).
    """
    # PanAccess (según WSDL) define xsd:boolean; en algunos entornos el modo "function"
    # es sensible a que se envíe como 1/0 (estilo SOAP) en vez de True/False.
    validate_params = {
        "code": subscriber_code,
        "contactId": contact_id,
        "asLogin": 1,
        # 'overrideContact' es string en WSDL. Para email, enviamos el mismo valor
        # que acabamos de agregar para reafirmarlo antes de validarlo.
        "overrideContact": email_normalized,
    }
    logger.info(
        "[ValidateContact] Llamando validateContactOfSubscriber "
        "(subscriber=%s, contactId=%s, email=%s, asLogin=True, overrideContact=%s)",
        subscriber_code,
        contact_id,
        email_normalized,
        email_normalized,
    )
    try:
        # Algunas instancias publican la operación sin prefijo "cv" y otras con "cv".
        # Intentamos primero sin prefijo (como el resto de este proyecto) y fallback con prefijo.
        try:
            response = panaccess.call("validateContactOfSubscriber", validate_params)
            func_used = "validateContactOfSubscriber"
        except PanAccessException:
            response = panaccess.call("cvValidateContactOfSubscriber", validate_params)
            func_used = "cvValidateContactOfSubscriber"

        logger.info(
            "[ValidateContact] Email validado correctamente "
            "(subscriber=%s, contactId=%s, func=%s, answer=%r)",
            subscriber_code,
            contact_id,
            func_used,
            response.get("answer"),
        )
        return True, None
    except PanAccessAPIError as exc:
        logger.error(
            "[ValidateContact] FALLÓ validateContactOfSubscriber | "
            "subscriber=%s contactId=%s email=%s asLogin=True overrideContact=%s | "
            "error=%s | error_code=%s | status_code=%s | params=%s",
            subscriber_code,
            contact_id,
            email_normalized,
            email_normalized,
            exc,
            getattr(exc, "error_code", None),
            getattr(exc, "status_code", None),
            validate_params,
            exc_info=True,
        )
        return False, str(exc)
    except PanAccessException as exc:
        logger.error(
            "[ValidateContact] FALLÓ validateContactOfSubscriber (PanAccess) | "
            "subscriber=%s contactId=%s email=%s asLogin=True| error=%s | params=%s",
            subscriber_code,
            contact_id,
            email_normalized,
            exc,
            validate_params,
            exc_info=True,
        )
        return False, str(exc)
    except Exception as exc:
        logger.error(
            "[ValidateContact] FALLÓ validateContactOfSubscriber (inesperado) | "
            "subscriber=%s contactId=%s email=%s asLogin=True| error=%s | params=%s",
            subscriber_code,
            contact_id,
            email_normalized,
            exc,
            validate_params,
            exc_info=True,
        )
        return False, str(exc)


def _create_subscriber_public_enabled() -> bool:
    return FeatureConfig.CREATE_SUBSCRIBER_PUBLIC_ENABLED


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
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
    if not getattr(request, "wind_internal_create", False) and not _create_subscriber_public_enabled():
        return Response(
            {
                "success": False,
                "message": (
                    "Registro HTTP deshabilitado. Use login social o "
                    "CREATE_SUBSCRIBER_PUBLIC_ENABLED=true en entornos controlados."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

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

    # Normalizar y validar teléfono (si se proporciona)
    phone_normalized = ""
    if data.get("phone"):
        try:
            default_region = (request.data.get("countryCode") or "DO").upper()
            phone_normalized = normalize_phone(data.get("phone"), default_region=default_region)
        except ValueError:
            return Response({
                'success': False,
                'message': 'Datos inválidos',
                'errors': {'phone': ['Teléfono inválido. Verifica el formato e inténtalo de nuevo.']}
            }, status=status.HTTP_400_BAD_REQUEST)
    
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
        
        # Obtener información completa del suscriptor desde PanAccess para guardarlo en la BD local
        subscriber_data_for_db = None
        smartcards_list = None
        
        try:
            logger.info(f"[DB] Obteniendo información completa del suscriptor {subscriber_code} desde PanAccess")
            
            # Intentar obtener el suscriptor desde getListOfExtendedSubscribers
            # Buscar en los primeros registros (el suscriptor recién creado debería estar al inicio)
            from wind.functions.getSubscriber import CallListExtendedSubscribers, extract_first_email, extract_first_phone
            
            # Intentar importar parser de fechas
            try:
                from dateutil import parser
                parser_instance = parser
            except ImportError:
                logger.warning("[DB] python-dateutil no está instalado, las fechas pueden no parsearse correctamente")
                parser_instance = None
            
            # Buscar el suscriptor en los primeros lotes
            found_subscriber = None
            offset = 0
            limit = 100
            max_search = 3  # Buscar en los primeros 3 lotes (300 registros)
            
            for i in range(max_search):
                result = CallListExtendedSubscribers(session_id=None, offset=offset, limit=limit)
                rows = result.get("extendedSubscriberEntries") or result.get("subscriberEntries") or result.get("rows", [])
                
                for row in rows:
                    if row.get("subscriberCode") == subscriber_code:
                        found_subscriber = row
                        break
                
                if found_subscriber:
                    break
                
                offset += limit
            
            if found_subscriber:
                logger.info(f"[DB] Suscriptor {subscriber_code} encontrado en PanAccess")
                
                # Obtener smartcards asociadas
                smartcards_list = found_subscriber.get("smartcards")
                if smartcards_list:
                    logger.info(f"[DB] Encontradas {len(smartcards_list) if isinstance(smartcards_list, list) else 'N/A'} smartcards asociadas")
                else:
                    logger.info(f"[DB] No se encontraron smartcards asociadas al suscriptor")
                
                # Preparar datos para guardar en la BD
                subscriber_data_for_db = {
                    "id": subscriber_code,
                    "code": subscriber_code,
                    "lastName": found_subscriber.get("lastName"),
                    "firstName": found_subscriber.get("firstName"),
                    "smartcards": smartcards_list,  # Lista de smartcards
                    "regionId": found_subscriber.get("regionId"),
                    "countryCode": found_subscriber.get("countryCode"),
                    "caf": found_subscriber.get("caf"),
                    "supervisor": found_subscriber.get("supervisor", "AUTOMATICO"),
                    "comment": found_subscriber.get("comment"),
                    "ip": found_subscriber.get("ip"),
                    "emails": extract_first_email(found_subscriber.get("emails")),
                    "phones": extract_first_phone(found_subscriber.get("phones")),
                    "faxes": found_subscriber.get("faxes"),
                    "skypes": found_subscriber.get("skypes"),
                    "mobiles": found_subscriber.get("mobiles"),
                    "custodians": found_subscriber.get("custodians"),
                    "address1": found_subscriber.get("address1"),
                    "address2": found_subscriber.get("address2"),
                    "address3": found_subscriber.get("address3"),
                    "addressCount": found_subscriber.get("addressCount", 0),
                    "newsletterAccepted": found_subscriber.get("newsletterAccepted", False),
                    "tags": found_subscriber.get("tags"),
                    "uniqueLogin": found_subscriber.get("uniqueLogin"),
                }
                
                # Procesar fechas
                if found_subscriber.get("created"):
                    try:
                        if parser_instance:
                            subscriber_data_for_db["created"] = parser_instance.parse(found_subscriber.get("created"))
                        else:
                            subscriber_data_for_db["created"] = found_subscriber.get("created")
                    except Exception as e:
                        logger.warning(f"[DB] Error parseando fecha created: {e}")
                        subscriber_data_for_db["created"] = timezone.now()
                else:
                    subscriber_data_for_db["created"] = timezone.now()
                
                if found_subscriber.get("firstOrderTime"):
                    try:
                        if parser_instance:
                            subscriber_data_for_db["firstOrderTime"] = parser_instance.parse(found_subscriber.get("firstOrderTime"))
                        else:
                            subscriber_data_for_db["firstOrderTime"] = found_subscriber.get("firstOrderTime")
                    except Exception as e:
                        logger.warning(f"[DB] Error parseando fecha firstOrderTime: {e}")
                        subscriber_data_for_db["firstOrderTime"] = None
                else:
                    subscriber_data_for_db["firstOrderTime"] = None
                
                if found_subscriber.get("lastExpiryTime"):
                    try:
                        if parser_instance:
                            subscriber_data_for_db["lastExpiryTime"] = parser_instance.parse(found_subscriber.get("lastExpiryTime"))
                        else:
                            subscriber_data_for_db["lastExpiryTime"] = found_subscriber.get("lastExpiryTime")
                    except Exception as e:
                        logger.warning(f"[DB] Error parseando fecha lastExpiryTime: {e}")
                        subscriber_data_for_db["lastExpiryTime"] = None
                else:
                    subscriber_data_for_db["lastExpiryTime"] = None
                
                # Guardar en la base de datos local
                try:
                    from wind.serializers import ListOfSubscriberSerializer
                    
                    serializer = ListOfSubscriberSerializer(data=subscriber_data_for_db)
                    if serializer.is_valid():
                        subscriber_obj = serializer.save()
                        logger.info(f"[DB] Suscriptor {subscriber_code} guardado exitosamente en ListOfSubscriber")
                        logger.info(f"[DB] Smartcards guardadas: {smartcards_list}")
                    else:
                        logger.error(f"[DB] Error validando datos del suscriptor: {serializer.errors}")
                        # Intentar guardar sin serializer si falla la validación
                        try:
                            ListOfSubscriber.objects.update_or_create(
                                code=subscriber_code,
                                defaults=subscriber_data_for_db
                            )
                            logger.info(f"[DB] Suscriptor {subscriber_code} guardado usando update_or_create")
                        except Exception as e:
                            logger.error(f"[DB] Error guardando suscriptor con update_or_create: {str(e)}", exc_info=True)
                except Exception as e:
                    logger.error(f"[DB] Error guardando suscriptor en BD: {str(e)}", exc_info=True)
            else:
                logger.warning(f"[DB] No se pudo encontrar el suscriptor {subscriber_code} en PanAccess después de crearlo")
                
        except Exception as e:
            logger.error(f"[DB] Error obteniendo información del suscriptor desde PanAccess: {str(e)}", exc_info=True)
            # Continuar aunque falle, el suscriptor ya está creado en PanAccess
        
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
        email_validated = False
        email_validation_error = None
        
        # Agregar email como contacto
        email_contact_response = None
        try:
            logger.info(f"Agregando email {email_normalized} al suscriptor {subscriber_code}")
            contact_params = {
                'code': subscriber_code,  # PanAccess espera 'code', no 'subscriberCode'
                'type': 'email',  # Parámetros planos según documentación SOAP
                'isBusiness': False,
                'contact': email_normalized
            }
            email_contact_response = panaccess.call('addContactToSubscriber', contact_params)
            
            if email_contact_response.get('success'):
                contacts_added.append({'type': 'email', 'value': email_normalized})
                logger.info(f"Email agregado exitosamente")

                contact_id = _resolve_email_contact_id(
                    panaccess,
                    subscriber_code,
                    email_contact_response,
                    email_normalized,
                )
                if contact_id is not None:
                    email_validated, email_validation_error = _validate_email_contact_of_subscriber(
                        panaccess,
                        subscriber_code,
                        contact_id,
                        email_normalized,
                    )
                else:
                    email_validation_error = (
                        "No se pudo obtener contactId del email tras addContactToSubscriber"
                    )
                    logger.error(
                        "[ValidateContact] %s (subscriber=%s, email=%s, addContact_answer=%r)",
                        email_validation_error,
                        subscriber_code,
                        email_normalized,
                        email_contact_response.get("answer"),
                    )
            else:
                error_msg = email_contact_response.get('errorMessage', 'Error desconocido')
                contacts_errors.append({'type': 'email', 'error': error_msg})
                logger.error(f"Error al agregar email: {error_msg}")
        except Exception as e:
            contacts_errors.append({'type': 'email', 'error': str(e)})
            logger.error(f"Excepción al agregar email: {str(e)}", exc_info=True)
        
        # Agregar teléfono si está presente
        if phone_normalized:
            try:
                logger.info(f"Agregando teléfono {phone_normalized} al suscriptor {subscriber_code}")
                contact_params = {
                    'code': subscriber_code,  # PanAccess espera 'code', no 'subscriberCode'
                    'type': 'phone',  # Parámetros planos según documentación SOAP
                    'isBusiness': False,
                    'contact': phone_normalized
                }
                contact_response = panaccess.call('addContactToSubscriber', contact_params)
                
                if contact_response.get('success'):
                    contacts_added.append({'type': 'phone', 'value': phone_normalized})
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
            # Login alternativo: el email (útil para que el frontend lo muestre/guarde).
            # Nota: que esté aquí no implica que PanAccess lo acepte como login si existe unique_db_violation.
            'alternative_login': email_normalized,
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

        # Salidas del flujo de asignación (license block -> smartcards -> producto)
        assigned_smartcards = None
        product_add_result = None
        
        # Agregar información de contactos a la respuesta
        if contacts_added:
            response_data['contacts_added'] = contacts_added
        if contacts_errors:
            response_data['contacts_errors'] = contacts_errors
            # Si hay errores en contactos, cambiar el mensaje pero mantener success=True
            # porque el suscriptor se creó correctamente
            response_data['message'] += '. Algunos contactos no pudieron agregarse.'

        response_data['email_validated'] = email_validated
        if email_validation_error:
            response_data['email_validation_error'] = email_validation_error
            if email_validated is False and 'email' in {c.get('type') for c in contacts_added}:
                response_data['message'] += '. El email no pudo validarse en PanAccess (ver logs ValidateContact).'
        
        # Llamar a addLicenseBlockToSubscriber
        license_block_success = False
        license_block_error = None
        
        try:
            logger.info(f"[LicenseBlock] Llamando addLicenseBlockToSubscriber para suscriptor: {subscriber_code}")
            
            # Parámetros según documentación:
            # - sessionId: Se agrega automáticamente
            # - code: Código del suscriptor
            license_params = {
                'code': subscriber_code
            }
            
            logger.info(f"[LicenseBlock] Parámetros a enviar: {license_params}")
            
            license_response = panaccess.call('addLicenseBlockToSubscriber', license_params)
            
            logger.info(f"[LicenseBlock] Respuesta recibida - success={license_response.get('success')}")
            
            if license_response.get('success'):
                license_block_success = True
                logger.info(f"[LicenseBlock] License block agregado exitosamente al suscriptor {subscriber_code}")
                
                # Actualizar smartcards en la BD local después de addLicenseBlockToSubscriber
                try:
                    logger.info(f"[DB] Actualizando smartcards del suscriptor {subscriber_code} después de addLicenseBlockToSubscriber")
                    
                    # Obtener información actualizada del suscriptor desde PanAccess
                    from wind.functions.getSubscriber import CallListExtendedSubscribers
                    
                    # Buscar el suscriptor actualizado
                    found_subscriber_updated = None
                    offset = 0
                    limit = 100
                    max_search = 3
                    
                    for i in range(max_search):
                        result = CallListExtendedSubscribers(session_id=None, offset=offset, limit=limit)
                        rows = result.get("extendedSubscriberEntries") or result.get("subscriberEntries") or result.get("rows", [])
                        
                        for row in rows:
                            if row.get("subscriberCode") == subscriber_code:
                                found_subscriber_updated = row
                                break
                        
                        if found_subscriber_updated:
                            break
                        
                        offset += limit
                    
                    if found_subscriber_updated:
                        # Obtener smartcards actualizadas
                        updated_smartcards = found_subscriber_updated.get("smartcards")
                        logger.info(f"[DB] Smartcards actualizadas desde PanAccess: {updated_smartcards}")
                        assigned_smartcards = updated_smartcards
                        
                        # Actualizar solo el campo smartcards en la BD local
                        try:
                            subscriber_obj = ListOfSubscriber.objects.get(code=subscriber_code)
                            subscriber_obj.smartcards = updated_smartcards
                            subscriber_obj.save(update_fields=['smartcards'])
                            logger.info(f"[DB] Campo smartcards actualizado exitosamente para suscriptor {subscriber_code}")
                            logger.info(f"[DB] Smartcards guardadas: {updated_smartcards}")
                            
                            # Agregar productos a las smartcards asociadas
                            if updated_smartcards and isinstance(updated_smartcards, list) and len(updated_smartcards) > 0:
                                try:
                                    logger.info(f"[Products] Iniciando proceso para agregar productos a {len(updated_smartcards)} smartcards")
                                    
                                    # ProductId fijo
                                    product_id = 4639
                                    
                                    # Calcular fecha de expiración: 30 días desde la creación del suscriptor
                                    from datetime import timedelta
                                    created_date = subscriber_obj.created if subscriber_obj.created else timezone.now()
                                    expiry_time = created_date + timedelta(days=30)
                                    
                                    # Formatear fecha para PanAccess (formato esperado: YYYY-MM-DD HH:MM:SS)
                                    expiry_time_str = expiry_time.strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    logger.info(f"[Products] Agregando producto {product_id} a {len(updated_smartcards)} smartcards")
                                    logger.info(f"[Products] Fecha de expiración: {expiry_time_str} (30 días desde creación)")
                                    
                                    # Preparar parámetros para addProductToSmartcards
                                    # PanAccess puede esperar smartcards en diferentes formatos
                                    # Intentar primero con notación de corchetes (smartcards[0], smartcards[1], etc.)
                                    product_params = {
                                        'productId': product_id,
                                        'hcId': hcId,  # Usar hcId de la configuración
                                        'expiryTime': expiry_time_str
                                    }
                                    
                                    # Agregar smartcards con notación de corchetes
                                    for idx, smartcard in enumerate(updated_smartcards):
                                        if smartcard:  # Solo agregar si no está vacío
                                            product_params[f'smartcards[{idx}]'] = str(smartcard)
                                    
                                    logger.info(f"[Products] Parámetros a enviar: smartcards={len(updated_smartcards)} items (formato indexado), productId={product_id}, hcId={hcId}, expiryTime={expiry_time_str}")
                                    
                                    # Llamar a addProductToSmartcards
                                    product_response = panaccess.call('addProductToSmartcards', product_params)
                                    
                                    logger.info(f"[Products] Respuesta recibida - success={product_response.get('success')}")
                                    
                                    if product_response.get('success'):
                                        logger.info(f"[Products] Producto {product_id} agregado exitosamente a {len(updated_smartcards)} smartcards")
                                        product_add_result = {
                                            'success': True,
                                            'productId': product_id,
                                            'expiryTime': expiry_time_str,
                                            'smartcards_count': len(updated_smartcards),
                                        }
                                    else:
                                        error_msg = product_response.get('errorMessage', 'Error desconocido')
                                        logger.error(f"[Products] Error al agregar producto a smartcards: {error_msg}")
                                        product_add_result = {
                                            'success': False,
                                            'productId': product_id,
                                            'expiryTime': expiry_time_str,
                                            'errorMessage': error_msg,
                                        }
                                        
                                except Exception as e:
                                    logger.error(f"[Products] Excepción al agregar productos a smartcards: {str(e)}", exc_info=True)
                                    # No fallar el proceso completo si esto falla
                                    product_add_result = {
                                        'success': False,
                                        'errorMessage': str(e),
                                    }
                            else:
                                logger.info(f"[Products] No hay smartcards asociadas para agregar productos")
                                product_add_result = {
                                    'success': False,
                                    'errorMessage': 'No hay smartcards asociadas para agregar productos',
                                }
                        except ListOfSubscriber.DoesNotExist:
                            logger.warning(f"[DB] Suscriptor {subscriber_code} no encontrado en BD local para actualizar smartcards")
                        except Exception as e:
                            logger.error(f"[DB] Error actualizando smartcards en BD: {str(e)}", exc_info=True)
                    else:
                        logger.warning(f"[DB] No se pudo encontrar el suscriptor {subscriber_code} en PanAccess para actualizar smartcards")
                        
                except Exception as e:
                    logger.error(f"[DB] Error obteniendo smartcards actualizadas: {str(e)}", exc_info=True)
                    # No fallar el proceso completo si esto falla
            else:
                license_block_error = license_response.get('errorMessage', 'Error desconocido')
                # Error de negocio (ej: no hay licencias disponibles) -> tratar como warning
                if isinstance(license_block_error, str) and "txt_not_enough_streaming_licenses" in license_block_error:
                    logger.warning(f"[LicenseBlock] No hay licencias disponibles: {license_block_error}")
                else:
                    logger.error(f"[LicenseBlock] Error al agregar license block: {license_block_error}")
                
        except Exception as e:
            license_block_error = str(e)
            # Si es un caso esperado (licencias), no lo reportamos como error ruidoso con traceback.
            if "txt_not_enough_streaming_licenses" in license_block_error:
                logger.warning(f"[LicenseBlock] No hay licencias disponibles: {license_block_error}")
            else:
                logger.error(f"[LicenseBlock] Excepción al agregar license block: {str(e)}", exc_info=True)
        
        # Agregar información de license block a la respuesta
        if license_block_success:
            response_data['license_block_added'] = True
            response_data['message'] += '. License block agregado correctamente.'
        else:
            response_data['license_block_added'] = False
            response_data['license_block_error'] = license_block_error
            response_data['message'] += '. No se pudo agregar el license block.'

        # Link firmado (corto) para mostrar credenciales inmediatamente tras registro.
        # Incluye estado de provisión (license block) para mostrar mensaje al usuario.
        signer = TimestampSigner(salt="wind.credentials")
        # Incluimos el email (b64 urlsafe) para poder mostrarlo como "usuario alternativo"
        # en la pantalla de credenciales, sin depender de login2.
        # Formato: "<code>|<license_ok_int>|<b64(license_error)>|<b64(email)>"
        license_err_raw = (response_data.get("license_block_error") or "")
        license_err_b64 = base64.urlsafe_b64encode(license_err_raw.encode("utf-8")).decode("ascii")
        email_b64 = base64.urlsafe_b64encode(email_normalized.encode("utf-8")).decode("ascii")
        payload = f"{subscriber_code}|{int(bool(response_data.get('license_block_added')))}|{license_err_b64}|{email_b64}"
        token = signer.sign(payload)
        response_data["credentials_url"] = f"/wind/credentials/?t={token}"

        # Exponer smartcards y resultado de producto en la respuesta (para el flujo social)
        response_data['assigned_smartcards'] = assigned_smartcards
        response_data['product_add_result'] = product_add_result
        
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

