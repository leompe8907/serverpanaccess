import logging
import os

from celery import shared_task

from wind.functions.getSubscriber import sync_subscribers
from wind.exceptions import PanAccessException

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

    Args:
        limit (int): cantidad máxima por página (se puede sobreescribir vía argumento
                     o env CELERY_SYNC_LIMIT)
    """
    # Permitir override por argumento; fallback a variable de entorno
    env_limit = _as_int(os.getenv("CELERY_SYNC_LIMIT"), None)
    limit = limit or env_limit or 200

    logger.info("🔄 [Celery] Iniciando sync_subscribers_task con limit=%s", limit)
    try:
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

