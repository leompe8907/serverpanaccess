"""
Comprueba configuración lista para producción (roadmap #3 y #4).
Ejecuta ``manage.py check --deploy`` y validaciones adicionales del .env.
"""
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from appConfig import DjangoConfig


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

        if strict and not settings.DEBUG:
            if not getattr(settings, "PRODUCTION_HTTPS", False):
                warnings.append(
                    "PRODUCTION_HTTPS no está activo; use true detrás de nginx con TLS"
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
