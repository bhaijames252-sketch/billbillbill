from datetime import datetime
from decimal import Decimal, ROUND_DOWN
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

    def _format_amount(self, value: Decimal) -> str:
        normalized = value.quantize(Decimal('0.000001')).normalize()
        result = format(normalized, 'f')
        if '.' in result:
            result = result.rstrip('0').rstrip('.')
        return result if result != '-0' else '0'

    def _parse_datetime(self, dt_str) -> datetime:
        if isinstance(dt_str, datetime):
            if dt_str.tzinfo is not None:
                return dt_str.replace(tzinfo=None)
            return dt_str
        parsed = parser.parse(dt_str.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)

    def _ensure_naive(self, dt: datetime) -> datetime:
        if dt is None:
            return datetime.utcnow()
        if dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        return dt

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

    def _calculate_hours(self, start: datetime, end: datetime) -> Decimal:
        delta = end - start
        return Decimal(str(delta.total_seconds())) / Decimal("3600")

    def _get_billable_segments(
        self,
        events: list,
        last_billed: datetime,
        period_end: datetime,
        resource_type: str
    ) -> list:
        relevant_events = []
        for event in events:
            event_time = self._parse_datetime(event["time"])
            if event_time > last_billed and event_time <= period_end:
                relevant_events.append({
                    "time": event_time,
                    "type": event["type"],
                    "meta": event.get("meta", {})
                })

        relevant_events.sort(key=lambda x: x["time"])
        return relevant_events

    def _calculate_compute_charge(
        self,
        compute: dict,
        last_billed: datetime,
        period_end: datetime,
        pricing: dict
    ) -> Decimal:
        events = compute.get("events", [])
        segments = self._get_billable_segments(events, last_billed, period_end, "compute")

        current_flavor = None
        current_state = None

        sorted_events = sorted(
            compute.get("events", []),
            key=lambda e: self._parse_datetime(e["time"])
        )
        for event in sorted_events:
            event_time = self._parse_datetime(event["time"])
            if event_time <= last_billed:
                if event["type"] == "create":
                    current_flavor = event.get("meta", {}).get("flavor", current_flavor)
                    current_state = "running"
                elif event["type"] == "resize":
                    current_flavor = event.get("meta", {}).get("flavor", current_flavor)
                elif event["type"] in ["running", "stopped", "deleted"]:
                    current_state = event["type"]
            else:
                break

        if current_flavor is None:
            current_flavor = compute["current_flavor"]
        if current_state is None:
            current_state = compute.get("state", "running")

        if not segments:
            if current_state != "running":
                return Decimal("0")
            hours = self._calculate_hours(last_billed, period_end)
            flavor = compute["current_flavor"]
            rate = pricing["compute"].get(flavor, pricing["compute"].get("others", {}))
            return hours * Decimal(str(rate.get("per_hour", 0)))

        total_charge = Decimal("0")
        current_time = last_billed

        for segment in segments:
            if current_state == "running" and current_flavor:
                hours = self._calculate_hours(current_time, segment["time"])
                rate = pricing["compute"].get(current_flavor, pricing["compute"].get("others", {}))
                total_charge += hours * Decimal(str(rate.get("per_hour", 0)))

            current_time = segment["time"]
            if segment["type"] == "resize":
                current_flavor = segment["meta"].get("flavor", current_flavor)
            elif segment["type"] in ["running", "stopped", "deleted"]:
                current_state = segment["type"]

        # Do not bill beyond a delete event. If the resource was deleted during the
        # billing window, the delete event will be part of segments and we should
        # not charge any time after it. Track deletion and only bill the tail
        # period if the resource was not deleted.
        is_deleted = False
        # Re-evaluate segments to see if delete appears (segments are sorted)
        for seg in segments:
            if seg.get("type") == "deleted":
                is_deleted = True
                break

        if current_state == "running" and current_flavor and (not is_deleted) and current_time < period_end:
            hours = self._calculate_hours(current_time, period_end)
            rate = pricing["compute"].get(current_flavor, pricing["compute"].get("others", {}))
            total_charge += hours * Decimal(str(rate.get("per_hour", 0)))

        return total_charge

    def _calculate_disk_charge(
        self,
        disk: dict,
        last_billed: datetime,
        period_end: datetime,
        pricing: dict
    ) -> Decimal:
        events = disk.get("events", [])
        segments = self._get_billable_segments(events, last_billed, period_end, "disk")
        per_gb_hour = Decimal(str(pricing["disk"].get("per_gb_hour", 0)))

        if not segments:
            hours = self._calculate_hours(last_billed, period_end)
            return hours * Decimal(str(disk["size_gb"])) * per_gb_hour

        total_charge = Decimal("0")
        current_time = last_billed
        current_size = None

        for event in disk.get("events", []):
            event_time = self._parse_datetime(event["time"])
            if event_time <= last_billed:
                if event["type"] == "create" or event["type"] == "resize":
                    current_size = event.get("meta", {}).get("size_gb", current_size)

        if current_size is None:
            current_size = disk["size_gb"]

        is_deleted = False
        for segment in segments:
            hours = self._calculate_hours(current_time, segment["time"])
            total_charge += hours * Decimal(str(current_size)) * per_gb_hour

            current_time = segment["time"]
            if segment["type"] == "resize":
                current_size = segment["meta"].get("size_gb", current_size)
            elif segment["type"] == "deleted":
                is_deleted = True

        if not is_deleted and current_time < period_end:
            hours = self._calculate_hours(current_time, period_end)
            total_charge += hours * Decimal(str(current_size)) * per_gb_hour

        return total_charge

    def _compute_resource_charges(
        self,
        user_id: str,
        period_end: datetime,
        pricing: dict
    ) -> tuple:
        charges = []
        total = Decimal("0")

        computes = self.resource_service.get_user_computes(user_id, include_deleted=True)
        for compute in computes:
            last_billed = self._parse_datetime(compute["last_billed_until"])
            
            billing_end = period_end
            if compute.get("deleted_at"):
                deleted_at = self._parse_datetime(compute["deleted_at"])
                if deleted_at < period_end:
                    billing_end = deleted_at
            
            if last_billed >= billing_end:
                continue

            amount = self._calculate_compute_charge(
                compute, last_billed, billing_end, pricing
            )

            if amount > 0:
                charges.append({
                    "type": "compute",
                    "resource_id": compute["resource_id"],
                    "amount": self._format_amount(amount)
                })
                total += amount

            self.resource_service.update_last_billed("compute", compute["resource_id"], billing_end)

        disks = self.resource_service.get_user_disks(user_id, include_deleted=True)
        for disk in disks:
            last_billed = self._parse_datetime(disk["last_billed_until"])
            
            billing_end = period_end
            if disk.get("deleted_at"):
                deleted_at = self._parse_datetime(disk["deleted_at"])
                if deleted_at < period_end:
                    billing_end = deleted_at
            
            if last_billed >= billing_end:
                continue

            amount = self._calculate_disk_charge(
                disk, last_billed, billing_end, pricing
            )

            if amount > 0:
                charges.append({
                    "type": "disk",
                    "resource_id": disk["resource_id"],
                    "amount": self._format_amount(amount)
                })
                total += amount

            self.resource_service.update_last_billed("disk", disk["resource_id"], billing_end)

        floating_ips = self.resource_service.get_user_floating_ips(user_id, include_released=True)
        for fip in floating_ips:
            last_billed = self._parse_datetime(fip["last_billed_until"])
            
            billing_end = period_end
            if fip.get("released_at"):
                released_at = self._parse_datetime(fip["released_at"])
                if released_at < period_end:
                    billing_end = released_at
            
            if last_billed >= billing_end:
                continue

            hours = self._calculate_hours(last_billed, billing_end)
            per_hour = Decimal(str(pricing["floating_ip"].get("per_hour", 0)))
            amount = hours * per_hour

            if amount > 0:
                charges.append({
                    "type": "floating_ip",
                    "resource_id": fip["resource_id"],
                    "amount": self._format_amount(amount)
                })
                total += amount

            self.resource_service.update_last_billed("floating_ip", fip["resource_id"], billing_end)

        return charges, total

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
        else:
            period_end = self._ensure_naive(period_end)

        period_start = self._ensure_naive(wallet.last_deducted_at) if wallet.last_deducted_at else datetime.utcnow()

        charges, total = self._compute_resource_charges(user_id, period_end, pricing)

        if total == Decimal("0"):
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
            "total": self._format_amount(total),
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
