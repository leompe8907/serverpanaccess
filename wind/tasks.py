import logging
import os

from celery import shared_task
from redis import Redis
from redis.lock import Lock

from wind.functions.getSubscriber import sync_subscribers
from wind.functions.getSmartcard import sync_smartcards
from wind.exceptions import PanAccessException

logger = logging.getLogger(__name__)

# Configuración de Redis para locks
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

def get_redis_client():
    """Obtiene cliente Redis para locks."""
    if REDIS_PASSWORD:
        return Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_PASSWORD, decode_responses=False)
    return Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=False)


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@shared_task(
    bind=True,
    autoretry_for=(PanAccessException, ConnectionError, Exception),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def sync_subscribers_task(self, limit=None):
    """
    Tarea periódica para sincronizar suscriptores.
    Evita ejecuciones concurrentes usando un lock distribuido.

    Args:
        limit (int): cantidad máxima por página (se puede sobreescribir vía argumento
                     o env CELERY_SYNC_LIMIT)
    """
    lock_key = "celery:lock:sync_subscribers_task"
    lock_timeout = 600  # 10 minutos máximo (mismo que CELERY_TASK_TIME_LIMIT)
    
    redis_client = get_redis_client()
    lock = Lock(redis_client, lock_key, timeout=lock_timeout)
    
    # Intentar adquirir el lock
    if not lock.acquire(blocking=False):
        logger.warning("⚠️ [Celery] sync_subscribers_task ya está ejecutándose, saltando esta ejecución")
        return {
            "success": False,
            "message": "Task already running, skipped",
            "skipped": True
        }
    
    try:
        # Permitir override por argumento; fallback a variable de entorno
        env_limit = _as_int(os.getenv("CELERY_SYNC_LIMIT"), None)
        limit = limit or env_limit or 200

        logger.info("🔄 [Celery] Iniciando sync_subscribers_task con limit=%s", limit)
        result = sync_subscribers(limit=limit)
        logger.info("✅ [Celery] Sincronización completada")
        return {
            "success": True,
            "limit": limit,
            "result": result,
        }
    except PanAccessException as exc:
        # Se reintenta por autoretry_for
        logger.error("❌ [Celery] Error de PanAccess: %s", exc)
        raise
    except Exception as exc:
        logger.exception("💥 [Celery] Error inesperado en sync_subscribers_task")
        raise
    finally:
        # Liberar el lock siempre, incluso si hay error
        try:
            lock.release()
        except Exception as e:
            logger.error(f"Error liberando lock: {e}")


@shared_task(
    bind=True,
    autoretry_for=(PanAccessException, ConnectionError, Exception),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def sync_smartcards_task(self, limit=None):
    """
    Tarea periódica para sincronizar smartcards.
    Evita ejecuciones concurrentes usando un lock distribuido.

    Args:
        limit (int): cantidad máxima por página (se puede sobreescribir vía argumento
                     o env CELERY_SYNC_LIMIT)
    """
    lock_key = "celery:lock:sync_smartcards_task"
    lock_timeout = 600  # 10 minutos máximo (mismo que CELERY_TASK_TIME_LIMIT)
    
    redis_client = get_redis_client()
    lock = Lock(redis_client, lock_key, timeout=lock_timeout)
    
    # Intentar adquirir el lock
    if not lock.acquire(blocking=False):
        logger.warning("⚠️ [Celery] sync_smartcards_task ya está ejecutándose, saltando esta ejecución")
        return {
            "success": False,
            "message": "Task already running, skipped",
            "skipped": True
        }
    
    try:
        # Permitir override por argumento; fallback a variable de entorno
        env_limit = _as_int(os.getenv("CELERY_SYNC_LIMIT"), None)
        limit = limit or env_limit or 200

        logger.info("🔄 [Celery] Iniciando sync_smartcards_task con limit=%s", limit)
        result = sync_smartcards(limit=limit)
        logger.info("✅ [Celery] Sincronización de smartcards completada")
        return {
            "success": True,
            "limit": limit,
            "result": result,
        }
    except PanAccessException as exc:
        # Se reintenta por autoretry_for
        logger.error("❌ [Celery] Error de PanAccess: %s", exc)
        raise
    except Exception as exc:
        logger.exception("💥 [Celery] Error inesperado en sync_smartcards_task")
        raise
    finally:
        # Liberar el lock siempre, incluso si hay error
        try:
            lock.release()
        except Exception as e:
            logger.error(f"Error liberando lock: {e}")

