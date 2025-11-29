from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.config import get_mysql_session
from models.schemas import (
    WalletCreateRequest,
    WalletResponse,
    CreditRequest,
    DebitRequest,
    TransactionHistoryResponse,
)
from services.wallet_service import WalletService

router = APIRouter(prefix="/wallets", tags=["Wallets"])


def get_wallet_service(session: Session = Depends(get_mysql_session)) -> WalletService:
    return WalletService(session)


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create user wallet",
    description="Creates a new wallet for a user with initial balance and settings"
)
def create_wallet(
    request: WalletCreateRequest,
    service: WalletService = Depends(get_wallet_service)
):
    existing = service.get_wallet(request.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wallet already exists for this user"
        )

    result = service.create_wallet(
        user_id=request.user_id,
        balance=request.balance,
        currency=request.currency,
        auto_recharge=request.auto_recharge,
        allow_negative=request.allow_negative
    )
    return result


@router.get(
    "/{user_id}",
    response_model=dict,
    summary="Get user wallet",
    description="Retrieves wallet information for a user"
)
def get_wallet(
    user_id: str,
    service: WalletService = Depends(get_wallet_service)
):
    result = service.get_wallet(user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    return result


@router.get(
    "/{user_id}/balance",
    response_model=dict,
    summary="Get user balance",
    description="Retrieves only the balance for a user"
)
def get_balance(
    user_id: str,
    service: WalletService = Depends(get_wallet_service)
):
    result = service.get_wallet(user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    return {
        "user_id": user_id,
        "balance": result["balance"],
        "currency": result["currency"]
    }


@router.post(
    "/{user_id}/credit",
    response_model=dict,
    summary="Add credit to wallet",
    description="Adds funds to user wallet"
)
def add_credit(
    user_id: str,
    request: CreditRequest,
    service: WalletService = Depends(get_wallet_service)
):
    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )

    result = service.add_credit(user_id, request.amount, request.reason)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    return result


@router.post(
    "/{user_id}/debit",
    response_model=dict,
    summary="Debit from wallet",
    description="Deducts funds from user wallet"
)
def add_debit(
    user_id: str,
    request: DebitRequest,
    service: WalletService = Depends(get_wallet_service)
):
    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )

    result = service.add_debit(
        user_id,
        request.amount,
        request.reason,
        request.price_version
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    return result


@router.get(
    "/{user_id}/transactions",
    response_model=dict,
    summary="Get transaction history",
    description="Retrieves all transactions for a user from MongoDB archive"
)
def get_transactions(
    user_id: str,
    service: WalletService = Depends(get_wallet_service)
):
    result = service.get_transaction_history(user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    return result
