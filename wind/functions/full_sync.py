"""
Endpoint de sincronización global.

Objetivo: con una sola llamada, dejar consistentes las tablas locales con PanAccess:
- ListOfSubscriber (crear/actualizar/borrar sobrantes)
- ListOfProducts (crear/actualizar/borrar sobrantes)
- ListOfSmartcards (crear/actualizar/borrar sobrantes)
- SubscriberLoginInfo (crear/actualizar y borrar sobrantes respecto a suscriptores locales)
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.exceptions import PanAccessException
from wind.models import ListOfProducts, ListOfSmartcards, SubscriberLoginInfo, ListOfSubscriber
from wind.functions.getSubscriber import compare_and_update_all_subscribers
from wind.functions.getProducts import sync_products, compare_and_update_all_products, CallListOfProducts
from wind.functions.getSmartcard import sync_smartcards, compare_and_update_all_smartcards, CallListSmartcards
from wind.functions.getSubscriberLoginInfo import sync_subscribers_login_info

logger = logging.getLogger(__name__)


def _parse_limit(request, default=100) -> int:
    if request.method == "GET":
        raw = request.query_params.get("limit", default)
    else:
        raw = request.data.get("limit", default)
    try:
        limit = int(raw)
    except Exception:
        limit = default
    return min(max(limit, 1), 1000)


def _delete_extra_products(limit: int) -> dict:
    """Elimina productos locales que ya no existan en PanAccess."""
    remote_ids = set()
    offset = 0
    remote_count = None

    while True:
        result = CallListOfProducts(session_id=None, offset=offset, limit=limit)
        entries = result.get("productEntries", []) or []
        if remote_count is None:
            remote_count = int(result.get("count") or 0)

        if not entries:
            break

        for e in entries:
            pid = e.get("productId")
            if pid is not None:
                remote_ids.add(pid)

        offset += limit
        if remote_count and len(remote_ids) >= remote_count:
            break

    local_ids = set(ListOfProducts.objects.values_list("productId", flat=True))
    extra = local_ids - remote_ids
    deleted = 0
    if extra:
        deleted = ListOfProducts.objects.filter(productId__in=extra).delete()[0]

    return {"remote": len(remote_ids), "local": len(local_ids), "extra_deleted": deleted}


def _delete_extra_smartcards(limit: int) -> dict:
    """Elimina smartcards locales que ya no existan en PanAccess."""
    remote_sns = set()
    offset = 0
    remote_count = None

    while True:
        result = CallListSmartcards(session_id=None, offset=offset, limit=limit)
        entries = result.get("smartcardEntries", []) or []
        if remote_count is None:
            remote_count = int(result.get("count") or 0)

        if not entries:
            break

        for e in entries:
            sn = e.get("sn") if isinstance(e, dict) else None
            if sn:
                remote_sns.add(sn)

        offset += limit
        if remote_count and len(remote_sns) >= remote_count:
            break

    local_sns = set(ListOfSmartcards.objects.values_list("sn", flat=True))
    extra = local_sns - remote_sns
    deleted = 0
    if extra:
        deleted = ListOfSmartcards.objects.filter(sn__in=extra).delete()[0]

    return {"remote": len(remote_sns), "local": len(local_sns), "extra_deleted": deleted}


def _cleanup_login_info() -> dict:
    """Elimina SubscriberLoginInfo sin suscriptor local."""
    local_codes = set(
        ListOfSubscriber.objects.exclude(code__isnull=True).exclude(code="").values_list("code", flat=True)
    )
    deleted = SubscriberLoginInfo.objects.exclude(subscriberCode__in=local_codes).delete()[0]
    total = SubscriberLoginInfo.objects.count()
    return {"remaining": total, "deleted_orphans": deleted}


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def full_sync_view(request):
    """
    Ejecuta una sincronización global.

    Parámetros opcionales (GET o POST):
    - limit: tamaño de página para llamadas a PanAccess (default 100, max 1000)
    """
    limit = _parse_limit(request, default=100)

    try:
        result_subscribers = compare_and_update_all_subscribers(session_id=None, limit=limit)

        # Productos: crear nuevos + actualizar existentes + borrar sobrantes
        result_products_new = sync_products(session_id=None, limit=limit)
        compare_and_update_all_products(session_id=None, limit=limit)
        result_products_delete = _delete_extra_products(limit=limit)

        # Smartcards: crear nuevas + actualizar existentes + borrar sobrantes
        result_smartcards_new = sync_smartcards(session_id=None, limit=limit)
        compare_and_update_all_smartcards(session_id=None, limit=limit)
        result_smartcards_delete = _delete_extra_smartcards(limit=limit)

        # Login info: actualizar/crear para todos + limpiar huérfanos
        result_login_info = sync_subscribers_login_info(session_id=None, limit=None)
        result_login_cleanup = _cleanup_login_info()

        return Response(
            {
                "success": True,
                "message": "Sincronización global completada",
                "limit_used": limit,
                "subscribers": result_subscribers,
                "products": {
                    "sync_result": result_products_new,
                    "delete_extras": result_products_delete,
                },
                "smartcards": {
                    "sync_result": result_smartcards_new,
                    "delete_extras": result_smartcards_delete,
                },
                "subscriber_login_info": {
                    "sync_result": result_login_info,
                    "cleanup": result_login_cleanup,
                },
            },
            status=status.HTTP_200_OK,
        )

    except PanAccessException as e:
        logger.error("Error PanAccess en full sync: %s", str(e), exc_info=True)
        return Response(
            {"success": False, "error_type": type(e).__name__, "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        logger.error("Error inesperado en full sync: %s", str(e), exc_info=True)
        return Response(
            {"success": False, "error_type": "Exception", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

