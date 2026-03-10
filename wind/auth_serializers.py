"""
Serializers para el flujo de login con Google (ID token desde el cliente).
Cuando el frontend envía el JWT de Google Identity en 'access_token',
lo tratamos como 'id_token' para que allauth decodifique el JWT en vez
de llamar a la API userinfo (que falla con un ID token).
"""
from dj_rest_auth.registration.serializers import SocialLoginSerializer


class GoogleIdTokenSocialLoginSerializer(SocialLoginSerializer):
    """
    Para Google: si el cliente envía solo 'access_token' (el JWT de
    Google Identity Services), lo usamos también como 'id_token' para
    que complete_login use _decode_id_token y no _fetch_user_info.
    """

    def validate(self, attrs):
        request = self._get_request()
        view = self.context.get('view')
        if view and getattr(view, 'adapter_class', None):
            adapter = view.adapter_class(request)
            if (
                adapter.provider_id == 'google'
                and attrs.get('access_token')
                and not attrs.get('id_token')
            ):
                attrs = attrs.copy()
                attrs['id_token'] = attrs['access_token']
        return super().validate(attrs)
