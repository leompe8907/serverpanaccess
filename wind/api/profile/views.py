import logging

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from wind.api.profile.serializers import (
    ProfileMeSerializer,
    ProfilePasswordSerializer,
    ProfileProductSerializer,
)
from wind.exceptions import PanAccessException
from wind.models import ListOfProducts, SubscriberEmailRegistry
from wind.permissions import IsOwnerSubscriber
from wind.services import get_panaccess
from wind.throttles import ProfileThrottle

logger = logging.getLogger(__name__)
User = get_user_model()


def _registry_for_user(user):
    try:
        return SubscriberEmailRegistry.objects.get(email=user.email)
    except SubscriberEmailRegistry.DoesNotExist:
        return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([ProfileThrottle])
def profile_me_view(request):
    """Datos del usuario autenticado y suscriptor vinculado."""
    serializer = ProfileMeSerializer(request.user)
    return Response({"success": True, "profile": serializer.data})


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsOwnerSubscriber])
@throttle_classes([ProfileThrottle])
def profile_password_view(request):
    """Cambia la contraseña PanAccess del propio suscriptor."""
    ser = ProfilePasswordSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {"success": False, "errors": ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    code = ser.validated_data["code"]
    new_pass = ser.validated_data["newPass"]

    try:
        panaccess = get_panaccess()
        response = panaccess.call(
            "resetSubscriberPassword",
            {"code": code, "newPass": new_pass, "hash": False},
        )
        if response.get("success"):
            return Response(
                {
                    "success": True,
                    "message": "Contraseña actualizada",
                    "result": response.get("answer", response),
                }
            )
        raise PanAccessException(response.get("errorMessage", "Error al cambiar contraseña"))
    except PanAccessException as e:
        return Response(
            {"success": False, "error_type": "PanAccessException", "message": str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as e:
        logger.exception("Error en profile_password_view")
        return Response(
            {"success": False, "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([ProfileThrottle])
def profile_products_view(request):
    """
    Lista productos del catálogo local (paginado).
    Filtrado por suscriptor específico: por implementar cuando exista relación directa.
    """
    registry = _registry_for_user(request.user)
    if not registry:
        return Response(
            {
                "success": False,
                "message": "No hay suscriptor vinculado a este usuario.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    qs = ListOfProducts.objects.filter(deleted=False).order_by("productId")
    page = request.query_params.get("page", "1")
    try:
        page_size = min(int(request.query_params.get("page_size", 20)), 100)
    except (TypeError, ValueError):
        page_size = 20

    from django.core.paginator import Paginator

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    serializer = ProfileProductSerializer(page_obj.object_list, many=True)

    return Response(
        {
            "success": True,
            "subscriber_code": registry.subscriber_code,
            "count": paginator.count,
            "page": page_obj.number,
            "total_pages": paginator.num_pages,
            "results": serializer.data,
        }
    )
