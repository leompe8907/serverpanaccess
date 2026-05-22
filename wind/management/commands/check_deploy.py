"""
Comprueba configuración lista para producción (roadmap #3–#4, #8–#9).
Ejecuta ``manage.py check --deploy`` y validaciones adicionales del .env.
"""
import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from appConfig import DjangoConfig, PanaccessConfig, RedisConfig, SocialConfig


class Command(BaseCommand):
    help = "Valida DEBUG, SECRET_KEY, ALLOWED_HOSTS, CORS y checks de despliegue de Django."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Falla si ALLOWED_HOSTS contiene '*' o SECRET_KEY es débil (recomendado en Ubuntu prod).",
        )

    def handle(self, *args, **options):
        strict = options["strict"]
        errors = []
        warnings = []

        self.stdout.write(f"DEBUG: {settings.DEBUG}")
        self.stdout.write(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
        cors_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        self.stdout.write(f"CORS_ALLOWED_ORIGINS: {cors_origins}")

        if settings.DEBUG:
            errors.append("DEBUG está activo. En producción use DEBUG=false en .env")

        hosts = settings.ALLOWED_HOSTS or []
        if "*" in hosts:
            msg = "ALLOWED_HOSTS contiene '*' — acepta cualquier Host (inseguro en internet)"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

        if not hosts or hosts == ["*"]:
            warnings.append("Define dominios concretos: ALLOWED_HOSTS=api.tudominio.com")

        secret = DjangoConfig.SECRET_KEY or ""
        if len(secret) < 50:
            errors.append("SECRET_KEY demasiado corta (use ≥ 50 caracteres aleatorios)")
        if secret in ("change-me", "django-insecure", "change-me-strong-password"):
            errors.append("SECRET_KEY es un valor de ejemplo; genere una nueva")

        cors_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", []) or []
        localhost_cors = {
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        }
        if not settings.DEBUG:
            if not cors_origins:
                errors.append(
                    "CORS_ALLOWED_ORIGINS vacío con DEBUG=false. "
                    "Defina los dominios del frontend (roadmap #4)."
                )
            elif strict and set(cors_origins) <= localhost_cors:
                errors.append(
                    "CORS_ALLOWED_ORIGINS solo tiene localhost; en prod use https://tu-front.com"
                )
            elif strict and any(o.startswith("http://") for o in cors_origins):
                warnings.append(
                    "CORS usa http:// en producción; preferir https:// si el front es público"
                )

        full_sync_http = os.getenv("FULL_SYNC_HTTP_ENABLED", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        celery_full_sync = os.getenv("CELERY_FULL_SYNC_ENABLED", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        self.stdout.write(f"FULL_SYNC_HTTP_ENABLED: {full_sync_http}")
        self.stdout.write(f"CELERY_FULL_SYNC_ENABLED: {celery_full_sync}")

        panaccess_session_redis = getattr(settings, "PANACCESS_SESSION_USE_REDIS", False)
        panaccess_session_ttl = getattr(settings, "PANACCESS_SESSION_TTL_SECONDS", 1500)
        self.stdout.write(f"PANACCESS_SESSION_USE_REDIS: {panaccess_session_redis}")
        self.stdout.write(f"PANACCESS_SESSION_TTL_SECONDS: {panaccess_session_ttl}")

        social_providers = SocialConfig.enabled_providers()
        self.stdout.write(
            f"SOCIAL_LOGIN_PROVIDERS: {', '.join(social_providers) or '(ninguno)'}"
        )

        sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
        self.stdout.write(f"SENTRY_DSN: {'configurado' if sentry_dsn else 'no (opcional)'}")
        if strict and not settings.DEBUG and not sentry_dsn:
            warnings.append(
                "SENTRY_DSN vacío en producción; errores nocturnos no irán a Sentry (roadmap #18)"
            )

        try:
            PanaccessConfig.validate()
            self.stdout.write(self.style.SUCCESS("PanAccess .env: variables obligatorias OK"))
        except EnvironmentError as exc:
            msg = str(exc)
            if strict and not settings.DEBUG:
                errors.append(msg)
            else:
                warnings.append(msg)

        if panaccess_session_redis:
            try:
                RedisConfig.get_client().ping()
                self.stdout.write(self.style.SUCCESS("Redis (sesión PanAccess): ping OK"))
            except Exception as exc:
                msg = f"PANACCESS_SESSION_USE_REDIS=true pero Redis no responde: {exc}"
                if strict and not settings.DEBUG:
                    errors.append(msg)
                else:
                    warnings.append(msg)

        if strict and not settings.DEBUG:
            if not panaccess_session_redis:
                errors.append(
                    "PANACCESS_SESSION_USE_REDIS=false en producción con varios workers Gunicorn. "
                    "Use true y Redis activo (roadmap #9)."
                )
            elif os.getenv("PANACCESS_SESSION_USE_REDIS") is None:
                warnings.append(
                    "Defina PANACCESS_SESSION_USE_REDIS=true explícitamente en .env (no solo el default)."
                )

        if strict and not settings.DEBUG:
            if full_sync_http:
                errors.append(
                    "FULL_SYNC_HTTP_ENABLED=true en producción. "
                    "Use false y deje el correctivo solo a Celery Beat (roadmap #8)."
                )
            if not celery_full_sync:
                errors.append(
                    "CELERY_FULL_SYNC_ENABLED=false: el full-sync nocturno no se programará en Beat."
                )
            if not getattr(settings, "PRODUCTION_HTTPS", False):
                errors.append(
                    "PRODUCTION_HTTPS=false en producción. Use true detrás de nginx con TLS (roadmap #23)."
                )
            sync_async = os.getenv("SYNC_HTTP_ASYNC", "true").lower() in (
                "true",
                "1",
                "yes",
            )
            self.stdout.write(f"SYNC_HTTP_ASYNC: {sync_async}")
            if not sync_async:
                warnings.append(
                    "SYNC_HTTP_ASYNC=false: POST /wind/sync-* bloquean Gunicorn hasta terminar"
                )
            allowlist = getattr(settings, "SYNC_ADMIN_IP_ALLOWLIST", []) or []
            if not allowlist:
                warnings.append(
                    "SYNC_ADMIN_IP_ALLOWLIST vacío: configure IPs o restrinja sync en nginx (roadmap #5)"
                )

        for w in warnings:
            self.stdout.write(self.style.WARNING(f"AVISO: {w}"))

        for e in errors:
            self.stdout.write(self.style.ERROR(f"ERROR: {e}"))

        if errors:
            raise CommandError("Configuración no apta para producción. Corrija .env y reintente.")

        self.stdout.write(self.style.SUCCESS("Validación .env: OK"))
        self.stdout.write("Ejecutando django check --deploy ...")
        call_command("check", "--deploy", verbosity=1)

        if strict and warnings:
            raise CommandError("Modo --strict: corrija los avisos antes de desplegar.")

        self.stdout.write(self.style.SUCCESS("check_deploy: OK"))
