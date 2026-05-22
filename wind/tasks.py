import logging
import os

from celery import shared_task

from wind.functions.getSubscriber import (
    compare_and_update_all_subscribers,
    sync_subscribers,
)
from wind.functions.getSmartcard import compare_and_update_all_smartcards, sync_smartcards
from wind.functions.full_sync import run_full_sync
from wind.exceptions import PanAccessException
from appConfig import RedisConfig

logger = logging.getLogger(__name__)


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _skipped_during_full_sync(task_name: str) -> dict:
    logger.warning(
        "[Celery] %s omitida: full_sync correctivo en curso",
        task_name,
    )
    return {
        "success": False,
        "skipped": True,
        "message": "Deferred: full_sync in progress",
    }


@shared_task(
    bind=True,
    autoretry_for=(PanAccessException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def sync_subscribers_task(self, limit=None):
    """
    Carga inicial / incremental de suscriptores (solo uso manual o encolado explícito).

    En producción la carga inicial se hace por HTTP tras el deploy; el mantenimiento
    periódico usa ``compare_and_update_subscribers_task`` (Beat).
    """
    if RedisConfig.is_full_sync_in_progress():
        return _skipped_during_full_sync("sync_subscribers_task")

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
    autoretry_for=(PanAccessException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def compare_and_update_subscribers_task(self, limit=None):
    """
    Mantenimiento periódico de suscriptores: reconcilia local vs PanAccess
    (crear, actualizar, eliminar). Programada en Celery Beat cada CELERY_SYNC_MINUTES.
    """
    if RedisConfig.is_full_sync_in_progress():
        return _skipped_during_full_sync("compare_and_update_subscribers_task")

    lock_key = "celery:lock:compare_and_update_subscribers_task"
    lock_timeout = 600

    with RedisConfig.task_lock(lock_key, timeout=lock_timeout) as acquired:
        if not acquired:
            logger.warning(
                "[Celery] compare_and_update_subscribers_task ya está ejecutándose, se omite"
            )
            return {
                "success": False,
                "message": "Task already running, skipped",
                "skipped": True,
            }

        try:
            env_limit = _as_int(os.getenv("CELERY_SYNC_LIMIT"), None)
            limit = limit or env_limit or 200

            logger.info(
                "[Celery] Iniciando compare_and_update_subscribers_task limit=%s", limit
            )
            result = compare_and_update_all_subscribers(session_id=None, limit=limit)
            logger.info("[Celery] compare_and_update_subscribers_task completada")
            return {"success": True, "limit": limit, "result": result}
        except PanAccessException as exc:
            logger.error("[Celery] Error PanAccess en compare subscribers: %s", exc)
            raise
        except Exception:
            logger.exception(
                "[Celery] Error inesperado en compare_and_update_subscribers_task"
            )
            raise


@shared_task(
    bind=True,
    autoretry_for=(PanAccessException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def compare_and_update_smartcards_task(self, limit=None):
    """
    Mantenimiento periódico de smartcards: reconcilia local vs PanAccess
    (crear, actualizar, eliminar). Programada en Celery Beat.
    """
    if RedisConfig.is_full_sync_in_progress():
        return _skipped_during_full_sync("compare_and_update_smartcards_task")

    lock_key = "celery:lock:compare_and_update_smartcards_task"
    lock_timeout = 600

    with RedisConfig.task_lock(lock_key, timeout=lock_timeout) as acquired:
        if not acquired:
            logger.warning(
                "[Celery] compare_and_update_smartcards_task ya está ejecutándose, se omite"
            )
            return {
                "success": False,
                "message": "Task already running, skipped",
                "skipped": True,
            }

        try:
            env_limit = _as_int(os.getenv("CELERY_SYNC_LIMIT"), None)
            limit = limit or env_limit or 200

            logger.info(
                "[Celery] Iniciando compare_and_update_smartcards_task limit=%s", limit
            )
            result = compare_and_update_all_smartcards(session_id=None, limit=limit)
            logger.info("[Celery] compare_and_update_smartcards_task completada")
            return {"success": True, "limit": limit, "result": result}
        except PanAccessException as exc:
            logger.error("[Celery] Error PanAccess en compare smartcards: %s", exc)
            raise
        except Exception:
            logger.exception(
                "[Celery] Error inesperado en compare_and_update_smartcards_task"
            )
            raise


@shared_task(
    bind=True,
    autoretry_for=(PanAccessException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def sync_smartcards_task(self, limit=None):
    """
    Carga inicial de smartcards (deploy manual). El mantenimiento periódico usa
    ``compare_and_update_smartcards_task``.
    """
    if RedisConfig.is_full_sync_in_progress():
        return _skipped_during_full_sync("sync_smartcards_task")

    lock_key = "celery:lock:sync_smartcards_task"
    lock_timeout = 600

    with RedisConfig.task_lock(lock_key, timeout=lock_timeout) as acquired:
        if not acquired:
            logger.warning(
                "[Celery] sync_smartcards_task ya está ejecutándose, se omite"
            )
            return {
                "success": False,
                "message": "Task already running, skipped",
                "skipped": True,
            }

        try:
            env_limit = _as_int(os.getenv("CELERY_SYNC_LIMIT"), None)
            limit = limit or env_limit or 200

            logger.info("[Celery] Iniciando sync_smartcards_task limit=%s", limit)
            result = sync_smartcards(limit=limit)
            logger.info("[Celery] sync_smartcards_task completada")
            return {"success": True, "limit": limit, "result": result}
        except PanAccessException as exc:
            logger.error("[Celery] Error PanAccess: %s", exc)
            raise
        except Exception:
            logger.exception("[Celery] Error inesperado en sync_smartcards_task")
            raise


@shared_task(
    bind=True,
    autoretry_for=(PanAccessException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def full_sync_task(self, limit=None):
    """
    Sincronización global correctiva (programar en horario de bajo tráfico, ej. medianoche).
    """
    lock_key = "celery:lock:full_sync_task"
    lock_timeout = int(os.getenv("CELERY_FULL_SYNC_TIME_LIMIT", "3600"))

    with RedisConfig.task_lock(lock_key, timeout=lock_timeout) as acquired:
        if not acquired:
            logger.warning("[Celery] full_sync_task ya está ejecutándose, se omite")
            return {"success": False, "skipped": True, "message": "Task already running"}

        RedisConfig.set_full_sync_in_progress(timeout=lock_timeout)
        try:
            env_limit = _as_int(os.getenv("CELERY_SYNC_LIMIT"), None)
            limit = limit or env_limit or 200
            logger.info("[Celery] Iniciando full_sync_task con limit=%s", limit)
            result = run_full_sync(limit=limit)
            logger.info("[Celery] full_sync_task completada")
            return result
        except PanAccessException as exc:
            logger.error("[Celery] Error PanAccess en full_sync_task: %s", exc)
            raise
        except Exception:
            logger.exception("[Celery] Error inesperado en full_sync_task")
            raise
        finally:
            RedisConfig.clear_full_sync_in_progress()
