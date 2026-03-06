import logging
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from wind.models import SubscriberEmailRegistry, SubscriberInfo
from wind.functions.create_subscriber import create_subscriber_view
from django.test import RequestFactory
import json

logger = logging.getLogger(__name__)

def create_subscriber_in_panaccess(email, first_name, last_name, auto_generate_code=True, comment=""):
    """
    Llama a la vista existente de creación de suscriptor simulando un request.
    """
    factory = RequestFactory()
    data = {
        'lastName': last_name,
        'firstName': first_name,
        'email': email,
        'comment': comment
    }
    # Asegurarse de que sea un POST request con application/json para que DRF lo parsee en request.data
    request = factory.post('/dummy/', data=json.dumps(data), content_type='application/json')
    response = create_subscriber_view(request)
    return response.data

class PanAccessSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adaptador personalizado para Allauth que intercepta el login social (Google)
    y sincroniza/registra al usuario en el sistema PanAccess.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Invocado después de que el usuario se autentica exitosamente con Google,
        pero antes de que se efectúe el login en Django.
        Aquí verificaremos o crearemos el suscriptor en PanAccess.
        """
        # Ignorar si es un inicio de sesión de cuenta vinculada existente
        if sociallogin.is_existing:
            return

        user_email = sociallogin.user.email
        if not user_email:
            logger.error("El proveedor social no retornó un email")
            raise ValidationError("Se requiere un correo electrónico del proveedor social.")

        logger.info(f"Procesando login social para email: {user_email}")

        # 1. Verificar si ya existe en PanAccess localmente (por correo)
        try:
            registry = SubscriberEmailRegistry.objects.get(email=user_email)
            subscriber_code = registry.subscriber_code
            logger.info(f"Usuario existente encontrado en registro: {subscriber_code}")
            
            # Si el usuario no fue creado en DB en un inicio de sesión anterior
            # Allauth lo enlazará automáticamente basándose en el email
            return

        except SubscriberEmailRegistry.DoesNotExist:
            logger.info(f"Email no registrado: {user_email}. Procediendo a creación automática en PanAccess.")
            
            # Extraer nombres de la cuenta social
            extra_data = sociallogin.account.extra_data
            first_name = extra_data.get('given_name', sociallogin.user.first_name)
            last_name = extra_data.get('family_name', sociallogin.user.last_name)
            
            if not last_name:
                last_name = "Social Login"  # PanAccess requiere lastName
            if not first_name:
                first_name = user_email.split('@')[0]

            # 2. Crear el suscriptor en PanAccess
            # Notemos que en un escenario ideal, esto debería ser asíncrono o manejar errores elegantemente.
            try:
                # Código autogenerado en create_subscriber_in_panaccess si code es None
                result = create_subscriber_in_panaccess(
                    email=user_email,
                    first_name=first_name,
                    last_name=last_name,
                    auto_generate_code=True,
                    comment="Creado vía Google Social Login"
                )
                
                if result.get('success'):
                    sub_code = result.get('subscriber_code')
                    logger.info(f"Suscriptor creado en PanAccess exitosamente: {sub_code}")
                    # create_subscriber_in_panaccess ya se encarga de poblar SubscriberEmailRegistry
                else:
                    logger.error(f"Falla al crear suscriptor en PanAccess: {result.get('message')}")
                    raise ValidationError(f"No se pudo crear la cuenta en el sistema proveedor: {result.get('message')}")
                    
            except Exception as e:
                logger.error(f"Error crítico conectando con PanAccess durante Social Login: {str(e)}")
                raise ValidationError("Error al procesar el registro con PanAccess. Inténtalo más tarde.")

    def save_user(self, request, sociallogin, form=None):
        """
        Guarda el usuario local en Django. Aseguramos que el nombre esté sincronizado.
        """
        user = super().save_user(request, sociallogin, form)
        
        extra_data = sociallogin.account.extra_data
        user.first_name = extra_data.get('given_name', user.first_name)
        user.last_name = extra_data.get('family_name', user.last_name)
        user.save()
        
        return user
