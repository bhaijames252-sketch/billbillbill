from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.config import get_mysql_session
from models.schemas import (
    PriceCreateRequest,
    PriceUpdateRequest,
    PriceResponse,
    LatestPricesResponse,
    PriceHistoryResponse,
    PricingVersionEntry,
)
from services.price_service import PriceService

router = APIRouter(prefix="/prices", tags=["Prices"])


def get_price_service(session: Session = Depends(get_mysql_session)) -> PriceService:
    return PriceService(session)


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create new pricing",
    description="Creates a new pricing version and stores it in both MySQL (latest) and MongoDB (history)"
)
def create_price(
    request: PriceCreateRequest,
    service: PriceService = Depends(get_price_service)
):
    price_version = service.create_price(request.pricing)
    return {
        "message": "Price created successfully",
        "price_version": price_version
    }


@router.put(
    "/",
    response_model=dict,
    summary="Update pricing",
    description="Updates pricing by creating a new version and appending to history"
)
def update_price(
    request: PriceUpdateRequest,
    service: PriceService = Depends(get_price_service)
):
    price_version = service.update_price(request.pricing)
    return {
        "message": "Price updated successfully",
        "price_version": price_version
    }


@router.get(
    "/",
    response_model=LatestPricesResponse,
    summary="Get latest prices",
    description="Retrieves the latest pricing for all currencies from MySQL"
)
def get_latest_prices(
    service: PriceService = Depends(get_price_service)
):
    result = service.get_latest_prices()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pricing data found"
        )
    return result


@router.get(
    "/currency/{currency}",
    response_model=PriceResponse,
    summary="Get price by currency",
    description="Retrieves the latest pricing for a specific currency"
)
def get_price_by_currency(
    currency: str,
    service: PriceService = Depends(get_price_service)
):
    result = service.get_price_by_currency(currency)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pricing found for currency: {currency}"
        )
    return result


@router.get(
    "/history",
    response_model=PriceHistoryResponse,
    summary="Get price history",
    description="Retrieves the complete pricing history from MongoDB"
)
def get_price_history(
    service: PriceService = Depends(get_price_service)
):
    result = service.get_price_history()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pricing history found"
        )
    return result


@router.get(
    "/version/{version}",
    response_model=PricingVersionEntry,
    summary="Get price by version",
    description="Retrieves pricing for a specific version from MongoDB"
)
def get_price_by_version(
    version: str,
    service: PriceService = Depends(get_price_service)
):
    result = service.get_price_by_version(version)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pricing found for version: {version}"
        )
    return result
