"""
Función para marcar cuando un usuario compra contenido.
Esto permite que el usuario pueda crear nuevas cuentas si lo desea.
"""
import logging
from django.utils import timezone
from wind.models import SubscriberEmailRegistry, SubscriberDocumentRegistry

logger = logging.getLogger(__name__)


def mark_email_as_purchased(email, subscriber_code=None):
    """
    Marca un email como que ha comprado contenido.
    Esto permite que el usuario pueda crear nuevas cuentas si lo desea.
    
    Args:
        email: Email del usuario
        subscriber_code: Código del suscriptor (opcional)
    
    Returns:
        bool: True si se marcó exitosamente, False si no se encontró el registro
    """
    email_normalized = email.lower().strip()
    
    try:
        registry = SubscriberEmailRegistry.objects.get(email=email_normalized)
        registry.has_purchased = True
        registry.purchased_at = timezone.now()
        if subscriber_code:
            registry.subscriber_code = subscriber_code
        registry.save()
        logger.info(f"Email {email_normalized} marcado como comprado")
        return True
    except SubscriberEmailRegistry.DoesNotExist:
        logger.warning(f"Intento de marcar compra para email no registrado: {email_normalized}")
        return False


def mark_document_as_purchased(document, subscriber_code=None):
    """
    Marca un documento como que ha comprado contenido.
    
    Args:
        document: Documento del usuario (normalizado)
        subscriber_code: Código del suscriptor (opcional)
    
    Returns:
        bool: True si se marcó exitosamente, False si no se encontró el registro
    """
    document_normalized = document.strip().upper()
    
    try:
        registry = SubscriberDocumentRegistry.objects.get(document=document_normalized)
        registry.has_purchased = True
        registry.purchased_at = timezone.now()
        if subscriber_code:
            registry.subscriber_code = subscriber_code
        registry.save()
        logger.info(f"Documento {document_normalized} marcado como comprado")
        return True
    except SubscriberDocumentRegistry.DoesNotExist:
        logger.warning(f"Intento de marcar compra para documento no registrado: {document_normalized}")
        return False


def mark_as_purchased(email=None, document=None, subscriber_code=None):
    """
    Marca tanto email como documento como comprados.
    
    Args:
        email: Email del usuario (opcional)
        document: Documento del usuario (opcional)
        subscriber_code: Código del suscriptor (opcional)
    
    Returns:
        dict: Resultado de las operaciones {'email': bool, 'document': bool}
    """
    result = {'email': False, 'document': False}
    
    if email:
        result['email'] = mark_email_as_purchased(email, subscriber_code)
    
    if document:
        result['document'] = mark_document_as_purchased(document, subscriber_code)
    
    return result
