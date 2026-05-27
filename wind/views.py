"""
Vistas para la aplicación wind.
"""
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from wind.functions.getSubscriberLoginInfo import CallGetSubscriberLoginInfo


def login_page_view(request):
    """
    Página principal de acceso: email/contraseña, registro y login social.
    """
    google_client_id = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']
    facebook_app_id = settings.SOCIALACCOUNT_PROVIDERS['facebook']['APP']['client_id']
    return render(
        request,
        'wind/login.html',
        {
            'google_client_id': google_client_id,
            'facebook_app_id': facebook_app_id,
        },
    )


def dashboard_view(request):
    """Área de usuario autenticado (JWT en el navegador)."""
    return render(request, "wind/dashboard.html")


def subscriber_test_view(request):
    """Página de prueba: solo muestra subscriber de /api/v1/profile/me/ con logs."""
    return render(request, "wind/subscriber_test.html")


def login_test_view(request):
    """
    Página de prueba para iniciar sesión con Google.
    Muestra un botón que enlaza al flujo de allauth (Google).
    """
    google_client_id = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']
    context = {
        'google_client_id': google_client_id,
    }
    return render(request, 'wind/login_test.html', context)


def login_facebook_test_view(request):
    """
    Página de prueba para iniciar sesión con Facebook (SDK JS) y consumir el endpoint REST.
    """
    facebook_app_id = settings.SOCIALACCOUNT_PROVIDERS['facebook']['APP']['client_id']
    context = {
        'facebook_app_id': facebook_app_id,
    }
    return render(request, 'wind/login_test_facebook.html', context)


@ensure_csrf_cookie
def register_view(request):
    """
    Página web para registrar suscriptores vía /wind/create-subscriber/.
    Se renderiza en el mismo origen para evitar CORS.
    """
    return render(request, 'wind/register.html', {'debug': bool(settings.DEBUG)})


def credentials_view(request):
    """
    Página web para mostrar credenciales PanAccess recién creadas.
    Se accede vía token firmado y expirable (?t=...).
    """
    token = request.GET.get("t", "")
    if not token:
        return render(request, "wind/credentials.html", {"error": "Enlace inválido o incompleto."}, status=400)

    signer = TimestampSigner(salt="wind.credentials")
    try:
        raw = signer.unsign(token, max_age=10 * 60)  # 10 minutos
    except SignatureExpired:
        return render(request, "wind/credentials.html", {"error": "Este enlace expiró. Regístrate de nuevo o solicita recuperación."}, status=400)
    except BadSignature:
        return render(request, "wind/credentials.html", {"error": "Enlace inválido."}, status=400)

    # Formato esperado (nuevo):
    # "<subscriber_code>|<license_ok_int>|<b64(license_error)>|<b64(email)>"
    # Formato anterior:
    # "<subscriber_code>|<license_ok_int>|<license_error>"
    parts = str(raw).split("|")
    subscriber_code = parts[0] if parts else ""
    license_ok = parts[1] if len(parts) > 1 else ""
    license_err = ""
    email_from_token = ""

    if len(parts) >= 4:
        import base64

        try:
            license_err = base64.urlsafe_b64decode(parts[2].encode("ascii")).decode("utf-8")
        except Exception:
            license_err = parts[2]

        try:
            email_from_token = base64.urlsafe_b64decode(parts[3].encode("ascii")).decode("utf-8")
        except Exception:
            email_from_token = parts[3]
    else:
        # Compatibilidad con tokens viejos (sin b64).
        license_err = parts[2] if len(parts) > 2 else ""

    try:
        login_info = CallGetSubscriberLoginInfo(subscriber_code=subscriber_code)
        # Mostrar el email como "usuario alternativo" cuando viene en el token.
        # Esto evita enseñar el login2 (que puede ser un identificador interno).
        login2_display = (email_from_token or "").strip() or (login_info.get("login2") or "")
        context = {
            "login2": login2_display,
            "login1": login_info.get("login1") or "",
            "password": login_info.get("password") or "",
            "license_block_added": True if str(license_ok) == "1" else False,
            "license_block_error": license_err or None,
        }
        return render(request, "wind/credentials.html", context)
    except Exception:
        return render(
            request,
            "wind/credentials.html",
            {"error": "No pudimos cargar tus credenciales en este momento. Intenta de nuevo en unos segundos."},
            status=500,
        )
