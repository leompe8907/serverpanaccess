import logging
import os

from celery import shared_task

from wind.functions.getSubscriber import sync_subscribers
from wind.functions.getSmartcard import sync_smartcards
from wind.exceptions import PanAccessException
from appConfig import RedisConfig

logger = logging.getLogger(__name__)


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

    with RedisConfig.task_lock(lock_key, timeout=lock_timeout) as acquired:
        if not acquired:
            logger.warning(
                "⚠️ [Celery] sync_subscribers_task ya está ejecutándose, saltando esta ejecución"
            )
            return {
                "success": False,
                "message": "Task already running, skipped",
                "skipped": True,
            }

        try:
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
            logger.error("❌ [Celery] Error de PanAccess: %s", exc)
            raise
        except Exception:
            logger.exception("💥 [Celery] Error inesperado en sync_subscribers_task")
            raise


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
    lock_timeout = 600

    with RedisConfig.task_lock(lock_key, timeout=lock_timeout) as acquired:
        if not acquired:
            logger.warning(
                "⚠️ [Celery] sync_smartcards_task ya está ejecutándose, saltando esta ejecución"
            )
            return {
                "success": False,
                "message": "Task already running, skipped",
                "skipped": True,
            }

        try:
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
            logger.error("❌ [Celery] Error de PanAccess: %s", exc)
            raise
        except Exception:
            logger.exception("💥 [Celery] Error inesperado en sync_smartcards_task")
            raise
