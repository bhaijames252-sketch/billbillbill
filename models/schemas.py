from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class PerHourRate(BaseModel):
    per_hour: float


class PerGbHourRate(BaseModel):
    per_gb_hour: float


class PricingData(BaseModel):
    currency: str
    compute: Dict[str, PerHourRate]
    disk: PerGbHourRate
    floating_ip: PerHourRate


class PricingUpdateData(BaseModel):
    currency: str
    compute: Optional[Dict[str, PerHourRate]] = None
    disk: Optional[PerGbHourRate] = None
    floating_ip: Optional[PerHourRate] = None


class PricingVersionEntry(BaseModel):
    price_version: str
    pricing: List[PricingData]


class PriceHistoryDocument(BaseModel):
    latest: str
    price_history: List[PricingVersionEntry]


class PriceCreateRequest(BaseModel):
    pricing: List[PricingData] = Field(..., min_length=1)


class PriceUpdateRequest(BaseModel):
    pricing: List[PricingUpdateData] = Field(..., min_length=1)


class PriceResponse(BaseModel):
    currency: str
    compute: Dict
    disk: Dict
    floating_ip: Dict
    price_version: str


class PriceHistoryResponse(BaseModel):
    latest: str
    price_history: List[PricingVersionEntry]


class LatestPricesResponse(BaseModel):
    price_version: str
    pricing: List[PriceResponse]


class WalletSettings(BaseModel):
    auto_recharge: bool = False
    allow_negative: bool = True
    last_deducted_at: Optional[datetime] = None


class WalletCreateRequest(BaseModel):
    user_id: str
    balance: Union[int, float, str] = 0
    currency: str = "USD"
    auto_recharge: bool = False
    allow_negative: bool = True


class WalletUpdateRequest(BaseModel):
    auto_recharge: Optional[bool] = None
    allow_negative: Optional[bool] = None
    currency: Optional[str] = None


class WalletResponse(BaseModel):
    user_id: str
    balance: str
    currency: str
    wallet: WalletSettings
    mongo_archival_id: Optional[str] = None

    class Config:
        from_attributes = True


class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class CreditRequest(BaseModel):
    amount: Union[int, float, str]
    reason: str


class DebitRequest(BaseModel):
    amount: Union[int, float, str]
    reason: str
    price_version: Optional[str] = None


class TransactionResponse(BaseModel):
    tx_id: str
    time: datetime
    amount: str
    balance_after: str
    type: str
    reason: str
    price_version: Optional[str] = None


class TransactionHistoryResponse(BaseModel):
    user_id: str
    transactions: List[TransactionResponse]


class ResourceState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    DELETED = "deleted"


class DiskState(str, Enum):
    ATTACHED = "attached"
    DETACHED = "detached"
    DELETED = "deleted"


class ComputeCreateRequest(BaseModel):
    resource_id: str
    user_id: str
    flavor: str = "small"


class ComputeUpdateRequest(BaseModel):
    state: Optional[ResourceState] = None
    flavor: Optional[str] = None


class ComputeResponse(BaseModel):
    resource_id: str
    user_id: str
    state: str
    current_flavor: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    last_billed_until: Optional[datetime] = None
    events: List[Dict] = []


class DiskCreateRequest(BaseModel):
    resource_id: str
    user_id: str
    size_gb: int
    attached_to: Optional[str] = None


class DiskUpdateRequest(BaseModel):
    state: Optional[DiskState] = None
    size_gb: Optional[int] = None
    attached_to: Optional[str] = None


class DiskResponse(BaseModel):
    resource_id: str
    user_id: str
    size_gb: int
    state: str
    attached_to: Optional[str] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None
    last_billed_until: Optional[datetime] = None
    events: List[Dict] = []


class FloatingIPCreateRequest(BaseModel):
    resource_id: str
    user_id: str
    ip_address: str
    port_id: Optional[str] = None
    attached_to: Optional[str] = None


class FloatingIPUpdateRequest(BaseModel):
    port_id: Optional[str] = None
    attached_to: Optional[str] = None


class FloatingIPResponse(BaseModel):
    resource_id: str
    user_id: str
    ip_address: str
    port_id: Optional[str] = None
    attached_to: Optional[str] = None
    created_at: datetime
    released_at: Optional[datetime] = None
    last_billed_until: Optional[datetime] = None
    events: List[Dict] = []


class ChargeItem(BaseModel):
    type: str
    amount: str
    resource_id: Optional[str] = None


class BillingCycleResponse(BaseModel):
    bill_id: str
    user_id: str
    period_start: datetime
    period_end: datetime
    status: str
    charges: List[ChargeItem]
    total: str
    paid: bool
    price_version: str
    generated_at: datetime


class ComputeBillRequest(BaseModel):
    user_id: str
    period_end: Optional[datetime] = None


class BillingHistoryResponse(BaseModel):
    user_id: str
    bills: List[BillingCycleResponse]
