"""
Comprueba Redis (broker Celery, caché y locks). Roadmap #2.
"""
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from appConfig import RedisConfig


class Command(BaseCommand):
    help = "Verifica Redis: ping, broker Celery y DB de caché configurada."

    def handle(self, *args, **options):
        eager = getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
        self.stdout.write(f"CELERY_TASK_ALWAYS_EAGER: {eager}")
        if eager:
            self.stdout.write(
                self.style.WARNING(
                    "Modo eager activo: las tareas no pasan por el worker. "
                    "En Ubuntu prod use CELERY_TASK_ALWAYS_EAGER=false."
                )
            )

        self.stdout.write(f"REDIS_HOST: {RedisConfig.HOST}:{RedisConfig.PORT}")
        self.stdout.write(f"REDIS_DB (broker): {RedisConfig.DB}")
        cache_db = getattr(settings, "REDIS_CACHE_DB", 1)
        self.stdout.write(f"REDIS_CACHE_DB: {cache_db}")
        self.stdout.write(f"broker_url: {RedisConfig.broker_url()}")

        try:
            client = RedisConfig.get_client()
            pong = client.ping()
            self.stdout.write(f"ping: {pong}")
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"ping: FAIL — {exc}"))
            raise SystemExit(1) from exc

        try:
            client = RedisConfig.get_client()
            client.set("health:redis_probe", b"1", ex=5)
            if client.get("health:redis_probe") != b"1":
                raise RuntimeError("read/write broker DB failed")
            self.stdout.write(self.style.SUCCESS("broker: ok"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"broker: FAIL — {exc}"))
            raise SystemExit(1) from exc

        if getattr(settings, "CACHES", {}).get("default", {}).get("BACKEND", "").endswith("LocMemCache"):
            self.stdout.write(self.style.WARNING("cache: LocMem (CACHE_BACKEND=locmem)"))
        else:
            try:
                cache.set("health:cache_probe", "ok", timeout=5)
                if cache.get("health:cache_probe") != "ok":
                    raise RuntimeError("django cache read failed")
                self.stdout.write(self.style.SUCCESS("cache_db: ok"))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"cache_db: FAIL — {exc}"))
                raise SystemExit(1) from exc

        self.stdout.write(self.style.SUCCESS("ok: True"))
