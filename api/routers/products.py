"""
api/routers/products.py — Product listing, filtering, pagination, and dossier detail.
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status
from api.schemas.product import (
    ProductListResponse,
    ProductDetailResponse,
    ProductRefreshResponse,
    SupplierDirectoryResponse,
    WatchlistAddRequest,
    WatchlistMutationResponse,
    ShortlistToggleRequest,
    ShortlistToggleResponse,
)
from api.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "/suppliers/directory",
    response_model=SupplierDirectoryResponse,
    summary="Get Supplier Directory",
    description="Returns verified factory partners, MOQs, FOB pricing, and manufacturing cluster locations from the SQLite SSOT."
)
def get_supplier_directory(
    limit: int = Query(default=50, ge=1, le=200, description="Max suppliers to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    region: Optional[str] = Query(default=None, description="Filter by region (e.g. India, Shenzhen, Ningbo)"),
    product_id: Optional[str] = Query(default=None, description="Filter by product ID")
) -> SupplierDirectoryResponse:
    return ProductService.get_supplier_directory(
        limit=limit,
        offset=offset,
        region=region,
        product_id=product_id
    )



@router.get(
    "",
    response_model=ProductListResponse,
    summary="List Products",
    description="Returns paginated, searchable, and filtered products from the master intelligence catalog."
)
def list_products(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=25, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(default=None, description="Search query across name, category, or ID"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    region: Optional[str] = Query(default=None, description="Filter by region (e.g. India, USA, Europe)"),
    is_shortlisted: Optional[bool] = Query(default=None, description="Filter shortlisted products"),
    status: Optional[str] = Query(default=None, description="Filter by status (e.g. PASS, FAIL, PENDING)"),
    sort_by: str = Query(default="created_at", description="Sort field: created_at, overall_score, planned_msrp, bsr_rank"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order: asc or desc")
) -> ProductListResponse:
    return ProductService.get_products(
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        region=region,
        is_shortlisted=is_shortlisted,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get(
    "/{product_id}",
    response_model=ProductDetailResponse,
    summary="Get Product Details",
    description="Returns complete product dossier including gate progress, marketplace listings, defect clusters, and economics."
)
def get_product(product_id: str) -> ProductDetailResponse:
    product = ProductService.get_product_detail(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PRODUCT_NOT_FOUND",
                "message": f"Product with ID '{product_id}' was not found in the SSOT database."
            }
        )
    return product


@router.post(
    "/{product_id}/refresh",
    response_model=ProductRefreshResponse,
    summary="Refresh Product Intelligence",
    description="Explicit action: Recomputes 10-dimension scorecard, kill tests, and counterfactuals, updating product_intelligence."
)
def refresh_product(product_id: str) -> ProductRefreshResponse:
    res = ProductService.refresh_product_intelligence(product_id)
    if not res.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in (res.error or "") else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REFRESH_FAILED",
                "message": res.error or "Failed to refresh product intelligence."
            }
        )
    return res


@router.post(
    "/{product_id}/observe",
    summary="Execute Live Observation Pipeline",
    description="Explicit Phase 6 action: Fetches fresh data from verified live sources (Google Trends, GDELT), validates and ingests with strict deduplication, compares against previous observations, and triggers intelligence refresh if material changes are detected."
)
def observe_product(product_id: str):
    res = ProductService.observe_product_pipeline(product_id)
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "OBSERVE_FAILED",
                "message": res.get("error", f"Product '{product_id}' not found.")
            }
        )
    return res


@router.post(
    "/{product_id}/watchlist",
    response_model=WatchlistMutationResponse,
    summary="Add Product to Watchlist",
    description="Adds a product to the local-first watchlist with priority and monitoring notes."
)
def add_to_watchlist_endpoint(
    product_id: str,
    payload: WatchlistAddRequest = WatchlistAddRequest()
) -> WatchlistMutationResponse:
    res = ProductService.add_to_watchlist(
        product_id=product_id,
        priority_status=payload.priority_status,
        notes=payload.notes
    )
    if not res.in_watchlist:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=res.message
        )
    return res


@router.delete(
    "/{product_id}/watchlist",
    response_model=WatchlistMutationResponse,
    summary="Remove Product from Watchlist",
    description="Removes a product from the local-first watchlist."
)
def remove_from_watchlist_endpoint(product_id: str) -> WatchlistMutationResponse:
    return ProductService.remove_from_watchlist(product_id=product_id)


@router.post(
    "/{product_id}/shortlist",
    response_model=ShortlistToggleResponse,
    summary="Toggle Shortlist Status",
    description="Marks or unmarks a product as shortlisted for active sourcing/procurement."
)
def toggle_shortlist_endpoint(
    product_id: str,
    payload: ShortlistToggleRequest = ShortlistToggleRequest()
) -> ShortlistToggleResponse:
    res = ProductService.toggle_shortlist(product_id=product_id, is_shortlisted=payload.is_shortlisted)
    return res


