from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.config import get_mysql_session
from models.schemas import ComputeBillRequest, BillingCycleResponse
from services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["Billing"])


def get_billing_service(session: Session = Depends(get_mysql_session)) -> BillingService:
    return BillingService(session)


@router.post(
    "/compute",
    response_model=dict,
    summary="Compute and charge bill",
    description="Computes resource usage and charges the user wallet"
)
def compute_bill(
    request: ComputeBillRequest,
    service: BillingService = Depends(get_billing_service)
):
    result = service.compute_bill(
        user_id=request.user_id,
        period_end=request.period_end
    )
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    return result


@router.get(
    "/{bill_id}",
    response_model=dict,
    summary="Get billing cycle",
    description="Retrieves a specific billing cycle by ID"
)
def get_bill(
    bill_id: str,
    service: BillingService = Depends(get_billing_service)
):
    result = service.get_bill(bill_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found"
        )
    return result


@router.get(
    "/user/{user_id}",
    response_model=list,
    summary="Get user billing history",
    description="Retrieves all billing cycles for a user"
)
def get_user_bills(
    user_id: str,
    service: BillingService = Depends(get_billing_service)
):
    return service.get_user_bills(user_id)


@router.post(
    "/{bill_id}/retry",
    response_model=dict,
    summary="Retry failed bill",
    description="Retries payment for a failed billing cycle"
)
def retry_bill(
    bill_id: str,
    service: BillingService = Depends(get_billing_service)
):
    result = service.retry_failed_bill(bill_id)
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    return result
