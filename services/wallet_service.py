from datetime import datetime
from typing import Optional
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

    def create_wallet(
        self,
        user_id: str,
        balance: float = 0.0,
        currency: str = "USD",
        auto_recharge: bool = False,
        allow_negative: bool = True
    ) -> dict:
        mongo_archival_id = str(uuid.uuid4().hex[:12])

        wallet = UserWallet(
            id=str(uuid.uuid4()),
            user_id=user_id,
            balance=balance,
            currency=currency,
            auto_recharge=auto_recharge,
            allow_negative=allow_negative,
            mongo_archival_id=mongo_archival_id
        )
        self.mysql_session.add(wallet)
        self.mysql_session.commit()

        self.collection.insert_one({
            "_id": mongo_archival_id,
            "user_id": user_id,
            "transactions": []
        })

        if balance > 0:
            self._add_transaction(
                mongo_archival_id,
                balance,
                balance,
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
        allow_negative: Optional[bool] = None,
        currency: Optional[str] = None
    ) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        if auto_recharge is not None:
            wallet.auto_recharge = auto_recharge
        if allow_negative is not None:
            wallet.allow_negative = allow_negative
        if currency is not None:
            wallet.currency = currency

        self.mysql_session.commit()
        return self._wallet_to_dict(wallet)

    def add_credit(
        self,
        user_id: str,
        amount: float,
        reason: str
    ) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        wallet.balance += amount
        balance_after = wallet.balance
        self.mysql_session.commit()

        tx = self._add_transaction(
            wallet.mongo_archival_id,
            amount,
            balance_after,
            "credit",
            reason
        )

        return {
            "tx_id": tx["tx_id"],
            "amount": amount,
            "balance_after": balance_after,
            "type": "credit",
            "reason": reason
        }

    def add_debit(
        self,
        user_id: str,
        amount: float,
        reason: str,
        price_version: Optional[str] = None
    ) -> Optional[dict]:
        wallet = self.mysql_session.query(UserWallet).filter(
            UserWallet.user_id == user_id
        ).first()

        if not wallet:
            return None

        if not wallet.allow_negative and wallet.balance < amount:
            return {"error": "Insufficient balance"}

        wallet.balance -= amount
        wallet.last_deducted_at = datetime.utcnow()
        balance_after = wallet.balance
        self.mysql_session.commit()

        tx = self._add_transaction(
            wallet.mongo_archival_id,
            -amount,
            balance_after,
            "debit",
            reason,
            price_version
        )

        return {
            "tx_id": tx["tx_id"],
            "amount": -amount,
            "balance_after": balance_after,
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
        amount: float,
        balance_after: float,
        tx_type: str,
        reason: str,
        price_version: Optional[str] = None
    ) -> dict:
        tx = {
            "tx_id": self._generate_tx_id(),
            "time": datetime.utcnow().isoformat() + "Z",
            "amount": amount,
            "balance_after": balance_after,
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
            "balance": wallet.balance,
            "currency": wallet.currency,
            "wallet": {
                "auto_recharge": wallet.auto_recharge,
                "allow_negative": wallet.allow_negative,
                "last_deducted_at": wallet.last_deducted_at.isoformat() + "Z" if wallet.last_deducted_at else None
            },
            "mongo_archival_id": wallet.mongo_archival_id
        }
