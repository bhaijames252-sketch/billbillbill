from datetime import datetime
from typing import Optional, List
import uuid

from sqlalchemy.orm import Session
from dateutil import parser

from db.config import get_mongo_db
from models.mysql_models import LatestPrice, UserWallet
from services.resource_service import ResourceService
from services.wallet_service import WalletService


class BillingService:
    BILLING_COLLECTION = "billing_cycles"

    def __init__(self, mysql_session: Session):
        self.mysql_session = mysql_session
        self.mongo_db = get_mongo_db()
        self.billing_col = self.mongo_db[self.BILLING_COLLECTION]
        self.resource_service = ResourceService()
        self.wallet_service = WalletService(mysql_session)

    def _generate_bill_id(self, user_id: str) -> str:
        now = datetime.utcnow()
        return f"bill_{now.strftime('%Y_%m_%d')}_{user_id}_{uuid.uuid4().hex[:6]}"

    def _parse_datetime(self, dt_str: str) -> datetime:
        if isinstance(dt_str, datetime):
            return dt_str
        return parser.parse(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)

    def _get_latest_price(self, currency: str) -> Optional[dict]:
        price = self.mysql_session.query(LatestPrice).filter(
            LatestPrice.currency == currency
        ).first()

        if not price:
            return None

        return {
            "compute": price.compute,
            "disk": price.disk,
            "floating_ip": price.floating_ip,
            "price_version": price.price_version
        }

    def _calculate_hours(self, start: datetime, end: datetime) -> float:
        delta = end - start
        return max(delta.total_seconds() / 3600, 0)

    def _compute_resource_charges(
        self,
        user_id: str,
        period_end: datetime,
        pricing: dict
    ) -> tuple:
        charges = []
        total = 0.0

        computes = self.resource_service.get_user_computes(user_id)
        for compute in computes:
            last_billed = self._parse_datetime(compute["last_billed_until"])
            if last_billed >= period_end:
                continue

            hours = self._calculate_hours(last_billed, period_end)
            flavor = compute["current_flavor"]
            rate = pricing["compute"].get(flavor, pricing["compute"].get("others", {}))
            per_hour = rate.get("per_hour", 0)
            amount = round(hours * per_hour, 4)

            if amount > 0:
                charges.append({
                    "type": "compute",
                    "resource_id": compute["resource_id"],
                    "amount": amount
                })
                total += amount

            self.resource_service.update_last_billed("compute", compute["resource_id"], period_end)

        disks = self.resource_service.get_user_disks(user_id)
        for disk in disks:
            last_billed = self._parse_datetime(disk["last_billed_until"])
            if last_billed >= period_end:
                continue

            hours = self._calculate_hours(last_billed, period_end)
            size_gb = disk["size_gb"]
            per_gb_hour = pricing["disk"].get("per_gb_hour", 0)
            amount = round(hours * size_gb * per_gb_hour, 4)

            if amount > 0:
                charges.append({
                    "type": "disk",
                    "resource_id": disk["resource_id"],
                    "amount": amount
                })
                total += amount

            self.resource_service.update_last_billed("disk", disk["resource_id"], period_end)

        floating_ips = self.resource_service.get_user_floating_ips(user_id)
        for fip in floating_ips:
            last_billed = self._parse_datetime(fip["last_billed_until"])
            if last_billed >= period_end:
                continue

            hours = self._calculate_hours(last_billed, period_end)
            per_hour = pricing["floating_ip"].get("per_hour", 0)
            amount = round(hours * per_hour, 4)

            if amount > 0:
                charges.append({
                    "type": "floating_ip",
                    "resource_id": fip["resource_id"],
                    "amount": amount
                })
                total += amount

            self.resource_service.update_last_billed("floating_ip", fip["resource_id"], period_end)

        return charges, round(total, 4)

    def compute_bill(
        self,
        user_id: str,
        period_end: Optional[datetime] = None
    ) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return {"error": "User wallet not found"}

        pricing = self._get_latest_price(wallet.currency)
        if not pricing:
            return {"error": f"No pricing found for currency: {wallet.currency}"}

        if period_end is None:
            period_end = datetime.utcnow()

        period_start = wallet.last_deducted_at or datetime.utcnow()

        charges, total = self._compute_resource_charges(user_id, period_end, pricing)

        if total == 0:
            return {
                "message": "No billable usage found",
                "user_id": user_id,
                "period_start": period_start.isoformat() + "Z",
                "period_end": period_end.isoformat() + "Z"
            }

        bill_id = self._generate_bill_id(user_id)
        now = datetime.utcnow()

        bill = {
            "bill_id": bill_id,
            "user_id": user_id,
            "period_start": period_start.isoformat() + "Z",
            "period_end": period_end.isoformat() + "Z",
            "status": "pending",
            "charges": charges,
            "total": total,
            "paid": False,
            "price_version": pricing["price_version"],
            "generated_at": now.isoformat() + "Z"
        }
        self.billing_col.insert_one(bill)

        debit_result = self.wallet_service.add_debit(
            user_id,
            total,
            f"Billing cycle: {bill_id}",
            pricing["price_version"]
        )

        if debit_result and "error" not in debit_result:
            self.billing_col.update_one(
                {"bill_id": bill_id},
                {"$set": {"status": "success", "paid": True}}
            )
            bill["status"] = "success"
            bill["paid"] = True
        else:
            self.billing_col.update_one(
                {"bill_id": bill_id},
                {"$set": {"status": "failed"}}
            )
            bill["status"] = "failed"

        bill.pop("_id", None)
        return bill

    def get_bill(self, bill_id: str) -> Optional[dict]:
        bill = self.billing_col.find_one({"bill_id": bill_id})
        if bill:
            bill.pop("_id", None)
        return bill

    def get_user_bills(self, user_id: str) -> List[dict]:
        bills = list(self.billing_col.find({"user_id": user_id}).sort("generated_at", -1))
        for bill in bills:
            bill.pop("_id", None)
        return bills

    def retry_failed_bill(self, bill_id: str) -> Optional[dict]:
        bill = self.billing_col.find_one({"bill_id": bill_id})
        if not bill:
            return {"error": "Bill not found"}

        if bill.get("paid"):
            return {"error": "Bill already paid"}

        debit_result = self.wallet_service.add_debit(
            bill["user_id"],
            bill["total"],
            f"Retry billing: {bill_id}",
            bill.get("price_version")
        )

        if debit_result and "error" not in debit_result:
            self.billing_col.update_one(
                {"bill_id": bill_id},
                {"$set": {"status": "success", "paid": True}}
            )
            bill["status"] = "success"
            bill["paid"] = True
        else:
            bill["status"] = "failed"
            bill["error"] = debit_result.get("error") if debit_result else "Unknown error"

        bill.pop("_id", None)
        return bill
