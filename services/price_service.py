from datetime import datetime
from typing import List, Optional, Union
import uuid

from sqlalchemy.orm import Session

from db.config import get_mongo_db
from models.mysql_models import LatestPrice
from models.schemas import PricingData, PricingVersionEntry, PricingUpdateData


class PriceService:
    COLLECTION_NAME = "price_history"

    def __init__(self, mysql_session: Session):
        self.mysql_session = mysql_session
        self.mongo_db = get_mongo_db()
        self.collection = self.mongo_db[self.COLLECTION_NAME]

    def _generate_version(self) -> str:
        now = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        existing = self.collection.find_one()
        
        if not existing:
            return f"{date_str}_v1"
        
        version_count = 1
        for entry in existing.get("price_history", []):
            if entry.get("price_version", "").startswith(date_str):
                version_count += 1
        
        return f"{date_str}_v{version_count}"

    def _update_mysql(self, pricing_list: List[PricingData], price_version: str):
        for pricing in pricing_list:
            existing = self.mysql_session.query(LatestPrice).filter(
                LatestPrice.currency == pricing.currency
            ).first()

            pricing_dict = pricing.model_dump()
            
            if existing:
                existing.compute = pricing_dict["compute"]
                existing.disk = pricing_dict["disk"]
                existing.floating_ip = pricing_dict["floating_ip"]
                existing.price_version = price_version
            else:
                new_price = LatestPrice(
                    id=str(uuid.uuid4()),
                    currency=pricing.currency,
                    compute=pricing_dict["compute"],
                    disk=pricing_dict["disk"],
                    floating_ip=pricing_dict["floating_ip"],
                    price_version=price_version
                )
                self.mysql_session.add(new_price)
        
        self.mysql_session.commit()

    def _append_to_mongo_history(self, pricing_list: List[PricingData], price_version: str):
        pricing_dicts = [p.model_dump() for p in pricing_list]
        version_entry = {
            "price_version": price_version,
            "pricing": pricing_dicts
        }

        existing = self.collection.find_one()
        
        if not existing:
            self.collection.insert_one({
                "latest": price_version,
                "price_history": [version_entry]
            })
        else:
            self.collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {"latest": price_version},
                    "$push": {"price_history": version_entry}
                }
            )

    def create_price(self, pricing_list: List[PricingData]) -> str:
        price_version = self._generate_version()
        self._update_mysql(pricing_list, price_version)
        self._append_to_mongo_history(pricing_list, price_version)
        return price_version

    def update_price(self, pricing_list: List[PricingUpdateData]) -> str:
        price_version = self._generate_version()
        merged_pricing = self._merge_and_update_mysql(pricing_list, price_version)
        self._append_to_mongo_history(merged_pricing, price_version)
        return price_version

    def _merge_and_update_mysql(self, pricing_list: List[PricingUpdateData], price_version: str) -> List[PricingData]:
        merged_results = []
        
        for pricing in pricing_list:
            existing = self.mysql_session.query(LatestPrice).filter(
                LatestPrice.currency == pricing.currency
            ).first()

            if existing:
                current_compute = dict(existing.compute) if existing.compute else {}
                current_disk = dict(existing.disk) if existing.disk else {}
                current_floating_ip = dict(existing.floating_ip) if existing.floating_ip else {}

                if pricing.compute:
                    for flavor, rate in pricing.compute.items():
                        current_compute[flavor] = rate.model_dump()

                if pricing.disk:
                    current_disk = pricing.disk.model_dump()

                if pricing.floating_ip:
                    current_floating_ip = pricing.floating_ip.model_dump()

                existing.compute = current_compute
                existing.disk = current_disk
                existing.floating_ip = current_floating_ip
                existing.price_version = price_version
                
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(existing, "compute")
                flag_modified(existing, "disk")
                flag_modified(existing, "floating_ip")

                merged_results.append(PricingData(
                    currency=pricing.currency,
                    compute={k: {"per_hour": v["per_hour"]} for k, v in current_compute.items()},
                    disk=current_disk,
                    floating_ip=current_floating_ip
                ))
            else:
                if not pricing.compute or not pricing.disk or not pricing.floating_ip:
                    raise ValueError(f"Currency {pricing.currency} does not exist. Use POST to create with all required fields.")
                
                pricing_dict = pricing.model_dump()
                compute_dict = {k: v.model_dump() for k, v in pricing.compute.items()}
                
                new_price = LatestPrice(
                    id=str(uuid.uuid4()),
                    currency=pricing.currency,
                    compute=compute_dict,
                    disk=pricing.disk.model_dump(),
                    floating_ip=pricing.floating_ip.model_dump(),
                    price_version=price_version
                )
                self.mysql_session.add(new_price)
                
                merged_results.append(PricingData(
                    currency=pricing.currency,
                    compute=pricing.compute,
                    disk=pricing.disk,
                    floating_ip=pricing.floating_ip
                ))
        
        self.mysql_session.commit()
        return merged_results

    def get_latest_prices(self) -> Optional[dict]:
        prices = self.mysql_session.query(LatestPrice).all()
        
        if not prices:
            return None
        
        return {
            "price_version": prices[0].price_version,
            "pricing": [
                {
                    "currency": p.currency,
                    "compute": p.compute,
                    "disk": p.disk,
                    "floating_ip": p.floating_ip,
                    "price_version": p.price_version
                }
                for p in prices
            ]
        }

    def get_price_by_currency(self, currency: str) -> Optional[dict]:
        price = self.mysql_session.query(LatestPrice).filter(
            LatestPrice.currency == currency.upper()
        ).first()
        
        if not price:
            return None
        
        return {
            "currency": price.currency,
            "compute": price.compute,
            "disk": price.disk,
            "floating_ip": price.floating_ip,
            "price_version": price.price_version
        }

    def get_price_history(self) -> Optional[dict]:
        doc = self.collection.find_one()
        
        if not doc:
            return None
        
        doc.pop("_id", None)
        return doc

    def get_price_by_version(self, version: str) -> Optional[dict]:
        doc = self.collection.find_one()
        
        if not doc:
            return None
        
        for entry in doc.get("price_history", []):
            if entry.get("price_version") == version:
                return entry
        
        return None
