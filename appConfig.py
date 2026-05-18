import os
import sys
from contextlib import contextmanager
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv(override=True)
load_dotenv()


def _strip_env(value: str | None) -> str:
    """Quita espacios y comillas envueltas (p. ej. REDIS_PASSWORD=\"\")."""
    if not value:
        return ""
    v = value.strip()
    if len(v) >= 2 and v[0] == v[1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _csv(name):
    raw = os.getenv(name, "")
    return [x.strip() for x in raw.split(",") if x.strip()]

class PanaccessConfig:
    PANACCESS = os.getenv("url_panaccess")
    USERNAME = os.getenv("username")
    PASSWORD = os.getenv("password")
    API_TOKEN = os.getenv("api_token")
    SALT = os.getenv("salt")
    HCID = os.getenv("hcId")
    KEY = os.getenv("ENCRYPTION_KEY")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.PANACCESS:
            missing.append("url_panaccess")
        if not cls.USERNAME:
            missing.append("username")
        if not cls.PASSWORD:
            missing.append("password")
        if not cls.API_TOKEN:
            missing.append("api_token")
        if not cls.SALT:
            missing.append("salt")
        if not cls.HCID:
            missing.append("hcId")
        if not cls.KEY:
            missing.append("ENCRYPTION_KEY")
        if missing:
            raise EnvironmentError(f"❌ Faltan variables de entorno: {', '.join(missing)}")

class DjangoConfig:
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

    # ✅ usar ALLOWED_HOSTS (plural) y filtrar vacíos
    ALLOWED_HOSTS = _csv("ALLOWED_HOSTS")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.SECRET_KEY:
            missing.append("SECRET_KEY")
        if not cls.ALLOWED_HOSTS:
            missing.append("ALLOWED_HOSTS")
        # lo siguiente solo si realmente los exigís:
        # if not cls.WS_ALLOWED_ORIGINS: missing.append("WS_ALLOWED_ORIGINS")
        if missing:
            raise EnvironmentError(f"❌ Faltan variables de entorno: {', '.join(missing)}")


class SocialConfig:
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

    FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
    FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
    FACEBOOK_REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")

    APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
    APPLE_CLIENT_SECRET = os.getenv("APPLE_CLIENT_SECRET")
    APPLE_REDIRECT_URI = os.getenv("APPLE_REDIRECT_URI")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.GOOGLE_CLIENT_ID:
            missing.append("GOOGLE_CLIENT_ID")
        if not cls.GOOGLE_CLIENT_SECRET:
            missing.append("GOOGLE_CLIENT_SECRET")
        if not cls.GOOGLE_REDIRECT_URI:
            missing.append("GOOGLE_REDIRECT_URI")
        if not cls.FACEBOOK_APP_ID:
            missing.append("FACEBOOK_APP_ID")
        if not cls.FACEBOOK_APP_SECRET:
            missing.append("FACEBOOK_APP_SECRET")
        if not cls.FACEBOOK_REDIRECT_URI:
            missing.append("FACEBOOK_REDIRECT_URI")
        if not cls.APPLE_CLIENT_ID:
            missing.append("APPLE_CLIENT_ID")
        if not cls.APPLE_CLIENT_SECRET:
            missing.append("APPLE_CLIENT_SECRET")
        if not cls.APPLE_REDIRECT_URI:
            missing.append("APPLE_REDIRECT_URI")

class DatabaseConfig:
    # SQLite en dev si DB_ENGINE no indica PostgreSQL.
    # Prod/staging: DB_ENGINE=django.db.backends.postgresql
    ENGINE = _strip_env(os.getenv("DB_ENGINE")) or _strip_env(os.getenv("ENGINE"))
    NAME = _strip_env(os.getenv("DB_NAME")) or _strip_env(os.getenv("NAME"))
    USER = _strip_env(os.getenv("DB_USER")) or _strip_env(os.getenv("USER"))
    PASSWORD = _strip_env(os.getenv("DB_PASSWORD")) or _strip_env(os.getenv("PASSWORD"))
    HOST = _strip_env(os.getenv("DB_HOST")) or _strip_env(os.getenv("HOST"))
    PORT = _strip_env(os.getenv("DB_PORT")) or _strip_env(os.getenv("PORT"))

    REPLICA_HOST = _strip_env(os.getenv("DB_REPLICA_HOST"))
    REPLICA_PORT = _strip_env(os.getenv("DB_REPLICA_PORT"))

    @classmethod
    def use_postgresql(cls) -> bool:
        engine = (cls.ENGINE or "").lower()
        return "postgresql" in engine or engine == "postgres"

    @classmethod
    def configure(cls):
        if not cls.use_postgresql():
            return cls
        missing = []
        if not cls.ENGINE:
            missing.append("DB_ENGINE")
        if not cls.NAME:
            missing.append("DB_NAME")
        if not cls.USER:
            missing.append("DB_USER")
        if cls.PASSWORD is None or cls.PASSWORD == "":
            missing.append("DB_PASSWORD")
        if not cls.HOST:
            missing.append("DB_HOST")
        if not cls.PORT:
            missing.append("DB_PORT")
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
        return cls

    @classmethod
    def django_default_database(cls) -> dict:
        cls.configure()
        db = {
            "ENGINE": cls.ENGINE,
            "NAME": cls.NAME,
            "USER": cls.USER,
            "PASSWORD": cls.PASSWORD,
            "HOST": cls.HOST,
            "PORT": cls.PORT,
        }
        conn_max_age = _strip_env(os.getenv("DB_CONN_MAX_AGE"))
        if conn_max_age:
            db["CONN_MAX_AGE"] = int(conn_max_age)
        return db

    @classmethod
    def django_replica_database(cls) -> dict | None:
        if not cls.use_postgresql() or not cls.REPLICA_HOST:
            return None
        base = cls.django_default_database()
        return {
            **base,
            "HOST": cls.REPLICA_HOST,
            "PORT": cls.REPLICA_PORT or base.get("PORT"),
        }

class RedisConfig:
    """
    Redis / Celery: una sola fuente de verdad para Windows (dev) y Linux (prod).

    Prioridad de URL del broker:
      1. CELERY_BROKER_URL
      2. REDIS_URL
      3. REDIS_HOST + REDIS_PORT + REDIS_DB + REDIS_PASSWORD
    """

    HOST = _strip_env(os.getenv("REDIS_HOST")) or "localhost"
    PORT = int(os.getenv("REDIS_PORT", "6379"))
    DB = int(os.getenv("REDIS_DB", "0"))
    PASSWORD = _strip_env(os.getenv("REDIS_PASSWORD"))

    @classmethod
    def build_url(cls, db: int | None = None) -> str:
        database = cls.DB if db is None else db
        if cls.PASSWORD:
            auth = f":{quote(cls.PASSWORD, safe='')}@"
        else:
            auth = ""
        return f"redis://{auth}{cls.HOST}:{cls.PORT}/{database}"

    @classmethod
    def broker_url(cls) -> str:
        explicit = _strip_env(os.getenv("CELERY_BROKER_URL")) or _strip_env(os.getenv("REDIS_URL"))
        return explicit or cls.build_url()

    @classmethod
    def result_backend_url(cls) -> str:
        explicit = _strip_env(os.getenv("CELERY_RESULT_BACKEND"))
        return explicit or cls.broker_url()

    @classmethod
    def celery_eager(cls) -> bool:
        """Ejecuta tareas en el mismo proceso (útil en dev sin Redis/worker)."""
        return _env_bool("CELERY_TASK_ALWAYS_EAGER", False)

    @classmethod
    def celery_worker_pool(cls) -> str:
        explicit = _strip_env(os.getenv("CELERY_WORKER_POOL"))
        if explicit:
            return explicit
        return "solo" if sys.platform == "win32" else "prefork"

    @classmethod
    def get_client(cls):
        from redis import Redis

        kwargs = {
            "host": cls.HOST,
            "port": cls.PORT,
            "db": cls.DB,
            "decode_responses": False,
        }
        if cls.PASSWORD:
            kwargs["password"] = cls.PASSWORD
        return Redis(**kwargs)

    @classmethod
    @contextmanager
    def task_lock(cls, key: str, *, timeout: int = 600):
        """
        Lock distribuido vía Redis. En modo eager (dev sin Redis) no bloquea.
        Yields True si se adquirió el lock, False si otra instancia ya corre.
        """
        from django.conf import settings

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            yield True
            return

        from redis.lock import Lock

        lock = Lock(cls.get_client(), key, timeout=timeout)
        acquired = lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    lock.release()
                except Exception:
                    pass

    @classmethod
    def validate(cls):
        missing = []
        if not cls.HOST:
            missing.append("REDIS_HOST")
        if cls.PORT < 1 or cls.PORT > 65535:
            raise EnvironmentError(f"❌ REDIS_PORT inválido: {cls.PORT}")
        if cls.DB < 0 or cls.DB > 15:
            raise EnvironmentError(f"❌ REDIS_DB inválido (use 0-15): {cls.DB}")
        if missing:
            raise EnvironmentError(f"❌ Faltan variables de entorno: {', '.join(missing)}")