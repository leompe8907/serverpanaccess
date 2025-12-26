"""
Vista para sincronizar productos desde PanAccess.

Endpoint que ejecuta el proceso de sincronización completo de productos.
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from wind.functions.getProducts import (
    sync_products,
    fetch_all_products,
    download_products_since_last,
    compare_and_update_all_products,
    CallListOfProducts,
    DataBaseEmpty,
    LastProduct
)
from wind.exceptions import PanAccessException

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def sync_products_view(request):
    """
    Vista para sincronizar productos desde PanAccess.
    
    Parámetros opcionales (GET o POST):
    - mode: 'full' (descarga completa), 'incremental' (solo nuevos), 
            'update' (solo actualizar existentes), 'sync' (completo - default)
    - limit: Cantidad de registros por página (default: 100, máximo: 1000)
    
    Returns:
        Respuesta con estadísticas de la sincronización
    """
    try:
        # Obtener parámetros
        if request.method == 'GET':
            mode = request.query_params.get('mode', 'sync')
            limit = int(request.query_params.get('limit', 100))
        else:
            mode = request.data.get('mode', 'sync')
            limit = int(request.data.get('limit', 100))
        
        # Validar limit
        if limit > 1000:
            limit = 1000
            logger.warning("Limit ajustado a 1000 (máximo permitido)")
        
        logger.info(f"🔄 Iniciando sincronización de productos - Modo: {mode}, Limit: {limit}")
        
        # Ejecutar según el modo
        if mode == 'full':
            logger.info("📥 Modo: Descarga completa")
            result = fetch_all_products(session_id=None, limit=limit)
            message = "Descarga completa de productos completada"
            
        elif mode == 'incremental':
            logger.info("📥 Modo: Descarga incremental (solo nuevos)")
            if DataBaseEmpty():
                return Response({
                    'success': False,
                    'message': 'La base de datos está vacía. Use mode=full para descarga completa.',
                    'suggestion': 'Use ?mode=full para realizar una descarga completa primero'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            result = download_products_since_last(session_id=None, limit=limit)
            message = "Descarga incremental de productos completada"
            
        elif mode == 'update':
            logger.info("🔄 Modo: Actualización de existentes")
            if DataBaseEmpty():
                return Response({
                    'success': False,
                    'message': 'La base de datos está vacía. No hay registros para actualizar.',
                    'suggestion': 'Use ?mode=full para realizar una descarga completa primero'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            compare_and_update_all_products(session_id=None, limit=limit)
            result = None
            message = "Actualización de productos existentes completada"
            
        else:  # mode == 'sync' (default)
            logger.info("🔄 Modo: Sincronización completa (nuevos + actualización)")
            result = sync_products(session_id=None, limit=limit)
            message = "Sincronización completa de productos completada"
        
        # Obtener estadísticas
        last_product = LastProduct()
        last_product_id = last_product.productId if last_product else None
        
        logger.info(f"✅ {message}")
        
        return Response({
            'success': True,
            'message': message,
            'mode': mode,
            'limit_used': limit,
            'last_product_id': last_product_id,
            'database_empty': DataBaseEmpty(),
            'result': result if result is not None else 'update_completed'
        }, status=status.HTTP_200_OK)
        
    except PanAccessException as e:
        error_msg = f"Error de PanAccess: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return Response({
            'success': False,
            'error_type': type(e).__name__,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ValueError as e:
        error_msg = f"Error de parámetros: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return Response({
            'success': False,
            'error_type': 'ValueError',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"
        logger.error(f"💥 {error_msg}", exc_info=True)
        
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def test_call_list_products(request):
    """
    Vista de prueba para llamar directamente a getListOfProducts.
    
    Parámetros opcionales (GET o POST):
    - offset: Índice de inicio (default: 0)
    - limit: Cantidad máxima de registros (default: 100, máximo: 1000)
    - orderBy: Campo para ordenar (default: 'productId')
    - orderDir: Dirección de ordenamiento 'ASC' o 'DESC' (default: 'ASC')
    
    Returns:
        Respuesta con los productos obtenidos de la API
    """
    try:
        # Obtener parámetros
        if request.method == 'GET':
            offset = int(request.query_params.get('offset', 0))
            limit = int(request.query_params.get('limit', 100))
            orderBy = request.query_params.get('orderBy', 'productId')
            orderDir = request.query_params.get('orderDir', 'ASC')
        else:
            offset = int(request.data.get('offset', 0))
            limit = int(request.data.get('limit', 100))
            orderBy = request.data.get('orderBy', 'productId')
            orderDir = request.data.get('orderDir', 'ASC')
        
        # Validar limit
        if limit > 1000:
            limit = 1000
            logger.warning("Limit ajustado a 1000 (máximo permitido)")
        
        # Validar orderDir
        if orderDir not in ['ASC', 'DESC']:
            orderDir = 'ASC'
            logger.warning("orderDir inválido, usando 'ASC'")
        
        logger.info(f"🧪 Probando getListOfProducts - offset={offset}, limit={limit}, orderBy={orderBy}, orderDir={orderDir}")
        
        # Llamar a la API
        result = CallListOfProducts(
            session_id=None,
            offset=offset,
            limit=limit,
            orderBy=orderBy,
            orderDir=orderDir
        )
        
        count = result.get('count', 0)
        product_entries = result.get('productEntries', [])
        
        logger.info(f"✅ Llamada exitosa - Total: {count}, Obtenidos: {len(product_entries)}")
        
        return Response({
            'success': True,
            'message': 'Llamada a getListOfProducts exitosa',
            'parameters': {
                'offset': offset,
                'limit': limit,
                'orderBy': orderBy,
                'orderDir': orderDir
            },
            'result': {
                'count': count,
                'product_entries_count': len(product_entries),
                'product_entries': product_entries[:10] if len(product_entries) > 10 else product_entries,  # Mostrar solo primeros 10
                'has_more': len(product_entries) > 10
            }
        }, status=status.HTTP_200_OK)
        
    except PanAccessException as e:
        error_msg = f"Error de PanAccess: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return Response({
            'success': False,
            'error_type': type(e).__name__,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except ValueError as e:
        error_msg = f"Error de parámetros: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return Response({
            'success': False,
            'error_type': 'ValueError',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error inesperado: {str(e)}"
        logger.error(f"💥 {error_msg}", exc_info=True)
        
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def products_stats_view(request):
    """
    Vista para obtener estadísticas de productos en la base de datos.
    
    Returns:
        Estadísticas de productos almacenados
    """
    try:
        from wind.models import ListOfProducts
        
        total_products = ListOfProducts.objects.count()
        last_product = LastProduct()
        database_empty = DataBaseEmpty()
        
        stats = {
            'success': True,
            'total_products': total_products,
            'database_empty': database_empty,
            'last_product_id': last_product.productId if last_product else None,
            'last_product_name': last_product.name if last_product else None,
        }
        
        if not database_empty:
            # Estadísticas adicionales
            deleted_count = ListOfProducts.objects.filter(deleted=True).count()
            active_count = ListOfProducts.objects.filter(deleted=False).count()
            with_packages = ListOfProducts.objects.exclude(packages__isnull=True).exclude(packages=[]).count()
            
            stats.update({
                'deleted_products': deleted_count,
                'active_products': active_count,
                'products_with_packages': with_packages,
            })
        
        return Response(stats, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"💥 Error obteniendo estadísticas: {str(e)}", exc_info=True)
        
        return Response({
            'success': False,
            'error_type': 'Exception',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

