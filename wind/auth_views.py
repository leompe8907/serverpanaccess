import logging

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

from wind.auth_serializers import GoogleIdTokenSocialLoginSerializer
from wind.functions.getSubscriberLoginInfo import CallGetSubscriberLoginInfo
from wind.models import SubscriberEmailRegistry

logger = logging.getLogger(__name__)


class GoogleLoginView(SocialLoginView):
    """
    Vista para procesar el login con Google mediante API REST.
    El cliente (frontend) envía el JWT de Google Identity en 'access_token';
    el serializer lo trata como id_token para que allauth decodifique el JWT.
    """
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client
    serializer_class = GoogleIdTokenSocialLoginSerializer

    callback_url = 'http://localhost:8000/accounts/google/login/callback/'

    def get_response(self):
        """
        Sobrescribimos la respuesta por defecto para también incluir las 
        credenciales nativas de PanAccess (login1, password).
        De esta manera, la app frontend puede tomar estas credenciales y
        solicitar el session_id directamente a PanAccess de forma autónoma.
        """
        response = super().get_response()
        user = self.user
        
        try:
            # Buscar el registro de correo para obtener el subscriber_code
            registry = SubscriberEmailRegistry.objects.get(email=user.email)
            subscriber_code = registry.subscriber_code
            
            # Llamar directamente a PanAccess para obtener login1 y password original
            login_info = CallGetSubscriberLoginInfo(subscriber_code=subscriber_code)
            
            panaccess_credentials = {
                'login1': login_info.get('login1'),
                'password': login_info.get('password'),
                'login2': login_info.get('login2', ''),
                'subscriberCode': subscriber_code
            }
            response.data['panaccess_credentials'] = panaccess_credentials
            
        except SubscriberEmailRegistry.DoesNotExist:
            logger.warning(f"No se encontraron credenciales para el usuario {user.email}")
            response.data['panaccess_credentials'] = None
        except Exception as e:
            logger.error(f"Error obteniendo credenciales de PanAccess para la vista: {str(e)}")
            response.data['panaccess_credentials'] = None

        return response
