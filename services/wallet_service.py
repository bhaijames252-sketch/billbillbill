from datetime import datetime
from decimal import Decimal
from typing import Optional, Union
import uuid

from sqlalchemy.orm import Session

from db.config import get_mongo_db
from models.mysql_models import UserWallet


class WalletService:
    TRANSACTIONS_COLLECTION = "transaction_archives"

    def __init__(self, mysql_session: Session):
        self.mysql_session = mysql_session
        self.mongo_db = get_mongo_db()
        self.collection = self.mongo_db[self.TRANSACTIONS_COLLECTION]

    def _generate_tx_id(self) -> str:
        return f"tx_{uuid.uuid4().hex[:12]}"

    def _to_decimal(self, value: Union[int, float, str, Decimal]) -> Decimal:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def _format_amount(self, value: Union[Decimal, str]) -> str:
        if isinstance(value, str):
            value = Decimal(value)
        normalized = value.quantize(Decimal('0.000001')).normalize()
        result = format(normalized, 'f')
        if '.' in result:
            result = result.rstrip('0').rstrip('.')
        return result if result != '-0' else '0'

    def create_wallet(
        self,
        user_id: str,
        balance: Union[int, float, str, Decimal] = 0,
        currency: str = "USD",
        auto_recharge: bool = False
    ) -> dict:
        mongo_archival_id = str(uuid.uuid4().hex[:12])
        balance_decimal = self._to_decimal(balance)

        wallet = UserWallet(
            id=str(uuid.uuid4()),
            user_id=user_id,
            balance=balance_decimal,
            currency=currency,
            auto_recharge=auto_recharge,
            mongo_archival_id=mongo_archival_id
        )
        self.mysql_session.add(wallet)
        self.mysql_session.commit()

        self.collection.insert_one({
            "_id": mongo_archival_id,
            "user_id": user_id,
            "transactions": []
        })

        if balance_decimal > 0:
            self._add_transaction(
                mongo_archival_id,
                balance_decimal,
                balance_decimal,
                "credit",
                "Initial Balance"
            )

        return self._wallet_to_dict(wallet)

    def get_wallet(self, user_id: str) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        return self._wallet_to_dict(wallet)

    def update_wallet(
        self,
        user_id: str,
        auto_recharge: Optional[bool] = None,
        currency: Optional[str] = None
    ) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        if auto_recharge is not None:
            wallet.auto_recharge = auto_recharge
        if currency is not None:
            wallet.currency = currency

        self.mysql_session.commit()
        return self._wallet_to_dict(wallet)

    def add_credit(
        self,
        user_id: str,
        amount: Union[int, float, str, Decimal],
        reason: str
    ) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        amount_decimal = self._to_decimal(amount)
        wallet.balance = self._to_decimal(wallet.balance) + amount_decimal
        balance_after = wallet.balance
        self.mysql_session.commit()

        tx = self._add_transaction(
            wallet.mongo_archival_id,
            amount_decimal,
            balance_after,
            "credit",
            reason
        )

        return {
            "tx_id": tx["tx_id"],
            "amount": self._format_amount(amount_decimal),
            "balance_after": self._format_amount(balance_after),
            "type": "credit",
            "reason": reason
        }

    def add_debit(
        self,
        user_id: str,
        amount: Union[int, float, str, Decimal],
        reason: str,
        price_version: Optional[str] = None
    ) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        amount_decimal = self._to_decimal(amount)
        current_balance = self._to_decimal(wallet.balance)

        wallet.balance = current_balance - amount_decimal
        wallet.last_deducted_at = datetime.utcnow()
        balance_after = wallet.balance
        self.mysql_session.commit()

        tx = self._add_transaction(
            wallet.mongo_archival_id,
            -amount_decimal,
            balance_after,
            "debit",
            reason,
            price_version
        )

        return {
            "tx_id": tx["tx_id"],
            "amount": self._format_amount(-amount_decimal),
            "balance_after": self._format_amount(balance_after),
            "type": "debit",
            "reason": reason,
            "price_version": price_version
        }

    def get_transaction_history(self, user_id: str) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        archive = self.collection.find_one({"_id": wallet.mongo_archival_id})
        if not archive:
            return {"user_id": user_id, "transactions": []}

        return {
            "user_id": user_id,
            "transactions": archive.get("transactions", [])
        }

    def _add_transaction(
        self,
        archival_id: str,
        amount: Union[int, float, str, Decimal],
        balance_after: Union[int, float, str, Decimal],
        tx_type: str,
        reason: str,
        price_version: Optional[str] = None
    ) -> dict:
        tx = {
            "tx_id": self._generate_tx_id(),
            "time": datetime.utcnow().isoformat() + "Z",
            "amount": self._format_amount(amount),
            "balance_after": self._format_amount(balance_after),
            "type": tx_type,
            "reason": reason
        }

        if price_version:
            tx["billing_cycle.price_version"] = price_version

        self.collection.update_one(
            {"_id": archival_id},
            {"$push": {"transactions": tx}}
        )

        return tx

    def _wallet_to_dict(self, wallet: UserWallet) -> dict:
        return {
            "user_id": wallet.user_id,
            "balance": self._format_amount(wallet.balance),
            "currency": wallet.currency,
            "wallet": {
                "auto_recharge": wallet.auto_recharge,
                "last_deducted_at": wallet.last_deducted_at.isoformat() + "Z" if wallet.last_deducted_at else None
            },
            "mongo_archival_id": wallet.mongo_archival_id
        }
